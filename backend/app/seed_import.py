"""`flask import-seed`: load the clean seed workbook into one organisation.

The workbook is 'Abhiyudhya Seed Data - Clean.xlsx': sheets 1 State ... 8
Trainers, in that order, each needing the ones before it. Every row goes
through the same rules as the admin's form (required fields, each resource's
own checks, a login for every trainer), so what loads here could have been
typed in.

- A dry run unless --commit: everything is checked, nothing is kept.
- All or nothing: one problem anywhere and nothing is saved.
- Safe to rerun: a record already there (same name / UDISE code / email) is
  left as it is and counted as "already there".
- The trainers' logins go to a new workbook next to the input, written only
  when the load is saved - the one place their passwords are ever shown.
"""
import os
import re
from collections import OrderedDict
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import func
from werkzeug.exceptions import HTTPException

from app.extensions import db

SHEETS = ["1 State", "2 Districts", "3 Sectors", "4 Job Roles", "5 Academic Years", "6 Schools", "7 Labs", "8 Trainers"]


class RowError(Exception):
    pass


def _read(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    missing = [s for s in SHEETS if s not in wb.sheetnames]
    if missing:
        raise RowError(f"The workbook has no sheet {', '.join(missing)} - is it the clean seed file?")
    out = {}
    for title in SHEETS:
        it = wb[title].iter_rows(values_only=True)
        head = [re.sub(r"\s*\*$", "", str(h or "").strip()) for h in next(it, [])]
        out[title] = [(n, dict(zip(head, r))) for n, r in enumerate(it, start=2)
                      if any(c not in (None, "") for c in r)]
    return out


def _text(v):
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


def _date(v, label):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v).strip(), "%d/%m/%Y").date()
    except ValueError:
        raise RowError(f"{label} '{v}' isn't a date as DD/MM/YYYY.")


def _key(v):
    return (v or "").strip().lower()


