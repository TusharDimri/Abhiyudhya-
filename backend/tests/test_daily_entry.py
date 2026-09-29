"""Daily-entry behaviour: every activity branch, class marking, cascades.

The competitor's app asks a trainer for one thing and fills the rest in; these
tests pin the two halves of that - the branch fields actually persist, and the
rules behind the dropdowns are enforced server-side, not just in the UI.
"""
import os
from datetime import date, timedelta

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
# The trainer's own daily attendance and their class attendance are both
# marked at the school: the sealed location must be within 1 km of it.
MUMBAI = {"lat": 19.0760, "lng": 72.8777}          # ~120 km from the school
NEARBY = {"lat": 18.5276, "lng": 73.8567}          # ~800 m north of it


def _school_located(world):
    from app.models.geo import point_wkt
    world["school"].location = point_wkt(18.5204, 73.8567)   # PUNE, as sealed by _save
    db.session.commit()


def _vt_attendance(**extra):
    return {"lab_id": None, "date": date.today().isoformat(), "attendance_time": "09:05",
            "details": "Reached early", **extra}


def _day(world, **extra):
    return _vt_attendance(lab_id=str(world["lab"].id), **extra)


def test_trainer_marks_attendance_at_the_school(client, world):
    _school_located(world)
    r = _save(client, "/api/attendance", _day(world))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["attendance_time"] == "09:05:00"
    assert body["distance_from_school_m"] == 0
    assert body["trainer_name"] == "VT"
    assert body["endorsement_status"] == "submitted"   # the Principal endorses it next
    assert body["school_id"] == str(world["school"].id)


def test_saved_records_cannot_be_deleted_by_anyone(client, world):
    _school_located(world)
    rid = _save(client, "/api/attendance", _day(world)).get_json()["id"]
    sa = User(full_name="SA", email="sa@x.com", role="SA")
    sa.set_password("Password@123")
    db.session.add(sa)
    db.session.commit()
    for email in ("vt@x.com", "sa@x.com"):
        r = client.delete(f"/api/attendance/{rid}", headers=_as(client, email))
        assert r.status_code == 403 and "can't be deleted" in r.get_json()["message"]
    assert client.get(f"/api/attendance/{rid}", headers=_login(client)).status_code == 200


def test_a_student_is_never_deleted_only_marked_as_left(client, world, principal):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    sid = str(world["students"][0].id)
    for email in ("vt@x.com", "pr@x.com", "oa@x.com"):
        r = client.delete(f"/api/students/{sid}", headers=_as(client, email))
        assert r.status_code == 403, email
    assert db.session.get(Student, sid).is_deleted is False
    # the way out is marking them as left - they stay on record
    r = client.post(f"/api/promotion/students/{sid}/status", headers=_as(client, "vt@x.com"),
                    json={"enrolment_status": "Dropped Out", "reason": "Family moved"})
    assert r.status_code == 200, r.get_json()
    assert client.get(f"/api/students/{sid}", headers=_as(client, "oa@x.com")).status_code == 200


def test_within_a_kilometre_is_fine(client, world):
    _school_located(world)
    r = _save(client, "/api/attendance", _day(world), **NEARBY)
    assert r.status_code == 201, r.get_json()
    assert 700 < r.get_json()["distance_from_school_m"] < 900


def test_too_far_from_the_school_is_refused(client, world):
    _school_located(world)
    r = _save(client, "/api/attendance", _day(world), **MUMBAI)
    assert r.status_code == 400
    assert "within 1.0 km" in r.get_json()["message"]


def test_school_must_have_a_location(client, world):
    r = _save(client, "/api/attendance", _day(world))
    assert r.status_code == 400
    assert "location hasn't been set up" in r.get_json()["message"]


def test_attendance_once_a_day_and_only_for_today(client, world):
    _school_located(world)
    assert _save(client, "/api/attendance", _day(world)).status_code == 201
    again = _save(client, "/api/attendance", _day(world))
    assert again.status_code == 400
    assert "already marked" in again.get_json()["message"]
    # (a day either side is allowed - the server runs on UTC)
    earlier = _save(client, "/api/attendance", _day(world, date=(date.today() - timedelta(days=3)).isoformat()))
    assert earlier.status_code == 400
    assert "only be marked for today" in earlier.get_json()["message"]
    # and a day in a year that has ended is refused as well
    assert _save(client, "/api/attendance", _day(world, date="2026-01-05")).status_code == 400


def test_attendance_needs_a_location(client, world):
    _school_located(world)
    r = _save(client, "/api/attendance", _day(world), fix=None)
    assert r.status_code == 400
    assert "Detect My Location" in r.get_json()["message"]


# --------------------------------------------------------- class attendance
def _class(world, **extra):
    return {"lab_id": str(world["lab"].id), "date": date.today().isoformat(), "time": "11:30",
            "class_grade": "9", "sections": "A,B", "activity": "Practical: typing speed drill",
            "comment": "Two computers down", **extra}


def test_class_attendance_with_students(client, world):
    _school_located(world)
    a, b, c = (str(s.id) for s in world["students"])
    marks = [{"student_id": a, "present": True}, {"student_id": b, "present": True},
             {"student_id": c, "present": False}]
    r = _save(client, "/api/class-attendance", _class(world, student_marks=marks))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["attended"] == "2 of 3"
    assert body["job_role_id"] == str(world["jr_low"].id)   # follows the class
    assert body["distance_from_school_m"] == 0
    assert body["time"] == "11:30:00"


@pytest.mark.parametrize("change, message", [
    ({"activity": " "}, "activity"),
    ({"class_grade": None}, "class"),
])
def test_class_attendance_required_answers(client, world, change, message):
    _school_located(world)
    r = _save(client, "/api/class-attendance", _class(world, **change))
    assert r.status_code == 400
    assert message in r.get_json()["message"]


def test_class_attendance_too_far_is_refused(client, world):
    _school_located(world)
    r = _save(client, "/api/class-attendance", _class(world), **MUMBAI)
    assert r.status_code == 400
    assert "within 1.0 km" in r.get_json()["message"]


# ---------------------------------------------------------- school location
def test_admin_sets_a_schools_location(client, world):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    sa = User(full_name="SA", email="sa@x.com", role="SA")
    sa.set_password("Password@123")
    db.session.add_all([oa, sa])
    db.session.commit()
    # an org admin gives the location when adding the school, and can't change a saved one
    oa_h = _login(client, email="oa@x.com")
    made = client.post("/api/schools", headers=oa_h, json={
        "name": "New School", "udise_code": "27999999999", "location_lat": 18.6, "location_lng": 73.9})
    assert made.status_code == 400 and "district" in made.get_json()["message"]
    made = client.post("/api/schools", headers=oa_h, json={
        "name": "New School", "udise_code": "27999999999", "district_id": str(world["school"].district_id),
        "school_type": "Co-education", "address": "Main Road",
        "location_lat": 18.6, "location_lng": 73.9})
    assert made.status_code == 201, made.get_json()
    assert (made.get_json()["location_lat"], made.get_json()["location_lng"]) == (18.6, 73.9)
    locked = client.patch(f"/api/schools/{made.get_json()['id']}", headers=oa_h, json={"phone": "020-1"})
    assert locked.status_code == 403 and "can't be edited" in locked.get_json()["message"]
    # the super admin only reads: they don't change it either
    h = _as(client, "sa@x.com")
    url = f"/api/schools/{world['school'].id}"
    assert client.patch(url, headers=h, json={"location_lat": 18.5204, "location_lng": 73.8567}).status_code == 403


# ------------------------------------------------------------- students etc.
def test_students_can_be_added_in_classes_9_to_12(client, world):
    h = _login(client)
    base = {"school_id": str(world["school"].id), "lab_id": str(world["lab"].id), "first_name": "Joiner"}
    assert client.post("/api/students", headers=h, json={**base, "class_grade": "10"}).status_code == 201
    r = client.post("/api/students", headers=h, json={**base, "class_grade": "8"})
    assert r.status_code == 400
    assert "Class must be 9, 10, 11 or 12" in r.get_json()["message"]


def _new_student(world):
    return {
        "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
        "class_grade": "9", "section": "A", "first_name": "New", "last_name": "Kid",
    }


def test_trainer_adds_students(client, world):
    r = client.post("/api/students", headers=_login(client), json=_new_student(world))
    assert r.status_code == 201, r.get_json()


# One login per test: the fixture's app context outlives each request, so the
# user cached on `g` would otherwise carry over from one login to the next.
@pytest.mark.parametrize("role", ["OA", "DM", "PR"])
def test_other_roles_only_view_students(client, world, role):
    """Students are registered by their trainer; other roles only view them."""
    u = User(organisation_id=world["org"].id, full_name=role, email=f"{role.lower()}@x.com",
             role=role, school_id=world["school"].id)
    u.set_password("Password@123")
    db.session.add(u)
    db.session.commit()

    h = _login(client, email=f"{role.lower()}@x.com")
    assert client.post("/api/students", headers=h, json=_new_student(world)).status_code == 403
    assert client.get("/api/students", headers=h).status_code == 200


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


def _trainer_body(world, **extra):
    return {"full_name": "A Trainer", "gender": "Female", "email": "a.trainer@x.com", "phone": "9876500001",
            "school_id": str(world["school"].id), "lab_id": str(world["lab"].id),
            "job_role_id": str(world["jr_low"].id), "date_of_joining": "2024-06-15", "vtp_name": "Skills Co", **extra}


