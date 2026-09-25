"""Admin-only endpoints: audit log viewer - spec Part 5.25."""
import json

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

    def ser(r):
        return {
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "actor_email": r.actor_email, "actor_role": r.actor_role,
            "action": r.action, "entity": r.entity,
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "before": _safe(r.before), "after": _safe(r.after), "ip": r.ip,
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
