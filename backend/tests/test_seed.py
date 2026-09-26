"""The demo seed must work on a brand-new database - it is what a teammate
runs after `flask db upgrade` - and running it twice must add nothing."""
import os
from datetime import date

os.environ["TESTING"] = "1"

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from tests.conftest import reset_schema  # noqa: E402
from app import models as M  # noqa: E402

COUNTED = {
    "students": M.Student, "daily attendance": M.DailyAttendance, "class attendance": M.ClassAttendance,
    "class attendance marks": M.ClassAttendanceStudentMark, "guest lectures": M.GuestLecture,
    "field visits": M.FieldVisit, "trainer issues": M.VTIssue, "principal issues": M.PrincipalIssue,
    "equipment": M.LabEquipment, "maintenance": M.EquipmentMaintenance, "assessments": M.Assessment,
    "ojt": M.OJTPlacement, "employers": M.Employer, "employer mappings": M.EmployerStudentMap,
    "diaries": M.DailyDiary, "feedback": M.Feedback, "promotions": M.StudentPromotion,
    "trainer qualifications": M.TrainerQualification, "principal postings": M.PrincipalPosting,
    "schools": M.School, "labs": M.Lab, "organisations": M.Organisation,
    "notifications": M.Notification, "audit log": M.AuditLog,
}


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        reset_schema()
        yield app
        db.session.remove()


def _counts():
    return {name: db.session.query(model).count() for name, model in COUNTED.items()}


@pytest.mark.parametrize("today", [date(2026, 9, 26), date(2027, 5, 20)])   # mid-year, and just after it ends
def test_full_seed_builds_a_complete_site_and_can_run_again(app, today):
    from app.full_seed import run_full_seed

    run_full_seed(today=today, quiet=True)
    first = _counts()
    empty = [name for name, n in first.items() if n == 0]
    assert not empty, f"nothing seeded for: {empty}"
    assert first["organisations"] == 2 and first["schools"] == 8 and first["labs"] == 8

    roles = dict(db.session.query(M.User.role, db.func.count(M.User.id)).group_by(M.User.role).all())
    assert roles["SA"] >= 1 and roles["OA"] >= 3 and roles["DM"] >= 3
    assert roles["PR"] >= 8 and roles["VT"] >= 16

    # every trainer and principal login is wired to a record, with a profile
    for u in db.session.query(M.User).filter(M.User.role == "VT"):
        t = db.session.query(M.Trainer).filter_by(user_id=u.id).one()
        assert t.lab_id and t.father_name, u.email
    for u in db.session.query(M.User).filter(M.User.role == "PR"):
        p = db.session.query(M.Principal).filter_by(user_id=u.id).one()
        assert p.linked_school_id and p.dob, u.email

    # every school has a location, so attendance can be marked there
    assert all(s.location is not None for s in db.session.query(M.School))
    # nothing dated in the future
    assert db.session.query(M.DailyAttendance).filter(M.DailyAttendance.date >= today).count() == 0
    # exactly one current academic year per organisation
    for org in db.session.query(M.Organisation):
        current = db.session.query(M.AcademicYear).filter_by(organisation_id=org.id, is_current=True).count()
        assert current == 1, org.name

    run_full_seed(today=today, quiet=True)
    assert _counts() == first, "running the seed again must add nothing"
