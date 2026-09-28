"""Generic resource controller - list/detail/create/update/delete.

One blueprint serves every registered resource. Every request is:
  1. authenticated (login_required),
  2. row-scoped via apply_scope (tenant + role isolation),
  3. write-gated by the resource's write_roles,
  4. audited on every write.

Query params (list):  ?page=&page_size=&search=&sort=&order=&<filter_col>=value
"""
import uuid
from datetime import datetime, date, time

from flask import Blueprint, request, jsonify, abort, current_app
from sqlalchemy import or_, asc, desc

from app.extensions import db
from app.models.base import GUID
from app.api.registry import LOCKED_MESSAGE, REGISTRY
from app.rbac import login_required, current_user, apply_scope, can_access_row
from app.rbac.roles import Role
from app.services import audit
from app.services.cache import cached_json
from app.services.academic_year import guard_closed_year, is_past_year

bp = Blueprint("resources", __name__, url_prefix="/api")


def _cfg(name):
    cfg = REGISTRY.get(name)
    if cfg is None:
        abort(404, description=f"Unknown resource '{name}'")
    return cfg


def _require_view(cfg, user):
    """Block roles that may not view this resource at all (defence in depth)."""
    if cfg.view_roles and user.role not in cfg.view_roles:
        abort(403, description="This section is not available for your role")


def _serialise(cfg, obj):
    data = obj.to_dict()
    # from an academic year that has ended: closed, the screens offer no changes
    data["past_year"] = is_past_year(obj)
    if cfg.computed:
        try:
            data.update(cfg.computed(obj) or {})
        except Exception:  # computed display fields must never break a read
            pass
    for child in cfg.children:
        rows = (
            db.session.query(child.model)
            .filter(
                getattr(child.model, child.parent_fk) == obj.id,
                child.model.is_deleted.is_(False),
            )
            .all()
        )
        data[child.payload_key] = [
            {f: (str(getattr(r, f)) if isinstance(getattr(r, f), uuid.UUID) else getattr(r, f))
             for f in child.fields}
            for r in rows
        ]
    return data


def _write_children(cfg, obj, payload, user):
    """Replace a parent's child collections from the request body.

    Sent as a whole list (`student_marks: [{student_id, present}, ...]`), so a
    re-save of the entry is the full truth for that day - rows that disappear
    from the list are removed rather than left behind as ghosts. A key that is
    absent from the body leaves the existing collection untouched.
    """
    for child in cfg.children:
        if child.payload_key not in payload:
            continue
        incoming = payload.get(child.payload_key) or []
        if not isinstance(incoming, list):
            abort(400, description=f"'{child.payload_key}' must be a list")
        if "student_id" in child.fields:
            _check_students_in_scope(incoming, user)
        existing = (
            db.session.query(child.model)
            .filter(getattr(child.model, child.parent_fk) == obj.id)
            .all()
        )
        for row in existing:
            db.session.delete(row)
        db.session.flush()
        for item in incoming:
            if not isinstance(item, dict):
                continue
            data = {f: _coerce(child.model, f, item.get(f)) for f in child.fields}
            if not data.get(child.fields[0]):
                continue  # no subject (e.g. no student_id) - skip the row
            data[child.parent_fk] = obj.id
            if hasattr(child.model, "organisation_id"):
                data["organisation_id"] = obj.organisation_id
            row = child.model(**data)
            if hasattr(row, "created_by"):
                row.created_by = user.id
            db.session.add(row)
        db.session.flush()


def _check_students_in_scope(items, user):
    """Every student a list of marks names must be one this user can see."""
    from app.models.student import Student
    wanted = set()
    for item in items:
        sid = _coerce(Student, "id", (item or {}).get("student_id")) if isinstance(item, dict) else None
        if sid is not None:
            wanted.add(sid)
    if not wanted:
        return
    if not all(isinstance(s, uuid.UUID) for s in wanted):
        abort(400, description="Unknown student in the list.")
    q = db.session.query(Student.id).filter(Student.id.in_(wanted), Student.is_deleted.is_(False))
    seen = {r[0] for r in apply_scope(q, Student, user).all()}
    if wanted - seen:
        abort(400, description="The list names a student outside your classes.")


