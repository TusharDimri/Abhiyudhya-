"""Endorsement + issue workflow endpoints - spec Part 5.21 & 3.12."""
from datetime import datetime

from flask import Blueprint, request, jsonify, abort

from app.extensions import db
from app.models.operations import ClassAttendance, DailyAttendance, VTIssue
from app.models.student import Student
from app.rbac import login_required, current_user, can_access_row
from app.rbac.roles import Role
from app.services import audit

bp = Blueprint("workflow", __name__, url_prefix="/api/workflow")


@bp.post("/students/<uid>/verify")
@login_required
def verify_student(uid):
    """VT/DM/OA/SA verify or reject a student registration (spec Part 2.7)."""
    from datetime import datetime
    user = current_user()
    if user.role not in (Role.TRAINER.value, Role.DISTRICT_MANAGER.value,
                         Role.ORG_ADMIN.value, Role.SUPER_ADMIN.value):
        abort(403, description="You cannot verify students")
    rec = db.session.get(Student, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    data = request.get_json(silent=True) or {}
    status = data.get("verification_status", "verified")
    if status not in ("pending", "verified", "rejected"):
        abort(400, description="invalid verification_status")
    before = {"verification_status": rec.verification_status}
    rec.verification_status = status
    rec.verified_by = user.id
    rec.verified_on = datetime.utcnow()
    rec.verification_remarks = data.get("remarks")
    audit.record(user, "update", "student", rec.id, before=before, after={"verification_status": status})
    db.session.commit()
    return jsonify({"id": str(rec.id), "verification_status": status})


def _endorse(model, uid):
    """The Principal endorses (or returns) a trainer's attendance record for
    their school. Endorsed: the trainer can no longer change it. Returned: the
    trainer corrects it, which sends it back for endorsement."""
    user = current_user()
    if user.role not in (Role.PRINCIPAL.value, Role.ORG_ADMIN.value, Role.SUPER_ADMIN.value):
        abort(403, description="Only the Principal can endorse")
    rec = db.session.get(model, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "endorsed")
    if decision not in ("endorsed", "returned"):
        abort(400, description="decision must be 'endorsed' or 'returned'")
    if decision == "returned" and not (data.get("remarks") or "").strip():
        abort(400, description="Say what needs correcting when returning an entry.")
    before = {"endorsement_status": rec.endorsement_status}
    rec.endorsement_status = decision
    rec.endorsed_by = user.id
    rec.endorsed_on = datetime.utcnow()
    rec.endorsement_remarks = data.get("remarks")
    audit.record(user, "update", model.__tablename__, rec.id, before=before,
                 after={"endorsement_status": decision})
    db.session.commit()
    return jsonify({"id": str(rec.id), "endorsement_status": decision})


@bp.post("/attendance/<uid>/endorse")
@login_required
def endorse_attendance(uid):
    return _endorse(DailyAttendance, uid)


@bp.post("/class-attendance/<uid>/endorse")
@login_required
def endorse_class_attendance(uid):
    return _endorse(ClassAttendance, uid)


@bp.post("/issues/<uid>/transition")
@login_required
def transition_issue(uid):
    """DM/OA/SA move an issue through open -> in-progress -> resolved."""
    user = current_user()
    if user.role not in (Role.DISTRICT_MANAGER.value, Role.ORG_ADMIN.value, Role.SUPER_ADMIN.value):
        abort(403, description="Only DM/OA/SA can action issues")
    rec = db.session.get(VTIssue, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    data = request.get_json(silent=True) or {}
    status = data.get("workflow_status")
    if status not in ("open", "in-progress", "resolved"):
        abort(400, description="invalid workflow_status")
    before = {"workflow_status": rec.workflow_status}
    rec.workflow_status = status
    rec.assigned_to = data.get("assigned_to", rec.assigned_to)
    rec.resolution_note = data.get("resolution_note", rec.resolution_note)
    if status == "resolved":
        rec.resolved_on = datetime.utcnow()
    audit.record(user, "update", "vt_issue", rec.id, before=before, after={"workflow_status": status})
    db.session.commit()
    return jsonify({"id": str(rec.id), "workflow_status": status})
