"""Authentication - JWT access + refresh, rate-limited - spec Part 7.8."""
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, get_jwt_identity,
)

from app.extensions import db, limiter
from app.models.user import User
from app.rbac import login_required, current_user
from app.rbac.roles import ROLE_LABELS, Role
from app.services import audit
from app.utils.security import validate_password

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MAX_FAILED = 5
LOCK_MINUTES = 15


@bp.post("/login")
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = db.session.query(User).filter(
        User.email == email, User.is_deleted.is_(False)
    ).first()

    # account lockout after repeated failures (brute-force protection)
    if user and user.locked_until and user.locked_until > datetime.utcnow():
        mins = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
        abort(429, description=f"Account temporarily locked. Try again in {mins} minute(s).")

    if user is None or not user.check_password(password):
        if user is not None:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= MAX_FAILED:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
                user.failed_attempts = 0
            db.session.commit()
        # identical message whether or not the email exists (no user enumeration)
        abort(401, description="Invalid email or password")

    if user.status != "active":
        abort(403, description="Account is not active")

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    identity = str(user.id)
    return jsonify({
        "access_token": create_access_token(identity=identity),
        "refresh_token": create_refresh_token(identity=identity),
        "user": user.public_dict(),
    })


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    uid = get_jwt_identity()
    return jsonify({"access_token": create_access_token(identity=uid)})


@bp.get("/me")
@login_required
def me():
    user = current_user()
    org = None
    if user.organisation_id:
        from app.models.organisation import Organisation
        o = db.session.get(Organisation, user.organisation_id)
        if o:
            org = {"id": str(o.id), "name": o.name, "org_code": o.org_code, "logo_url": o.logo_url}
    return jsonify({
        "user": user.public_dict(),
        "role_label": ROLE_LABELS.get(Role(user.role), user.role),
        "organisation": org,
    })


@bp.post("/change-password")
@login_required
def change_password():
    user = current_user()
    data = request.get_json(silent=True) or {}
    if not user.check_password(data.get("current_password", "")):
        abort(400, description="Current password is incorrect")
    new = data.get("new_password") or ""
    ok, msg = validate_password(new)
    if not ok:
        abort(400, description=msg)
    user.set_password(new)
    user.must_change_password = False
    audit.record(user, "update", "app_user", user.id, after={"password": "changed"})
    db.session.commit()
    return jsonify({"changed": True})
