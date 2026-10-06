"""Profile pages - a person's own record, shown and edited by them.

GET   /api/profile   everything, with sensitive numbers masked
PATCH /api/profile   any subset: single fields and/or whole lists

One engine, one description per role (PROFILES below): which fields there
are, which are locked once on record, what each section needs before it can
be saved, the history lists, and what is worked out rather than typed.

Sensitive numbers (a trainer's Aadhaar, bank account, PAN) are never sent
back whole: only the last four characters show. Sending a masked value back
(the page re-saving what it was shown) leaves the stored number as it is.
"""
import re
from datetime import date, datetime

from flask import Blueprint, abort, jsonify, request

from app.extensions import db
from app.models.lab import Lab, Trainer
from app.models.geography import District, Principal, School
from app.models.masters import JobRole, Sector, SocialCategory
from app.models.trainer_profile import (
    PrincipalPosting, PrincipalQualification, PrincipalTraining,
    TrainerExperience, TrainerPosting, TrainerQualification, TrainerTraining,
)
from app.rbac import current_user, login_required
from app.rbac.roles import Role
from app.services import audit
from app.services.academic_year import academic_year_for
from app.services.cache import cached_json
from app.utils.masking import mask

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


class Invalid(ValueError):
    pass


# ------------------------------------------------------------- shared rules
FORMATS = {
    "aadhaar_number": (re.compile(r"^\d{12}$"), "Aadhaar number must be 12 digits."),
    "pan_number": (re.compile(r"^[A-Z]{5}\d{4}[A-Z]$"), "PAN must look like ABCDE1234F."),
    "ifsc_code": (re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$"), "IFSC must look like PUNB0797200."),
    "account_number": (re.compile(r"^\d{9,18}$"), "Account number must be 9 to 18 digits."),
    "phone": (re.compile(r"^[6-9]\d{9}$"), "Mobile number must be 10 digits starting 6-9."),
    "mobile": (re.compile(r"^[6-9]\d{9}$"), "Mobile number must be 10 digits starting 6-9."),
    "alternate_mobile": (re.compile(r"^[6-9]\d{9}$"), "Alternate mobile must be 10 digits starting 6-9."),
    "email": (re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"), "Enter a valid email address."),
    "vocational_prabhari_mobile": (re.compile(r"^[6-9]\d{9}$"), "Vocational Prabhari's mobile must be 10 digits starting 6-9."),
    "vocational_prabhari_email": (re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"), "Enter a valid email for the Vocational Prabhari."),
}
FIELD_LABELS = {
    "full_name": "Name", "father_name": "Father's name", "mother_name": "Mother's name",
    "dob": "Date of birth", "gender": "Gender", "phone": "Mobile number", "mobile": "Mobile number",
    "alternate_mobile": "Alternate mobile", "email": "Email",
    "aadhaar_number": "Aadhaar number", "pan_number": "PAN", "vtp_name": "VTP name",
    "correspondence_address": "Correspondence address", "permanent_address": "Permanent address",
    "beneficiary_name": "Beneficiary name", "bank_name": "Bank name",
    "account_number": "Account number", "ifsc_code": "IFSC code",
    "designation": "Designation", "employee_id": "Employee ID",
    "service_joining_date": "Date of joining service", "substantive_post": "Substantive post",
    "highest_qualification": "Highest qualification", "gross_salary": "Gross salary",
    "deduction_esi": "ESI deduction", "deduction_epf": "EPF deduction",
    "deduction_tds": "TDS deduction", "deduction_other": "Other deduction",
    "date_of_joining": "In charge since", "appointment_nature": "Nature of appointment",
    "vocational_prabhari_name": "Vocational Prabhari's name",
    "vocational_prabhari_mobile": "Vocational Prabhari's mobile", "vocational_prabhari_email": "Vocational Prabhari's email",
}
# answers that must be one of a fixed list (enums.py)
CHOICES = {"gender": "genders", "marital_status": "marital_status", "blood_group": "blood_groups",
           "designation": "principal_designations", "highest_qualification": "qualification_levels",
           "appointment_nature": "appointment_nature"}
ROW_CHOICES = {"qualification": "qualification_levels", "course_type": "course_types", "job_type": "job_types",
               "job_nature": "job_nature", "appointment_nature": "appointment_nature", "school_type": "school_types"}
DATES = {"dob", "service_joining_date", "date_of_joining"}
MONEY = {"gross_salary", "deduction_esi", "deduction_epf", "deduction_tds", "deduction_other"}

QUALIFICATION_FIELDS = ["qualification", "course", "institution", "course_type", "passing_year", "marksheet_date"]
TRAINING_FIELDS = ["training_type", "training_level", "venue", "from_date", "to_date"]


def _years(start, end):
    return max((end - start).days, 0) / 365.25 if start and end else 0.0


def _school_facts(school):
    district = db.session.get(District, school.district_id) if school and school.district_id else None
    return {
        "school_name": school.name if school else None,
        "udise_code": school.udise_code if school else None,
        "district": district.name if district else None,
        "block": school.block if school else None,
        "school_type": school.school_type if school else None,
    }


# ------------------------------------------------------ what each role has
def _trainer_extras(tr):
    past = sum(_years(e.date_of_joining, e.date_of_resignation or e.date_of_joining)
               for e in db.session.query(TrainerExperience).filter(
                   TrainerExperience.trainer_id == tr.id, TrainerExperience.is_deleted.is_(False)))
    current = _years(tr.date_of_joining, tr.date_of_exit or date.today())
    deductions = sum(getattr(tr, f) or 0 for f in ("deduction_esi", "deduction_epf", "deduction_tds", "deduction_other"))
    school = db.session.get(School, tr.school_id) if tr.school_id else None
    lab = db.session.get(Lab, tr.lab_id) if tr.lab_id else None
    sector = db.session.get(Sector, lab.sector_id) if lab and lab.sector_id else None
    role = db.session.get(JobRole, tr.job_role_id) if tr.job_role_id else None
    return {
        "total_experience_years": round(past + current, 1),
        "net_salary": round(tr.gross_salary - deductions, 2) if tr.gross_salary is not None else None,
        "date_of_joining": tr.date_of_joining.isoformat() if tr.date_of_joining else None,
        "appointment_nature": tr.appointment_nature,
        # where they are posted now - kept by the admins, read-only here
        "posting": {
            **_school_facts(school),
            "school_year": academic_year_for(tr.organisation_id, tr.date_of_joining) if tr.date_of_joining else None,
            "lab_name": lab.name if lab else None,
            "skill_name": sector.name if sector else None,
            "job_role": role.name if role else None,
            "date_of_joining": tr.date_of_joining.isoformat() if tr.date_of_joining else None,
            "appointment_nature": tr.appointment_nature,
            "trainer_status": tr.trainer_status,
        },
    }


def _superannuation(dob):
    """Retirement at 60: the last day of the month they turn 60."""
    if not dob:
        return None
    y, m = dob.year + 60, dob.month
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def _principal_extras(pr):
    school = db.session.get(School, pr.linked_school_id) if pr.linked_school_id else None
    labs = (db.session.query(Lab).filter(Lab.school_id == school.id, Lab.is_deleted.is_(False))
            .order_by(Lab.name).all()) if school else []
    trainers = (db.session.query(Trainer).filter(
        Trainer.school_id == school.id, Trainer.is_deleted.is_(False), Trainer.trainer_status != "exited")
        .order_by(Trainer.full_name).all()) if school else []
    retire = _superannuation(pr.dob)
    return {
        "total_service_years": round(_years(pr.service_joining_date, date.today()), 1) if pr.service_joining_date else None,
        "years_at_school": round(_years(pr.date_of_joining, pr.date_of_resignation or date.today()), 1)
        if pr.date_of_joining else None,
        "superannuation_date": retire.isoformat() if retire else None,
        "posting": {
            **_school_facts(school),
            "school_address": school.address if school else None,
            "school_email": school.email if school else None,
            "school_phone": school.phone if school else None,
            "labs": [lab.name for lab in labs],
            "trainers": [t.full_name for t in trainers],
            "date_of_joining": pr.date_of_joining.isoformat() if pr.date_of_joining else None,
            "appointment_nature": pr.appointment_nature,
            "designation": pr.designation,
            "employee_id": pr.employee_id,
        },
    }


PROFILES = {
    Role.TRAINER.value: {
        "model": Trainer, "parent_fk": "trainer_id", "audit": "trainer_profile",
        "missing": "This login has no trainer profile.",
        "fields": {
            "full_name", "phone", "email", "gender", "photo_url", "father_name", "mother_name", "dob",
            "domicile_state", "social_category_id", "marital_status", "nationality", "blood_group",
            "aadhaar_number", "vtp_name", "correspondence_address", "permanent_address",
            "beneficiary_name", "bank_name", "branch_address", "account_number", "ifsc_code",
            "gross_salary", "deduction_esi", "deduction_epf", "deduction_tds", "deduction_other",
            "pan_number", "esi_number", "uan_number", "vt_signature_url", "vtp_signature_url",
        },
        "sensitive": {"aadhaar_number", "account_number", "pan_number"},
        # identity details: blank ones filled in once, then only an admin changes them
        "locked": {"full_name", "father_name", "dob", "gender", "aadhaar_number", "pan_number", "vtp_name"},
        # shown to the trainer, never changed by them - their admin keeps it
        # (the admin's trainer form: apply_admin_profile)
        "read_only_sections": {"bank"},
        # the page saves one section at a time; a saved section must be complete
        "sections": {
            "general": {
                "fields": {"full_name", "father_name", "mother_name", "dob", "gender", "social_category_id",
                           "marital_status", "nationality", "blood_group", "aadhaar_number", "vtp_name",
                           "phone", "email", "domicile_state"},
                "required": ["full_name", "father_name", "dob", "gender", "phone", "email", "aadhaar_number"],
            },
            "address": {"fields": {"correspondence_address", "permanent_address"},
                        "required": ["correspondence_address", "permanent_address"]},
            "bank": {
                "fields": {"beneficiary_name", "bank_name", "branch_address", "account_number", "ifsc_code",
                           "gross_salary", "deduction_esi", "deduction_epf", "deduction_tds", "deduction_other",
                           "pan_number", "esi_number", "uan_number"},
                "required": ["beneficiary_name", "bank_name", "account_number", "ifsc_code"],
            },
            "pictures": {"fields": {"photo_url", "vt_signature_url", "vtp_signature_url"}, "required": []},
        },
        "lists": {
            "qualifications": (TrainerQualification, QUALIFICATION_FIELDS),
            "experiences": (TrainerExperience, ["organisation_name", "address", "date_of_joining",
                                                "date_of_resignation", "last_designation", "last_salary",
                                                "job_type", "job_nature", "reason_for_resignation"]),
            "trainings": (TrainerTraining, TRAINING_FIELDS),
            "postings": (TrainerPosting, ["vtp_name", "district", "block", "school_name", "school_year",
                                          "school_type", "date_of_joining", "date_of_relieving",
                                          "appointment_nature", "appointment_letter", "experience_certificate"]),
        },
        "pictures": ["photo_url", "vt_signature_url", "vtp_signature_url"],
        "extras": _trainer_extras,
    },
    Role.PRINCIPAL.value: {
        "model": Principal, "parent_fk": "principal_id", "audit": "principal_profile",
        "missing": "This login has no principal profile.",
        "fields": {
            "full_name", "designation", "employee_id", "father_name", "dob", "gender", "social_category_id",
            "mobile", "alternate_mobile", "email", "photo_url", "correspondence_address", "permanent_address",
            "service_joining_date", "substantive_post", "highest_qualification",
            "professional_qualification", "subject_specialisation", "signature_url", "school_seal_url",
            "date_of_joining", "appointment_nature",
            "vocational_prabhari_name", "vocational_prabhari_mobile", "vocational_prabhari_email",
        },
        "sensitive": set(),
        "locked": {"full_name", "father_name", "dob", "gender", "employee_id"},
        "sections": {
            "general": {
                "fields": {"full_name", "designation", "employee_id", "father_name", "dob", "gender",
                           "social_category_id", "mobile", "alternate_mobile", "email"},
                "required": ["full_name", "designation", "dob", "gender", "mobile", "email"],
            },
            "service": {
                "fields": {"service_joining_date", "substantive_post", "highest_qualification",
                           "professional_qualification", "subject_specialisation"},
                "required": ["service_joining_date", "highest_qualification"],
            },
            "address": {"fields": {"correspondence_address", "permanent_address"},
                        "required": ["correspondence_address", "permanent_address"]},
            # at this school: since when, and how appointed (no longer asked
            # when the admin adds them)
            "posting": {"fields": {"date_of_joining", "appointment_nature"}, "required": ["date_of_joining"]},
            # optional; once begun, it needs at least a name and a mobile
            "prabhari": {"fields": {"vocational_prabhari_name", "vocational_prabhari_mobile", "vocational_prabhari_email"},
                         "required": ["vocational_prabhari_name", "vocational_prabhari_mobile"]},
            "pictures": {"fields": {"photo_url", "signature_url", "school_seal_url"}, "required": []},
        },
        "lists": {
            "qualifications": (PrincipalQualification, QUALIFICATION_FIELDS),
            "postings": (PrincipalPosting, ["school_name", "district", "block", "designation", "from_date", "to_date"]),
            "trainings": (PrincipalTraining, TRAINING_FIELDS),
        },
        "pictures": ["photo_url", "signature_url", "school_seal_url"],
        "extras": _principal_extras,
    },
}


def _kind_and_record():
    user = current_user()
    kind = PROFILES.get(user.role)
    if kind is None:
        abort(404, description="This login has no profile page.")
    model = kind["model"]
    rec = db.session.query(model).filter(model.user_id == user.id, model.is_deleted.is_(False)).first()
    if rec is None:
        abort(404, description=kind["missing"])
    return user, kind, rec


# ------------------------------------------------------------------ parsing
def _date(value, label):
    if value in (None, ""):
        return None
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise Invalid(f"{label}: enter a real date.")
    if d > date.today():
        raise Invalid(f"{label} can't be in the future.")
    return d


def _money(value, label):
    if value in (None, ""):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise Invalid(f"{label} must be a number.")
    if n < 0:
        raise Invalid(f"{label} can't be negative.")
    return n


def _text(value):
    return None if value is None else (str(value).strip() or None)


def _field(name, value):
    if name in DATES:
        return _date(value, FIELD_LABELS.get(name, name))
    if name in MONEY:
        return _money(value, FIELD_LABELS.get(name, name))
    if name == "social_category_id":
        if not value:
            return None
        if not db.session.get(SocialCategory, value):
            raise Invalid("Unknown category.")
        return value
    v = _text(value)
    if v is not None and name in CHOICES:
        from app.api import enums
        if v not in enums.values(CHOICES[name]):
            raise Invalid(f"Pick a valid {FIELD_LABELS.get(name, name.replace('_', ' ')).lower()}.")
    if v is not None:
        if name in ("pan_number", "ifsc_code"):
            v = v.upper().replace(" ", "")
        if name in ("aadhaar_number", "account_number"):
            v = v.replace(" ", "")
        fmt = FORMATS.get(name)
        if fmt and not fmt[0].match(v):
            raise Invalid(fmt[1])
    return v


def _row(model, fields, item):
    """One list row from the page, checked."""
    out = {}
    for f in fields:
        v = item.get(f)
        col = model.__table__.columns[f]
        if f in ("appointment_letter", "experience_certificate"):
            out[f] = None if v in (None, "") else bool(v) and str(v).lower() not in ("false", "no", "0")
        elif isinstance(col.type, db.Date):
            out[f] = _date(v, f.replace("_", " ").capitalize())
        elif f in ("last_salary",):
            out[f] = _money(v, "Last salary")
        elif f == "passing_year":
            if v in (None, ""):
                out[f] = None
            else:
                try:
                    y = int(v)
                except (TypeError, ValueError):
                    raise Invalid("Passing year must be a year, e.g. 2006.")
                if not 1950 <= y <= date.today().year:
                    raise Invalid("Passing year must be between 1950 and this year.")
                out[f] = y
        else:
            out[f] = _text(v)
            if out[f] is not None and f in ROW_CHOICES:
                from app.api import enums
                if out[f] not in enums.values(ROW_CHOICES[f]):
                    raise Invalid(f"Pick a valid {f.replace('_', ' ')}.")
    # a stretch of time must run forwards
    for start, end in (("date_of_joining", "date_of_resignation"), ("date_of_joining", "date_of_relieving"),
                       ("from_date", "to_date")):
        if out.get(start) and out.get(end) and out[end] < out[start]:
            raise Invalid(f"{end.replace('_', ' ').capitalize()} can't be before {start.replace('_', ' ')}.")
    return out


# --------------------------------------------------------------- reading
def _serialise(kind, rec):
    data = {k: getattr(rec, k) for k in kind["fields"] if k not in kind["sensitive"]}
    for k in kind["sensitive"]:
        data[k] = mask(getattr(rec, k))
    for k, v in list(data.items()):
        if isinstance(v, (date, datetime)):
            data[k] = v.isoformat()
    data["id"] = str(rec.id)
    data["social_category_id"] = str(rec.social_category_id) if rec.social_category_id else None

    fk = kind["parent_fk"]
    for key, (model, fields) in kind["lists"].items():
        rows = (db.session.query(model)
                .filter(getattr(model, fk) == rec.id, model.is_deleted.is_(False))
                .order_by(model.created_at.asc()).all())
        data[key] = [{"id": str(r.id), **{f: (getattr(r, f).isoformat() if isinstance(getattr(r, f), date)
                                              else getattr(r, f)) for f in fields}} for r in rows]

    data.update(kind["extras"](rec))
    category = db.session.get(SocialCategory, rec.social_category_id) if rec.social_category_id else None
    data["category_name"] = category.name if category else None
    data["locked"] = sorted(f for f in kind["locked"] if getattr(rec, f) not in (None, ""))
    data["required"] = {k: v["required"] for k, v in kind["sections"].items()}
    data["read_only_sections"] = sorted(kind.get("read_only_sections", ()))

    # pictures: short-lived links the browser can open
    from app.services import storage
    for key in kind["pictures"]:
        path = getattr(rec, key)
        try:
            data[key.replace("_url", "_src")] = (path if str(path).startswith("http") else storage.presign_download(path)) if path else None
        except Exception:  # storage not configured - the page just shows no picture
            data[key.replace("_url", "_src")] = None
    return data


def _write_lists(kind, rec, payload, user):
    """Replace the profile's tables (qualifications, experience ...) sent in
    the payload; a table not sent is left alone, blank rows are skipped."""
    fk = kind["parent_fk"]
    for key, (model, fields) in kind["lists"].items():
        if key not in payload:
            continue
        items = payload.get(key) or []
        if not isinstance(items, list):
            raise Invalid(f"{key} must be a list.")
        rows = [_row(model, fields, it) for it in items if isinstance(it, dict)]
        rows = [r for r in rows if any(v not in (None, "") for v in r.values())]  # skip blank rows
        db.session.query(model).filter(getattr(model, fk) == rec.id).delete()
        for r in rows:
            db.session.add(model(organisation_id=rec.organisation_id, created_by=user.id,
                                 **{fk: rec.id}, **r))


# ------------------------------------------------- an admin filling it in
def admin_profile_view(role, rec):
    """The profile fields and tables of a trainer / principal, for the admin's
    add-and-edit form (sensitive numbers masked, pictures as links)."""
    kind = PROFILES[role]
    data = _serialise(kind, rec)
    keys = kind["fields"] | set(kind["lists"]) | {k.replace("_url", "_src") for k in kind["pictures"]}
    return {k: data.get(k) for k in keys}


def apply_admin_profile(role, rec, payload, user, base_fields=()):
    """Save the profile part of an admin's trainer / principal form. Same
    checks as the profile page, except an admin may change locked details.
    A section only has to be complete once something beyond the basic record
    (`base_fields`: name, contact, posting) has been filled in it. Raises
    Invalid."""
    kind = PROFILES[role]
    for name, value in payload.items():
        if name not in kind["fields"]:
            continue
        if name in kind["sensitive"] and value is not None and value == mask(getattr(rec, name)):
            continue  # the masked value the form was shown - keep what is stored
        setattr(rec, name, _field(name, value))
    for section in kind["sections"].values():
        started = [f for f in section["fields"] - set(base_fields) if getattr(rec, f) not in (None, "")]
        if started:
            missing = [FIELD_LABELS.get(f, f) for f in section["required"] if getattr(rec, f) in (None, "")]
            if missing:
                raise Invalid("Please fill in: " + ", ".join(missing) + ".")
    _write_lists(kind, rec, payload, user)


@bp.get("")
@login_required
@cached_json("profile", ttl=120)
def get_profile():
    _, kind, rec = _kind_and_record()
    return jsonify(_serialise(kind, rec))


@bp.patch("")
@login_required
def update_profile():
    user, kind, rec = _kind_and_record()
    payload = request.get_json(silent=True) or {}
    before = _serialise(kind, rec)
    read_only = {f for sec in kind.get("read_only_sections", ()) for f in kind["sections"][sec]["fields"]}
    try:
        for name, value in payload.items():
            if name not in kind["fields"]:
                continue
            if name in kind["sensitive"] and value is not None and value == mask(getattr(rec, name)):
                continue  # the masked value the page was shown - keep what is stored
            new = _field(name, value)
            current = getattr(rec, name)
            if name in read_only and str(new or "") != str(current or ""):
                raise Invalid("Bank and salary details are kept by your admin - ask them to change them.")
            if name in kind["locked"] and current not in (None, "") and str(new or "") != str(current):
                raise Invalid(f"{FIELD_LABELS.get(name, name)} is on record and can't be changed here "
                              "- ask your admin.")
            setattr(rec, name, new)

        for section in kind["sections"].values():
            if section["fields"] & payload.keys():
                missing = [FIELD_LABELS.get(f, f) for f in section["required"] if getattr(rec, f) in (None, "")]
                if missing:
                    raise Invalid("Please fill in: " + ", ".join(missing) + ".")

        _write_lists(kind, rec, payload, user)
    except Invalid as exc:
        db.session.rollback()
        abort(400, description=str(exc))

    rec.updated_by = user.id
    db.session.flush()
    audit.record(user, "update", kind["audit"], rec.id, before=before, after=_serialise(kind, rec))
    db.session.commit()
    return jsonify(_serialise(kind, rec))
