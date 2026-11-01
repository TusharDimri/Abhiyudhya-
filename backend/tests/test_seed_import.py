"""`flask import-seed`: the clean seed workbook into one organisation."""
import glob
import os

import openpyxl
import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from tests.conftest import reset_schema
from app.models.organisation import Organisation
from app.models.user import User
from app.models.geography import School
from app.models.lab import Lab, Trainer
from app.models.misc import AuditLog
from app.models.misc import Notification

SHEETS = {
    "1 State": (["State name *", "Code *"], [["Uttarakhand", "UK"]]),
    "2 Districts": (["District name *", "Code", "State *"], [["Almora", "UK-01", "Uttarakhand"]]),
    "3 Sectors": (["Sector name *"], [["IT/ITeS"], ["Electronics & Hardware"]]),
    "4 Job Roles": (["Job role name *", "Sector *", "Class band *", "QP code", "NSQF level", "Used by labs"], [
        ["Domestic Data Entry Operator", "IT/ITeS", "9-10", None, None, 1],
        ["Junior Software Developer", "IT/ITeS", "11-12", None, None, 1],
        ["Drone Service Technician", "Electronics & Hardware", "11-12", None, None, 1]]),
    "5 Academic Years": (["Label *", "Start date *", "End date *", "Current", "Notes"],
                         [["2026-27", "01/04/2026", "31/03/2027", "Yes", None]]),
    "6 Schools": (["School name *", "UDISE code *", "District *", "Block", "School type", "Board of school *",
                   "Full address *", "Email *", "Phone *", "Latitude *", "Longitude *", "Source row", "Notes"], [
        ["GIC One", "05090517902", "Almora", "B1", None, "Samagra Shiksha", "GIC One, Almora", "one@x.com",
         "9410715734", 29.55, 79.79, 2, None],
        ["GIC Two", "05090517903", "Almora", "B1", None, "PM Shri", "GIC Two, Almora",
         "pending.05090517903@placeholder.invalid", "9999999999", 29.56, 79.80, 3, None]]),
    "7 Labs": (["Lab name *", "School UDISE code *", "School name", "Trade / Sector *", "Job role (Class 9-10)",
                "Job role (Class 11-12)", "AY of setup *", "Source row (VT sheet)"], [
        ["IT/ITeS Lab", "05090517902", "GIC One", "IT/ITeS", "Domestic Data Entry Operator",
         "Junior Software Developer", "2026-27", 2],
        ["Electronics & Hardware Lab", "05090517903", "GIC Two", "Electronics & Hardware", None,
         "Drone Service Technician", "2026-27", 3]]),
    "8 Trainers": (["Full name *", "Gender *", "Email *", "Mobile *", "School UDISE code *", "School name", "Lab *",
                    "Job role(s) taught *", "Date of joining (DD/MM/YYYY) *", "VTP (training provider)",
                    "Candidate's code", "Source row (VT sheet)", "Notes"], [
        ["Asha Rawat", "Female", "Asha.Rawat@x.com", "9876500001", "05090517902", "GIC One", "IT/ITeS Lab",
         "Domestic Data Entry Operator; Junior Software Developer", "28/10/2026", "-", "VT1", 2, None],
        ["Ravi Negi", "Male", "ravi.negi@x.com", "9876500002", "05090517903", "GIC Two", "Electronics & Hardware Lab",
         "Drone Service Technician", "28/10/2026", "-", "VT2", 3, None]]),
}