def _coerce(model, fieldname, value):
    """Best-effort coercion of query/body strings to column python types."""
    col = model.__table__.columns.get(fieldname)
    if col is None or value is None:
        return value
    # UUID/GUID columns: coerce strings to UUID regardless of python_type support
    if isinstance(col.type, GUID) or fieldname == "id" or fieldname.endswith("_id"):
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except (ValueError, TypeError):
                return value
        return value
    try:
        pytype = col.type.python_type
    except NotImplementedError:
        return value
    try:
        if pytype is bool:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("1", "true", "yes", "on")
        if pytype in (int,):
            return int(value)
        if pytype is float:
            return float(value)
        if pytype is uuid.UUID:
            return uuid.UUID(str(value))
        if pytype is datetime and isinstance(value, str):
            return datetime.fromisoformat(value)
        if pytype is date and isinstance(value, str):
            return date.fromisoformat(value[:10])
        if pytype is time and isinstance(value, str):
            return time.fromisoformat(value)
    except (ValueError, TypeError):
        return value
    return value


LOCATION_NEEDED = ("We need your location to save this. Click \u201cDetect My Location\u201d "
                   "at the top of the page and allow location access.")


def _missing_required(cfg, obj, payload=None):
    """The required fields left empty: all of them for a new record; for an
    edit (payload given) only the ones it tries to blank."""
    missing = []
    for name, label in cfg.required.items():
        if payload is not None:
            sent = name in payload or (name == "location" and ("location_lat" in payload or "location_lng" in payload))
            if not sent:
                continue
        if getattr(obj, name, None) in (None, ""):
            missing.append(label)
    if missing:
        abort(400, description="Please fill in: " + ", ".join(missing) + ".")


