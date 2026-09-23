"""Daily-entry behaviour: every activity branch, class marking, cascades.

The competitor's app asks a trainer for one thing and fills the rest in; these
tests pin the two halves of that - the branch fields actually persist, and the
rules behind the dropdowns are enforced server-side, not just in the UI.
"""
import os
from datetime import date

import pytest

os.environ["TESTING"] = "1"

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from tests.conftest import reset_schema  # noqa: E402
from app.models.organisation import Organisation  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.geography import State, District, School  # noqa: E402
from app.models.masters import AcademicYear, Sector, JobRole  # noqa: E402
from app.models.lab import Lab, Module, Unit, Session, Trainer  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.operations import DailyAttendance, AttendanceStudentMark  # noqa: E402


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        reset_schema()
        yield app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def world(app):
    """One org, one school, one lab with two job-role slots, a 9A/9B class."""
    org = Organisation(name="Org", org_code="ORG")
    db.session.add(org)
    db.session.flush()
    db.session.add(AcademicYear(organisation_id=org.id, label="2025-26", is_current=True))
    st = State(organisation_id=org.id, name="S")
    db.session.add(st)
    db.session.flush()
    dis = District(organisation_id=org.id, state_id=st.id, name="D")
    db.session.add(dis)
    db.session.flush()
    school = School(organisation_id=org.id, district_id=dis.id, name="Sch", udise_code="U1")
    sector = Sector(organisation_id=org.id, name="IT")
    db.session.add_all([school, sector])
    db.session.flush()
    jr_low = JobRole(organisation_id=org.id, name="DDEO", sector_id=sector.id, class_band="9-10")
    jr_high = JobRole(organisation_id=org.id, name="JSD", sector_id=sector.id, class_band="11-12")
    db.session.add_all([jr_low, jr_high])
    db.session.flush()
    lab = Lab(organisation_id=org.id, name="Lab", school_id=school.id, sector_id=sector.id,
              job_role_9_10_id=jr_low.id, job_role_11_12_id=jr_high.id,
              sections_9="A,B", sections_10="A", sections_11="A", sections_12="A")
    db.session.add(lab)
    db.session.flush()

    mod = Module(organisation_id=org.id, job_role_id=jr_low.id, name="M1", module_type="Vocational")
    db.session.add(mod)
    db.session.flush()
    unit = Unit(organisation_id=org.id, module_id=mod.id, name="U1")
    db.session.add(unit)
    db.session.flush()
    db.session.add(Session(organisation_id=org.id, unit_id=unit.id, name="S1"))

    students = []
    for i, sec in enumerate(["A", "A", "B"]):
        s = Student(organisation_id=org.id, school_id=school.id, lab_id=lab.id,
                    job_role_id=jr_low.id, class_grade="9", section=sec,
                    roll_number=f"9{sec}-{i}", first_name=f"Stu{i}")
        students.append(s)
    db.session.add_all(students)

    vt = User(organisation_id=org.id, full_name="VT", email="vt@x.com", role="VT", school_id=school.id)
    vt.set_password("Password@123")
    db.session.add(vt)
    db.session.flush()
    vt.labs.append(lab)
    db.session.add(Trainer(organisation_id=org.id, full_name="VT", school_id=school.id,
                           lab_id=lab.id, job_role_id=jr_low.id, user_id=vt.id))
    db.session.commit()
    return {
        "org": org, "school": school, "lab": lab, "jr_low": jr_low, "jr_high": jr_high,
        "module": mod, "unit": unit, "students": students,
    }


def _login(client, email="vt@x.com"):
    r = client.post("/api/auth/login", json={"email": email, "password": "Password@123"})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


# ---------------------------------------------------------------- bootstrap
def test_bootstrap_ships_lab_sections_and_enums(client, world):
    h = _login(client)
    boot = client.get("/api/meta/bootstrap", headers=h).get_json()

    lab = next(l for l in boot["options"]["labs"] if l["value"] == str(world["lab"].id))
    assert lab["sections"]["9"] == ["A", "B"], "section dropdowns read from the lab"
    assert lab["job_role_9_10_id"] == str(world["jr_low"].id)
    assert lab["job_role_11_12_id"] == str(world["jr_high"].id)

    # the sub-issue cascade is served, not hardcoded in the client
    subs = boot["enums"]["issue_sub"]["Lab-Room/Infrastructure"]
    assert {o["value"] for o in subs} == {
        "Maintenance Required", "Only Single Room Allotted - MSFC",
        "Room Condition Repair Needed", "Room Not Allotted",
    }
    assert boot["my_scope"]["profile"]["school_id"] == str(world["school"].id)


