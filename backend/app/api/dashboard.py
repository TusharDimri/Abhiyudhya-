"""Role-scoped dashboards + rollups - spec Part 5.20."""
from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.models.geography import School
from app.models.student import Student
from app.models.lab import Lab, Trainer
from app.models.operations import DailyAttendance, VTIssue, GuestLecture, FieldVisit
from app.models.internship import OJTPlacement, DailyDiary
from app.rbac import login_required, current_user, apply_scope
from app.services.cache import cached_json

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

# metric -> (model, date column) for time-based dashboards/reports
TIME_METRICS = {
    "attendance": (DailyAttendance, "date"),
    "guest-lectures": (GuestLecture, "reporting_date"),
    "field-visits": (FieldVisit, "reporting_date"),
    "diaries": (DailyDiary, "date"),
    "students": (Student, "date_of_enrolment"),
}


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _range():
    return _parse_date(request.args.get("date_from")), _parse_date(request.args.get("date_to"))


def _apply_range(q, model, col_name):
    """Filter a query by the request's date range on the given date column."""
    df, dt = _range()
    col = getattr(model, col_name, None)
    if col is None:
        return q
    if df:
        q = q.filter(col >= df)
    if dt:
        q = q.filter(col <= dt)
    return q


def _scoped(q, model, user):
    """apply_scope + (for Super Admin) an optional organisation slice."""
    q = apply_scope(q, model, user)
    oid = request.args.get("organisation_id")
    if oid and user.role == "SA" and hasattr(model, "organisation_id"):
        q = q.filter(model.organisation_id == oid)
    return q


def _count(model, user, date_col=None):
    q = db.session.query(func.count(model.id)).select_from(model)
    if hasattr(model, "is_deleted"):
        q = q.filter(model.is_deleted.is_(False))
    q = _scoped(q, model, user)
    if date_col:
        q = _apply_range(q, model, date_col)
    return q.scalar() or 0


def _status_count(model, user, col, val, negate=False):
    column = getattr(model, col)
    cond = column != val if negate else column == val
    q = db.session.query(func.count(model.id)).filter(model.is_deleted.is_(False), cond)
    return _scoped(q, model, user).scalar() or 0


@bp.get("/summary")
@login_required
@cached_json("summary", ttl=120)
def summary():
    """Role-tailored KPI cards. Each role sees only what's relevant to it."""
    user = current_user()
    role = user.role

    # every possible metric, computed lazily by key
    M = {
        "schools": lambda: {"key": "schools", "label": "Schools", "value": _count(School, user), "icon": "school"},
        "labs": lambda: {"key": "labs", "label": "Labs", "value": _count(Lab, user), "icon": "flask"},
        "trainers": lambda: {"key": "trainers", "label": "Trainers", "value": _count(Trainer, user), "icon": "user"},
        "students": lambda: {"key": "students", "label": "Students", "value": _count(Student, user, "date_of_enrolment"), "icon": "users"},
        "pending_verification": lambda: {"key": "pending_verification", "label": "Pending Verification", "value": _status_count(Student, user, "verification_status", "pending"), "icon": "clock"},
        "attendance": lambda: {"key": "attendance", "label": "Attendance Entries", "value": _count(DailyAttendance, user, "date"), "icon": "calendar"},
        "guest_lectures": lambda: {"key": "guest_lectures", "label": "Guest Lectures", "value": _count(GuestLecture, user, "reporting_date"), "icon": "mic"},
        "field_visits": lambda: {"key": "field_visits", "label": "Field Visits", "value": _count(FieldVisit, user, "reporting_date"), "icon": "map"},
        "open_issues": lambda: {"key": "open_issues", "label": "Open Issues", "value": _status_count(VTIssue, user, "workflow_status", "resolved", negate=True), "icon": "alert"},
        "pending_endorsement": lambda: {"key": "pending_endorsement", "label": "Awaiting Endorsement", "value": _status_count(DailyAttendance, user, "endorsement_status", "submitted"), "icon": "clock"},
        "endorsed": lambda: {"key": "endorsed", "label": "Endorsed Attendance", "value": _status_count(DailyAttendance, user, "endorsement_status", "endorsed"), "icon": "check"},
        "diaries": lambda: {"key": "diaries", "label": "Diary Entries", "value": _count(DailyDiary, user, "date"), "icon": "book"},
        "placements": lambda: {"key": "placements", "label": "Students Placed", "value": _status_count(OJTPlacement, user, "placement_placed", True), "icon": "briefcase"},
        "issues_resolved": lambda: {"key": "issues_resolved", "label": "Issues Resolved", "value": _status_count(VTIssue, user, "workflow_status", "resolved"), "icon": "check"},
        "pending_issues_action": lambda: {"key": "pending_issues_action", "label": "Issues Needing Action", "value": _status_count(VTIssue, user, "workflow_status", "open"), "icon": "alert"},
    }

    # relevant card sets per role (spec Part 5.20 - role-scoped dashboards)
    ROLE_CARDS = {
        "SA": ["schools", "labs", "trainers", "students", "attendance", "guest_lectures", "field_visits", "open_issues", "endorsed", "placements"],
        "OA": ["schools", "labs", "trainers", "students", "pending_verification", "attendance", "guest_lectures", "field_visits", "open_issues", "placements"],
        "DM": ["schools", "labs", "trainers", "students", "pending_verification", "attendance", "pending_issues_action", "issues_resolved", "endorsed", "field_visits"],
        "PR": ["students", "trainers", "attendance", "pending_endorsement", "endorsed", "guest_lectures", "field_visits", "open_issues"],
        "VT": ["students", "pending_verification", "attendance", "pending_endorsement", "guest_lectures", "field_visits", "open_issues"],
    }
    keys = ROLE_CARDS.get(role, ROLE_CARDS["OA"])
    return jsonify({"cards": [M[k]() for k in keys if k in M]})


