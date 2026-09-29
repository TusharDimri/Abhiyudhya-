"""Endorsement + issue workflow endpoints - spec Part 5.21 & 3.12."""
from datetime import datetime

from flask import Blueprint, request, jsonify, abort

from app.extensions import db
from app.models.operations import ClassAttendance, DailyAttendance, PrincipalIssue, VTIssue
from app.models.student import Student
from app.rbac import login_required, current_user, can_access_row
from app.rbac.roles import Role
from app.services import audit
from app.services.academic_year import guard_closed_year

bp = Blueprint("workflow", __name__, url_prefix="/api/workflow")


@bp.post("/students/<uid>/verify")
@login_required
def verify_student(uid):
    """An admin (org admin, district manager, super admin) verifies a student
    the trainer added - at Class 9 and again at Class 11 (spec Part 2.7)."""
    from datetime import datetime
    user = current_user()
    if user.role not in (Role.DISTRICT_MANAGER.value, Role.ORG_ADMIN.value):   # (the super admin only reads)
        abort(403, description="Students are verified by the admin, not by the trainer.")
    rec = db.session.get(Student, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    guard_closed_year(rec, user)
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
    """The Principal verifies a trainer's attendance record for their school
    (stored as 'endorsed'). Once verified the trainer can no longer change it."""
    user = current_user()
    if user.role != Role.PRINCIPAL.value:
        abort(403, description="Only the Principal can verify attendance")
    rec = db.session.get(model, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    guard_closed_year(rec, user)
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "endorsed")
    if decision != "endorsed":
        abort(400, description="Attendance can only be verified.")
    if rec.endorsement_status == "endorsed":
        abort(409, description="This attendance is already verified.")
    before = {"endorsement_status": rec.endorsement_status}
    rec.endorsement_status = decision
    rec.endorsed_by = user.id
    rec.endorsed_on = datetime.utcnow()
    rec.endorsement_remarks = data.get("remarks")
    audit.record(user, "update", model.__tablename__, rec.id, before=before,
                 after={"endorsement_status": decision})
    from app.services import notify
    notify.attendance_verified(rec, user, "daily" if model is DailyAttendance else "class")
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


ISSUE_KINDS = {"issues": ("vt", VTIssue, "vt_issue"), "principal-issues": ("pr", PrincipalIssue, "principal_issue")}


@bp.post("/<any(issues, 'principal-issues'):which>/<uid>/transition")
@login_required
def transition_issue(which, uid):
    """DM/OA/SA move a trainer's or a principal's issue through
    open -> in-progress -> resolved (whoever raised it is told when it's resolved)."""
    user = current_user()
    if user.role not in (Role.DISTRICT_MANAGER.value, Role.ORG_ADMIN.value):   # (the super admin only reads)
        abort(403, description="Only DM/OA/SA can action issues")
    kind, model, table = ISSUE_KINDS[which]
    rec = db.session.get(model, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    data = request.get_json(silent=True) or {}
    status = data.get("workflow_status")
    if status not in ("open", "in-progress", "resolved"):
        abort(400, description="invalid workflow_status")
    if status == "resolved" and not (data.get("resolution_note") or "").strip():
        abort(400, description="Write how the issue was resolved.")
    before = {"workflow_status": rec.workflow_status}
    rec.workflow_status = status
    if hasattr(rec, "assigned_to"):
        rec.assigned_to = data.get("assigned_to", rec.assigned_to)
    rec.resolution_note = data.get("resolution_note", rec.resolution_note)
    if status == "resolved":
        rec.resolved_on = datetime.utcnow()
    audit.record(user, "update", table, rec.id, before=before, after={"workflow_status": status})
    if before["workflow_status"] != status:
        from app.services import notify
        notify.issue_status_changed(rec, user, kind, status)
    db.session.commit()
    return jsonify({"id": str(rec.id), "workflow_status": status})


@bp.post("/equipment-maintenance/<uid>/status")
@login_required
def maintenance_status(uid):
    """An admin moves a maintenance record along (Reported -> ... -> Repaired);
    the trainer who logged it is told."""
    from app.api import enums
    from app.models.operations import EquipmentMaintenance, LabEquipment
    user = current_user()
    if user.role not in (Role.DISTRICT_MANAGER.value, Role.ORG_ADMIN.value):   # (the super admin only reads)
        abort(403, description="Only an admin updates maintenance status")
    rec = db.session.get(EquipmentMaintenance, uid)
    if rec is None or rec.is_deleted:
        abort(404)
    if not can_access_row(rec, user):
        abort(403, description="Outside your scope")
    data = request.get_json(silent=True) or {}
    status = data.get("maintenance_status")
    if status == "Open":      # back to being worked on
        status = rec.maintenance_status if rec.maintenance_status not in ("Resolved", None) else "Reported"
    if status not in enums.values("maintenance_status"):
        abort(400, description="Pick a valid status.")
    resolution = (data.get("resolution") or data.get("note") or "").strip()
    if status == "Resolved" and not resolution:
        abort(400, description="Write how it was resolved.")
    before = {"maintenance_status": rec.maintenance_status}
    rec.maintenance_status = status
    if resolution:
        rec.action = resolution       # "what was done" - the org admin's resolution
        rec.resolved_by = user.full_name
    rec.updated_by = user.id
    audit.record(user, "update", "equipment_maintenance", rec.id, before=before, after={"maintenance_status": status})
    if before["maintenance_status"] != status:
        from app.services import notify
        notify.maintenance_status_changed(rec, db.session.get(LabEquipment, rec.equipment_id), user)
    db.session.commit()
    return jsonify({"id": str(rec.id), "maintenance_status": status})
