"""The signed-in user's own notifications: the bell's count and dropdown, the
Notifications page, and marking them read. (What creates them: services/notify.py.)"""
from flask import Blueprint, abort, jsonify, request

from app.extensions import db
from app.models.misc import Notification
from app.rbac import current_user, login_required
from app.services.notify import link_for

bp = Blueprint("my_notifications", __name__, url_prefix="/api/me/notifications")


def _mine(user):
    q = db.session.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_deleted.is_(False))
    # nothing pointing at a list this role can't open (e.g. a district
    # manager's older notices about trainers' issues)
    from app.api.registry import REGISTRY
    for name, cfg in REGISTRY.items():
        if user.role not in (cfg.view_roles or []):
            q = q.filter(~Notification.link.like(f"/app/{name}?%"), Notification.link != f"/app/{name}")
    return q


def _row(n, user):
    # the link made whole for this user (older notifications carry older links)
    return {"id": str(n.id), "title": n.title, "body": n.body, "category": n.category, "link": link_for(user, n.link),
            "is_read": bool(n.is_read), "created_at": n.created_at.isoformat() if n.created_at else None}


@bp.get("")
@login_required
def list_mine():
    """?page=&page_size= (newest first), ?unread=1 for unread only."""
    user = current_user()
    page = max(1, request.args.get("page", 1, type=int))
    size = min(50, max(1, request.args.get("page_size", 10, type=int)))
    q = _mine(user)
    if request.args.get("unread") in ("1", "true"):
        q = q.filter(Notification.is_read.is_(False))
    total = q.count()
    rows = q.order_by(Notification.created_at.desc()).limit(size).offset((page - 1) * size).all()
    unread = _mine(user).filter(Notification.is_read.is_(False)).count()
    return jsonify({"unread": unread, "data": [_row(n, user) for n in rows],
                    "pagination": {"page": page, "page_size": size, "total": total,
                                   "pages": max(1, (total + size - 1) // size)}})


@bp.post("/<uid>/read")
@login_required
def read_one(uid):
    user = current_user()
    n = db.session.get(Notification, uid)
    if n is None or n.user_id != user.id:
        abort(404)
    n.is_read = True
    db.session.commit()
    return jsonify({"id": str(n.id), "is_read": True})


@bp.post("/read-all")
@login_required
def read_all():
    user = current_user()
    n = _mine(user).filter(Notification.is_read.is_(False)).update({"is_read": True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"marked": n})
