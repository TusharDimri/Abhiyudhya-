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
ST = Role.STUDENT.value


ALL_ROLES = [SA, OA, DM, PR, VT, ST]


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


def _validate_attendance(instance, user, is_create=False):
    err = _own_job_role_validator()(instance, user, is_create)
    if err:
        return err
    if user.role != VT:
        return None
    jr = instance.job_role_id
    if jr and instance.class_taught:
        from app.rbac.curriculum import allowed_class_grades
        if str(instance.class_taught) not in allowed_class_grades(user, jr):
            return f"Class {instance.class_taught} is not taught under this job role in your lab."
    if jr and instance.module_id:
        from app.extensions import db
        mod = db.session.get(M.Module, instance.module_id)
        if mod and str(mod.job_role_id) != str(jr):
            return "Selected module does not belong to the chosen job role."
    return None


def _validate_curriculum_module(instance, user, is_create=False):
    return _own_job_role_validator()(instance, user, is_create)


def _validate_issue(instance, user, is_create=False):
    """Main issue and sub-issue must be a pair the spec actually defines, and
    'some students affected' must say how many (spec 3.12)."""
    from app.api import enums

    err = _own_job_role_validator()(instance, user, is_create)
    if err:
        return err
    main = instance.main_issue
    if main and main not in enums.values("issue_main"):
        return f"'{main}' is not a valid main issue."
    if instance.sub_issue and main:
        allowed = enums.sub_issue_values(main)
        if allowed and instance.sub_issue not in allowed:
            return f"'{instance.sub_issue}' is not a sub-issue of '{main}'."
    if instance.students_affected == "some" and not instance.number_affected:
        return "Tell us how many students are affected."
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
              "address", "email", "phone", "status"],
    search=["name", "udise_code", "block"],
    filters=["district_id", "block"],
    sortable=["name", "udise_code", "created_at"], default_sort=("name", "asc"),
    computed=lambda o: {"district_name": o.district.name if o.district else None},
))