def _workbook(folder, change=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, (head, rows) in SHEETS.items():
        ws = wb.create_sheet(title)
        ws.append(head)
        for r in rows:
            ws.append(list(r))
    if change:
        change(wb)
    path = os.path.join(folder, "clean.xlsx")
    wb.save(path)
    return path


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        reset_schema()
        yield app
        db.session.remove()


@pytest.fixture
def org_admin(app):
    org = Organisation(name="Rural Nurture and Advancement Foundation", org_code="RNAF")
    db.session.add(org)
    db.session.flush()
    oa = User(organisation_id=org.id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    return oa


def _run(app, path, *extra):
    return app.test_cli_runner().invoke(args=["import-seed", path, "--org", "rnaf", "--by", "oa@x.com", *extra])


def test_a_dry_run_checks_everything_and_keeps_nothing(app, org_admin, tmp_path):
    r = _run(app, _workbook(str(tmp_path)))
    assert r.exit_code == 0, r.output
    assert "Dry run" in r.output and "No problems" in r.output
    assert db.session.query(School).count() == 0 and db.session.query(Trainer).count() == 0
    assert not glob.glob(str(tmp_path / "Abhiyudhya VT Logins*"))


def test_the_load_makes_every_record_and_the_trainers_logins(app, org_admin, tmp_path):
    path = _workbook(str(tmp_path))
    r = _run(app, path, "--commit")
    assert r.exit_code == 0, r.output
    school = db.session.query(School).filter_by(udise_code="05090517902").one()
    assert school.board == "Samagra Shiksha" and school.location is not None
    drone = db.session.query(Lab).filter_by(name="Electronics & Hardware Lab").one()
    assert drone.job_role_9_10_id is None and drone.sections_9 == "A"
    asha = db.session.query(Trainer).filter_by(email="asha.rawat@x.com").one()
    assert len(asha.job_role_id_list) == 2 and asha.vtp_name == "RNAF"
    # nobody is told about each row
    assert db.session.query(Notification).count() == 0
    assert db.session.query(AuditLog).filter_by(entity="trainer").count() == 2

    # the logins file: written only now, and its passwords work (once)
    files = glob.glob(str(tmp_path / "Abhiyudhya VT Logins - *.xlsx"))
    assert len(files) == 1 and not glob.glob(str(tmp_path / "*.partial"))
    rows = list(openpyxl.load_workbook(files[0])["VT Logins"].iter_rows(values_only=True))
    assert len(rows) == 3
    head = rows[0]
    first = dict(zip(head, rows[1]))
    client = app.test_client()
    signed = client.post("/api/auth/login", json={"email": first["Username (email)"], "password": first["One-time password"]})
    assert signed.status_code == 200 and signed.get_json()["user"]["must_change_password"] is True
    user = db.session.query(User).filter_by(email="asha.rawat@x.com").one()
    assert [l.name for l in user.labs] == ["IT/ITeS Lab"] and user.role == "VT"

    # a second run finds it all there, adds nothing and makes no new logins
    again = _run(app, path, "--commit")
    assert again.exit_code == 0, again.output
    assert "No new trainer logins" in again.output
    assert db.session.query(School).count() == 2 and db.session.query(User).filter_by(role="VT").count() == 2


def test_one_problem_and_nothing_is_saved(app, org_admin, tmp_path):
    def spoil(wb):
        wb["6 Schools"]["F3"] = "Some Board"                   # GIC Two's board
        wb["8 Trainers"]["H2"] = "Plumber (General)"           # not a role of Asha's lab
    r = _run(app, _workbook(str(tmp_path), spoil), "--commit")
    assert r.exit_code == 1
    assert "6 Schools, row 3: Pick the school's board from the list." in r.output
    assert "8 Trainers, row 2: 'Plumber (General)' isn't a job role of IT/ITeS Lab at GIC One." in r.output
    assert "nothing was saved" in r.output
    assert db.session.query(School).count() == 0 and db.session.query(User).filter_by(role="VT").count() == 0
    assert not glob.glob(str(tmp_path / "Abhiyudhya VT Logins*"))


def test_only_this_organisations_admin_may_load_it(app, org_admin, tmp_path):
    other = Organisation(name="Other", org_code="OTHER")
    db.session.add(other)
    db.session.flush()
    stranger = User(organisation_id=other.id, full_name="Other OA", email="other@x.com", role="OA")
    stranger.set_password("Password@123")
    db.session.add(stranger)
    db.session.commit()
    r = app.test_cli_runner().invoke(args=["import-seed", _workbook(str(tmp_path)), "--org", "RNAF", "--by", "other@x.com"])
    assert r.exit_code != 0 and "must be this organisation's Org Admin" in r.output


def test_two_districts_of_one_name_stop_the_load(app, org_admin, tmp_path):
    # an older, misspelt state already holds an 'ALMORA': the sheet's 'Almora' could be either
    from app.models.geography import State, District
    old = State(organisation_id=org_admin.organisation_id, name="UTTRAKHAND")
    db.session.add(old)
    db.session.flush()
    db.session.add(District(organisation_id=org_admin.organisation_id, state_id=old.id, name="ALMORA"))
    db.session.commit()
    r = _run(app, _workbook(str(tmp_path)), "--commit")
    assert r.exit_code == 1
    assert "6 Schools, row 2: There are 2 districts called 'Almora' (in different states)" in r.output
    assert db.session.query(School).count() == 0