class Loader:
    def __init__(self, org, actor):
        from app.api.registry import REGISTRY
        self.org, self.actor, self.cfgs = org, actor, REGISTRY
        # what the audit trail records: the actor, without a notification per row
        self.counts = OrderedDict((s, {"created": 0, "already there": 0}) for s in SHEETS)
        self.errors, self.logins = [], []

    # -- the form's rules, row by row (resource.create_resource without the request)
    def make(self, resource, values, location=None):
        from app.api.resource import _missing_required, _set_manual_location
        from app.api.users import LoginError, create_login_for
        from app.services import audit
        from app.services.academic_year import guard_closed_year

        cfg = self.cfgs[resource]
        obj = cfg.model(organisation_id=self.org.id, **values)
        try:
            if cfg.prepare:
                err = cfg.prepare(obj, self.actor)
                if err:
                    raise RowError(err)
            if cfg.manual_location and location:
                _set_manual_location(obj, {"location_lat": location[0], "location_lng": location[1]})
            _missing_required(cfg, obj)
            guard_closed_year(obj, self.actor, creating=True)
        except HTTPException as exc:
            raise RowError(exc.description)
        if hasattr(obj, "created_by"):
            obj.created_by = self.actor.id
        db.session.add(obj)
        db.session.flush()
        if cfg.validate:
            err = cfg.validate(obj, self.actor, True)
            if err:
                raise RowError(err)
        if cfg.on_saved:
            cfg.on_saved(obj, self.actor, True, None)
        login = None
        if cfg.profile_role and not obj.user_id:
            try:
                login = create_login_for(cfg.profile_role, obj, self.actor)
            except LoginError as exc:
                raise RowError(str(exc))
        audit.record(self.actor, "create", cfg.model.__tablename__, obj.id, after=obj.to_dict(),
                     tell_super_admin=False)
        return obj, login

    def row(self, sheet, n, fn):
        """One row inside its own savepoint, so a bad row is reported and the
        rest are still checked."""
        try:
            with db.session.begin_nested():
                made = fn()
            self.counts[sheet]["created" if made else "already there"] += 1
        except RowError as exc:
            self.errors.append(f"{sheet}, row {n}: {exc}")
        except Exception as exc:     # a database refusal: report it like the rest
            self.errors.append(f"{sheet}, row {n}: {exc.__class__.__name__}: {str(exc).splitlines()[0]}")

    def mine(self, model, *conds):
        return db.session.query(model).filter(model.organisation_id == self.org.id,
                                              model.is_deleted.is_(False), *conds)

    def named(self, model, name, *conds, attr="name"):
        return self.mine(model, func.lower(getattr(model, attr)) == _key(name), *conds).first()

    def need(self, found, what, value):
        if found is None:
            raise RowError(f"{what} '{value}' isn't in the portal or earlier in the workbook.")
        return found

    # -- the sheets ---------------------------------------------------------
    def load(self, data):
        from app import models as M

        for n, r in data["1 State"]:
            def state(r=r):
                if self.named(M.State, r.get("State name")):
                    return False
                self.make("states", {"name": _text(r.get("State name")), "code": _text(r.get("Code"))})
                return True
            self.row("1 State", n, state)

        for n, r in data["2 Districts"]:
            def district(r=r):
                st = self.need(self.named(M.State, r.get("State")), "State", r.get("State"))
                if self.named(M.District, r.get("District name"), M.District.state_id == st.id):
                    return False
                self.make("districts", {"name": _text(r.get("District name")), "code": _text(r.get("Code")),
                                        "state_id": st.id})
                return True
            self.row("2 Districts", n, district)

        for n, r in data["3 Sectors"]:
            def sector(r=r):
                if self.named(M.Sector, r.get("Sector name")):
                    return False
                self.make("sectors", {"name": _text(r.get("Sector name"))})
                return True
            self.row("3 Sectors", n, sector)

        def job_role(name, sector_id, band):
            return self.named(M.JobRole, name, M.JobRole.sector_id == sector_id, M.JobRole.class_band == band)

        for n, r in data["4 Job Roles"]:
            def role(r=r):
                sec = self.need(self.named(M.Sector, r.get("Sector")), "Sector", r.get("Sector"))
                band = _text(r.get("Class band"))
                if job_role(r.get("Job role name"), sec.id, band):
                    return False
                level = _text(r.get("NSQF level"))
                self.make("job-roles", {"name": _text(r.get("Job role name")), "sector_id": sec.id, "class_band": band,
                                        "qp_code": _text(r.get("QP code")), "nsqf_level": int(level) if level else None})
                return True
            self.row("4 Job Roles", n, role)

        for n, r in data["5 Academic Years"]:
            def year(r=r):
                label = _text(r.get("Label"))
                if self.named(M.AcademicYear, label, attr="label"):
                    return False
                # only one current year: if there is one already, it stays current
                current = _key(_text(r.get("Current"))) == "yes" and not self.mine(
                    M.AcademicYear, M.AcademicYear.is_current.is_(True)).first()
                self.make("academic-years", {"label": label, "is_current": current,
                                             "start_date": _date(r.get("Start date"), "Start date"),
                                             "end_date": _date(r.get("End date"), "End date")})
                return True
            self.row("5 Academic Years", n, year)

        for n, r in data["6 Schools"]:
            def school(r=r):
                code = _text(r.get("UDISE code"))
                code = code.zfill(11) if code and code.isdigit() else code
                there = db.session.query(M.School).filter(M.School.udise_code == code).first()
                if there:
                    if there.organisation_id != self.org.id:
                        raise RowError(f"UDISE code {code} belongs to a school in another organisation.")
                    return False
                # the sheet names a district only: two of that name (in two
                # states) and it can't tell which - say so, never guess
                same = self.mine(M.District, func.lower(M.District.name) == _key(r.get("District"))).all()
                if len(same) > 1:
                    raise RowError(f"There are {len(same)} districts called '{r.get('District')}' (in different states) - "
                                   "keep one, then load again.")
                dist = self.need(same[0] if same else None, "District", r.get("District"))
                self.make("schools", {
                    "name": _text(r.get("School name")), "udise_code": code, "district_id": dist.id,
                    "block": _text(r.get("Block")), "school_type": _text(r.get("School type")),
                    "board": _text(r.get("Board of school")), "address": _text(r.get("Full address")),
                    "email": (_text(r.get("Email")) or "").lower() or None, "phone": _text(r.get("Phone")),
                }, location=(r.get("Latitude"), r.get("Longitude")))
                return True
            self.row("6 Schools", n, school)

        def school_of(udise):
            code = _text(udise)
            code = code.zfill(11) if code and code.isdigit() else code
            return self.need(self.mine(M.School, M.School.udise_code == code).first(), "School with UDISE code", code)

        for n, r in data["7 Labs"]:
            def lab(r=r):
                sch = school_of(r.get("School UDISE code"))
                if self.named(M.Lab, r.get("Lab name"), M.Lab.school_id == sch.id):
                    return False
                sec = self.need(self.named(M.Sector, r.get("Trade / Sector")), "Sector", r.get("Trade / Sector"))
                ids = {}
                for col, band in (("Job role (Class 9-10)", "9-10"), ("Job role (Class 11-12)", "11-12")):
                    name = _text(r.get(col))
                    ids[band] = self.need(job_role(name, sec.id, band), f"{band} job role", name).id if name else None
                self.make("labs", {"name": _text(r.get("Lab name")), "school_id": sch.id, "sector_id": sec.id,
                                   "job_role_9_10_id": ids["9-10"], "job_role_11_12_id": ids["11-12"],
                                   "academic_year_of_setup": _text(r.get("AY of setup"))})
                return True
            self.row("7 Labs", n, lab)

        from app.models.user import User
        for n, r in data["8 Trainers"]:
            def trainer(r=r):
                email = (_text(r.get("Email")) or "").lower()
                if self.mine(M.Trainer, func.lower(M.Trainer.email) == email).first():
                    return False
                if email and db.session.query(User).filter(User.email == email).first():
                    raise RowError(f"A login with the email {email} already exists, but not as this organisation's trainer.")
                sch = school_of(r.get("School UDISE code"))
                lab = self.need(self.named(M.Lab, r.get("Lab"), M.Lab.school_id == sch.id), "Lab", r.get("Lab"))
                taught = {}
                for jr_id in (lab.job_role_9_10_id, lab.job_role_11_12_id):
                    jr = db.session.get(M.JobRole, jr_id) if jr_id else None
                    if jr:
                        taught[_key(jr.name)] = jr.id
                names = [s for s in re.split(r"\s*;\s*", _text(r.get("Job role(s) taught")) or "") if s]
                wrong = [s for s in names if _key(s) not in taught]
                if wrong:
                    raise RowError(f"'{'; '.join(wrong)}' isn't a job role of {lab.name} at {sch.name}.")
                obj, login = self.make("trainers", {
                    "full_name": _text(r.get("Full name")), "gender": _text(r.get("Gender")), "email": email or None,
                    "phone": re.sub(r"\D", "", _text(r.get("Mobile")) or "") or None,
                    "school_id": sch.id, "lab_id": lab.id,
                    "job_role_ids": ",".join(str(taught[_key(s)]) for s in names) or None,
                    "date_of_joining": _date(r.get("Date of joining (DD/MM/YYYY)"), "Date of joining"),
                    "trainer_status": "active",
                })
                if login:
                    district = db.session.get(M.District, sch.district_id)
                    self.logins.append({"Full name": obj.full_name, "Username (email)": login["username"],
                                        "One-time password": login["password"], "Mobile": obj.phone,
                                        "School name": sch.name, "School UDISE code": sch.udise_code,
                                        "District": district.name if district else None, "Lab": lab.name,
                                        "Candidate's code": _text(r.get("Candidate's code"))})
                return True
            self.row("8 Trainers", n, trainer)


