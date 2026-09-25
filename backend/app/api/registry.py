"""Declarative resource registry.

Instead of 25 hand-written CRUD blueprints, every module is described once here
and the resource factory (resource.py) turns each entry into a fully
scoped, audited, paginated REST resource. This keeps the list/filter/pagination
+ RBAC pattern identical everywhere (spec Part 7.2).

Each ResourceConfig declares:
  model         SQLAlchemy model
  name          URL slug (/api/<name>)
  label         human label
  write_roles   roles allowed to create/update/delete
  search        columns matched by ?search=
  filters       columns exposed as ?<col>=value
  sortable      columns allowed in ?sort=
  default_sort  (column, direction)
  writable      input fields accepted on create/update (whitelist)
  computed      extra read-only fields added to serialised output
  children      nested collections written/read with the parent record
                (e.g. the per-student present/absent marks on an attendance
                entry) - see ChildCollection
"""
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from app import models as M
from app.rbac.roles import Role

SA = Role.SUPER_ADMIN.value
OA = Role.ORG_ADMIN.value
DM = Role.DISTRICT_MANAGER.value
PR = Role.PRINCIPAL.value
VT = Role.TRAINER.value


ALL_ROLES = [SA, OA, DM, PR, VT]


@dataclass
class ChildCollection:
    """A collection written and read with its parent in one request.

    Student attendance marks belong to the attendance entry that records them -
    asking the trainer to save the entry and then visit a second screen to mark
    the class would be two round trips for one action. The parent resource
    accepts `payload_key` in its body and returns it on read.
    """
    payload_key: str
    model: type
    parent_fk: str
    fields: List[str]


@dataclass
class ResourceConfig:
    name: str
    model: type
    label: str
    write_roles: List[str]
    writable: List[str]
    search: List[str] = field(default_factory=list)
    filters: List[str] = field(default_factory=list)
    sortable: List[str] = field(default_factory=list)
    default_sort: Tuple[str, str] = ("created_at", "desc")
    computed: Optional[Callable] = None
    # roles allowed to VIEW/list this resource (drives nav + API access).
    # None -> defaults applied from VIEW_ROLES below (see _finalise).
    view_roles: Optional[List[str]] = None
    # column used for date-range filtering on dashboards/reports
    date_field: Optional[str] = None
    # business-rule check run after create/update, before commit:
    # (instance, user, is_create) -> error message string, or None if valid.
    validate: Optional[Callable] = None
    # nested collections saved/returned with the parent record
    children: List[ChildCollection] = field(default_factory=list)
    # query params that need more than a column comparison:
    # {param: (query, model, value) -> query}
    extra_filters: dict = field(default_factory=dict)
    # fields a role may set when creating but never change afterwards:
    # {role: {field: message shown when they try}}
    locked_on_update: dict = field(default_factory=dict)
    # stamp new records with where the user was (model mixes in
    # CapturesLocation); required from trainers
    captures_location: bool = False
    # a `location` point typed in by an admin (location_lat / location_lng) -
    # e.g. where a school is
    manual_location: bool = False


REGISTRY = {}


def register(cfg: ResourceConfig):
    REGISTRY[cfg.name] = cfg
    return cfg


# ---- helpers for computed display fields (keeps list screens readable) ----
def _school_name(obj):
    return {"school_name": obj.school.name if getattr(obj, "school", None) else None}


def _student_name(obj):
    from app.extensions import db
    if getattr(obj, "student_id", None):
        s = db.session.get(M.Student, obj.student_id)
        return {"student_name": s.full_name if s else None}
    return {}


# ---- VT association enforcement -----------------------------------------
# A trainer's daily-entry records must stay inside the subject/class-band
# their own lab(s) actually teach (derived in rbac/curriculum.py from lab
# assignment, spec Part 1.3). Higher roles (SA/OA/DM) keep full authority to
# correct data across the org, matching the existing RBAC matrix - only VT is
# restricted here.
def _own_job_role_validator(job_role_field="job_role_id"):
    def _validate(instance, user, is_create=False):
        if user.role != VT:
            return None
        jr = getattr(instance, job_role_field, None)
        if jr is None:
            return None
        from app.rbac.curriculum import allowed_job_role_ids
        allowed = {str(x) for x in allowed_job_role_ids(user)}
        if str(jr) not in allowed:
            return "This job role is not taught in your assigned lab(s)."
        return None
    return _validate


