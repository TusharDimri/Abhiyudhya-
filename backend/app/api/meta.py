"""Metadata + upload endpoints consumed by the frontend.

- /meta/bootstrap: reference lists for dropdowns (scoped), role + resource catalog.
- /uploads/presign: S3/MinIO pre-signed upload URL (spec 6.5).
"""
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.api.registry import REGISTRY
from app.rbac import login_required, current_user, apply_scope
from app.rbac.roles import ROLE_LABELS, Role
from app.models.masters import Sector, JobRole, SocialCategory, AcademicYear
from app.models.geography import State, District, School, Principal
from app.models.lab import Lab, Trainer
from app.api.enums import ENUMS
from app.services import storage
from app.services.cache import cached_json

bp = Blueprint("meta", __name__, url_prefix="/api")


def _options(model, user, label_attr="name", extra=None):
    q = db.session.query(model).filter(model.is_deleted.is_(False))
    q = apply_scope(q, model, user).limit(1000)
    out = []
    for r in q.all():
        item = {"value": str(r.id), "label": getattr(r, label_attr, str(r.id))}
        if extra:
            item.update(extra(r))
        out.append(item)
    return out


def _lab_extra(lab):
    """Everything a form needs to work out, from a chosen lab, what the job
    role and section options are - so the trainer never types them."""
    sid = lambda v: str(v) if v else None  # noqa: E731
    return {
        "school_id": sid(lab.school_id),
        "sector_id": sid(lab.sector_id),
        "job_role_9_10_id": sid(lab.job_role_9_10_id),
        "job_role_11_12_id": sid(lab.job_role_11_12_id),
        "curriculum_level": lab.curriculum_level,
        "sections": {g: lab.sections_for(g) for g in ("9", "10", "11", "12")},
    }


def _org_branding(user):
    from app.models.organisation import Organisation
    if not user.organisation_id:
        return None
    org = db.session.get(Organisation, user.organisation_id)
    if not org:
        return None
    return {
        "id": str(org.id), "name": org.name, "org_code": org.org_code,
        "logo_url": org.logo_url,
    }


def _current_academic_year(user):
    q = db.session.query(AcademicYear).filter(
        AcademicYear.is_deleted.is_(False), AcademicYear.is_current.is_(True)
    )
    ay = apply_scope(q, AcademicYear, user).first()
    return ay.label if ay else None


def _user_profile(user):
    """Everything we already know about this user - used by the frontend to
    pre-fill and hide form fields so each role only fills what it must.

    Nothing here is a security boundary (scope.py still enforces that); it is
    purely "don't ask a user for something we already know."
    """
    profile = {}
    ay = _current_academic_year(user)
    if ay:
        profile["academic_year"] = ay
    if user.school_id:
        profile["school_id"] = str(user.school_id)
        school = db.session.get(School, user.school_id)
        if school and school.district_id:
            # single-school roles (PR/VT) sit in exactly one district too
            profile["district_id"] = str(school.district_id)

    if user.role in (Role.DISTRICT_MANAGER.value, Role.DEPARTMENT.value) and len(user.districts) == 1:
        profile["district_id"] = str(user.districts[0].id)

    if user.role == Role.TRAINER.value:
        from app.models.lab import Trainer
        from app.rbac.curriculum import allowed_job_role_ids
        tr = db.session.query(Trainer).filter(
            Trainer.user_id == user.id, Trainer.is_deleted.is_(False)
        ).first()
        if tr:
            profile["trainer_id"] = str(tr.id)
        labs = user.labs
        if len(labs) == 1:
            profile["lab_id"] = str(labs[0].id)
        # only pre-fill job role when the lab(s) leave no ambiguity
        jr = allowed_job_role_ids(user)
        if len(jr) == 1:
            profile["job_role_id"] = str(next(iter(jr)))
    return profile


def _year_labels(user):
    from datetime import date
    from app.services.academic_year import academic_year_for
    configured = {r.label for r in apply_scope(
        db.session.query(AcademicYear).filter(AcademicYear.is_deleted.is_(False)), AcademicYear, user)}
    today = date.today()
    recent = {academic_year_for(user.organisation_id, date(today.year - k, today.month, min(today.day, 28)))
              for k in range(0, 5)}
    return sorted(configured | recent, reverse=True)


