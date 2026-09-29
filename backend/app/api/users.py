"""User provisioning - create logins + assign scope. spec Part 0.2.

Admins and District Managers create staff logins. Students never get a login.
"""
from flask import Blueprint, request, jsonify, abort
from sqlalchemy import or_

from app.extensions import db
from app.models.user import User
from app.models.geography import District
from app.models.lab import Lab
from app.rbac import login_required, current_user
from app.rbac.roles import Role, ROLE_LABELS
from app.services import audit
from app.utils.security import validate_password
from app.services.cache import cached_json

bp = Blueprint("users", __name__, url_prefix="/api/users")

# who may create/manage which roles
CREATE_MATRIX = {
    # org admins' logins come with their organisation (Organisations page)
    Role.SUPER_ADMIN.value: set(),
    # an org admin's principals and trainers get their logins when they are
    # added (Master Data), so Users & Access only resets and disables them
    Role.ORG_ADMIN.value: set(),
    Role.DISTRICT_MANAGER.value: {"PR", "VT"},
}

MANAGER_ROLES = {Role.SUPER_ADMIN.value, Role.ORG_ADMIN.value,
                 Role.DISTRICT_MANAGER.value}
# the logins an org admin looks after: their schools' principals and trainers
# (not other org admins, nor district managers)
SCHOOL_STAFF = (Role.PRINCIPAL.value, Role.TRAINER.value)

# no look-alike characters (0/O, 1/l/I) - the password is read off a screen
_PW_UPPER, _PW_LOWER, _PW_DIGIT = "ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnpqrstuvwxyz", "23456789"