# A record can be back-dated but not forward-dated. One day of slack: the
# server runs on UTC while trainers are on IST, so "today" for a trainer just
# after midnight is still "tomorrow" here.
def _future_date_error(value, label="Date"):
    from datetime import date, timedelta
    if value and value > date.today() + timedelta(days=1):
        return f"{label} can't be in the future."
    return None


def _equipment_display(obj):
    from app.extensions import db
    lab = db.session.get(M.Lab, obj.lab_id) if obj.lab_id else None
    tr = db.session.get(M.Trainer, obj.trainer_id) if obj.trainer_id else None
    return {"lab_name": lab.name if lab else None,
            "trainer_name": tr.full_name if tr else None}


def _validate_equipment(instance, user, is_create=False):
    from app.extensions import db

    if not (instance.name or "").strip():
        return "Give the equipment a name."
    if not instance.lab_id:
        return "Choose the lab this equipment belongs to."
    err = _future_date_error(instance.receipt_date)
    if err:
        return err

    # the school always follows the lab - never asked for, never out of step
    lab = db.session.get(M.Lab, instance.lab_id)
    instance.school_id = lab.school_id if lab else None

    if user.role == VT and is_create:
        # A trainer's equipment is theirs. Handing it to someone else is the
        # Principal's call (when a trainer leaves), not the trainer's - see
        # locked_on_update on the resource.
        own = db.session.query(M.Trainer.id).filter(
            M.Trainer.user_id == user.id, M.Trainer.is_deleted.is_(False)
        ).first()
        if not own:
            return "Your login isn't linked to a trainer profile yet - ask your admin."
        instance.trainer_id = own[0]
    elif not instance.trainer_id:
        return "Choose the trainer responsible for this equipment."
    return None


def _validate_guest_lecture(instance, user, is_create=False):
    from app.extensions import db

    if not (instance.lecturer_name or "").strip():
        return "Enter the guest lecturer's name."
    if not (instance.topic or "").strip():
        return "Enter the topic covered."
    if not instance.lab_id:
        return "Choose the lab."
    if not instance.class_grade:
        return "Choose the class."
    if not instance.reporting_date:
        return "Enter the date."
    err = _future_date_error(instance.reporting_date)
    if err:
        return err
    # the school always follows the lab, and the year always follows the date
    # (it is what yearly targets are counted by - api/targets.py)
    from app.services.academic_year import academic_year_for
    lab = db.session.get(M.Lab, instance.lab_id)
    instance.school_id = lab.school_id if lab else None
    instance.academic_year = academic_year_for(instance.organisation_id, instance.reporting_date)
    return _own_job_role_validator()(instance, user, is_create)


def _validate_field_visit(instance, user, is_create=False):
    from app.extensions import db

    if not (instance.organisation_name or "").strip() and not (instance.address or "").strip():
        return "Enter the organisation visited and its address."
    if not instance.lab_id:
        return "Choose the lab."
    if not instance.job_role_id:
        return "Choose the job role."
    if not instance.class_grade:
        return "Choose the class."
    if not instance.reporting_date:
        return "Enter the date."
    err = _future_date_error(instance.reporting_date)
    if err:
        return err
    # the school always follows the lab, and the year always follows the date
    # (it is what yearly targets are counted by - api/targets.py)
    from app.services.academic_year import academic_year_for
    lab = db.session.get(M.Lab, instance.lab_id)
    instance.school_id = lab.school_id if lab else None
    instance.academic_year = academic_year_for(instance.organisation_id, instance.reporting_date)
    err = _own_job_role_validator()(instance, user, is_create)
    if err or user.role != VT:
        return err
    from app.rbac.curriculum import allowed_class_grades
    if str(instance.class_grade) not in allowed_class_grades(user, instance.job_role_id):
        return f"Class {instance.class_grade} is not taught under this job role in your lab."
    return None


def _own_trainer_id(user):
    from app.extensions import db
    row = db.session.query(M.Trainer.id).filter(
        M.Trainer.user_id == user.id, M.Trainer.is_deleted.is_(False)
    ).first()
    return row[0] if row else None


def _attendance_day_error(instance, user, is_create):
    """A trainer marks attendance for today only - it is checked against where
    they are right now. (One day either side: the server runs on UTC.)"""
    from datetime import date, timedelta
    if not instance.date:
        return "Enter the date."
    if user.role == VT and is_create and abs(instance.date - date.today()) > timedelta(days=1):
        return "Attendance can only be marked for today."
    return _future_date_error(instance.date)