register(ResourceConfig(
    name="principals", model=M.Principal, label="Principal / Headmaster",
    write_roles=[SA, OA, DM],
    writable=["full_name", "mobile", "email", "gender", "years_in_school",
              "date_of_joining", "date_of_resignation", "linked_school_id",
              "user_id", "status"],
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
              "qualification", "user_id", "status"],
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
    write_roles=[SA, OA, DM, VT],
    writable=["school_id", "lab_id", "job_role_id", "academic_year", "class_grade",
              "section", "roll_number", "first_name", "middle_name", "last_name",
              "gender", "dob", "email", "father_name", "mother_name", "guardian_name",
              "stream", "mobile_primary", "mobile_secondary", "whatsapp_number",
              "cwsn", "social_category_id", "date_of_enrolment", "photo_url",
              "had_vocational_9_10", "continuing_same_trade", "verification_status",
              "verification_remarks", "user_id", "status"],
    search=["first_name", "last_name", "roll_number", "email"],
    filters=["school_id", "lab_id", "job_role_id", "class_grade", "section",
             "academic_year", "verification_status", "cwsn"],
    sortable=["first_name", "roll_number", "created_at"],
    default_sort=("created_at", "desc"),
    computed=lambda o: {"full_name": o.full_name, **_school_name(o)},
    validate=_validate_student,
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
    writable=["trainer_id", "school_id", "lab_id", "job_role_id", "academic_year",
              "date", "day_type", "leave_reason", "activity_type",
              # a. Teaching Vocational Education
              "class_taught", "section_taught", "theory_or_practical", "class_type",
              "duration_mins", "module_id", "unit_id", "session_id",
              "class_picture_url", "lesson_plan_picture_url",
              # b. Visit to Industry
              "industry_name", "industry_contact_person", "industry_contact_phone",
              # c. Visit to Educational Institution
              "institute_name", "institute_contact_person", "institute_contact_phone",
              # d. On-Job Training Coordination
              "ojt_activity_type",
              # e. Parent Teachers Meeting / f. Community Home Visit
              "parents_count",
              # h. Teaching Non-Vocational Subject
              "other_class_details", "other_class_duration_mins",
              # j. Assignment from Vocational Department
              "assignment_number", "assignment_photo_url",
              # l. Assessor in Other School for Exam
              "assessor_school_name", "assessor_udise", "assessor_class",
              "boys_present", "girls_present",
              # m. Training of Teacher/Trainer
              "training_type",
              # o. Guidance & Counselling
              "students_count",
              # shared
              "details", "status"],
    search=["activity_type", "class_taught", "industry_name", "institute_name", "details"],
    filters=["trainer_id", "school_id", "lab_id", "job_role_id", "academic_year", "date",
             "activity_type", "day_type", "class_taught", "endorsement_status"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
    computed=_school_name,
    validate=_validate_attendance,
    children=[ChildCollection("student_marks", M.AttendanceStudentMark,
                              "attendance_id", ["student_id", "present"])],
))
register(ResourceConfig(
    name="issues", model=M.VTIssue, label="VT Issue",
    write_roles=[SA, OA, DM, VT],
    writable=["trainer_id", "lab_id", "job_role_id", "academic_year", "reporting_date",
              "main_issue", "sub_issue", "students_affected", "number_affected",
              "details", "workflow_status", "assigned_to", "resolution_note", "status"],
    search=["main_issue", "sub_issue", "details"],
    filters=["trainer_id", "lab_id", "main_issue", "workflow_status", "academic_year"],
    sortable=["reporting_date", "created_at"], default_sort=("reporting_date", "desc"),
    validate=_validate_issue,
))
register(ResourceConfig(
    name="field-visits", model=M.FieldVisit, label="Field / Industry Visit",
    write_roles=[SA, OA, DM, VT],
    writable=["school_id", "lab_id", "job_role_id", "class_grade", "sections",
              "academic_year", "reporting_date", "purpose", "activities", "module_id",
              "units_covered", "sessions_covered", "organisation_name", "address",
              "distance_km", "picture_url", "contact_person", "contact_mobile",
              "contact_email", "contact_designation", "more_visits_interest",
              "ojt_internship_interest", "organisation_feedback", "student_feedback",
              "status"],
    search=["organisation_name", "purpose"],
    filters=["school_id", "lab_id", "job_role_id", "academic_year", "class_grade"],
    sortable=["reporting_date", "created_at"], default_sort=("reporting_date", "desc"),
    computed=_school_name,
    validate=_own_job_role_validator(),
    children=[ChildCollection("student_marks", M.FieldVisitStudentMark,
                              "field_visit_id", ["student_id", "present"])],
))
register(ResourceConfig(
    name="guest-lectures", model=M.GuestLecture, label="Guest Lecture",
    write_roles=[SA, OA, DM, VT],
    writable=["school_id", "lab_id", "job_role_id", "class_grade", "sections",
              "academic_year", "reporting_date", "lecture_type", "topic",
              "duration_mins", "module_id", "units", "sessions", "methodology",
              "photo_url", "lecturer_name", "lecturer_qualification", "lecturer_phone",
              "lecturer_email", "lecturer_experience", "lecturer_address",
              "lecturer_work_status", "lecturer_photo_url", "student_feedback", "status"],
    search=["topic", "lecturer_name"],
    filters=["school_id", "lab_id", "job_role_id", "academic_year", "class_grade", "lecture_type"],
    sortable=["reporting_date", "created_at"], default_sort=("reporting_date", "desc"),
    computed=_school_name,
    validate=_own_job_role_validator(),
))
register(ResourceConfig(
    name="equipment", model=M.LabEquipment, label="Lab Equipment",
    write_roles=[SA, OA, DM, VT],
    writable=["school_id", "lab_id", "academic_year", "receiving_status",
              "receipt_date", "equipment_status", "raw_material_availability",
              "raw_material_fund_status", "details", "status"],
    search=["details"], filters=["school_id", "lab_id", "academic_year", "equipment_status"],
    sortable=["created_at"], default_sort=("created_at", "desc"),
    computed=_school_name,
))
register(ResourceConfig(
    name="equipment-maintenance", model=M.EquipmentMaintenance, label="Maintenance Log",
    write_roles=[SA, OA, DM, VT],
    writable=["equipment_id", "date", "issue", "action", "cost_incurred",
              "downtime_hours", "resolved_by", "status"],
    search=["issue", "action", "resolved_by"], filters=["equipment_id"],
    sortable=["date", "created_at"], default_sort=("date", "desc"),
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
    write_roles=[SA, OA, DM, VT, ST],
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
    write_roles=[SA, OA, DM, PR, VT, ST],
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
STAFF = [SA, OA, DM, PR, VT]           # every staff role (not students)
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
    "assessments": ALL_ROLES,            # ST sees own via scope
    "attendance": STAFF,
    "issues": STAFF,
    "field-visits": STAFF,
    "guest-lectures": STAFF,
    "equipment": STAFF,
    "equipment-maintenance": STAFF,
    "employers": STAFF,
    "employer-student-maps": STAFF + [ST],
    "diaries": STAFF + [ST],
    "ojt-placements": STAFF + [ST],
    "feedback": ALL_ROLES,
    "notifications": [SA, OA],
}
DATE_FIELDS = {
    "attendance": "date", "issues": "reporting_date", "field-visits": "reporting_date",
    "guest-lectures": "reporting_date", "diaries": "date", "assessments": "date",
    "students": "date_of_enrolment", "feedback": "date",
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