def new_password(length=10):
    """A one-time password for a new login: mixed case and digits."""
    import secrets
    chars = [secrets.choice(_PW_UPPER), secrets.choice(_PW_LOWER), secrets.choice(_PW_DIGIT)]
    chars += [secrets.choice(_PW_UPPER + _PW_LOWER + _PW_DIGIT) for _ in range(length - 3)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


class LoginError(ValueError):
    pass


def create_login_for(role, record, actor):
    """The login for a trainer / principal an admin has just added: their
    email is the username, the password is generated (and must be changed at
    first login). Links the record to it. Returns {username, password} - the
    only time the password is ever shown."""
    email = (record.email or "").strip().lower()
    if not email:
        raise LoginError("Enter their email - it is their username for logging in.")
    if db.session.query(User).filter(User.email == email).first():
        raise LoginError(f"A login with the email {email} already exists.")
    password = new_password()
    u = User(
        organisation_id=record.organisation_id, full_name=record.full_name, email=email,
        phone=getattr(record, "phone", None) or getattr(record, "mobile", None), role=role,
        school_id=getattr(record, "school_id", None) or getattr(record, "linked_school_id", None),
        must_change_password=True, created_by=actor.id,
    )
    u.set_password(password)
    if role == Role.TRAINER.value and getattr(record, "lab_id", None):
        lab = db.session.get(Lab, record.lab_id)
        if lab:
            u.labs.append(lab)
    db.session.add(u)
    db.session.flush()
    record.user_id = u.id
    audit.record(actor, "create", "app_user", u.id, after=u.public_dict())
    return {"username": email, "password": password}


def _require_manager(user):
    if user.role not in MANAGER_ROLES:
        abort(403, description="You cannot manage users")


def _scoped_target(actor, target):
    """A manager may only act on users inside their organisation (SA: any)."""
    if target is None or target.is_deleted:
        abort(404)
    if actor.role != Role.SUPER_ADMIN.value and target.organisation_id != actor.organisation_id:
        abort(403, description="Outside your organisation")
    if actor.role == Role.ORG_ADMIN.value and target.role not in SCHOOL_STAFF:
        abort(403, description="Org admins look after principals' and trainers' logins only.")
    if actor.role == Role.SUPER_ADMIN.value and target.role != Role.ORG_ADMIN.value:
        abort(403, description="The super admin looks after org admins' logins only.")


@bp.get("")
@login_required
@cached_json("list_users", ttl=60)
def list_users():
    user = current_user()
    _require_manager(user)
    q = db.session.query(User).filter(User.is_deleted.is_(False))
    if user.role != Role.SUPER_ADMIN.value:
        q = q.filter(User.organisation_id == user.organisation_id)
    if user.role == Role.ORG_ADMIN.value:
        q = q.filter(User.role.in_(SCHOOL_STAFF), User.school_id.isnot(None))
    if user.role == Role.SUPER_ADMIN.value:      # their org admins, nobody below
        q = q.filter(User.role == Role.ORG_ADMIN.value)
    role = request.args.get("role")
    if role:
        q = q.filter(User.role == role)
    if request.args.get("search"):
        term = f"%{request.args['search']}%"
        q = q.filter(db.or_(User.full_name.ilike(term), User.email.ilike(term)))
    q = q.order_by(User.full_name.asc())
    return jsonify({
        "data": [u.public_dict() | {"status": u.status, "role_label": ROLE_LABELS.get(Role(u.role), u.role),
                                    "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}
                 for u in q.limit(500).all()],
        "can_create": sorted(CREATE_MATRIX.get(user.role, set())),
    })


@bp.post("")
@login_required
def create_user():
    actor = current_user()
    allowed = CREATE_MATRIX.get(actor.role, set())
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if role not in allowed:
        abort(403, description=f"You cannot create a '{role}' user")
    missing = [label for key, label in (("full_name", "Full name"), ("email", "Email"), ("password", "Password"))
               if not str(data.get(key) or "").strip()]
    if role in (Role.PRINCIPAL.value, Role.TRAINER.value) and not data.get("school_id"):
        missing.append("School")
    if role == Role.TRAINER.value and not data.get("lab_ids"):
        missing.append("Lab")
    if role == Role.DISTRICT_MANAGER.value and not data.get("district_ids"):
        missing.append("District")
    if missing:
        abort(400, description="Please fill in: " + ", ".join(missing) + ".")
    ok, msg = validate_password(data["password"])
    if not ok:
        abort(400, description=msg)
    if db.session.query(User).filter(User.email == data["email"].lower()).first():
        abort(409, description="A user with this email already exists")

    org_id = actor.organisation_id
    if actor.role == Role.SUPER_ADMIN.value and data.get("organisation_id"):
        org_id = data["organisation_id"]

    u = User(
        organisation_id=org_id if role != Role.SUPER_ADMIN.value else data.get("organisation_id"),
        full_name=data.get("full_name", data["email"]),
        email=data["email"].strip().lower(),
        phone=data.get("phone"),
        role=role,
        school_id=data.get("school_id"),
        must_change_password=data.get("must_change_password", True),
        created_by=actor.id,
    )
    u.set_password(data["password"])

    # attach many-to-many scopes
    for did in data.get("district_ids", []) or []:
        d = db.session.get(District, did)
        if d:
            u.districts.append(d)
    for lid in data.get("lab_ids", []) or []:
        lab = db.session.get(Lab, lid)
        if lab:
            u.labs.append(lab)

    db.session.add(u)
    db.session.flush()
    audit.record(actor, "create", "app_user", u.id, after=u.public_dict())
    db.session.commit()
    return jsonify(u.public_dict()), 201


@bp.patch("/<uid>")
@login_required
def update_user(uid):
    actor = current_user()
    _require_manager(actor)
    target = db.session.get(User, uid)
    _scoped_target(actor, target)
    data = request.get_json(silent=True) or {}
    if actor.role == Role.SUPER_ADMIN.value:
        abort(403, description="The super admin only resets org admins' passwords.")
    if actor.role == Role.ORG_ADMIN.value:
        data = {k: v for k, v in data.items() if k == "status"}   # disable / enable only
    before = target.public_dict()
    for f in ("full_name", "phone"):
        if f in data:
            setattr(target, f, data[f])
    if "status" in data and data["status"] in ("active", "disabled"):
        target.status = data["status"]
    if "school_id" in data:
        target.school_id = data["school_id"]
    if "district_ids" in data:
        target.districts = [d for d in (db.session.get(District, x) for x in data["district_ids"]) if d]
    if "lab_ids" in data:
        target.labs = [l for l in (db.session.get(Lab, x) for x in data["lab_ids"]) if l]
    target.updated_by = actor.id
    audit.record(actor, "update", "app_user", target.id, before=before, after=target.public_dict())
    db.session.commit()
    return jsonify(target.public_dict())


@bp.post("/<uid>/reset-password")
@login_required
def reset_password(uid):
    actor = current_user()
    _require_manager(actor)
    target = db.session.get(User, uid)
    _scoped_target(actor, target)
    data = request.get_json(silent=True) or {}
    new = data.get("new_password") or ""
    ok, msg = validate_password(new)
    if not ok:
        abort(400, description=msg)
    target.set_password(new)
    target.must_change_password = True
    target.failed_attempts = 0
    target.locked_until = None
    audit.record(actor, "update", "app_user", target.id, after={"password": "reset by admin"})
    db.session.commit()
    return jsonify({"reset": True})