def _endorsement_on_edit(instance, user, is_create):
    """A trainer's attendance, once the Principal endorsed it, is final. One
    they returned goes back to them for endorsement when corrected."""
    if is_create or user.role != VT:
        return None
    if instance.endorsement_status == "endorsed":
        return "The Principal has endorsed this entry, so it can't be changed."
    if instance.endorsement_status == "returned":
        instance.endorsement_status = "submitted"
    return None


def _validate_vt_attendance(instance, user, is_create=False):
    from app.extensions import db
    from app.models.geo import school_distance_error
    from app.services.academic_year import academic_year_for

    err = _endorsement_on_edit(instance, user, is_create)
    if err:
        return err
    if not instance.lab_id:
        return "Choose the lab."
    err = _attendance_day_error(instance, user, is_create)
    if err:
        return err
    lab = db.session.get(M.Lab, instance.lab_id)
    instance.school_id = lab.school_id if lab else None
    instance.academic_year = academic_year_for(instance.organisation_id, instance.date)
    if not instance.day_type:
        instance.day_type = "Working day"

    if user.role == VT and is_create:
        own = _own_trainer_id(user)
        if not own:
            return "Your login isn't linked to a trainer profile yet - ask your admin."
        instance.trainer_id = own
        # once a day
        already = db.session.query(M.DailyAttendance.id).filter(
            M.DailyAttendance.trainer_id == own,
            M.DailyAttendance.date == instance.date,
            M.DailyAttendance.is_deleted.is_(False),
            M.DailyAttendance.id != instance.id,
        ).first()
        if already:
            return f"You've already marked your attendance for {instance.date:%d/%m/%Y}."
        return school_distance_error(instance, instance.school_id)
    return None


def _trainer_name(obj):
    from app.extensions import db
    tr = db.session.get(M.Trainer, obj.trainer_id) if obj.trainer_id else None
    return tr.full_name if tr else None


def _attendance_display(obj):
    return {**_school_name(obj), "trainer_name": _trainer_name(obj)}


def _class_attendance_display(obj):
    marks = [m for m in obj.student_marks if not m.is_deleted]
    present = sum(1 for m in marks if m.present)
    return {"trainer_name": _trainer_name(obj), "attended_count": present,
            "attended": f"{present} of {len(marks)}" if marks else None}


def _validate_class_attendance(instance, user, is_create=False):
    from app.extensions import db
    from app.models.geo import school_distance_error
    from app.services.academic_year import academic_year_for

    err = _endorsement_on_edit(instance, user, is_create)
    if err:
        return err
    if not instance.lab_id:
        return "Choose the lab."
    if not instance.class_grade:
        return "Choose the class."
    if not (instance.activity or "").strip():
        return "Describe the activity."
    err = _attendance_day_error(instance, user, is_create)
    if err:
        return err
    lab = db.session.get(M.Lab, instance.lab_id)
    instance.school_id = lab.school_id if lab else None
    instance.academic_year = academic_year_for(instance.organisation_id, instance.date)
    if lab and not instance.job_role_id:
        instance.job_role_id = lab.job_role_for(instance.class_grade)

    if user.role != VT:
        return None
    err = _own_job_role_validator()(instance, user, is_create)
    if err:
        return err
    from app.rbac.curriculum import allowed_class_grades
    if instance.job_role_id and str(instance.class_grade) not in allowed_class_grades(user, instance.job_role_id):
        return f"Class {instance.class_grade} is not taught under this job role in your lab."
    if is_create:
        own = _own_trainer_id(user)
        if not own:
            return "Your login isn't linked to a trainer profile yet - ask your admin."
        instance.trainer_id = own
        return school_distance_error(instance, instance.school_id)
    return None


def _maintenance_display(obj):
    from app.extensions import db
    eq = db.session.get(M.LabEquipment, obj.equipment_id) if obj.equipment_id else None
    return {"equipment_name": eq.name if eq else None}


def _validate_maintenance(instance, user, is_create=False):
    from app.api import enums
    if not instance.equipment_id:
        return "Choose the equipment."
    if not (instance.issue or "").strip():
        return "Describe the issue."
    if instance.maintenance_status and instance.maintenance_status not in enums.values("maintenance_status"):
        return "Pick a valid status."
    return _future_date_error(instance.date)


