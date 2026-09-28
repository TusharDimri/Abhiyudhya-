"""Admin-only endpoints: audit log viewer - spec Part 5.25.

Each entry is told in plain words for the people reading it: who, did what,
to which record, and what changed (field: before -> after). Internal details
(ids, timestamps, the IP address) are left out."""
import json
import re
from datetime import date, datetime

from flask import Blueprint, request, jsonify, abort
from sqlalchemy import or_

from app.extensions import db
from app.models.misc import AuditLog
from app.rbac import login_required, current_user
from app.rbac.roles import Role
from app.services.cache import cached_json

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/audit-logs")
@login_required
@cached_json("audit_logs", ttl=60)
def audit_logs():
    user = current_user()
    if user.role not in (Role.SUPER_ADMIN.value, Role.ORG_ADMIN.value):
        abort(403, description="Audit log is restricted to administrators")

    q = db.session.query(AuditLog)
    if user.role != Role.SUPER_ADMIN.value:
        q = q.filter(AuditLog.organisation_id == user.organisation_id)

    for col in ("entity", "action", "actor_email"):
        val = request.args.get(col)
        if val:
            q = q.filter(getattr(AuditLog, col) == val)
    if request.args.get("search"):
        term = f"%{request.args['search']}%"
        q = q.filter(or_(AuditLog.entity.ilike(term), AuditLog.actor_email.ilike(term)))

    q = q.order_by(AuditLog.created_at.desc())
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    size = 30
    total = q.count()
    rows = q.limit(size).offset((page - 1) * size).all()

    from app.models.user import User
    actors = {u.id: u.full_name for u in db.session.query(User).filter(
        User.id.in_({r.actor_id for r in rows if r.actor_id} or [None]))}

    def ser(r):
        before, after = _safe(r.before), _safe(r.after)
        return {
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "actor_email": r.actor_email, "actor_role": r.actor_role,
            "actor_name": actors.get(r.actor_id) or r.actor_email,
            "action": r.action, "entity": r.entity,
            "entity_id": str(r.entity_id) if r.entity_id else None,
            # in plain words
            "verb": _verb(r.action, after),
            "what": ENTITY_NAMES.get(r.entity, r.entity.replace("_", " ")),
            "record": _record_name(r.entity, r.entity_id, before, after),
            "changes": _changes(r.action, before, after),
        }

    return jsonify({
        "data": [ser(r) for r in rows],
        "pagination": {"page": page, "page_size": size, "total": total,
                       "pages": (total + size - 1) // size},
    })


def _safe(v):
    if not v:
        return None
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return v


# ------------------------------------------------------------ plain words
ENTITY_NAMES = {
    "student": "student", "daily_attendance": "daily attendance", "class_attendance": "class attendance",
    "vt_issue": "trainer's issue", "principal_issue": "principal's issue", "lab_equipment": "lab equipment",
    "equipment_maintenance": "maintenance log", "guest_lecture": "guest lecture", "field_visit": "field visit",
    "trainer": "trainer", "principal": "principal", "school": "school", "lab": "lab", "district": "district",
    "state": "state", "app_user": "login", "trainer_profile": "trainer profile",
    "principal_profile": "principal profile", "academic_year": "academic year", "sector": "sector",
    "job_role": "job role", "social_category": "social category", "assessment": "assessment",
    "ojt_placement": "OJT / placement", "notification": "notification",
}
FIELD_NAMES = {
    "dob": "Date of birth", "workflow_status": "Status", "endorsement_status": "Verification",
    "verification_status": "Verification", "maintenance_status": "Status", "enrolment_status": "Enrolment",
    "leaving_stage": "Leaving", "leaving_type": "Leaving as", "tc_number": "TC number", "tc_issued_on": "TC date",
    "left_reason": "Reason", "resolution_note": "Resolution", "action": "Resolution", "details": "Details",
    "mobile_primary": "Contact number", "full_name": "Name", "is_current": "Current", "cwsn": "CWSN",
    "class_grade": "Class", "udise_code": "UDISE code", "vtp_name": "VTP", "phone": "Mobile",
}
VALUE_WORDS = {
    "endorsed": "Verified", "submitted": "Pending verification", "requested": "TC pending",
    "tc_issued": "TC issued", "left": "Left", "in-progress": "In progress", "open": "Open",
    "resolved": "Resolved", "pending": "Pending", "verified": "Verified", "rejected": "Rejected",
    "active": "Active", "disabled": "Disabled",
}
# never shown: ids, bookkeeping, where-it-was-captured
HIDDEN = re.compile(r"(^id$|_id$|_by$|^created_at$|^updated_at$|^is_deleted$|^organisation|^location|_accuracy|"
                    r"captured_at|^snapshot$|_url$|^password|^academic_year_of_setup$|_src$|^distance_from_school_m$)")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _field(name):
    return FIELD_NAMES.get(name) or name.replace("_", " ").strip().capitalize()


def _value(v):
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (list, tuple)):
        return ", ".join(_value(x) for x in v) or "—"
    if isinstance(v, dict):
        return "…"
    text = str(v)
    if ISO_DATE.match(text):
        try:
            d = datetime.fromisoformat(text.replace("Z", ""))
            return d.strftime("%d/%m/%Y") if len(text) <= 10 else d.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass
    text = VALUE_WORDS.get(text, text)
    return text if len(text) <= 120 else text[:117] + "…"


