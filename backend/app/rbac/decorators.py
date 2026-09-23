"""RBAC decorators + current-user helpers - spec Part 7.8."""
from functools import wraps

from flask import g, abort
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from app.extensions import db
from app.models.user import User


def load_current_user():
    """Resolve and cache the authenticated User on `g` for this request."""
    if "current_user" in g:
        return g.current_user
    verify_jwt_in_request()
    uid = get_jwt_identity()
    user = db.session.get(User, uid)
    if user is None or user.is_deleted:
        abort(401, description="User no longer exists")
    g.current_user = user
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        load_current_user()
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    """Allow only the given role codes (e.g. require_role('SA', 'OA'))."""
    allowed = set(roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = load_current_user()
            if user.role not in allowed:
                abort(403, description="Insufficient role for this action")
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    return load_current_user()