def _validate_curriculum_module(instance, user, is_create=False):
    return _own_job_role_validator()(instance, user, is_create)


def _validate_issue(instance, user, is_create=False):
    """A trainer reports an issue in their own words, on a date and time, from
    where they are. (The older categorised fields - main/sub issue, students
    affected - are no longer asked for; their columns keep past answers.)"""
    from app.extensions import db

    if not (instance.details or "").strip():
        return "Describe the issue."
    if not instance.lab_id:
        return "Choose the lab."
    err = _future_date_error(instance.reporting_date)
    if err:
        return err
    if user.role == VT and is_create:
        # an issue is reported by the trainer themselves
        own = db.session.query(M.Trainer.id).filter(
            M.Trainer.user_id == user.id, M.Trainer.is_deleted.is_(False)
        ).first()
        if not own:
            return "Your login isn't linked to a trainer profile yet - ask your admin."
        instance.trainer_id = own[0]
    return None


def _validate_student(instance, user, is_create=False):
    """Registration happens in Class 9 and Class 11 only (spec 2.6); a student
    reaches 10 or 12 by being promoted, not by being registered there."""
    if instance.class_grade and str(instance.class_grade) not in ("9", "10", "11", "12"):
        return "Class must be 9, 10, 11 or 12."
    if is_create and str(instance.class_grade) in ("10", "12"):
        return ("Students are registered in Class 9 or Class 11 only. A Class "
                f"{instance.class_grade} student is created by verifying/promoting "
                "their existing Class " + ("9" if instance.class_grade == "10" else "11")
                + " record.")
    return None


def _validate_trainer(instance, user, is_create=False):
    """One trainer per job role in a lab (spec 1.5) - a second active trainer
    on the same slot would make 'whose class is this?' ambiguous."""
    from app.extensions import db

    if not instance.lab_id or not instance.job_role_id:
        return None
    if instance.trainer_status == "exited":
        return None
    clash = (
        db.session.query(M.Trainer)
        .filter(
            M.Trainer.lab_id == instance.lab_id,
            M.Trainer.job_role_id == instance.job_role_id,
            M.Trainer.id != instance.id,
            M.Trainer.is_deleted.is_(False),
            M.Trainer.trainer_status != "exited",
        )
        .first()
    )
    if clash:
        return (f"{clash.full_name} already holds this job role in this lab. "
                "Mark them as exited/substitute first, or pick the other job role.")
    return None


def _validate_lab(instance, user, is_create=False):
    """A lab teaches a 9-10 role and an 11-12 role; both slots may hold the
    same role, but each must belong to the band it is filed under."""
    from app.extensions import db

    for field_name, band in (("job_role_9_10_id", "9-10"), ("job_role_11_12_id", "11-12")):
        jr_id = getattr(instance, field_name)
        if not jr_id:
            continue
        jr = db.session.get(M.JobRole, jr_id)
        if jr and jr.class_band and jr.class_band != band:
            return f"'{jr.name}' is a {jr.class_band} job role - it cannot fill the {band} slot."
    return None


# =========================================================================
#  PART 1 - CORE / MASTER DATA
# =========================================================================
register(ResourceConfig(
    name="organisations", model=M.Organisation, label="Organisation",
    write_roles=[SA],
    writable=["name", "legal_name", "org_code", "logo_url", "primary_contact_name",
              "primary_contact_email", "primary_contact_phone", "registered_address",
              "affiliation_cert_number", "affiliation_valid_till", "status"],
    search=["name", "org_code", "legal_name"],
    filters=[], sortable=["name", "org_code", "created_at"],
    default_sort=("name", "asc"),
))

register(ResourceConfig(
    name="states", model=M.State, label="State",
    write_roles=[SA, OA],
    writable=["name", "code", "status"],
    search=["name", "code"], filters=[], sortable=["name"],
    default_sort=("name", "asc"),
))

register(ResourceConfig(
    name="districts", model=M.District, label="District",
    write_roles=[SA, OA],
    writable=["name", "code", "state_id", "status"],
    search=["name", "code"], filters=["state_id"], sortable=["name"],
    default_sort=("name", "asc"),
))

register(ResourceConfig(
    name="schools", model=M.School, label="School",
    write_roles=[SA, OA, DM],
    writable=["name", "udise_code", "district_id", "block", "principal_id",
              "school_type", "address", "email", "phone", "status"],
    search=["name", "udise_code", "block"],
    filters=["district_id", "block"],
    sortable=["name", "udise_code", "created_at"], default_sort=("name", "asc"),
    computed=lambda o: {"district_name": o.district.name if o.district else None},
    manual_location=True,
))