# --------------------------------------------------------------- attendance
def test_teaching_entry_saves_curriculum_and_marks_the_class(client, world):
    h = _login(client)
    ids = [str(s.id) for s in world["students"]]
    r = client.post("/api/attendance", headers=h, json={
        "date": "2025-07-01", "day_type": "Working day",
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "job_role_id": str(world["jr_low"].id), "academic_year": "2025-26",
        "activity_type": "Teaching Vocational Education",
        "class_taught": "9", "section_taught": "A,B",
        "theory_or_practical": "Practical", "class_type": "regular", "duration_mins": 45,
        "module_id": str(world["module"].id), "unit_id": str(world["unit"].id),
        "student_marks": [
            {"student_id": ids[0], "present": True},
            {"student_id": ids[1], "present": False},
            {"student_id": ids[2], "present": True},
        ],
    })
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert len(body["student_marks"]) == 3
    assert sum(1 for m in body["student_marks"] if m["present"]) == 2

    # re-saving is the full truth for that day: a removed student leaves
    got = client.put(f"/api/attendance/{body['id']}", headers=h, json={
        "student_marks": [{"student_id": ids[0], "present": False}],
    })
    assert got.status_code == 200
    assert got.get_json()["student_marks"] == [{"student_id": ids[0], "present": False}]
    assert db.session.query(AttendanceStudentMark).filter_by(is_deleted=False).count() == 1


@pytest.mark.parametrize("activity,payload,check", [
    ("Visit to Industry",
     {"industry_name": "Tata", "industry_contact_person": "R", "industry_contact_phone": "9000000000"},
     "industry_name"),
    ("Visit to Educational Institution",
     {"institute_name": "IIT", "institute_contact_person": "P", "institute_contact_phone": "9000000001"},
     "institute_name"),
    ("On-Job Training Coordination", {"ojt_activity_type": "Orientation of Students"}, "ojt_activity_type"),
    ("Parent Teachers Meeting", {"parents_count": 22}, "parents_count"),
    ("Community Home Visit", {"parents_count": 4}, "parents_count"),
    ("Teaching Non-Vocational Subject",
     {"other_class_details": "Maths cover", "other_class_duration_mins": 40}, "other_class_details"),
    ("Assignment from Vocational Department",
     {"assignment_number": "A-12", "assignment_photo_url": "s3://x.jpg"}, "assignment_number"),
    ("Assessor in Other School",
     {"assessor_school_name": "Other Sch", "assessor_udise": "U9", "assessor_class": "10",
      "boys_present": 15, "girls_present": 18}, "assessor_udise"),
    ("Training of Teacher/Trainer", {"training_type": "VTP Training Programme"}, "training_type"),
    ("Guidance & Counselling", {"students_count": 30}, "students_count"),
])
def test_every_activity_branch_persists_its_own_fields(client, world, activity, payload, check):
    h = _login(client)
    r = client.post("/api/attendance", headers=h, json={
        "date": "2025-07-02", "day_type": "Working day",
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "job_role_id": str(world["jr_low"].id), "activity_type": activity,
        "details": "narrative", **payload,
    })
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body[check] == payload[check]
    assert body["details"] == "narrative"


def test_leave_day_keeps_its_school_and_lab(client, world):
    """A leave day is still the trainer's day: blanking school/lab would push
    the record outside their own scope and the save would be refused."""
    h = _login(client)
    r = client.post("/api/attendance", headers=h, json={
        "date": "2025-07-05", "day_type": "On leave", "leave_reason": "Medical",
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "activity_type": None, "class_taught": None,
    })
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["leave_reason"] == "Medical"
    assert body["lab_id"] == str(world["lab"].id)
    assert body["activity_type"] is None

    # and it comes back in the trainer's own list
    listed = client.get("/api/attendance?day_type=On leave", headers=h).get_json()
    assert listed["pagination"]["total"] == 1


def test_switching_activity_clears_the_previous_branch(client, world):
    """Re-saving a day as a different activity must not leave the old
    branch's answers behind on the record."""
    h = _login(client)
    created = client.post("/api/attendance", headers=h, json={
        "date": "2025-07-06", "day_type": "Working day",
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "job_role_id": str(world["jr_low"].id),
        "activity_type": "Visit to Industry", "industry_name": "Tata",
    }).get_json()
    assert created["industry_name"] == "Tata"

    # the form sends every field it is no longer showing as null
    updated = client.put(f"/api/attendance/{created['id']}", headers=h, json={
        "activity_type": "Parent Teachers Meeting", "parents_count": 12,
        "industry_name": None, "industry_contact_person": None, "industry_contact_phone": None,
    }).get_json()
    assert updated["parents_count"] == 12
    assert updated["industry_name"] is None