def test_admin_form_needs_the_required_fields(client, world):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _login(client, "oa@x.com")
    r = client.post("/api/trainers", headers=h, json={"full_name": "Half Done", "school_id": str(world["school"].id)})
    assert r.status_code == 400
    assert r.get_json()["message"].startswith("Please fill in:") and "VTP" in r.get_json()["message"]
    # a district needs its state (the database insists - now with a message, not a crash)
    r = client.post("/api/districts", headers=h, json={"name": "No State"})
    assert r.status_code == 400 and "State" in r.get_json()["message"]
    # an org admin doesn't make logins in Users & Access (they come with the trainer / principal) ...
    r = client.post("/api/users", headers=h, json={"role": "VT", "full_name": "V", "email": "v@x.com", "password": "Password1"})
    assert r.status_code == 403
    # ... a district manager may, and a trainer's login needs its school and lab
    dm = User(organisation_id=world["org"].id, full_name="DM", email="dm@x.com", role="DM")
    dm.set_password("Password@123")
    db.session.add(dm)
    db.session.commit()
    r = client.post("/api/users", headers=_as(client, "dm@x.com"), json={
        "role": "VT", "full_name": "V", "email": "v@x.com", "password": "Password1"})
    assert r.status_code == 400 and "School" in r.get_json()["message"] and "Lab" in r.get_json()["message"]


def test_super_admin_reads_everything_and_adds_organisations(client, world, principal):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    sa = User(full_name="SA", email="sa@x.com", role="SA")
    for u in (oa, sa):
        u.set_password("Password@123")
    db.session.add_all([oa, sa])
    db.session.commit()
    h = _as(client, "sa@x.com")
    res = client.get("/api/meta/bootstrap", headers=h).get_json()["resources"]
    assert res["organisations"]["can_write"] is True
    assert not any(v["can_write"] for k, v in res.items() if k != "organisations")      # everything else: read only
    assert client.post("/api/equipment", headers=h, json=_equipment(world)).status_code == 403

    # a new organisation comes with its org admin's login (after the review, on screen)
    r = client.post("/api/organisations", headers=h, json={"name": "New Org", "org_code": "NEW-1",
                                                           "admin_full_name": "Asha Rao", "admin_email": "asha@new.org"})
    assert r.status_code == 201, r.get_json()
    login = r.get_json()["login"]
    assert login["username"] == "asha@new.org" and login["name"] == "Asha Rao"
    assert client.post("/api/auth/login", json={"email": "asha@new.org", "password": login["password"]}).status_code == 200
    assert client.post("/api/organisations", headers=_as(client, "sa@x.com"),
                       json={"name": "No Admin", "org_code": "NEW-2"}).status_code == 400

    # Users & Access: org admins only, and only their passwords reset
    h = _as(client, "sa@x.com")
    listed = client.get("/api/users", headers=h).get_json()
    assert {u["role"] for u in listed["data"]} == {"OA"} and listed["can_create"] == []
    assert client.patch(f"/api/users/{oa.id}", headers=h, json={"status": "disabled"}).status_code == 403
    vt = db.session.query(User).filter_by(email="vt@x.com").one()
    assert client.post(f"/api/users/{vt.id}/reset-password", headers=h, json={"new_password": "Newpass123"}).status_code == 403

    # what org admins do reaches the super admin's bell and audit log - not what others do
    _as(client, "vt@x.com")
    _endorsable(client, world, "daily")                                   # a trainer's work: not for them
    school = client.post("/api/schools", headers=_as(client, "oa@x.com"), json={
        "name": "Org Admin's School", "udise_code": "27111111111", "district_id": str(world["school"].district_id),
        "school_type": "Co-education", "address": "Main Road", "location_lat": 18.6, "location_lng": 73.9}).get_json()
    box = client.get("/api/me/notifications?page_size=50", headers=_as(client, "sa@x.com")).get_json()
    added = [n for n in box["data"] if "school" in n["title"]]
    assert added and f"_open={school['id']}" in added[0]["link"] and f"_org={world['org'].id}" in added[0]["link"]
    assert not any(n["category"] == "attendance" for n in box["data"])
    log = client.get("/api/admin/audit-logs", headers=_as(client, "sa@x.com")).get_json()["data"]
    assert log and all(r["actor_role"] == "OA" or r["entity"] == "app_user" for r in log)
    # ... and the one thing they do in Users & Access: reset an org admin's password
    r = client.post(f"/api/users/{oa.id}/reset-password", headers=_as(client, "sa@x.com"), json={"new_password": "Newpass123"})
    assert r.status_code == 200


def test_org_admin_sees_and_manages_only_their_schools_staff(client, world, principal, principal_record):
    org = world["org"]
    oa = User(organisation_id=org.id, full_name="OA", email="oa@x.com", role="OA")
    oa2 = User(organisation_id=org.id, full_name="OA Two", email="oa2@x.com", role="OA")
    for u in (oa, oa2):
        u.set_password("Password@123")
    db.session.add_all([oa, oa2])
    db.session.commit()
    h = _as(client, "oa@x.com")
    listed = client.get("/api/users", headers=h).get_json()
    assert sorted(u["role"] for u in listed["data"]) == ["PR", "VT"]      # no org admins, not even themselves
    assert listed["can_create"] == []
    # another org admin can't be touched; a trainer can only be disabled / enabled
    assert client.patch(f"/api/users/{oa2.id}", headers=h, json={"status": "disabled"}).status_code == 403
    vt = db.session.query(User).filter_by(email="vt@x.com").one()
    r = client.patch(f"/api/users/{vt.id}", headers=h, json={"status": "disabled", "full_name": "Renamed"})
    assert r.status_code == 200
    db.session.refresh(vt)
    assert (vt.status, vt.full_name) == ("disabled", "VT")
    # and they can see attendance but not verify it
    assert client.post("/api/auth/login", json={"email": "vt@x.com", "password": "Password@123"}).status_code == 403  # disabled
    vt.status = "active"
    db.session.commit()
    _as(client, "vt@x.com")
    url, rid = _endorsable(client, world, "daily")
    r = client.post(f"/api/workflow/attendance/{rid}/endorse", headers=_as(client, "oa@x.com"), json={"decision": "endorsed"})
    assert r.status_code == 403


def test_a_principal_sees_only_their_schools_principals(client, world, principal, principal_record):
    from app.models.geography import Principal, School
    other_school = School(organisation_id=world["org"].id, name="Other School", udise_code="27000000009",
                          district_id=world["school"].district_id)
    db.session.add(other_school)
    db.session.flush()
    db.session.add(Principal(organisation_id=world["org"].id, full_name="Someone Else", linked_school_id=other_school.id))
    db.session.commit()
    names = [p["full_name"] for p in client.get("/api/principals", headers=_as(client, "pr@x.com")).get_json()["data"]]
    assert names == ["PR"]