register(ResourceConfig(
    name="principals", model=M.Principal, label="Principal / Headmaster",
    write_roles=[SA, OA, DM],
    writable=["full_name", "mobile", "email", "gender", "years_in_school",
              "date_of_joining", "date_of_resignation", "linked_school_id",
              "designation", "employee_id", "appointment_nature", "user_id", "status"],
    search=["full_name", "email", "mobile"],
    filters=["linked_school_id"], sortable=["full_name", "created_at"],
    default_sort=("full_name", "asc"),
))

register(ResourceConfig(
    name="labs", model=M.Lab, label="Lab",
    write_roles=[SA, OA, DM],
    writable=["name", "sector_id", "school_id", "job_role_9_10_id",
              "job_role_11_12_id", "curriculum_level", "sections_per_class",
              "sections_9", "sections_10", "sections_11", "sections_12",
              "academic_year_of_setup", "status"],
    search=["name"], filters=["school_id", "sector_id"],
    sortable=["name", "created_at"], default_sort=("name", "asc"),
    computed=_school_name,
    validate=_validate_lab,
))

register(ResourceConfig(
    name="trainers", model=M.Trainer, label="Vocational Trainer",
    write_roles=[SA, OA, DM],
    writable=["full_name", "school_id", "lab_id", "job_role_id", "email", "phone",
              "gender", "date_of_joining", "date_of_exit", "trainer_status",
              "qualification", "vtp_name", "appointment_nature", "user_id", "status"],
    search=["full_name", "email", "phone"],
    filters=["school_id", "lab_id", "trainer_status"],
    sortable=["full_name", "created_at"], default_sort=("full_name", "asc"),
    computed=_school_name,
    validate=_validate_trainer,
))

# ---- masters ----
register(ResourceConfig(
    name="academic-years", model=M.AcademicYear, label="Academic Year",
    write_roles=[SA, OA],
    writable=["label", "start_date", "end_date", "is_current", "status"],
    search=["label"], filters=["is_current"], sortable=["label"],
    default_sort=("label", "desc"),
))
register(ResourceConfig(
    name="sectors", model=M.Sector, label="Sector / Trade",
    write_roles=[SA, OA, DM],
    writable=["name", "code", "status"], search=["name", "code"],
    filters=[], sortable=["name"], default_sort=("name", "asc"),
))
register(ResourceConfig(
    name="job-roles", model=M.JobRole, label="Job Role",
    write_roles=[SA, OA, DM],
    writable=["name", "sector_id", "qp_code", "nsqf_level", "class_band", "status"],
    search=["name", "qp_code"], filters=["sector_id", "nsqf_level", "class_band"],
    sortable=["name", "nsqf_level"], default_sort=("name", "asc"),
    computed=lambda o: {"sector_name": o.sector.name if o.sector else None},
))
register(ResourceConfig(
    name="social-categories", model=M.SocialCategory, label="Social Category",
    write_roles=[SA, OA],
    writable=["name", "status"], search=["name"], sortable=["name"],
    default_sort=("name", "asc"),
))

# ---- curriculum tree ----
register(ResourceConfig(
    name="modules", model=M.Module, label="Curriculum Module",
    write_roles=[SA, OA, DM, VT],
    writable=["job_role_id", "nsqf_level", "name", "module_type", "sort_order", "status"],
    search=["name"], filters=["job_role_id", "nsqf_level", "module_type"],
    sortable=["sort_order", "name"], default_sort=("sort_order", "asc"),
    validate=_validate_curriculum_module,
))
register(ResourceConfig(
    name="units", model=M.Unit, label="Curriculum Unit",
    write_roles=[SA, OA, DM, VT],
    writable=["module_id", "name", "sort_order", "status"],
    search=["name"], filters=["module_id"], sortable=["sort_order", "name"],
    default_sort=("sort_order", "asc"),
))
def _any_section(query, model, value):
    """?section=B on a record covering several sections ("A,B"): the ones
    that include B. Several at once (?section=A,C) means any of them."""
    from sqlalchemy import func, or_
    wanted = [s.strip() for s in str(value).split(",") if s.strip()]
    padded = func.concat(",", func.replace(model.sections, " ", ""), ",")
    return query.filter(or_(*[padded.like(f"%,{s},%") for s in wanted])) if wanted else query