@bp.get("/meta/bootstrap")
@login_required
@cached_json("bootstrap", ttl=300)
def bootstrap():
    user = current_user()
    is_platform_admin = user.role == Role.SUPER_ADMIN.value

    my_scope = {"profile": _user_profile(user)}
    if user.role == Role.TRAINER.value:
        from app.rbac.curriculum import class_grades_by_job_role
        my_scope["class_grades_by_job_role"] = class_grades_by_job_role(user)

    org_options = []
    if is_platform_admin:
        from app.models.organisation import Organisation
        org_options = [
            {"value": str(o.id), "label": o.name}
            for o in db.session.query(Organisation)
            .filter(Organisation.is_deleted.is_(False))
            .order_by(Organisation.name.asc()).all()
        ]

    return jsonify({
        "role": user.role,
        "role_label": ROLE_LABELS.get(Role(user.role), user.role),
        "organisation": _org_branding(user),
        "is_platform_admin": is_platform_admin,
        "my_scope": my_scope,
        # fixed option lists (spec-defined, not editable masters) - served from
        # one place so the dropdown and the server rule can't drift apart
        "enums": ENUMS,
        "resources": {
            name: {
                "label": cfg.label,
                "can_write": cfg.can_create(user.role),
                "can_edit": cfg.can_edit(user.role),
                "filters": cfg.filters,
                "sortable": cfg.sortable,
                "search": cfg.search,
                "date_field": cfg.date_field,
            }
            # only resources this role may view (drives nav + access)
            for name, cfg in REGISTRY.items()
            if not cfg.view_roles or user.role in cfg.view_roles
        },
        "options": {
            "sectors": _options(Sector, user),
            "job_roles": _options(JobRole, user, extra=lambda r: {"nsqf_level": r.nsqf_level, "class_band": r.class_band}),
            "social_categories": _options(SocialCategory, user),
            "academic_years": _options(AcademicYear, user, label_attr="label", extra=lambda r: {"is_current": r.is_current}),
            # every year worth filtering by: the ones set up, and (since a
            # record's year follows its date) this school year and the last few
            "year_labels": _year_labels(user),
            "states": _options(State, user),
            "districts": _options(District, user),
            "schools": _options(School, user, extra=lambda r: {
                "district_id": str(r.district_id) if r.district_id else None,
                "udise_code": r.udise_code,
                "principal_id": str(r.principal_id) if r.principal_id else None,
            }),
            "labs": _options(Lab, user, extra=_lab_extra),
            "principals": _options(Principal, user, label_attr="full_name", extra=lambda r: {
                "linked_school_id": str(r.linked_school_id) if r.linked_school_id else None,
            }),
            "trainers": _options(Trainer, user, label_attr="full_name", extra=lambda r: {
                "school_id": str(r.school_id) if r.school_id else None,
                "lab_id": str(r.lab_id) if r.lab_id else None,
                "job_role_id": str(r.job_role_id) if r.job_role_id else None,
            }),
            "organisations": org_options,  # populated for Super Admin only
        },
    })


@bp.post("/location/seal")
@login_required
def seal_location():
    """Sign a fix the browser just took, so it can be kept client-side
    without being editable (services/location_seal.py)."""
    from app.services.location_seal import LocationError, seal
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(seal(current_user().id, data.get("lat"), data.get("lng"),
                            data.get("accuracy"), data.get("captured_at")))
    except LocationError as exc:
        return jsonify({"error": "bad_location", "message": str(exc)}), 400


@bp.post("/uploads/presign")
@login_required
def presign():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "file")
    content_type = data.get("content_type", "application/octet-stream")
    try:
        return jsonify(storage.presign_upload(filename, content_type))
    except Exception as exc:  # storage may be unconfigured locally
        return jsonify({"error": "storage_unavailable", "detail": str(exc)}), 503