def _set_manual_location(obj, payload):
    """A point typed in (or picked) by an admin, sent as location_lat /
    location_lng. Both blank clears it; absent leaves it as it is."""
    from app.models.geo import point_wkt
    if "location_lat" not in payload and "location_lng" not in payload:
        return
    lat, lng = payload.get("location_lat"), payload.get("location_lng")
    if lat in (None, "") and lng in (None, ""):
        obj.location = None
        return
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        abort(400, description="Enter both latitude and longitude as numbers.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        abort(400, description="Latitude must be -90 to 90 and longitude -180 to 180.")
    obj.location = point_wkt(lat, lng)


def _capture_location(obj, payload, user):
    """Where the record was made. The browser sends the fix the server sealed
    when it was detected (`location_fix`, see services/location_seal.py) -
    never typed by anyone, and refused if it was altered. Trainers must send
    one."""
    from app.rbac.roles import Role
    from app.services.location_seal import LocationError, verify

    fix = payload.get("location_fix")
    if not fix:
        if user.role == Role.TRAINER.value:
            abort(400, description=LOCATION_NEEDED)
        return
    try:
        lat, lng, accuracy, captured_at = verify(user.id, fix)
    except LocationError as exc:
        abort(400, description=str(exc))
    obj.set_location(lat, lng, accuracy, captured_at)


@bp.get("/<resource>")
@login_required
@cached_json("list_resource", ttl=60)
def list_resource(resource):
    cfg = _cfg(resource)
    user = current_user()
    _require_view(cfg, user)
    model = cfg.model

    q = db.session.query(model)
    if hasattr(model, "is_deleted"):
        q = q.filter(model.is_deleted.is_(False))
    q = apply_scope(q, model, user)

    # Super Admin is cross-org: let them slice any tenant list by organisation.
    oid = request.args.get("organisation_id")
    if oid and user.role == Role.SUPER_ADMIN.value and hasattr(model, "organisation_id"):
        q = q.filter(model.organisation_id == _coerce(model, "organisation_id", oid))

    # --- search ---
    term = request.args.get("search", "").strip()
    if term and cfg.search:
        clauses = [getattr(model, c).ilike(f"%{term}%") for c in cfg.search]
        q = q.filter(or_(*clauses))

    # --- filters ---
    # A comma-separated value means "any of these" - needed because sections
    # are picked as a set ("9A and 9B"), and handy for every other filter too.
    for col in cfg.filters:
        if col in (cfg.extra_filters or {}):
            continue  # applied below, by its own function
        if col in request.args and request.args.get(col) != "":
            raw = request.args.get(col)
            column = getattr(model, col)
            if "," in raw:
                vals = [_coerce(model, col, v.strip()) for v in raw.split(",") if v.strip()]
                q = q.filter(column.in_(vals or [None]))
            else:
                q = q.filter(column == _coerce(model, col, raw))

    # filters that need a join or subquery rather than a column comparison
    for param, fn in (cfg.extra_filters or {}).items():
        val = request.args.get(param)
        if val:
            q = fn(q, model, _coerce(model, param, val))

    # --- sort ---
    sort_col, sort_dir = cfg.default_sort
    req_sort = request.args.get("sort")
    if req_sort in cfg.sortable:
        sort_col = req_sort
    if request.args.get("order") in ("asc", "desc"):
        sort_dir = request.args.get("order")
    if hasattr(model, sort_col):
        col = getattr(model, sort_col)
        q = q.order_by(asc(col) if sort_dir == "asc" else desc(col))

    # --- pagination ---
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    max_size = current_app.config["MAX_PAGE_SIZE"]
    try:
        page_size = int(request.args.get("page_size", current_app.config["DEFAULT_PAGE_SIZE"]))
    except ValueError:
        page_size = current_app.config["DEFAULT_PAGE_SIZE"]
    page_size = max(1, min(page_size, max_size))

    total = q.count()
    rows = q.limit(page_size).offset((page - 1) * page_size).all()

    return jsonify({
        "data": [_serialise(cfg, r) for r in rows],
        "pagination": {
            "page": page, "page_size": page_size, "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    })


@bp.get("/<resource>/trash")
@login_required
@cached_json("list_trash", ttl=60)
def list_trash(resource):
    """Soft-deleted rows (Recycle Bin) - visible to writers, for restore."""
    cfg = _cfg(resource)
    user = current_user()
    if not cfg.can_edit(user.role):
        abort(403, description="Only editors can view the recycle bin")
    model = cfg.model
    if not hasattr(model, "is_deleted"):
        return jsonify({"data": [], "pagination": {"page": 1, "pages": 1, "total": 0, "page_size": 25}})
    q = db.session.query(model).filter(model.is_deleted.is_(True))
    q = apply_scope(q, model, user).order_by(model.updated_at.desc())
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    page_size = current_app.config["DEFAULT_PAGE_SIZE"]
    total = q.count()
    rows = q.limit(page_size).offset((page - 1) * page_size).all()
    return jsonify({
        "data": [_serialise(cfg, r) for r in rows],
        "pagination": {"page": page, "page_size": page_size, "total": total,
                       "pages": (total + page_size - 1) // page_size},
    })


@bp.post("/<resource>/<uid>/restore")
@login_required
def restore_resource(resource, uid):
    cfg = _cfg(resource)
    user = current_user()
    if not cfg.can_edit(user.role):
        abort(403, description="You cannot restore this record")
    obj = db.session.get(cfg.model, uid)
    if obj is None or not getattr(obj, "is_deleted", False):
        abort(404)
    if not can_access_row(obj, user):
        abort(403, description="Outside your scope")
    obj.is_deleted = False
    obj.status = "active"
    if hasattr(obj, "updated_by"):
        obj.updated_by = user.id
    audit.record(user, "restore", cfg.model.__tablename__, obj.id, after={"restored": True})
    db.session.commit()
    return jsonify({"restored": True, "id": str(obj.id)})


@bp.get("/<resource>/<uid>")
@login_required
@cached_json("get_resource", ttl=60)
def get_resource(resource, uid):
    cfg = _cfg(resource)
    user = current_user()
    _require_view(cfg, user)
    obj = db.session.get(cfg.model, uid)
    if obj is None or getattr(obj, "is_deleted", False):
        abort(404)
    if not can_access_row(obj, user):
        abort(403, description="Outside your scope")
    data = _for_viewing(cfg, _serialise(cfg, obj))
    if cfg.profile_role and cfg.can_edit(user.role):
        from app.api.profile import admin_profile_view
        data.update(admin_profile_view(cfg.profile_role, obj))
    return jsonify(data)


def _apply_profile(cfg, obj, payload, user):
    """The profile part of an admin's trainer / principal form."""
    from app.api.profile import Invalid, apply_admin_profile
    try:
        apply_admin_profile(cfg.profile_role, obj, payload, user, base_fields=cfg.writable)
    except Invalid as exc:
        db.session.rollback()
        abort(400, description=str(exc))
    db.session.flush()


def _create_login(cfg, obj, user):
    from app.api.users import LoginError, create_login_for
    try:
        return create_login_for(cfg.profile_role, obj, user)
    except LoginError as exc:
        db.session.rollback()
        abort(400, description=str(exc))


def _for_viewing(cfg, data):
    """One record opened on its own (the View window): a link for each photo
    and the name of each student in its lists, not just their ids."""
    from app.models.student import Student
    from app.services import storage

    for key in ("photo_url", "picture_url", "tc_url"):
        path = data.get(key)
        if path:
            try:
                data[key.replace("_url", "_src")] = path if str(path).startswith("http") else storage.presign_download(path)
            except Exception:  # storage not set up locally: just no picture
                data[key.replace("_url", "_src")] = None
    for child in cfg.children:
        rows = data.get(child.payload_key) or []
        ids = [r["student_id"] for r in rows if r.get("student_id")]
        if not ids:
            continue
        found = {str(s.id): s for s in db.session.query(Student).filter(Student.id.in_(ids))}
        for r in rows:
            s = found.get(str(r.get("student_id")))
            r["student_name"] = s.full_name if s else None
            r["roll_number"] = s.roll_number if s else None
            r["section"] = s.section if s else None
    return data


@bp.post("/<resource>")
@login_required
def create_resource(resource):
    cfg = _cfg(resource)
    user = current_user()
    if not cfg.can_create(user.role):
        abort(403, description="You cannot create this record")

    payload = request.get_json(silent=True) or {}
    data = {k: payload.get(k) for k in cfg.writable if k in payload}
    for k, v in list(data.items()):
        data[k] = _coerce(cfg.model, k, v)

    # tenant stamp - never trust a client-supplied org id (spec 7.8)
    if hasattr(cfg.model, "organisation_id"):
        from app.rbac.roles import Role
        if user.role == Role.SUPER_ADMIN.value and payload.get("organisation_id"):
            data["organisation_id"] = _coerce(cfg.model, "organisation_id", payload["organisation_id"])
        elif user.role != Role.SUPER_ADMIN.value:
            data["organisation_id"] = user.organisation_id

    obj = cfg.model(**data)
    if cfg.prepare:
        err = cfg.prepare(obj, user)
        if err:
            abort(400, description=err)
    if cfg.captures_location:
        _capture_location(obj, payload, user)
    if cfg.manual_location:
        _set_manual_location(obj, payload)
    _missing_required(cfg, obj)
    guard_closed_year(obj, user, creating=True)     # nothing new in a closed year
    if hasattr(obj, "created_by"):
        obj.created_by = user.id
    db.session.add(obj)
    db.session.flush()

    # Business-rule check (e.g. a trainer logging outside their own subject).
    if cfg.validate:
        err = cfg.validate(obj, user, True)
        if err:
            db.session.rollback()
            abort(400, description=err)

    if cfg.children:
        _write_children(cfg, obj, payload, user)
    if cfg.profile_role:
        _apply_profile(cfg, obj, payload, user)
    if cfg.on_saved:
        cfg.on_saved(obj, user, True, None)
    # a new trainer / principal gets their login now; its password goes back
    # in this one response and is never shown again
    login = _create_login(cfg, obj, user) if cfg.profile_role and not obj.user_id else None

    # Verify the newly created row is inside the creator's scope.
    if not can_access_row(obj, user):
        db.session.rollback()
        abort(403, description="Record would fall outside your scope")

    audit.record(user, "create", cfg.model.__tablename__, obj.id, after=obj.to_dict())
    db.session.commit()
    out = _serialise(cfg, obj)
    if login:
        out["login"] = login
    return jsonify(out), 201


@bp.route("/<resource>/<uid>", methods=["PUT", "PATCH"])
@login_required
def update_resource(resource, uid):
    cfg = _cfg(resource)
    user = current_user()
    if cfg.locked_for(user.role):
        abort(403, description=LOCKED_MESSAGE)
    if not cfg.can_edit(user.role):
        abort(403, description="You cannot edit this record")

    obj = db.session.get(cfg.model, uid)
    if obj is None or getattr(obj, "is_deleted", False):
        abort(404)
    if not can_access_row(obj, user):
        abort(403, description="Outside your scope")
    guard_closed_year(obj, user)                    # a closed year's record stays as it is

    before = obj.to_dict()
    payload = request.get_json(silent=True) or {}
    from app.utils.masking import mask
    for k in cfg.masked_fields:
        if k in payload and payload[k] is not None and payload[k] == mask(getattr(obj, k)):
            payload = {kk: vv for kk, vv in payload.items() if kk != k}   # shown masked, sent back as-is
    for k, msg in cfg.locked_on_update.get(user.role, {}).items():
        if k in payload and str(_coerce(cfg.model, k, payload[k])) != str(getattr(obj, k)):
            abort(400, description=msg)
    old = {k: getattr(obj, k, None) for k in cfg.writable}
    for k in cfg.writable:
        if k in payload:
            setattr(obj, k, _coerce(cfg.model, k, payload[k]))
    if cfg.manual_location:
        _set_manual_location(obj, payload)
    _missing_required(cfg, obj, payload)
    guard_closed_year(obj, user, creating=True)     # nor moved into a closed year
    if hasattr(obj, "updated_by"):
        obj.updated_by = user.id
    db.session.flush()

    if cfg.validate:
        err = cfg.validate(obj, user, False)
        if err:
            db.session.rollback()
            abort(400, description=err)

    if cfg.children:
        _write_children(cfg, obj, payload, user)
    if cfg.profile_role:
        _apply_profile(cfg, obj, payload, user)
    if cfg.on_saved:
        changed = {k for k in cfg.writable if str(getattr(obj, k, None)) != str(old[k])}
        cfg.on_saved(obj, user, False, changed)

    if not can_access_row(obj, user):
        db.session.rollback()
        abort(403, description="Edit would move record outside your scope")

    audit.record(user, "update", cfg.model.__tablename__, obj.id, before=before, after=obj.to_dict())
    db.session.commit()
    return jsonify(_serialise(cfg, obj))


@bp.delete("/<resource>/<uid>")
@login_required
def delete_resource(resource, uid):
    """Nothing is deleted once saved - by anyone. Forms ask for a 30-second
    review before they save instead; mistakes are fixed by editing."""
    _cfg(resource)
    abort(403, description="Saved records can't be deleted. Edit the record to correct it.")