def write_logins(rows, path, org):
    """The trainers' passwords - confidential, shown only here."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    info = wb.active
    info.title = "Read me"
    for i, line in enumerate([
        f"{org.name} - Vocational Trainer logins (CONFIDENTIAL)",
        f"{len(rows)} logins made by `flask import-seed` on {datetime.now():%d/%m/%Y %H:%M}. The username is the trainer's email.",
        "Each trainer signs in at the portal with their email and this password. It keeps working.",
        "Share each login with its trainer only, privately. Don't email or forward this file; delete copies once shared.",
        "A lost password: an Org Admin resets it from the portal's Users page.",
    ], start=1):
        info.cell(row=i, column=1, value=line).font = Font(name="Arial", size=12 if i == 1 else 10, bold=i == 1)
    info.column_dimensions["A"].width = 120
    ws = wb.create_sheet("VT Logins")
    cols = ["S.No"] + list(rows[0].keys())
    for c, name in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=c, value=name)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F2A44")
        ws.column_dimensions[cell.column_letter].width = 22 if name != "S.No" else 6
    for i, row in enumerate(rows, start=1):
        for c, name in enumerate(cols, start=1):
            cell = ws.cell(row=i + 1, column=c, value=i if name == "S.No" else row[name])
            cell.font = Font(name="Arial", size=10)
            cell.number_format = "@"
    ws.freeze_panes = "A2"
    wb.save(path)


def run_import(path, org_code, by_email, commit, echo):
    from app.models.organisation import Organisation
    from app.models.user import User

    org = db.session.query(Organisation).filter(func.lower(Organisation.org_code) == _key(org_code)).first()
    if not org:
        raise RowError(f"No organisation with the code {org_code}.")
    actor = db.session.query(User).filter(User.email == _key(by_email), User.is_deleted.is_(False)).first()
    if not actor or not (actor.role == "SA" or (actor.role == "OA" and actor.organisation_id == org.id)):
        raise RowError(f"{by_email} must be this organisation's Org Admin (or the Super Admin): "
                       "the records are created in their name.")
    data = _read(path)
    loader = Loader(org, actor)
    loader.load(data)

    echo(f"{'Loading' if commit else 'Dry run (nothing is saved)'}: {os.path.basename(path)} -> {org.name}")
    for sheet, c in loader.counts.items():
        echo(f"  {sheet:<18} {c['created']:>4} to add   {c['already there']:>4} already there")
    if loader.errors:
        db.session.rollback()
        echo(f"\n{len(loader.errors)} problem(s) - nothing was saved:")
        for e in loader.errors:
            echo(f"  - {e}")
        return False
    if not commit:
        db.session.rollback()
        echo("\nNo problems. Run again with --commit to load it.")
        return True

    # the logins file is written first and kept only if the load is saved:
    # a password is never lost, and never handed out for a login that isn't there
    out = None
    if loader.logins:
        folder = os.path.dirname(os.path.abspath(path))
        out = os.path.join(folder, f"Abhiyudhya VT Logins - {datetime.now():%Y-%m-%d %H%M}.xlsx")
        partial = out + ".partial"
        write_logins(loader.logins, partial, org)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if out:
            os.remove(partial)
        raise
    if out:
        os.replace(partial, out)
    echo("\nSaved.")
    echo(f"Trainer logins ({len(loader.logins)}): {out}" if out else "No new trainer logins.")
    return True