def _changes(action, before, after):
    """[{field, from, to}] - for an edit, only what changed; for a new record,
    nothing (it was added whole)."""
    if not isinstance(after, dict) or action == "create":
        return []
    before = before if isinstance(before, dict) else {}
    out = []
    for key, new in after.items():
        if HIDDEN.search(key) or key in ("change", "promotion", "joined", "restored"):
            continue
        old = before.get(key)
        if key in before and str(old) == str(new):
            continue
        out.append({"field": _field(key), "from": _value(old) if key in before else None, "to": _value(new)})
    return out[:12]


def _verb(action, after):
    after = after if isinstance(after, dict) else {}
    if after.get("password") == "reset by admin":
        return "Reset the password of"
    if after.get("endorsement_status") == "endorsed" or after.get("verification_status") == "verified":
        return "Verified"
    if after.get("workflow_status") == "resolved" or after.get("maintenance_status") == "Resolved":
        return "Resolved"
    return {"create": "Added", "update": "Changed", "delete": "Deleted", "restore": "Restored"}.get(action, action.capitalize())


def _record_name(entity, entity_id, before, after):
    """A name a person recognises: the student's name, the school's, the date..."""
    for data in (after, before):
        if isinstance(data, dict):
            for key in ("full_name", "name", "topic", "title", "label", "lecturer_name", "organisation_name"):
                if data.get(key):
                    return str(data[key])
    from app.api.registry import REGISTRY
    model = next((c.model for c in REGISTRY.values() if c.model.__tablename__ == entity), None)
    if model is None and entity in ("app_user",):
        from app.models.user import User as model  # noqa: N813
    if model is None and entity in ("trainer_profile",):
        from app.models.lab import Trainer as model  # noqa: N813
    if model is None and entity in ("principal_profile",):
        from app.models.geography import Principal as model  # noqa: N813
    rec = db.session.get(model, entity_id) if model is not None and entity_id else None
    if rec is None:
        return None
    for key in ("full_name", "name", "topic", "title", "label", "lecturer_name", "organisation_name"):
        val = getattr(rec, key, None)
        if val:
            return str(val)
    when = getattr(rec, "date", None) or getattr(rec, "reporting_date", None)
    text = getattr(rec, "details", None) or getattr(rec, "issue", None)
    parts = [when.strftime("%d/%m/%Y") if isinstance(when, date) else None,
             (text[:60] + ("…" if len(text) > 60 else "")) if text else None]
    return " · ".join(p for p in parts if p) or None