def test_one_trainer_per_job_role_in_a_lab(client, world):
    # an org admin adding a second trainer on the same slot is refused
    org = world["org"]
    oa = User(organisation_id=org.id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _login(client, "oa@x.com")
    r = client.post("/api/trainers", headers=h, json=_trainer_body(world, full_name="Second VT", email="second.vt@x.com"))
    assert r.status_code == 400
    assert "already holds this job role" in r.get_json()["message"]

    # the other slot is free
    ok = client.post("/api/trainers", headers=h, json=_trainer_body(
        world, full_name="Senior VT", email="senior.vt@x.com", job_role_id=str(world["jr_high"].id)))
    assert ok.status_code == 201, ok.get_json()


def test_admin_adds_a_trainer_with_their_profile(client, world):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _login(client, "oa@x.com")
    base = _trainer_body(world, full_name="New VT", job_role_id=str(world["jr_high"].id), phone="9876543210",
                         email="new.vt@x.com")
    general = {"father_name": "Ramesh", "dob": "1990-04-01", "gender": "Male", "aadhaar_number": "123412341234"}
    # a started section must be complete, and formats are checked
    r = client.post("/api/trainers", headers=h, json={**base, **general, "bank_name": "SBI"})
    assert r.status_code == 400 and "Please fill in" in r.get_json()["message"]
    r = client.post("/api/trainers", headers=h, json={**base, **general, "beneficiary_name": "New VT", "bank_name": "SBI",
                                                      "account_number": "123456789012", "ifsc_code": "BAD"})
    assert r.status_code == 400 and "IFSC" in r.get_json()["message"]
    r = client.post("/api/trainers", headers=h, json={
        **base, **general,
        "qualifications": [{"qualification": "Graduation", "course": "BCA", "institution": "Pune University",
                            "passing_year": 2012}, {"course": ""}],
    })
    assert r.status_code == 201, r.get_json()
    assert "aadhaar_number" not in r.get_json() and "father_name" not in r.get_json()   # never in the list row
    tid = r.get_json()["id"]
    # their login came with it: the email is the username, the password is shown this once
    login = r.get_json()["login"]
    assert login["username"] == "new.vt@x.com"
    signed_in = client.post("/api/auth/login", json={"email": login["username"], "password": login["password"]})
    assert signed_in.status_code == 200 and signed_in.get_json()["user"]["must_change_password"] is True
    assert "login" not in client.get(f"/api/trainers/{tid}", headers=h).get_json()
    # the same email can't make a second login
    again = client.post("/api/trainers", headers=h, json={**base, "trainer_status": "exited"})
    assert again.status_code == 400 and "already exists" in again.get_json()["message"]
    full = client.get(f"/api/trainers/{tid}", headers=h).get_json()
    assert full["father_name"] == "Ramesh" and full["aadhaar_number"] == "XXXXXXXX1234"
    assert [q["course"] for q in full["qualifications"]] == ["BCA"]            # the blank row is skipped
    # sending the masked number back keeps the real one
    assert client.patch(f"/api/trainers/{tid}", headers=h, json={"aadhaar_number": "XXXXXXXX1234"}).status_code == 200
    from app.models.lab import Trainer as T
    assert db.session.get(T, tid).aadhaar_number == "123412341234"


def test_lab_slot_rejects_a_job_role_from_the_wrong_band(client, world):
    org = world["org"]
    oa = User(organisation_id=org.id, full_name="OA2", email="oa2@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _login(client, "oa2@x.com")
    r = client.post("/api/labs", headers=h, json={
        "name": "Bad Lab", "school_id": str(world["school"].id), "sector_id": str(world["lab"].sector_id),
        "job_role_9_10_id": str(world["jr_high"].id), "job_role_11_12_id": str(world["jr_high"].id),
        "academic_year_of_setup": "2024-25",
    })
    assert r.status_code == 400
    assert "cannot fill the 9-10 slot" in r.get_json()["message"]


# ------------------------------------------------------------- lab equipment
def _other_trainer(world):
    t = Trainer(organisation_id=world["org"].id, full_name="Someone Else",
                school_id=world["school"].id, lab_id=world["lab"].id)
    db.session.add(t)
    db.session.commit()
    return t


def _equipment(world, **extra):
    return {"lab_id": str(world["lab"].id), "name": "Desktop computer",
            "receipt_date": date.today().isoformat(), **extra}


def test_trainer_owns_the_equipment_they_add(client, world):
    other = _other_trainer(world)
    h = _login(client)
    # even if another trainer is sent, a trainer's equipment is their own
    r = client.post("/api/equipment", headers=h, json=_equipment(world, trainer_id=str(other.id)))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["trainer_name"] == "VT"
    assert body["school_id"] == str(world["school"].id)  # follows the lab
    assert body["lab_name"] == world["lab"].name


def test_trainer_cannot_edit_a_saved_record(client, world):
    h = _login(client)
    eq = client.post("/api/equipment", headers=h, json=_equipment(world)).get_json()
    r = client.patch(f"/api/equipment/{eq['id']}", headers=h, json={"note": "Kept in cupboard 2"})
    assert r.status_code == 403
    assert "can't be edited" in r.get_json()["message"]
    boot = client.get("/api/meta/bootstrap", headers=h).get_json()
    assert boot["resources"]["equipment"]["can_edit"] is False


def test_equipment_needs_a_name_and_a_past_date(client, world):
    h = _login(client)
    assert client.post("/api/equipment", headers=h, json=_equipment(world, name="  ")).status_code == 400
    future = (date.today() + timedelta(days=5)).isoformat()
    r = client.post("/api/equipment", headers=h, json=_equipment(world, receipt_date=future))
    assert r.status_code == 400
    assert "future" in r.get_json()["message"]


def test_maintenance_log_entry(client, world):
    h = _login(client)
    eq = client.post("/api/equipment", headers=h, json=_equipment(world)).get_json()
    entry = {"equipment_id": eq["id"], "date": date.today().isoformat(),
             "issue": "Screen flickers", "maintenance_status": "Reported", "note": "Reported to vendor"}
    r = client.post("/api/equipment-maintenance", headers=h, json=entry)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["equipment_name"] == "Desktop computer"

    bad = client.post("/api/equipment-maintenance", headers=h, json={**entry, "maintenance_status": "lost"})
    assert bad.status_code == 400
    future = (date.today() + timedelta(days=5)).isoformat()
    assert client.post("/api/equipment-maintenance", headers=h, json={**entry, "date": future}).status_code == 400


# -------------------------------------------------------- location (sealed)
PUNE = {"lat": 18.5204, "lng": 73.8567, "accuracy": 12.5, "captured_at": "2026-09-25T09:30:00Z"}


def _sealed(client, h, **where):
    """A fix as the browser gets it: detected, then sealed by the server."""
    r = client.post("/api/location/seal", headers=h, json={**PUNE, **where})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _save(client, url, body, fix="seal", **where):
    """Post a form the way a trainer's browser does, with the sealed fix."""
    h = _login(client)
    if fix == "seal":
        fix = _sealed(client, h, **where)
    return client.post(url, headers=h, json={**body, **({"location_fix": fix} if fix else {})})


def test_seal_refuses_nonsense(client, world):
    h = _login(client)
    for bad in ({"lat": 95}, {"lng": "east"}, {"accuracy": -3}):
        r = client.post("/api/location/seal", headers=h, json={**PUNE, **bad})
        assert r.status_code == 400, bad


# ------------------------------------------------------------ guest lectures
def _lecture(world, **extra):
    return {"lab_id": str(world["lab"].id), "job_role_id": str(world["jr_low"].id),
            "class_grade": "9", "sections": "A,B", "reporting_date": date.today().isoformat(),
            "lecturer_name": "Dr. Meera Rao", "lecturer_qualification": "M.Tech",
            "lecturer_email": "meera@example.com", "lecturer_phone": "9800000000",
            "lecturer_experience": "8 years", "topic": "Networking basics", **extra}


def test_guest_lecture_with_only_the_simple_fields(client, world):
    r = _save(client, "/api/guest-lectures", _lecture(world))
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["school_id"] == str(world["school"].id)  # follows the lab


@pytest.mark.parametrize("change, message", [
    ({"lecturer_name": ""}, "lecturer's name"),
    ({"topic": " "}, "topic"),
    ({"class_grade": None}, "class"),
])
def test_guest_lecture_required_answers(client, world, change, message):
    r = _save(client, "/api/guest-lectures", _lecture(world, **change))
    assert r.status_code == 400
    assert message in r.get_json()["message"]


def test_guest_lecture_cannot_be_dated_in_the_future(client, world):
    future = (date.today() + timedelta(days=5)).isoformat()
    r = _save(client, "/api/guest-lectures", _lecture(world, reporting_date=future))
    assert r.status_code == 400


def test_guest_lecture_records_where_it_was_logged(client, world):
    from sqlalchemy import text
    r = _save(client, "/api/guest-lectures", _lecture(world))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert (body["location_lat"], body["location_lng"]) == (18.5204, 73.8567)
    assert body["location_accuracy_m"] == 12.5
    assert body["location_captured_at"].startswith("2026-09-25T09:30")
    # it is a real geographic point: PostGIS measures from it in metres
    metres = db.session.execute(text(
        "SELECT ST_Distance(location, ST_MakePoint(73.8567, 18.5304)::geography) "
        "FROM guest_lecture WHERE id = :id"), {"id": body["id"]}).scalar()
    assert 1100 < metres < 1120  # 0.01 degree of latitude is ~1.1 km


def test_trainer_must_share_location(client, world):
    r = _save(client, "/api/guest-lectures", _lecture(world), fix=None)
    assert r.status_code == 400
    assert "Detect My Location" in r.get_json()["message"]


@pytest.mark.parametrize("edit", [
    {"lat": 19.0760},                            # moved to Mumbai in dev tools
    {"accuracy": 3.0},                           # made to look more precise
    {"issued_at": "2099-01-01T00:00:00+00:00"},  # kept "fresh" forever
    {"sig": "0" * 64},
])
def test_an_edited_location_is_refused(client, world, edit):
    h = _login(client)
    fix = {**_sealed(client, h), **edit}
    r = client.post("/api/guest-lectures", headers=h, json={**_lecture(world), "location_fix": fix})
    assert r.status_code == 400
    assert "couldn't be verified" in r.get_json()["message"]


def test_someone_elses_location_is_refused(client, world, app):
    from app.services.location_seal import seal
    other = User(organisation_id=world["org"].id, full_name="Other", email="other@x.com", role="VT")
    other.set_password("Password@123")
    db.session.add(other)
    db.session.commit()
    with app.test_request_context():
        fix = seal(other.id, 18.5204, 73.8567, 12.5)
    r = _save(client, "/api/guest-lectures", _lecture(world), fix=fix)
    assert r.status_code == 400


def test_a_stale_location_is_refused(client, world, app, monkeypatch):
    from datetime import datetime, timezone
    from app.services import location_seal
    vt = db.session.query(User).filter_by(email="vt@x.com").one()
    long_ago = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(location_seal, "_now", lambda: long_ago)
    with app.test_request_context():
        fix = location_seal.seal(vt.id, 18.5204, 73.8567, 12.5)
    monkeypatch.undo()
    r = _save(client, "/api/guest-lectures", _lecture(world), fix=fix)
    assert r.status_code == 400
    assert "out of date" in r.get_json()["message"]


# -------------------------------------------------------------- field visits
def _visit(world, **extra):
    return {"lab_id": str(world["lab"].id), "job_role_id": str(world["jr_low"].id),
            "class_grade": "9", "sections": "A", "reporting_date": date.today().isoformat(),
            "organisation_name": "Tata Motors", "address": "Pimpri, Pune",
            "activities": "Assembly line walkthrough", "purpose": "See industrial automation",
            "contact_person": "R. Kulkarni", "contact_designation": "HR Manager",
            "contact_email": "hr@example.com", "contact_mobile": "9811111111", **extra}


def test_field_visit_with_only_the_simple_fields(client, world):
    r = _save(client, "/api/field-visits", _visit(world), lat=18.6298, lng=73.7997, accuracy=20)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["school_id"] == str(world["school"].id)  # follows the lab
    assert (body["location_lat"], body["location_lng"]) == (18.6298, 73.7997)


@pytest.mark.parametrize("change, message", [
    ({"organisation_name": "", "address": ""}, "organisation"),
    ({"job_role_id": None}, "job role"),
    ({"class_grade": None}, "class"),
])
def test_field_visit_required_answers(client, world, change, message):
    r = _save(client, "/api/field-visits", _visit(world, **change))
    assert r.status_code == 400
    assert message in r.get_json()["message"]


def test_field_visit_needs_a_location(client, world):
    r = _save(client, "/api/field-visits", _visit(world), fix=None)
    assert r.status_code == 400
    assert "Detect My Location" in r.get_json()["message"]


def test_field_visit_class_must_match_the_job_role(client, world):
    ok = _save(client, "/api/field-visits", _visit(world, job_role_id=str(world["jr_high"].id), class_grade="11"))
    assert ok.status_code == 201, ok.get_json()
    bad = _save(client, "/api/field-visits", _visit(world, class_grade="11"))
    assert bad.status_code == 400
    assert "not taught under this job role" in bad.get_json()["message"]


# ------------------------------------------------- who attended (Attend button)
@pytest.mark.parametrize("url, body", [("/api/guest-lectures", _lecture), ("/api/field-visits", _visit)])
def test_attendance_is_saved_and_read_back(client, world, url, body):
    a, b, c = (str(s.id) for s in world["students"])
    marks = [{"student_id": a, "present": True}, {"student_id": b, "present": False},
             {"student_id": c, "present": True}]
    r = _save(client, url, body(world, sections="A,B", student_marks=marks))
    assert r.status_code == 201, r.get_json()
    got = client.get(f"{url}/{r.get_json()['id']}", headers=_login(client)).get_json()
    attended = {m["student_id"] for m in got["student_marks"] if m["present"]}
    assert attended == {a, c}


@pytest.mark.parametrize("url, body", [("/api/guest-lectures", _lecture), ("/api/field-visits", _visit)])
def test_attendance_cannot_name_someone_elses_student(client, world, url, body):
    # same school, but not in this trainer's lab
    stranger = Student(organisation_id=world["org"].id, school_id=world["school"].id,
                       first_name="Not", last_name="Yours", class_grade="9")
    db.session.add(stranger)
    db.session.commit()
    marks = [{"student_id": str(stranger.id), "present": True}]
    r = _save(client, url, body(world, student_marks=marks))
    assert r.status_code == 400
    assert "outside your classes" in r.get_json()["message"]


# -------------------------------------------------------------------- issues
def _issue(world, **extra):
    return {"lab_id": str(world["lab"].id), "reporting_date": date.today().isoformat(),
            "reporting_time": "10:45", "details": "Two computers won't start", **extra}


def test_issue_with_date_time_location_and_text(client, world, app):
    r = _save(client, "/api/issues", _issue(world))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["reporting_time"] == "10:45:00"
    assert (body["location_lat"], body["location_lng"]) == (18.5204, 73.8567)
    assert body["workflow_status"] == "open"
    # filed as the trainer themselves
    tr = db.session.query(Trainer).filter_by(full_name="VT").one()
    assert body["trainer_id"] == str(tr.id)


@pytest.mark.parametrize("change, message", [
    ({"details": "  "}, "Describe the issue"),
    ({"reporting_date": (date.today() + timedelta(days=5)).isoformat()}, "future"),
])
def test_issue_required_answers(client, world, change, message):
    r = _save(client, "/api/issues", _issue(world, **change))
    assert r.status_code == 400
    assert message in r.get_json()["message"]


def test_issue_needs_a_location(client, world):
    r = _save(client, "/api/issues", _issue(world), fix=None)
    assert r.status_code == 400
    assert "Detect My Location" in r.get_json()["message"]


# ------------------------------------------- academic year + yearly targets
@pytest.mark.parametrize("on, year", [
    ("2024-08-01", "Custom 2024"),   # inside a year the organisation set up
    ("2025-09-10", "2025-26"),       # none set up: June-May school year
    ("2026-02-10", "2025-26"),
    ("2026-06-01", "2026-27"),
])
def test_year_follows_the_date(client, world, on, year, monkeypatch):
    # (these dates are in years that have ended - open them for this test)
    monkeypatch.setattr("app.services.academic_year.current_year_label", lambda *a, **k: "2000-01")
    db.session.add(AcademicYear(organisation_id=world["org"].id, label="Custom 2024",
                                start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)))
    db.session.commit()
    # even a client that sends the "current" year gets the date's own year
    r = _save(client, "/api/guest-lectures", _lecture(world, reporting_date=on, academic_year="2025-26"))
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["academic_year"] == year


def test_field_visit_targets_per_level(client, world, monkeypatch):
    # (2025-26 has ended - open it for this test)
    monkeypatch.setattr("app.services.academic_year.current_year_label", lambda *a, **k: "2000-01")
    for cls, when in (("9", "2025-08-01"), ("9", "2025-11-12"), ("10", "2025-12-01")):
        r = _save(client, "/api/field-visits", _visit(world, class_grade=cls, reporting_date=when))
        assert r.status_code == 201, r.get_json()
    h = _login(client)

    body = client.get("/api/targets/field-visits?academic_year=2025-26", headers=h).get_json()
    assert body["target"] == 2
    by_class = {row["class_grade"]: row for row in body["rows"]}
    assert set(by_class) == {"9", "10", "11", "12"}   # the lab runs both slots
    assert (by_class["9"]["count"], by_class["9"]["met"], by_class["9"]["level"]) == (2, True, 1)
    assert (by_class["10"]["count"], by_class["10"]["remaining"]) == (1, 1)
    assert by_class["11"]["count"] == 0

    met = client.get("/api/targets/field-visits?academic_year=2025-26&status=met", headers=h).get_json()
    assert [row["class_grade"] for row in met["rows"]] == ["9"]
    not_met = client.get("/api/targets/field-visits?academic_year=2025-26&status=not_met", headers=h).get_json()
    assert sorted(row["class_grade"] for row in not_met["rows"]) == ["10", "11", "12"]
    # another year starts from nothing
    other = client.get("/api/targets/field-visits?academic_year=2024-25", headers=h).get_json()
    assert all(row["count"] == 0 for row in other["rows"])


def test_guest_lecture_target_is_fifteen(client, world):
    body = client.get("/api/targets/guest-lectures", headers=_login(client)).get_json()
    assert body["target"] == 15
    assert body["academic_year"] == body["current_year"]
    assert "2025-26" in body["years"]


# ------------------------------------------------------ promotion + status
def _class_of(world, year="2024-25", grade="9", verified=(True, True, True)):
    for s, v in zip(world["students"], verified):
        s.academic_year, s.class_grade = year, grade
        s.verification_status = "verified" if v else "pending"
    db.session.commit()
    return [str(s.id) for s in world["students"]]


def test_moving_up_into_class_11_needs_verifying_again(client, world):
    a, b, c = _class_of(world, grade="10")
    r = client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2024-25", "class_grade": "10", "promote": [a, b], "hold_back": [c]})
    assert r.status_code == 200, r.get_json()
    moved, held = db.session.get(Student, a), db.session.get(Student, c)
    assert (moved.class_grade, moved.verification_status) == ("11", "pending")   # verified again at Class 11
    assert held.verification_status == "verified"                                # still in Class 10


def test_previous_students_join_class_11(client, world):
    from app.services.academic_year import academic_year_for
    this_year = academic_year_for(world["org"].id, date.today())
    a, b, c = world["students"]
    for s, (status, year) in zip((a, b, c), (("Completed", "2024-25"), ("Studying", "2023-24"), ("Studying", this_year))):
        s.class_grade, s.enrolment_status, s.academic_year, s.verification_status = "10", status, year, "verified"
    db.session.commit()
    h = _login(client)
    listed = client.get(f"/api/students/previous?lab_id={world['lab'].id}", headers=h).get_json()["data"]
    assert sorted(x["id"] for x in listed) == sorted([str(a.id), str(b.id)])   # not the one in Class 10 now
    r = client.post("/api/students/previous", headers=h, json={
        "lab_id": str(world["lab"].id), "section": "A", "student_ids": [str(a.id), str(b.id)]})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["added"] == 2 and all(x["roll_number"].startswith("11A-") for x in r.get_json()["students"])
    s = db.session.get(Student, a.id)
    assert (s.class_grade, s.enrolment_status, s.verification_status, s.academic_year) == ("11", "Studying", "pending", this_year)
    # their Class 10 year is kept in the history
    hist = client.get(f"/api/promotion/history/{a.id}", headers=h).get_json()
    assert "Joined Class 11" in str(hist)
    # someone still in Class 10 this year can't be pulled in this way
    bad = client.post("/api/students/previous", headers=h, json={
        "lab_id": str(world["lab"].id), "section": "A", "student_ids": [str(c.id)]})
    assert bad.status_code == 400


def test_only_an_admin_verifies_a_student(client, world):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    sid = str(world["students"][0].id)
    url = f"/api/workflow/students/{sid}/verify"
    # the trainer adds students but doesn't verify them - neither directly nor by editing
    assert client.post(url, headers=_as(client, "vt@x.com"), json={"verification_status": "verified"}).status_code == 403
    client.patch(f"/api/students/{sid}", headers=_as(client, "vt@x.com"), json={"verification_status": "verified"})
    assert db.session.get(Student, sid).verification_status == "pending"
    r = client.post(url, headers=_as(client, "oa@x.com"), json={"verification_status": "verified"})
    assert r.status_code == 200, r.get_json()
    assert db.session.get(Student, sid).verification_status == "verified"


def test_promotion_preview(client, world):
    a, b, c = _class_of(world, verified=(True, True, False))
    body = client.get("/api/promotion/preview?from_year=2024-25&class_grade=9", headers=_login(client)).get_json()
    assert body["ended"] and body["to_year"] == "2025-26"
    rows = {r["id"]: r for r in body["students"]}
    assert rows[a]["to_class"] == "10" and rows[a]["eligible"]
    assert not rows[c]["eligible"] and "Verify" in rows[c]["reason"]


def test_promote_and_hold_back(client, world):
    from app.models.student import StudentPromotion
    a, b, c = _class_of(world)
    r = client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2024-25", "class_grade": "9", "promote": [a, b], "hold_back": [c]})
    assert r.status_code == 200, r.get_json()
    assert (r.get_json()["promoted"], r.get_json()["held_back"]) == (2, 1)
    s_a, s_c = (db.session.get(Student, x) for x in (a, c))
    assert (s_a.class_grade, s_a.academic_year) == ("10", "2025-26")
    assert (s_c.class_grade, s_c.academic_year) == ("9", "2025-26")      # repeats Class 9
    outcomes = {str(p.student_id): p.outcome for p in db.session.query(StudentPromotion)}
    assert outcomes == {a: "Promoted", b: "Promoted", c: "Held Back"}
    # the same class can't be promoted twice
    again = client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2024-25", "class_grade": "9", "promote": [a]})
    assert again.status_code == 400


def test_class_12_completes_the_course(client, world):
    a, b, c = _class_of(world, grade="12")
    r = client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2024-25", "class_grade": "12", "promote": [a]})
    assert r.get_json()["completed"] == 1
    s = db.session.get(Student, a)
    assert (s.enrolment_status, s.class_grade) == ("Completed", "12")
    # a finished student drops out of class rosters
    roster = client.get("/api/students?enrolment_status=Studying&class_grade=12", headers=_login(client)).get_json()
    assert a not in {row["id"] for row in roster["data"]}


def test_promotion_waits_for_the_year_to_end(client, world):
    a, b, c = _class_of(world, year="2026-27")
    r = client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2026-27", "class_grade": "9", "promote": [a]})
    assert r.status_code == 400
    assert "once 2026-27 has ended" in r.get_json()["message"]


def test_unverified_students_are_not_promoted(client, world):
    a, b, c = _class_of(world, verified=(True, True, False))
    r = client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2024-25", "class_grade": "9", "promote": [a, c]})
    assert r.status_code == 400
    assert "Verify these students first" in r.get_json()["message"]


def _this_year(world):
    from app.services.academic_year import academic_year_for
    return academic_year_for(world["org"].id, date.today())


def test_trainer_cannot_change_class_by_editing(client, world):
    a, b, c = _class_of(world, year=_this_year(world))
    r = client.patch(f"/api/students/{a}", headers=_login(client), json={"class_grade": "10"})
    assert r.status_code == 400
    assert "Promote Students" in r.get_json()["message"]


def test_a_closed_academic_year_cannot_be_changed(client, world, principal):
    """Records of a year that has ended are read-only for trainers,
    principals and org admins - only the super admin may correct them."""
    a, b, c = _class_of(world)                     # 2024-25: over
    h = _as(client, "vt@x.com")
    r = client.patch(f"/api/students/{a}", headers=h, json={"father_name": "Someone"})
    assert r.status_code == 403 and "previous academic year (2024-25)" in r.get_json()["message"]
    assert client.post(f"/api/promotion/students/{a}/status", headers=h,
                       json={"enrolment_status": "Dropped Out", "reason": "x"}).status_code == 403
    row = next(x for x in client.get("/api/students", headers=h).get_json()["data"] if x["id"] == a)
    assert row["past_year"] is True
    # nothing new dated in a closed year, either
    _school_located(world)
    r = _save(client, "/api/guest-lectures", _lecture(world, reporting_date="2025-01-10"))
    assert r.status_code == 400 and "previous academic year" in r.get_json()["message"]
    # promotion still moves them on - that's how a year closes
    r = client.post("/api/promotion", headers=_as(client, "vt@x.com"), json={
        "from_year": "2024-25", "class_grade": "9", "promote": [a, b, c]})
    assert r.status_code == 200, r.get_json()
    # the rule itself: closed for everyone but the super admin
    from werkzeug.exceptions import Forbidden
    from app.services.academic_year import guard_closed_year
    old = db.session.get(Student, b)
    old.academic_year = "2024-25"
    guard_closed_year(old, User(role="SA"))               # no objection
    for role in ("OA", "PR", "VT"):
        with pytest.raises(Forbidden):
            guard_closed_year(old, User(role=role))
    db.session.rollback()


def test_a_student_leaves_in_three_steps(client, world, principal, principal_record):
    """Trainer marks as leaving -> principal records the TC -> org admin confirms."""
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    a, b, c = _class_of(world, year=_this_year(world))
    url = f"/api/promotion/students/{a}/status"
    h = _as(client, "vt@x.com")
    assert client.post(url, headers=h, json={"enrolment_status": "Dropped Out"}).status_code == 400  # needs a reason
    # 1. the trainer marks them as leaving - they're still on the list until it's confirmed
    r = client.post(url, headers=h, json={"enrolment_status": "Dropped Out", "reason": "Family moved"})
    assert r.status_code == 200, r.get_json()
    s = db.session.get(Student, a)
    assert (s.enrolment_status, s.leaving_stage, s.leaving_type) == ("Studying", "requested", "Dropped Out")
    assert client.post(url, headers=h, json={"enrolment_status": "Dropped Out", "reason": "x"}).status_code == 400
    assert client.post(url, headers=h, json={"enrolment_status": "Studying"}).status_code == 400    # no rejoining
    box = _mine(client, "pr@x.com")
    assert box["unread"] == 1 and "TC needed" in box["data"][0]["title"]
    # the org admin can't skip the principal's TC
    assert client.post(f"/api/promotion/students/{a}/left", headers=_as(client, "oa@x.com")).status_code == 400
    # 2. the principal records the TC (a photo is required)
    tc = f"/api/promotion/students/{a}/tc"
    assert client.post(tc, headers=_as(client, "vt@x.com"), json={"tc_url": "uploads/tc.jpg"}).status_code == 403
    assert client.post(tc, headers=_as(client, "pr@x.com"), json={"tc_number": "TC/1"}).status_code == 400
    r = client.post(tc, headers=_as(client, "pr@x.com"), json={"tc_url": "uploads/tc.jpg", "tc_number": "TC/1"})
    assert r.status_code == 200, r.get_json()
    assert any("TC to verify" in n["title"] for n in _mine(client, "oa@x.com")["data"])
    # 3. the org admin checks it and confirms - now they've left, for good
    r = client.post(f"/api/promotion/students/{a}/left", headers=_as(client, "oa@x.com"))
    assert r.status_code == 200, r.get_json()
    s = db.session.get(Student, a)
    assert (s.enrolment_status, s.leaving_stage, s.tc_number) == ("Dropped Out", "left", "TC/1")
    # every step is in their history
    hist = client.get(f"/api/promotion/history/{a}", headers=_as(client, "oa@x.com")).get_json()
    assert [y["outcome"] for y in hist["years"]][:3] == ["Dropped Out", "TC issued", "Marked as leaving"]
    assert hist["current"]["tc_number"] == "TC/1" and hist["current"]["tc_verified_on"]   # the TC, in their history
    row = client.get(f"/api/students/{a}", headers=_as(client, "oa@x.com")).get_json()
    assert row["status_label"] == "Left"


def test_a_leaving_student_is_not_promoted(client, world):
    a, b, c = _class_of(world)
    s = db.session.get(Student, a)                # marked as leaving before the year ended
    s.leaving_stage, s.leaving_type = "requested", "Transferred Out"
    db.session.commit()
    rows = {r["id"]: r for r in client.get("/api/promotion/preview?from_year=2024-25&class_grade=9",
                                          headers=_login(client)).get_json()["students"]}
    assert not rows[a]["eligible"] and rows[a]["reason"] == "Leaving the school"


# --------------------------------------------------------------- redis cache
@pytest.fixture
def cache_on(app):
    """The real Redis cache, under a prefix of its own."""
    import uuid
    app.config.update(CACHE_ENABLED=True, CACHE_PREFIX=f"rnaf-test-{uuid.uuid4().hex[:8]}")
    yield
    app.config["CACHE_ENABLED"] = False


def test_reads_are_cached_until_something_changes(client, world, cache_on):
    h = _login(client)
    first = client.get("/api/equipment", headers=h)
    assert first.headers["X-Cache"] == "MISS"
    again = client.get("/api/equipment", headers=h)
    assert again.headers["X-Cache"] == "HIT"
    assert again.get_json() == first.get_json()

    # a write in the organisation makes the next read fresh - and complete
    made = client.post("/api/equipment", headers=h, json={
        "lab_id": str(world["lab"].id), "name": "Projector", "receipt_date": date.today().isoformat()})
    assert made.status_code == 201
    after = client.get("/api/equipment", headers=h)
    assert after.headers["X-Cache"] == "MISS"
    assert [r["name"] for r in after.get_json()["data"]] == ["Projector"]


def test_bootstrap_and_dashboards_are_cached(client, world, cache_on):
    h = _login(client)
    for url in ("/api/meta/bootstrap", "/api/dashboard/summary", "/api/targets/guest-lectures"):
        assert client.get(url, headers=h).headers["X-Cache"] == "MISS", url
        assert client.get(url, headers=h).headers["X-Cache"] == "HIT", url


def test_app_works_when_redis_is_down(client, world, cache_on, app):
    app.config["CACHE_REDIS_URL"] = "redis://localhost:1/0"   # nothing listens there
    try:
        r = client.get("/api/equipment", headers=_login(client))
        assert r.status_code == 200
        assert "X-Cache" not in r.headers
    finally:
        app.config.pop("CACHE_REDIS_URL")


# -------------------------------------------------- filtering by one section
def test_section_filter_on_multi_section_records(client, world):
    for sections, topic in (("A,B", "Both"), ("B", "Only B"), ("A", "Only A")):
        r = _save(client, "/api/guest-lectures", _lecture(world, sections=sections, topic=topic))
        assert r.status_code == 201, r.get_json()
    h = _login(client)
    topics = lambda q: sorted(x["topic"] for x in client.get(f"/api/guest-lectures?{q}", headers=h).get_json()["data"])
    assert topics("section=B") == ["Both", "Only B"]
    assert topics("section=A") == ["Both", "Only A"]
    assert topics("section=A,B") == ["Both", "Only A", "Only B"]
    assert topics("section=C") == []


# ---------------------------------------------------------------- my profile
GENERAL = {"full_name": "VT", "father_name": "Ramesh Kumar", "dob": "1990-05-14", "gender": "Female",
           "phone": "9876543210", "email": "vt@example.com", "aadhaar_number": "123412341234"}


def test_profile_general_section_must_be_complete(client, world):
    h = _login(client)
    r = client.patch("/api/profile", headers=h, json={"father_name": "Ramesh Kumar"})
    assert r.status_code == 400
    assert "Please fill in" in r.get_json()["message"] and "Aadhaar" in r.get_json()["message"]
    ok = client.patch("/api/profile", headers=h, json=GENERAL)
    assert ok.status_code == 200, ok.get_json()
    body = ok.get_json()
    assert body["aadhaar_number"] == "XXXXXXXX1234"            # never sent back whole
    assert {"father_name", "dob", "gender", "aadhaar_number"} <= set(body["locked"])


def test_locked_details_cannot_be_changed_but_others_can(client, world):
    h = _login(client)
    assert client.patch("/api/profile", headers=h, json=GENERAL).status_code == 200
    r = client.patch("/api/profile", headers=h, json={**GENERAL, "dob": "1991-01-01"})
    assert r.status_code == 400 and "can't be changed" in r.get_json()["message"]
    # re-saving the section as the page shows it (Aadhaar masked) is fine
    same = {**GENERAL, "aadhaar_number": "XXXXXXXX1234", "phone": "9123456789", "blood_group": "O+"}
    r = client.patch("/api/profile", headers=h, json=same)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["phone"] == "9123456789"


@pytest.mark.parametrize("field, value", [
    ("aadhaar_number", "1234"), ("phone", "12345"), ("email", "not-an-email"), ("blood_group", "Z+"),
])
def test_profile_formats_are_checked(client, world, field, value):
    r = client.patch("/api/profile", headers=_login(client), json={**GENERAL, field: value})
    assert r.status_code == 400


def test_bank_section(client, world):
    h = _login(client)
    bank = {"beneficiary_name": "VT", "bank_name": "Demo Bank", "account_number": "123456789012",
            "ifsc_code": "demo0123456", "gross_salary": 25000, "deduction_epf": 1800, "pan_number": "abcde1234f"}
    assert client.patch("/api/profile", headers=h, json={**bank, "ifsc_code": "BAD"}).status_code == 400
    r = client.patch("/api/profile", headers=h, json=bank)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert (body["account_number"], body["pan_number"], body["ifsc_code"]) == ("XXXXXXXX9012", "XXXXXX234F", "DEMO0123456")
    assert body["net_salary"] == 23200


def test_profile_lists_and_total_experience(client, world):
    h = _login(client)
    bad = client.patch("/api/profile", headers=h, json={"experiences": [
        {"organisation_name": "Old Co", "date_of_joining": "2015-01-01", "date_of_resignation": "2014-01-01"}]})
    assert bad.status_code == 400
    r = client.patch("/api/profile", headers=h, json={
        "experiences": [{"organisation_name": "Old Co", "date_of_joining": "2015-01-01",
                         "date_of_resignation": "2017-01-01", "job_type": "Full Time"}],
        "qualifications": [{"qualification": "Graduation", "course": "B.Tech", "passing_year": 2012}, {}],
    })
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert [q["course"] for q in body["qualifications"]] == ["B.Tech"]   # the blank row is dropped
    assert body["total_experience_years"] == 2.0                          # no joining date on record yet


def test_a_photo_can_be_added_before_the_rest(client, world):
    r = client.patch("/api/profile", headers=_login(client), json={"photo_url": "uploads/abc/me.png"})
    assert r.status_code == 200, r.get_json()


def test_personal_details_stay_off_the_trainer_list(client, world):
    h = _login(client)
    client.patch("/api/profile", headers=h, json=GENERAL)
    rows = client.get("/api/trainers", headers=h).get_json()["data"]
    assert rows and all("aadhaar_number" not in r and "dob" not in r and "account_number" not in r for r in rows)


def test_only_trainers_have_a_profile(client, world):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa2@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    assert client.get("/api/profile", headers=_login(client, email="oa2@x.com")).status_code == 404


# ------------------------------------------------------ principal endorsement
def _as(client, email):
    """Switch who is logged in. (The fixture's app context outlives each
    request, so the user cached on `g` must be dropped between logins.)"""
    from flask import g
    g.pop("current_user", None)
    return _login(client, email=email)


@pytest.fixture
def principal(world):
    pr = User(organisation_id=world["org"].id, full_name="PR", email="pr@x.com", role="PR",
              school_id=world["school"].id)
    pr.set_password("Password@123")
    db.session.add(pr)
    db.session.commit()
    return pr


def _endorsable(client, world, kind):
    _school_located(world)
    url, body = ("/api/class-attendance", _class(world)) if kind == "class" else ("/api/attendance", _day(world))
    r = _save(client, url, body)
    assert r.status_code == 201, r.get_json()
    return url, r.get_json()["id"]


@pytest.mark.parametrize("kind", ["class", "daily"])
def test_principal_endorses_and_it_becomes_final(client, world, principal, kind):
    url, rid = _endorsable(client, world, kind)
    route = "class-attendance" if kind == "class" else "attendance"
    h_pr = _as(client, "pr@x.com")
    r = client.post(f"/api/workflow/{route}/{rid}/endorse", headers=h_pr, json={"decision": "endorsed"})
    assert r.status_code == 200, r.get_json()
    h_vt = _as(client, "vt@x.com")
    edit = client.patch(f"{url}/{rid}", headers=h_vt, json={"comment": "late change", "details": "late change"})
    assert edit.status_code == 403


def test_attendance_can_only_be_verified(client, world, principal):
    url, rid = _endorsable(client, world, "class")
    h_pr = _as(client, "pr@x.com")
    r = client.post(f"/api/workflow/class-attendance/{rid}/endorse", headers=h_pr,
                    json={"decision": "returned", "remarks": "Wrong section"})
    assert r.status_code == 400
    ok = client.post(f"/api/workflow/class-attendance/{rid}/endorse", headers=h_pr, json={"decision": "endorsed"})
    assert ok.get_json()["endorsement_status"] == "endorsed"
    # verifying twice is refused, so the first verifier and time are kept
    again = client.post(f"/api/workflow/class-attendance/{rid}/endorse", headers=h_pr, json={"decision": "endorsed"})
    assert again.status_code == 409


def test_trainer_cannot_endorse(client, world, principal):
    url, rid = _endorsable(client, world, "class")
    r = client.post(f"/api/workflow/class-attendance/{rid}/endorse", headers=_as(client, "vt@x.com"),
                    json={"decision": "endorsed"})
    assert r.status_code == 403


def test_principal_is_read_only_otherwise(client, world, principal):
    h = _as(client, "pr@x.com")
    assert client.get("/api/students", headers=h).status_code == 200
    assert client.get("/api/feedback", headers=h).status_code == 200
    assert client.post("/api/feedback", headers=h, json={"subject": "x", "school_id": str(world["school"].id)}).status_code == 403
    assert client.post("/api/guest-lectures", headers=h, json={}).status_code == 403
    cards = [c["key"] for c in client.get("/api/dashboard/summary", headers=h).get_json()["cards"]]
    assert cards[:2] == ["pending_endorsement", "class_pending_endorsement"]


# ---------------------------------------------------------- principal profile
@pytest.fixture
def principal_record(world, principal):
    from app.models.geography import Principal
    rec = Principal(organisation_id=world["org"].id, full_name="PR", email="pr@x.com",
                    linked_school_id=world["school"].id, user_id=principal.id,
                    designation="Principal", employee_id="EMP-1", date_of_joining=date(2021, 6, 15))
    db.session.add(rec)
    db.session.commit()
    return rec


PR_GENERAL = {"full_name": "PR", "designation": "Principal", "dob": "1975-03-10", "gender": "Male",
              "mobile": "9876501234", "email": "pr@example.com", "father_name": "S. Rao"}


def _mine(client, email):
    return client.get("/api/me/notifications?page_size=50", headers=_as(client, email)).get_json()


def test_notifications_reach_the_right_people(client, world, principal, principal_record):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()

    # the trainer marks attendance -> the principal is asked to verify it
    _as(client, "vt@x.com")
    url, rid = _endorsable(client, world, "daily")
    pr_box = _mine(client, "pr@x.com")
    assert pr_box["unread"] == 1 and pr_box["data"][0]["category"] == "attendance"
    assert "endorsement_status=submitted" in pr_box["data"][0]["link"]
    assert _mine(client, "vt@x.com")["unread"] == 0                 # nobody hears about their own action
    # ... verifies it -> the trainer hears
    client.post(f"/api/workflow/attendance/{rid}/endorse", headers=_as(client, "pr@x.com"), json={"decision": "endorsed"})
    vt_box = _mine(client, "vt@x.com")
    assert vt_box["unread"] == 1 and vt_box["data"][0]["title"] == "Attendance verified"

    # the principal raises an issue -> org admins; resolved -> the principal
    issue = client.post("/api/principal-issues", headers=_as(client, "pr@x.com"), json={
        "reporting_date": date.today().isoformat(), "details": "Roof leaks"}).get_json()
    oa_box = _mine(client, "oa@x.com")
    assert any(n["category"] == "issue" and f"_school={world['school'].id}" in n["link"] for n in oa_box["data"])
    r = client.post(f"/api/workflow/principal-issues/{issue['id']}/transition", headers=_as(client, "oa@x.com"),
                    json={"workflow_status": "resolved", "resolution_note": "Roof fixed"})
    assert r.status_code == 200, r.get_json()
    assert any(n["title"] == "Your issue has been resolved" for n in _mine(client, "pr@x.com")["data"])

    # equipment and its upkeep: org admins hear of both; the trainer hears of status changes
    eq = client.post("/api/equipment", headers=_as(client, "vt@x.com"), json=_equipment(world)).get_json()
    m = client.post("/api/equipment-maintenance", headers=_as(client, "vt@x.com"), json={
        "equipment_id": eq["id"], "date": date.today().isoformat(), "issue": "Won't start",
        "maintenance_status": "Reported"}).get_json()
    cats = [n["category"] for n in _mine(client, "oa@x.com")["data"]]
    assert "equipment" in cats and "maintenance" in cats
    client.post(f"/api/workflow/equipment-maintenance/{m['id']}/status", headers=_as(client, "oa@x.com"),
                json={"maintenance_status": "Under Repair"})
    assert any(n["category"] == "maintenance" and "Under Repair" in n["title"] for n in _mine(client, "vt@x.com")["data"])

    # reading them
    box = _mine(client, "oa@x.com")
    client.post(f"/api/me/notifications/{box['data'][0]['id']}/read", headers=_as(client, "oa@x.com"))
    assert _mine(client, "oa@x.com")["unread"] == box["unread"] - 1
    client.post("/api/me/notifications/read-all", headers=_as(client, "oa@x.com"))
    assert _mine(client, "oa@x.com")["unread"] == 0
    # nobody can mark someone else's
    other = _mine(client, "vt@x.com")["data"][0]["id"]
    assert client.post(f"/api/me/notifications/{other}/read", headers=_as(client, "oa@x.com")).status_code == 404


def test_org_admin_adds_only_master_data(client, world):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    h = _as(client, "oa@x.com")
    res = client.get("/api/meta/bootstrap", headers=h).get_json()["resources"]
    for view_only in ("attendance", "class-attendance", "issues", "field-visits", "guest-lectures",
                      "equipment", "equipment-maintenance", "assessments", "ojt-placements"):
        assert res[view_only]["can_write"] is False, view_only
    for master in ("schools", "labs", "trainers", "principals", "districts", "job-roles"):
        assert res[master]["can_write"] is True, master
    assert client.post("/api/equipment", headers=h, json=_equipment(world)).status_code == 403


def test_org_admin_resolves_issues_and_maintenance(client, world):
    from app.models.operations import VTIssue
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    vt = db.session.query(User).filter_by(email="vt@x.com").one()
    issue = VTIssue(organisation_id=world["org"].id, lab_id=world["lab"].id, reporting_date=date.today(),
                    details="Projector cable missing", created_by=vt.id)
    db.session.add(issue)
    db.session.commit()
    h = _as(client, "oa@x.com")
    row = next(r for r in client.get("/api/issues", headers=h).get_json()["data"] if r["id"] == str(issue.id))
    assert row["trainer_name"] == "VT" and row["school_name"] == world["school"].name      # filled in on the form
    url = f"/api/workflow/issues/{issue.id}/transition"
    assert client.post(url, headers=h, json={"workflow_status": "resolved"}).status_code == 400   # needs a resolution
    r = client.post(url, headers=h, json={"workflow_status": "resolved", "resolution_note": "New cable fitted"})
    assert r.status_code == 200, r.get_json()
    assert any(n["title"] == "Your issue has been resolved" for n in _mine(client, "vt@x.com")["data"])

    eq = client.post("/api/equipment", headers=_as(client, "vt@x.com"), json=_equipment(world)).get_json()
    m = client.post("/api/equipment-maintenance", headers=_as(client, "vt@x.com"), json={
        "equipment_id": eq["id"], "date": date.today().isoformat(), "issue": "No display",
        "maintenance_status": "Reported"}).get_json()
    murl = f"/api/workflow/equipment-maintenance/{m['id']}/status"
    h = _as(client, "oa@x.com")
    assert client.post(murl, headers=h, json={"maintenance_status": "Resolved"}).status_code == 400
    r = client.post(murl, headers=h, json={"maintenance_status": "Resolved", "resolution": "Vendor replaced the board"})
    assert r.status_code == 200, r.get_json()
    listed = next(x for x in client.get("/api/equipment-maintenance", headers=h).get_json()["data"] if x["id"] == m["id"])
    assert (listed["maintenance_status"], listed["action"], listed["equipment_name"]) == ("Resolved", "Vendor replaced the board", "Desktop computer")
    assert any("Resolved" in n["title"] for n in _mine(client, "vt@x.com")["data"])
    # and back to open if it wasn't
    assert client.post(murl, headers=_as(client, "oa@x.com"), json={"maintenance_status": "Open"}).get_json()["maintenance_status"] == "Reported"


def test_a_trainer_editing_a_verified_student_sends_them_back(client, world, category):
    oa = User(organisation_id=world["org"].id, full_name="OA", email="oa@x.com", role="OA")
    oa.set_password("Password@123")
    db.session.add(oa)
    db.session.commit()
    kid = _bulk(client, world, [_kid(category, 21)]).get_json()["students"][0]["id"]
    assert any(n["category"] == "verification" for n in _mine(client, "oa@x.com")["data"])   # new student to verify
    client.post(f"/api/workflow/students/{kid}/verify", headers=_as(client, "oa@x.com"), json={"verification_status": "verified"})
    client.post("/api/me/notifications/read-all", headers=_as(client, "oa@x.com"))
    # saving without a change keeps it verified; a real change sends it back
    same = client.get(f"/api/students/{kid}", headers=_as(client, "vt@x.com")).get_json()
    client.patch(f"/api/students/{kid}", headers=_as(client, "vt@x.com"), json={"father_name": same["father_name"]})
    assert db.session.get(Student, kid).verification_status == "verified"
    client.patch(f"/api/students/{kid}", headers=_as(client, "vt@x.com"), json={"father_name": "New Father"})
    assert db.session.get(Student, kid).verification_status == "pending"
    box = _mine(client, "oa@x.com")
    assert box["unread"] == 1 and "changed after verification" in box["data"][0]["body"]


def test_principal_profile_shows_their_school(client, world, principal_record):
    body = client.get("/api/profile", headers=_as(client, "pr@x.com")).get_json()
    assert body["posting"]["school_name"] == world["school"].name
    assert body["posting"]["trainers"] == ["VT"]
    assert {"full_name", "employee_id"} <= set(body["locked"])
    assert "aadhaar_number" not in body and "account_number" not in body   # not collected for principals


def test_principal_profile_sections(client, world, principal_record):
    h = _as(client, "pr@x.com")
    assert client.patch("/api/profile", headers=h, json={"designation": "Principal"}).status_code == 400
    r = client.patch("/api/profile", headers=h, json=PR_GENERAL)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["superannuation_date"] == "2035-03-31"           # turns 60 in March 2035
    assert client.patch("/api/profile", headers=h, json={"employee_id": "EMP-2"}).status_code == 400  # locked
    svc = client.patch("/api/profile", headers=h, json={"service_joining_date": "2000-07-01",
                                                        "highest_qualification": "Masters/Post-Graduation"})
    assert svc.status_code == 200, svc.get_json()
    assert svc.get_json()["total_service_years"] > 25
    hist = client.patch("/api/profile", headers=h, json={"postings": [
        {"school_name": "GSSS Old Town", "designation": "Lecturer", "from_date": "2000-07-01", "to_date": "2021-06-14"}]})
    assert [p["school_name"] for p in hist.get_json()["postings"]] == ["GSSS Old Town"]


def test_principal_personal_details_stay_off_the_principal_list(client, world, principal_record):
    client.patch("/api/profile", headers=_as(client, "pr@x.com"), json=PR_GENERAL)
    rows = client.get("/api/principals", headers=_as(client, "vt@x.com")).get_json()["data"]
    assert rows and all("dob" not in r and "father_name" not in r for r in rows)


# ------------------------------------------------ adding students in bulk
@pytest.fixture
def category(world):
    from app.models.masters import SocialCategory
    c = SocialCategory(organisation_id=world["org"].id, name="General")
    db.session.add(c)
    db.session.commit()
    return str(c.id)


def _kid(category, n, **extra):
    return {"admission_number": f"ADM-{n}", "first_name": f"Kid{n}", "last_name": "Test", "gender": "Female",
            "dob": "2012-05-01", "father_name": "Father", "mobile_primary": "9876500000",
            "social_category_id": category, "aadhaar_number": f"12341234{n:04d}", **extra}


def _bulk(client, world, students, **extra):
    return client.post("/api/students/bulk", headers=_login(client), json={
        "lab_id": str(world["lab"].id), "class_grade": "9", "section": "A", "students": students, **extra})


def test_trainer_adds_several_students_at_once(client, world, category):
    r = _bulk(client, world, [_kid(category, 1), _kid(category, 2, roll_number="9A-50")])
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["added"] == 2 and body["academic_year"]
    rolls = sorted(s["roll_number"] for s in body["students"])
    assert "9A-50" not in rolls and len(set(rolls)) == 2        # roll numbers are always given, never typed
    assert all(r.startswith("9A-") for r in rolls)
    listed = client.get("/api/students?class_grade=9&section=A&search=Kid1", headers=_login(client)).get_json()["data"][0]
    assert listed["aadhaar_number"] == "XXXXXXXX0001"            # never sent out whole
    assert listed["verification_status"] == "pending"
    assert listed["level"] == "Level 1"


def test_every_row_is_checked_and_nothing_saved_on_error(client, world, category):
    before = client.get("/api/students", headers=_login(client)).get_json()["pagination"]["total"]
    r = _bulk(client, world, [_kid(category, 3),
                              _kid(category, 4, father_name="", aadhaar_number="123"),
                              _kid(category, 5, admission_number="ADM-3")])   # same as row 1
    assert r.status_code == 400
    errors = {e["row"]: e["message"] for e in r.get_json()["errors"]}
    assert set(errors) == {2, 3}
    assert "Father's name" in errors[2] and "Aadhaar" in errors[2]
    assert "already used" in errors[3]
    after = client.get("/api/students", headers=_login(client)).get_json()["pagination"]["total"]
    assert after == before


@pytest.mark.parametrize("change, message", [
    ({"class_grade": "8"}, "Class 9, 10, 11 or 12"),
    ({"section": "C"}, "section"),
])
def test_bulk_add_class_and_section_rules(client, world, category, change, message):
    r = _bulk(client, world, [_kid(category, 6)], **change)
    assert r.status_code == 400
    assert message in r.get_json()["message"]


def test_aadhaar_is_unique_and_stays_masked_when_editing(client, world, category):
    first = _bulk(client, world, [_kid(category, 7)]).get_json()["students"][0]["id"]
    dup = _bulk(client, world, [_kid(category, 8, aadhaar_number="123412340007")])
    assert dup.status_code == 400 and "already registered" in dup.get_json()["errors"][0]["message"]
    h = _login(client)   # a student's details stay editable by the trainer
    # the edit form sends back what it was shown - the stored number stays
    r = client.patch(f"/api/students/{first}", headers=h, json={"aadhaar_number": "XXXXXXXX0007", "father_name": "New Father"})
    assert r.status_code == 200, r.get_json()
    from app.models.student import Student as S
    assert db.session.get(S, first).aadhaar_number == "123412340007"
    assert client.patch(f"/api/students/{first}", headers=h, json={"aadhaar_number": "12"}).status_code == 400


def test_move_a_student_to_another_section(client, world, category):
    kid = _bulk(client, world, [_kid(category, 3)]).get_json()["students"][0]
    h = _login(client)
    r = client.post(f"/api/students/{kid['id']}/section", headers=h, json={"section": "B"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["section"] == "B" and r.get_json()["roll_number"].startswith("9B-")
    assert client.post(f"/api/students/{kid['id']}/section", headers=h, json={"section": "Z"}).status_code == 400
    assert client.post(f"/api/students/{kid['id']}/section", headers=h, json={"section": "B"}).status_code == 400


def test_bulk_add_into_class_10(client, world, category):
    r = _bulk(client, world, [_kid(category, 11)], class_grade="10")
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["students"][0]["roll_number"].startswith("10A-")


def test_only_trainers_bulk_add(client, world, principal, category):
    r = client.post("/api/students/bulk", headers=_as(client, "pr@x.com"), json={
        "lab_id": str(world["lab"].id), "class_grade": "9", "section": "A", "students": [_kid(category, 9)]})
    assert r.status_code == 403


def test_promotion_keeps_the_year_that_ended(client, world):
    a, b, c = _class_of(world)
    s_a = db.session.get(Student, a)
    s_a.roll_number, s_a.section = "9A-07", "A"
    db.session.commit()
    client.post("/api/promotion", headers=_login(client), json={
        "from_year": "2024-25", "class_grade": "9", "promote": [a]})
    h = _login(client)
    hist = client.get(f"/api/promotion/history/{a}", headers=h).get_json()
    assert hist["current"]["class_grade"] == "10" and hist["current"]["academic_year"] == "2025-26"
    year = hist["years"][0]
    assert (year["academic_year"], year["class_grade"], year["roll_number"]) == ("2024-25", "9", "9A-07")
    assert year["outcome"] == "Promoted" and year["job_role"] == world["jr_low"].name
    assert year["snapshot"]["class_grade"] == "9"                 # the whole record as it was
    assert year["snapshot"]["academic_year"] == "2024-25"


# ------------------------------------------------------------ principal issues
def test_principal_raises_an_issue_but_cannot_change_it(client, world, principal_record):
    h = _as(client, "pr@x.com")
    boot = client.get("/api/meta/bootstrap", headers=h).get_json()
    assert boot["resources"]["principal-issues"]["can_write"] is True
    assert boot["resources"]["principal-issues"]["can_edit"] is False
    assert "issues" not in boot["resources"]                     # trainers' issues go to the admins
    r = client.post("/api/principal-issues", headers=h, json={
        "reporting_date": date.today().isoformat(), "reporting_time": "11:15", "details": "Roof leaks in Room 4"})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["school_id"] == str(world["school"].id) and body["workflow_status"] == "open"
    assert client.patch(f"/api/principal-issues/{body['id']}", headers=h, json={"details": "x"}).status_code == 403
    assert client.delete(f"/api/principal-issues/{body['id']}", headers=h).status_code == 403
    assert client.get("/api/issues", headers=h).status_code == 403
    assert client.post("/api/principal-issues", headers=h, json={"reporting_date": date.today().isoformat(),
                                                                  "details": " "}).status_code == 400


def test_trainers_do_not_see_principal_issues(client, world):
    assert client.get("/api/principal-issues", headers=_login(client)).status_code == 403



# ------------------------------------------------ sections (trainer, add students)
def _section(client, world, path, **body):
    return client.post(f"/api/students/sections{path}", headers=_login(client),
                       json={"lab_id": str(world["lab"].id), "class_grade": "9", **body})


def test_trainer_adds_and_removes_a_section(client, world):
    r = _section(client, world, "", section="c")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["sections"] == ["A", "B", "C"]
    assert _section(client, world, "", section="C").status_code == 400          # already there
    assert _section(client, world, "", section="TOO-LONG").status_code == 400
    # section A has students - it can't go; the new, empty C can
    busy = _section(client, world, "/remove", section="A")
    assert busy.status_code == 400 and "still has" in busy.get_json()["message"]
    gone = _section(client, world, "/remove", section="C")
    assert gone.status_code == 200 and gone.get_json()["sections"] == ["A", "B"]
    boot = client.get("/api/meta/bootstrap", headers=_login(client)).get_json()
    lab = next(l for l in boot["options"]["labs"] if l["value"] == str(world["lab"].id))
    assert lab["sections"]["9"] == ["A", "B"]


def test_a_class_keeps_its_last_section(client, world):
    lab = world["lab"]
    lab.sections_10 = "A"
    db.session.commit()
    r = client.post("/api/students/sections/remove", headers=_login(client),
                    json={"lab_id": str(lab.id), "class_grade": "10", "section": "A"})
    assert r.status_code == 400 and "at least one section" in r.get_json()["message"]


def test_year_filter_offers_recent_years(client, world):
    years = client.get("/api/meta/bootstrap", headers=_login(client)).get_json()["options"]["year_labels"]
    assert "2025-26" in years and len(years) >= 5
    assert years == sorted(years, reverse=True)