@bp.get("/timeseries")
@login_required
@cached_json("timeseries", ttl=120)
def timeseries():
    """Daily counts for a metric over the selected date range (line chart)."""
    user = current_user()
    metric = request.args.get("metric", "attendance")
    if metric not in TIME_METRICS:
        return jsonify({"data": [], "metric": metric})
    model, col = TIME_METRICS[metric]
    date_col = getattr(model, col)
    q = db.session.query(func.date(date_col).label("d"), func.count(model.id)).filter(
        model.is_deleted.is_(False), date_col.isnot(None)
    )
    q = _scoped(q, model, user)
    q = _apply_range(q, model, col).group_by(func.date(date_col)).order_by(func.date(date_col))
    rows = [{"date": str(d), "count": c} for d, c in q.all()]
    return jsonify({"data": rows, "metric": metric})


@bp.get("/attendance-by-activity")
@login_required
@cached_json("attendance_by_activity", ttl=120)
def attendance_by_activity():
    user = current_user()
    q = db.session.query(
        DailyAttendance.activity_type, func.count(DailyAttendance.id)
    ).filter(DailyAttendance.is_deleted.is_(False))
    q = _scoped(q, DailyAttendance, user)
    q = _apply_range(q, DailyAttendance, "date").group_by(DailyAttendance.activity_type)
    rows = [{"activity": (a or "unspecified"), "count": c} for a, c in q.all()]
    return jsonify({"data": rows})


@bp.get("/students-by-school")
@login_required
@cached_json("students_by_school", ttl=120)
def students_by_school():
    user = current_user()
    q = db.session.query(School.name, func.count(Student.id)).select_from(Student).join(
        School, School.id == Student.school_id
    ).filter(Student.is_deleted.is_(False))
    q = _scoped(q, Student, user).group_by(School.name).order_by(func.count(Student.id).desc())
    rows = [{"school": n, "count": c} for n, c in q.limit(12).all()]
    return jsonify({"data": rows})


@bp.get("/students-by-verification")
@login_required
@cached_json("students_by_verification", ttl=120)
def students_by_verification():
    """Distribution across pending / verified / rejected (status palette donut)."""
    user = current_user()
    q = db.session.query(Student.verification_status, func.count(Student.id)).filter(
        Student.is_deleted.is_(False)
    )
    q = _scoped(q, Student, user)
    q = _apply_range(q, Student, "date_of_enrolment").group_by(Student.verification_status)
    rows = [{"status": (s or "pending"), "count": c} for s, c in q.all()]
    return jsonify({"data": rows})


@bp.get("/endorsement-status")
@login_required
@cached_json("endorsement_status", ttl=120)
def endorsement_status():
    """Attendance endorsement funnel: submitted / endorsed / returned."""
    user = current_user()
    q = db.session.query(DailyAttendance.endorsement_status, func.count(DailyAttendance.id)).filter(
        DailyAttendance.is_deleted.is_(False)
    )
    q = _scoped(q, DailyAttendance, user)
    q = _apply_range(q, DailyAttendance, "date").group_by(DailyAttendance.endorsement_status)
    rows = [{"status": (s or "submitted"), "count": c} for s, c in q.all()]
    return jsonify({"data": rows})