def test_trainer_cannot_log_a_class_their_lab_does_not_teach(client, world):
    h = _login(client)
    r = client.post("/api/attendance", headers=h, json={
        "date": "2025-07-03", "day_type": "Working day",
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "job_role_id": str(world["jr_low"].id),
        "activity_type": "Teaching Vocational Education",
        "class_taught": "11",  # 11 belongs to the other job-role slot
    })
    assert r.status_code == 400
    assert "not taught" in r.get_json()["message"]


# ------------------------------------------------------------------- issues
def test_sub_issue_must_belong_to_its_main_issue(client, world):
    h = _login(client)
    bad = client.post("/api/issues", headers=h, json={
        "reporting_date": "2025-07-04", "lab_id": str(world["lab"].id),
        "main_issue": "Lab-Room/Infrastructure", "sub_issue": "VT Salary",
    })
    assert bad.status_code == 400
    assert "not a sub-issue" in bad.get_json()["message"]

    ok = client.post("/api/issues", headers=h, json={
        "reporting_date": "2025-07-04", "lab_id": str(world["lab"].id),
        "main_issue": "Lab-Room/Infrastructure", "sub_issue": "Room Not Allotted",
        "students_affected": "all",
    })
    assert ok.status_code == 201, ok.get_json()


def test_some_students_affected_needs_a_number(client, world):
    h = _login(client)
    r = client.post("/api/issues", headers=h, json={
        "reporting_date": "2025-07-04", "lab_id": str(world["lab"].id),
        "main_issue": "Other", "sub_issue": "Other", "students_affected": "some",
    })
    assert r.status_code == 400
    assert "how many" in r.get_json()["message"]


# ------------------------------------------------------------- students etc.
def test_registration_is_class_9_or_11_only(client, world):
    h = _login(client)
    r = client.post("/api/students", headers=h, json={
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "class_grade": "10", "first_name": "Late",
    })
    assert r.status_code == 400
    assert "Class 9 or Class 11" in r.get_json()["message"]


def test_roster_filter_accepts_several_sections(client, world):
    h = _login(client)
    both = client.get(f"/api/students?lab_id={world['lab'].id}&class_grade=9&section=A,B", headers=h)
    assert both.get_json()["pagination"]["total"] == 3
    one = client.get(f"/api/students?lab_id={world['lab'].id}&class_grade=9&section=B", headers=h)
    assert one.get_json()["pagination"]["total"] == 1


def test_sessions_can_be_listed_by_module(client, world):
    h = _login(client)
    r = client.get(f"/api/sessions?module_id={world['module'].id}", headers=h)
    assert r.status_code == 200
    assert [s["name"] for s in r.get_json()["data"]] == ["S1"]


def test_one_trainer_per_job_role_in_a_lab(client, world):
    # an org admin adding a second trainer on the same slot is refused
    org = world["org"]
    oa = User(organisation_id=org.id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _login(client, "oa@x.com")
    r = client.post("/api/trainers", headers=h, json={
        "full_name": "Second VT", "school_id": str(world["school"].id),
        "lab_id": str(world["lab"].id), "job_role_id": str(world["jr_low"].id),
    })
    assert r.status_code == 400
    assert "already holds this job role" in r.get_json()["message"]

    # the other slot is free
    ok = client.post("/api/trainers", headers=h, json={
        "full_name": "Senior VT", "school_id": str(world["school"].id),
        "lab_id": str(world["lab"].id), "job_role_id": str(world["jr_high"].id),
    })
    assert ok.status_code == 201, ok.get_json()


def test_lab_slot_rejects_a_job_role_from_the_wrong_band(client, world):
    org = world["org"]
    oa = User(organisation_id=org.id, full_name="OA2", email="oa2@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _login(client, "oa2@x.com")
    r = client.post("/api/labs", headers=h, json={
        "name": "Bad Lab", "school_id": str(world["school"].id),
        "job_role_9_10_id": str(world["jr_high"].id),
    })
    assert r.status_code == 400
    assert "cannot fill the 9-10 slot" in r.get_json()["message"]
