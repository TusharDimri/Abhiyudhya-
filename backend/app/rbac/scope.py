"""Tenant + row-level scoping engine - spec Part 7.8.

The single place scope is *derived from the authenticated user* (never trusted
from the client). Every list/detail/write query for tenant-scoped data passes
through `apply_scope`, so isolation logic lives here, not per-endpoint.
"""
from app.rbac.roles import DISTRICT_ROLES, Role
from app.rbac.curriculum import allowed_job_role_ids


class ScopeError(PermissionError):
    """Raised when a user attempts to act outside their scope."""


def _has(model, attr):
    return hasattr(model, attr)


# Models with no direct school_id/lab_id/district_id column, but that carry a
# foreign key to an entity which does (e.g. an Assessment references a
# Student, who carries school_id/lab_id). Scoping these "through" the anchor -
# by recursively applying this same engine to the anchor model for the same
# user - keeps one source of truth per role instead of duplicating join logic
# per resource. Lazily built (avoids import cycles at module load).
def _indirect_anchors():
    from app.models.student import Student
    from app.models.operations import LabEquipment, DailyAttendance, FieldVisit, GuestLecture, ClassAttendance
    from app.models.lab import Module, Unit

    return {
        "assessment": ("student_id", Student),
        "employer_student_map": ("student_id", Student),
        "ojt_placement": ("student_id", Student),
        "equipment_maintenance": ("equipment_id", LabEquipment),
        "curriculum_unit": ("module_id", Module),
        "curriculum_session": ("unit_id", Unit),
        "attendance_student_mark": ("attendance_id", DailyAttendance),
        "field_visit_student_mark": ("field_visit_id", FieldVisit),
        "guest_lecture_student_mark": ("guest_lecture_id", GuestLecture),
        "class_attendance_student_mark": ("class_attendance_id", ClassAttendance),
    }


def _apply_indirect(query, model, user):
    """Fallback for models with no direct geographic column: scope through a
    known foreign key to an entity that does carry one (see above)."""
    from app.extensions import db

    anchor = _indirect_anchors().get(model.__tablename__)
    if not anchor:
        return query  # no known indirection - stays organisation-scoped only
    fk_name, anchor_model = anchor
    if not _has(model, fk_name):
        return query
    ids_q = apply_scope(db.session.query(anchor_model.id), anchor_model, user)
    ids = [r[0] for r in ids_q.all()] or [None]
    return query.filter(getattr(model, fk_name).in_(ids))


def apply_scope(query, model, user):
    """Restrict a query to the rows `user` is allowed to see.

    `user` is the current User object. Scope is layered:
      SA -> everything (all orgs)
      OA -> their organisation
      DM, DEPT -> their districts (via school -> district or direct district_id)
      PR -> their school
      VT -> their labs/school, and (for curriculum) only the job role(s) those
            labs actually teach (spec Part 1.3 lab job-role slots)
    """
    role = user.role

    # Super Admin sees all orgs, no scoping.
    if role == Role.SUPER_ADMIN.value:
        return query

    # Everyone else is locked to their organisation. (The organisation table
    # itself has no organisation_id - its row *is* one - so it's matched by id:
    # an org admin sees their own organisation, never the others.)
    if model.__tablename__ == "organisation":
        return query.filter(model.id == user.organisation_id)
    if _has(model, "organisation_id"):
        query = query.filter(model.organisation_id == user.organisation_id)

    if role == Role.ORG_ADMIN.value:
        return query

    if role == Role.DEPARTMENT.value and getattr(model, "raiser_own_only", False):
        return query.filter(model.raised_by == user.id)     # their own issues only
    if role in DISTRICT_ROLES:
        district_ids = [d.id for d in user.districts]
        if model.__tablename__ == "district":
            # a DM's own assigned district(s) - was previously falling through
            # to unrestricted org-wide, so the district list didn't reflect
            # what they actually manage.
            query = query.filter(model.id.in_(district_ids or [None]))
        elif _has(model, "district_id"):
            query = query.filter(model.district_id.in_(district_ids or [None]))
        elif _has(model, "linked_school_id"):   # principals
            query = query.filter(model.linked_school_id.in_(_schools_in_districts(user, district_ids)))
        elif _has(model, "school_id"):
            query = query.filter(
                model.school_id.in_(_schools_in_districts(user, district_ids))
            )
        else:
            query = _apply_indirect(query, model, user)
        return query

    if role == Role.PRINCIPAL.value:
        if model.__tablename__ == "school":
            query = query.filter(model.id == user.school_id)
        elif model.__tablename__ == "district":
            query = _filter_to_district_of(query, model, user.school_id)
        elif _has(model, "linked_school_id"):   # principals: themselves and any other at their school
            query = query.filter(model.linked_school_id == user.school_id)
        elif _has(model, "school_id"):
            query = query.filter(model.school_id == user.school_id)
        else:
            query = _apply_indirect(query, model, user)
        return query

    if role == Role.TRAINER.value:
        lab_ids = [l.id for l in user.labs]
        if getattr(model, "vt_own_only", False):
            # a trainer's own papers (e.g. their monthly attendance PDF) - not
            # a colleague's in the same lab
            from app.models.lab import Trainer
            from app.extensions import db
            mine = [r[0] for r in db.session.query(Trainer.id).filter(Trainer.user_id == user.id)]
            return query.filter(model.trainer_id.in_(mine or [None]))
        if model.__tablename__ == "school":
            query = query.filter(model.id == user.school_id)
        elif model.__tablename__ == "district":
            query = _filter_to_district_of(query, model, user.school_id)
        elif model.__tablename__ == "lab":
            query = query.filter(model.id.in_(lab_ids or [None]))
        elif model.__tablename__ == "job_role":
            # a trainer only teaches the job role(s) their lab(s) offer
            query = query.filter(model.id.in_(allowed_job_role_ids(user) or [None]))
        elif model.__tablename__ == "curriculum_module":
            query = query.filter(model.job_role_id.in_(allowed_job_role_ids(user) or [None]))
        elif _has(model, "lab_id"):
            query = query.filter(model.lab_id.in_(lab_ids or [None]))
        elif _has(model, "linked_school_id"):   # their school's principal
            query = query.filter(model.linked_school_id == user.school_id)
        elif _has(model, "school_id"):
            query = query.filter(model.school_id == user.school_id)
        else:
            query = _apply_indirect(query, model, user)
        return query

    # Unknown role -> deny.
    return query.filter(False)


def _filter_to_district_of(query, model, school_id):
    """Narrow a District query to the single district a school belongs to -
    used so PR/VT (single-school roles) see their own district, not every
    district in the organisation."""
    from app.models.geography import School
    from app.extensions import db

    if not school_id:
        return query.filter(False)
    row = db.session.query(School.district_id).filter(School.id == school_id).first()
    return query.filter(model.id == row[0]) if row else query.filter(False)


def _schools_in_districts(user, district_ids):
    from app.models.geography import School
    from app.extensions import db

    rows = (
        db.session.query(School.id)
        .filter(School.district_id.in_(district_ids or [None]))
        .all()
    )
    return [r[0] for r in rows] or [None]


def can_access_row(instance, user):
    """Object-level check reusing the query engine for a single row."""
    from app.extensions import db

    model = type(instance)
    q = apply_scope(db.session.query(model).filter(model.id == instance.id), model, user)
    return db.session.query(q.exists()).scalar()


def enforce_org_on_write(data, user):
    """Stamp organisation_id from the user on writes; SA must supply it."""
    if user.role != Role.SUPER_ADMIN.value:
        data["organisation_id"] = user.organisation_id
    return data