def _sessions_by_module(query, model, value):
    """?module_id= on sessions - a visit or lecture covers several units at
    once, so its session picker is scoped by module, not by one unit."""
    from app.extensions import db
    unit_ids = [
        r[0] for r in db.session.query(M.Unit.id)
        .filter(M.Unit.module_id == value, M.Unit.is_deleted.is_(False)).all()
    ]
    return query.filter(model.unit_id.in_(unit_ids or [None]))


register(ResourceConfig(
    name="sessions", model=M.Session, label="Curriculum Session",
    write_roles=[SA, OA, DM, VT],
    writable=["unit_id", "name", "sort_order", "status"],
    search=["name"], filters=["unit_id"], sortable=["sort_order", "name"],
    default_sort=("sort_order", "asc"),
    extra_filters={"module_id": _sessions_by_module},
))

# =========================================================================
#  PART 2 - STUDENT LIFECYCLE
# =========================================================================
register(ResourceConfig(
    name="students", model=M.Student, label="Student",
    # Only the trainer registers and maintains students; every other role just
    # views them. Verification is a separate workflow (workflow.py), not a write.
    # Students are records only - they never get a login.
    write_roles=[VT],
    writable=["school_id", "lab_id", "job_role_id", "academic_year", "class_grade",
              "section", "roll_number", "first_name", "middle_name", "last_name",
              "gender", "dob", "email", "father_name", "mother_name", "guardian_name",
              "stream", "mobile_primary", "mobile_secondary", "whatsapp_number",
              "cwsn", "social_category_id", "date_of_enrolment", "photo_url",
              "had_vocational_9_10", "continuing_same_trade", "verification_status",
              "verification_remarks", "status"],
    search=["first_name", "last_name", "roll_number", "email"],
    filters=["school_id", "lab_id", "job_role_id", "class_grade", "section",
             "academic_year", "verification_status", "enrolment_status", "cwsn"],
    sortable=["first_name", "roll_number", "created_at"],
    default_sort=("created_at", "desc"),
    computed=lambda o: {"full_name": o.full_name, **_school_name(o)},
    validate=_validate_student,
    # a trainer moves students up through Promote, not by editing them
    locked_on_update={VT: {
        "class_grade": "A student's class changes through Promote Students at the end of the year.",
        "academic_year": "A student's year changes through Promote Students at the end of the year.",
    }},
))
register(ResourceConfig(
    name="assessments", model=M.Assessment, label="Assessment / Marks",
    write_roles=[SA, OA, DM, VT],
    writable=["student_id", "academic_year", "class_grade", "job_role_id", "nsqf_level",
              "assessment_type", "name", "date", "max_marks", "marks_obtained",
              "result", "level_certification_status", "certificate_number",
              "remarks", "evidence_url", "status"],
    search=["name", "certificate_number"],
    filters=["student_id", "academic_year", "assessment_type", "result", "nsqf_level"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
    computed=_student_name,
))

# =========================================================================
#  PART 3 - DAILY OPERATIONS
# =========================================================================
register(ResourceConfig(
    name="attendance", model=M.DailyAttendance, label="Daily Attendance",
    write_roles=[SA, OA, DM, VT],
    # the trainer's own daily attendance: date, time, photo, comment - and where
    # they were (within 1 km of the school). Older activity-branch columns keep
    # past answers but are no longer written.
    writable=["trainer_id", "lab_id", "date", "attendance_time", "photo_url", "details", "status"],
    search=["details"],
    filters=["trainer_id", "lab_id", "academic_year", "date", "endorsement_status"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
    computed=_attendance_display,
    validate=_validate_vt_attendance,
    captures_location=True,
    children=[ChildCollection("student_marks", M.AttendanceStudentMark,
                              "attendance_id", ["student_id", "present"])],
))
register(ResourceConfig(
    name="class-attendance", model=M.ClassAttendance, label="Class Attendance",
    write_roles=[SA, OA, DM, VT],
    writable=["trainer_id", "lab_id", "job_role_id", "date", "time", "class_grade",
              "sections", "activity", "photo_url", "comment", "status"],
    search=["activity", "comment"],
    filters=["trainer_id", "lab_id", "academic_year", "class_grade", "section", "date", "endorsement_status"],
    extra_filters={"section": _any_section},
    sortable=["date", "created_at"], default_sort=("date", "desc"),
    computed=_class_attendance_display,
    validate=_validate_class_attendance,
    captures_location=True,
    children=[ChildCollection("student_marks", M.ClassAttendanceStudentMark,
                              "class_attendance_id", ["student_id", "present"])],
))
register(ResourceConfig(
    name="issues", model=M.VTIssue, label="VT Issue",
    write_roles=[SA, OA, DM, VT],
    writable=["trainer_id", "lab_id", "academic_year", "reporting_date", "reporting_time",
              "details", "workflow_status", "assigned_to", "resolution_note", "status"],
    search=["details"],
    filters=["trainer_id", "lab_id", "workflow_status", "academic_year"],
    sortable=["reporting_date", "created_at"], default_sort=("reporting_date", "desc"),
    validate=_validate_issue,
    captures_location=True,
))
register(ResourceConfig(
    name="field-visits", model=M.FieldVisit, label="Field / Industry Visit",
    write_roles=[SA, OA, DM, VT],
    writable=["lab_id", "job_role_id", "class_grade", "sections", "academic_year",
              "reporting_date", "purpose", "activities", "organisation_name", "address",
              "picture_url", "contact_person", "contact_mobile", "contact_email",
              "contact_designation", "status"],
    search=["organisation_name", "address", "purpose"],
    filters=["lab_id", "job_role_id", "academic_year", "class_grade", "section"],
    extra_filters={"section": _any_section},
    sortable=["reporting_date", "created_at"], default_sort=("reporting_date", "desc"),
    computed=_school_name,
    validate=_validate_field_visit,
    captures_location=True,
    children=[ChildCollection("student_marks", M.FieldVisitStudentMark,
                              "field_visit_id", ["student_id", "present"])],
))
register(ResourceConfig(
    name="guest-lectures", model=M.GuestLecture, label="Guest Lecture",
    write_roles=[SA, OA, DM, VT],
    writable=["lab_id", "job_role_id", "class_grade", "sections", "academic_year",
              "reporting_date", "topic", "photo_url", "lecturer_name",
              "lecturer_qualification", "lecturer_phone", "lecturer_email",
              "lecturer_experience", "status"],
    search=["topic", "lecturer_name"],
    filters=["lab_id", "academic_year", "class_grade", "section"],
    extra_filters={"section": _any_section},
    sortable=["reporting_date", "created_at"], default_sort=("reporting_date", "desc"),
    computed=_school_name,
    validate=_validate_guest_lecture,
    captures_location=True,
    children=[ChildCollection("student_marks", M.GuestLectureStudentMark,
                              "guest_lecture_id", ["student_id", "present"])],
))
register(ResourceConfig(
    name="equipment", model=M.LabEquipment, label="Lab Equipment",
    write_roles=[SA, OA, DM, VT],
    writable=["trainer_id", "lab_id", "name", "receipt_date", "details",
              "photo_url", "note", "status"],
    search=["name", "details", "note"], filters=["lab_id", "trainer_id"],
    sortable=["name", "receipt_date", "created_at"], default_sort=("created_at", "desc"),
    computed=_equipment_display,
    validate=_validate_equipment,
    locked_on_update={VT: {"trainer_id": "Only the Principal can reassign equipment to another trainer."}},
))
register(ResourceConfig(
    name="equipment-maintenance", model=M.EquipmentMaintenance, label="Maintenance Log",
    write_roles=[SA, OA, DM, VT],
    writable=["equipment_id", "date", "issue", "maintenance_status", "note", "status"],
    search=["issue", "note"], filters=["equipment_id", "maintenance_status"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
    computed=_maintenance_display,
    validate=_validate_maintenance,
))

# =========================================================================
#  PART 4 - INTERNSHIP / OJT / PLACEMENT
# =========================================================================
register(ResourceConfig(
    name="employers", model=M.Employer, label="Employer",
    write_roles=[SA, OA, DM, VT],
    writable=["first_name", "last_name", "gender", "org_name", "business_description",
              "employee_count", "year_of_foundation", "sector_id", "is_active",
              "branch_name", "branch_address", "poc_mobile", "poc_email", "state",
              "district", "pincode", "status"],
    search=["org_name", "poc_email", "poc_mobile"],
    filters=["sector_id", "is_active", "state", "district"],
    sortable=["org_name", "created_at"], default_sort=("org_name", "asc"),
))
register(ResourceConfig(
    name="employer-student-maps", model=M.EmployerStudentMap, label="Employer-Student Map",
    write_roles=[SA, OA, DM, VT],
    writable=["student_id", "employer_id", "job_role_id", "academic_year",
              "start_date", "end_date", "status", "ojt_hours_target", "ojt_hours_logged"],
    search=[], filters=["student_id", "employer_id", "academic_year", "status"],
    sortable=["start_date", "created_at"], default_sort=("start_date", "desc"),
    computed=_student_name,
))
register(ResourceConfig(
    name="diaries", model=M.DailyDiary, label="Daily Diary",
    write_roles=[SA, OA, DM, VT],
    writable=["date", "student_id", "school_id", "lab_id", "class_grade", "section",
              "employer_id", "learning", "hours_spent", "photo_url", "status"],
    search=["learning"], filters=["student_id", "school_id", "date"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
    computed=_student_name,
))
register(ResourceConfig(
    name="ojt-placements", model=M.OJTPlacement, label="OJT / Placement",
    write_roles=[SA, OA, DM, VT],
    writable=["student_id", "academic_year", "job_role_id", "ojt_hours_logged",
              "ojt_hours_required", "ojt_establishment", "ojt_start", "ojt_end",
              "apprenticeship_interested", "apprenticeship_placed",
              "apprenticeship_employer_id", "placement_interested", "placement_placed",
              "placement_letter_date", "placement_employer_id", "placement_letter_url",
              "status"],
    search=["ojt_establishment"],
    filters=["student_id", "academic_year", "placement_placed", "apprenticeship_placed"],
    sortable=["created_at"], default_sort=("created_at", "desc"),
    computed=_student_name,
))

# =========================================================================
#  PART 5 - CROSS-CUTTING
# =========================================================================
register(ResourceConfig(
    name="feedback", model=M.Feedback, label="Feedback",
    write_roles=[SA, OA, DM, VT],
    writable=["source", "subject", "rating", "comments", "date", "school_id",
              "lab_id", "status"],
    search=["subject", "comments"], filters=["source", "school_id", "rating"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
))
register(ResourceConfig(
    name="notifications", model=M.Notification, label="Notification",
    write_roles=[SA, OA],
    writable=["user_id", "title", "body", "category", "is_read", "link", "status"],
    search=["title", "body"], filters=["category", "is_read", "user_id"],
    sortable=["created_at"], default_sort=("created_at", "desc"),
))


# =========================================================================
#  VIEW ROLES + DATE FIELDS - who may see each resource in nav + API, and
#  which column drives date-range reporting. Applied in _finalise().
# =========================================================================
STAFF = ALL_ROLES                      # every role that can log in
VIEW_ROLES = {
    "organisations": [SA, OA],
    "states": [SA, OA, DM],
    "districts": [SA, OA, DM],
    "schools": STAFF,
    "principals": STAFF,
    "labs": STAFF,
    "trainers": STAFF,
    "academic-years": STAFF,
    "sectors": STAFF,
    "job-roles": STAFF,
    "social-categories": [SA, OA],
    "modules": ALL_ROLES,
    "units": ALL_ROLES,
    "sessions": ALL_ROLES,
    "students": STAFF,
    "assessments": STAFF,
    "attendance": STAFF,
    "issues": STAFF,
    "field-visits": STAFF,
    "guest-lectures": STAFF,
    "equipment": STAFF,
    "equipment-maintenance": STAFF,
    "employers": STAFF,
    "employer-student-maps": STAFF,
    "diaries": STAFF,
    "ojt-placements": STAFF,
    "feedback": ALL_ROLES,
    "notifications": [SA, OA],
}
DATE_FIELDS = {
    "attendance": "date", "issues": "reporting_date", "field-visits": "reporting_date",
    "guest-lectures": "reporting_date", "diaries": "date", "assessments": "date",
    "students": "date_of_enrolment", "feedback": "date", "class-attendance": "date",
}


def _finalise():
    for name, cfg in REGISTRY.items():
        if cfg.view_roles is None:
            cfg.view_roles = VIEW_ROLES.get(name, ALL_ROLES)
        # writers can always view what they write
        for r in cfg.write_roles:
            if r not in cfg.view_roles:
                cfg.view_roles.append(r)
        if cfg.date_field is None:
            cfg.date_field = DATE_FIELDS.get(name)


_finalise()
