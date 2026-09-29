"""Audit trail writer - spec Part 5.25 / 7.8. Logs actor + before/after diff."""
import json
import uuid

from flask import request

from app.extensions import db
from app.models.misc import AuditLog


def _serialise(obj):
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return str(obj)


def record(user, action, entity, entity_id, before=None, after=None):
    log = AuditLog(
        id=uuid.uuid4(),
        organisation_id=getattr(user, "organisation_id", None),
        actor_id=getattr(user, "id", None),
        actor_email=getattr(user, "email", None),
        actor_role=getattr(user, "role", None),
        action=action,
        entity=entity,
        entity_id=entity_id,
        before=_serialise(before),
        after=_serialise(after),
        ip=request.remote_addr if request else None,
    )
    db.session.add(log)
    # the super admin hears what org admins do
    if getattr(user, "role", None) == "OA":
        from app.services import notify
        notify.org_admin_action(user, action, entity, entity_id, before, after)
