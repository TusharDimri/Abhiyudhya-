"""Daily operations - spec Part 3 (attendance, issues, visits, lectures, equipment)."""
from app.extensions import db
from app.models.base import BaseModel, GUID
from app.models.geo import CapturesLocation


class DailyAttendance(CapturesLocation, BaseModel):
    """Daily Attendance with all activity-type branches - spec Part 3.11.

    A single record captures one day for one trainer. `activity_type` selects
    which branch (a-o) applies. Every branch field from the spec is a typed
    column rather than free text inside `details`, so each one stays
    filterable, reportable and exportable; `details` remains the shared
    narrative box that every branch asks for.
    """
    __tablename__ = "daily_attendance"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    trainer_id = db.Column(GUID(), db.ForeignKey("trainer.id"), index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"), index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    academic_year = db.Column(db.String(20), index=True)

    date = db.Column(db.Date, nullable=False, index=True)
    day_type = db.Column(db.String(20))  # Working / On leave / Holiday-Off
    leave_reason = db.Column(db.String(200))

    # activity_type is one of a..o (see spec 3.11)
    activity_type = db.Column(db.String(40))

    # --- a. Teaching Vocational Education -------------------------------
    class_taught = db.Column(db.String(10))
    section_taught = db.Column(db.String(80))  # one or more, comma-separated
    theory_or_practical = db.Column(db.String(20))
    class_type = db.Column(db.String(20))  # regular/revision/online/community
    duration_mins = db.Column(db.Integer)
    module_id = db.Column(GUID(), db.ForeignKey("curriculum_module.id"))
    unit_id = db.Column(GUID(), db.ForeignKey("curriculum_unit.id"))
    session_id = db.Column(GUID(), db.ForeignKey("curriculum_session.id"))
    class_picture_url = db.Column(db.String(500))
    lesson_plan_picture_url = db.Column(db.String(500))

    # --- b. Visit to Industry -------------------------------------------
    industry_name = db.Column(db.String(200))
    industry_contact_person = db.Column(db.String(160))
    industry_contact_phone = db.Column(db.String(30))

    # --- c. Visit to Educational Institution ----------------------------
    institute_name = db.Column(db.String(200))
    institute_contact_person = db.Column(db.String(160))
    institute_contact_phone = db.Column(db.String(30))

    # --- d. On-Job Training Coordination --------------------------------
    ojt_activity_type = db.Column(db.String(80))

    # --- e. Parent Teachers Meeting / f. Community Home Visit -----------
    parents_count = db.Column(db.Integer)

    # --- h. Teaching Non-Vocational Subject -----------------------------
    other_class_details = db.Column(db.Text)
    other_class_duration_mins = db.Column(db.Integer)

    # --- j. Assignment from Vocational Department -----------------------
    assignment_number = db.Column(db.String(60))
    assignment_photo_url = db.Column(db.String(500))

    # --- l. Assessor in Other School for Exam ---------------------------
    assessor_school_name = db.Column(db.String(200))
    assessor_udise = db.Column(db.String(30))
    assessor_class = db.Column(db.String(10))
    boys_present = db.Column(db.Integer)
    girls_present = db.Column(db.Integer)

    # --- m. Training of Teacher/Trainer ---------------------------------
    training_type = db.Column(db.String(80))

    # --- o. Guidance & Counselling --------------------------------------
    students_count = db.Column(db.Integer)

    # shared narrative box - every branch (g, i, k, n and the rest) uses it
    details = db.Column(db.Text)

    # --- the trainer's own daily attendance --------------------------------
    # (the form is now just date, time, photo, comment; the activity branches
    # above keep what was recorded with the older form)
    attendance_time = db.Column(db.Time)  # trainer's local time
    photo_url = db.Column(db.String(500))
    distance_from_school_m = db.Column(db.Float)  # checked against the 1 km rule

    # Endorsement (spec Part 5.21)
    endorsement_status = db.Column(db.String(20), default="submitted", index=True)
    endorsed_by = db.Column(GUID(), db.ForeignKey("app_user.id"))
    endorsed_on = db.Column(db.DateTime)
    endorsement_remarks = db.Column(db.Text)

    student_marks = db.relationship("AttendanceStudentMark", backref="attendance", lazy="selectin")


class AttendanceStudentMark(BaseModel):
    """Per-student present/absent marks for a teaching-activity attendance record."""
    __tablename__ = "attendance_student_mark"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    attendance_id = db.Column(GUID(), db.ForeignKey("daily_attendance.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    present = db.Column(db.Boolean, default=True)


class ClassAttendance(CapturesLocation, BaseModel):
    """A trainer taking a class: which class and sections, what they did,
    which students attended, a photo - marked at the school (within 1 km)."""
    __tablename__ = "class_attendance"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    trainer_id = db.Column(GUID(), db.ForeignKey("trainer.id"), index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"), index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    academic_year = db.Column(db.String(20), index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    time = db.Column(db.Time)  # trainer's local time
    class_grade = db.Column(db.String(10))
    sections = db.Column(db.String(80))  # one or more, comma-separated
    activity = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    comment = db.Column(db.Text)
    distance_from_school_m = db.Column(db.Float)

    # the Principal endorses (or returns) it, as with daily attendance
    endorsement_status = db.Column(db.String(20), default="submitted", server_default="submitted", index=True)
    endorsed_by = db.Column(GUID(), db.ForeignKey("app_user.id", name="fk_class_attendance_endorsed_by_app_user"))
    endorsed_on = db.Column(db.DateTime)
    endorsement_remarks = db.Column(db.Text)

    student_marks = db.relationship("ClassAttendanceStudentMark", backref="class_attendance", lazy="selectin")


class ClassAttendanceStudentMark(BaseModel):
    """Which students attended a class."""
    __tablename__ = "class_attendance_student_mark"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    class_attendance_id = db.Column(GUID(), db.ForeignKey("class_attendance.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    present = db.Column(db.Boolean, default=False)


class PrincipalIssue(BaseModel):
    """An issue a principal raises about their school. (Trainers' issues are
    VTIssue and go to the admins, not to the principal.)"""
    __tablename__ = "principal_issue"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), nullable=False, index=True)
    principal_id = db.Column(GUID(), db.ForeignKey("principal.id"), index=True)
    academic_year = db.Column(db.String(20), index=True)
    reporting_date = db.Column(db.Date, nullable=False)
    reporting_time = db.Column(db.Time)
    details = db.Column(db.Text, nullable=False)
    # what the admins do with it (their side comes later)
    workflow_status = db.Column(db.String(20), default="open", server_default="open", index=True)
    resolution_note = db.Column(db.Text)
    resolved_on = db.Column(db.DateTime)


class MonthlyAttendanceReport(BaseModel):
    """MAPP - Maasik Anusaran Praman Patra: a trainer's whole month of
    attendance, uploaded as one PDF for an academic year and month. A trainer
    sees only their own (rbac/scope.py: vt_own_only)."""
    __tablename__ = "monthly_attendance_report"
    vt_own_only = True
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    trainer_id = db.Column(GUID(), db.ForeignKey("trainer.id"), nullable=False, index=True)
    academic_year = db.Column(db.String(20), nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)    # 1-12
    document_url = db.Column(db.String(500), nullable=False)     # the PDF


class OrgIssue(BaseModel):
    """An issue an org admin raises ("My Issues") - about their organisation,
    not one school. The super admin sees them."""
    __tablename__ = "org_issue"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    raised_by = db.Column(GUID(), db.ForeignKey("app_user.id", name="fk_org_issue_raised_by_app_user"), index=True)
    academic_year = db.Column(db.String(20), index=True)
    reporting_date = db.Column(db.Date, nullable=False)
    reporting_time = db.Column(db.Time)
    details = db.Column(db.Text, nullable=False)
    workflow_status = db.Column(db.String(20), default="open", server_default="open", index=True)
    resolution_note = db.Column(db.Text)
    resolved_on = db.Column(db.DateTime)


class VTIssue(CapturesLocation, BaseModel):
    """VT Issue Reporting with workflow - spec Part 3.12. Records where it was logged."""
    __tablename__ = "vt_issue"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    trainer_id = db.Column(GUID(), db.ForeignKey("trainer.id"), index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"))
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    academic_year = db.Column(db.String(20), index=True)
    reporting_date = db.Column(db.Date)
    reporting_time = db.Column(db.Time)  # trainer's local time the issue arose
    main_issue = db.Column(db.String(80))
    sub_issue = db.Column(db.String(120))
    students_affected = db.Column(db.String(20))  # all/some/not applicable
    number_affected = db.Column(db.Integer)
    details = db.Column(db.Text)
    # workflow
    workflow_status = db.Column(db.String(20), default="open", index=True)  # open/in-progress/resolved
    assigned_to = db.Column(GUID(), db.ForeignKey("app_user.id"))
    resolution_note = db.Column(db.Text)
    resolved_on = db.Column(db.DateTime)


class FieldVisit(CapturesLocation, BaseModel):
    """Field / Industry Visit Conducted - spec Part 3.13. Records where it was logged."""
    __tablename__ = "field_visit"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"))
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    class_grade = db.Column(db.String(10))
    sections = db.Column(db.String(80))  # one or more, comma-separated
    academic_year = db.Column(db.String(20), index=True)
    reporting_date = db.Column(db.Date)
    purpose = db.Column(db.Text)
    activities = db.Column(db.Text)
    module_id = db.Column(GUID(), db.ForeignKey("curriculum_module.id"))
    units_covered = db.Column(db.Text)
    sessions_covered = db.Column(db.Text)
    organisation_name = db.Column(db.String(200))
    address = db.Column(db.Text)
    distance_km = db.Column(db.Float)
    picture_url = db.Column(db.String(500))       # photo 1 of the four
    picture_2_url = db.Column(db.String(500))
    picture_3_url = db.Column(db.String(500))
    picture_4_url = db.Column(db.String(500))
    report_url = db.Column(db.String(500))        # the visit's report (PDF), optional
    contact_person = db.Column(db.String(120))
    contact_mobile = db.Column(db.String(30))
    contact_email = db.Column(db.String(120))
    contact_designation = db.Column(db.String(120))
    more_visits_interest = db.Column(db.Boolean)
    ojt_internship_interest = db.Column(db.Boolean)
    organisation_feedback = db.Column(db.Text)
    student_feedback = db.Column(db.Text)

    student_marks = db.relationship("FieldVisitStudentMark", backref="field_visit", lazy="selectin")


class FieldVisitStudentMark(BaseModel):
    """Per-student present/absent marks for a field visit (spec 3.13)."""
    __tablename__ = "field_visit_student_mark"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    field_visit_id = db.Column(GUID(), db.ForeignKey("field_visit.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    present = db.Column(db.Boolean, default=True)


class GuestLecture(CapturesLocation, BaseModel):
    """Guest Lecture Conducted - spec Part 3.14. Records where it was logged."""
    __tablename__ = "guest_lecture"
    student_marks = db.relationship("GuestLectureStudentMark", backref="guest_lecture", lazy="selectin")
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"))
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    class_grade = db.Column(db.String(10))
    sections = db.Column(db.String(80))  # one or more, comma-separated
    academic_year = db.Column(db.String(20), index=True)
    reporting_date = db.Column(db.Date)
    lecture_type = db.Column(db.String(20))  # paid/unpaid
    topic = db.Column(db.String(200))
    duration_mins = db.Column(db.Integer)
    module_id = db.Column(GUID(), db.ForeignKey("curriculum_module.id"))
    units = db.Column(db.Text)
    sessions = db.Column(db.Text)
    methodology = db.Column(db.String(60))
    photo_url = db.Column(db.String(500))         # photo 1 of the four
    photo_2_url = db.Column(db.String(500))
    photo_3_url = db.Column(db.String(500))
    photo_4_url = db.Column(db.String(500))
    report_url = db.Column(db.String(500))        # the lecture's report (PDF), optional
    lecturer_name = db.Column(db.String(120))
    lecturer_qualification = db.Column(db.String(200))
    lecturer_phone = db.Column(db.String(30))
    lecturer_email = db.Column(db.String(120))
    lecturer_experience = db.Column(db.String(200))
    lecturer_address = db.Column(db.Text)
    lecturer_work_status = db.Column(db.String(40))  # job/self-employed
    lecturer_photo_url = db.Column(db.String(500))
    student_feedback = db.Column(db.Text)


class GuestLectureStudentMark(BaseModel):
    """Which students of the class attended a guest lecture."""
    __tablename__ = "guest_lecture_student_mark"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    guest_lecture_id = db.Column(GUID(), db.ForeignKey("guest_lecture.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    present = db.Column(db.Boolean, default=False)


class LabEquipment(BaseModel):
    """Lab Equipment Details + maintenance log - spec Part 3.15.

    Every item belongs to the trainer responsible for it, so it can be handed
    over to another trainer when one leaves.
    """
    __tablename__ = "lab_equipment"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)  # derived from the lab
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"), index=True)
    trainer_id = db.Column(GUID(), db.ForeignKey("trainer.id"), index=True)
    name = db.Column(db.String(200))
    photo_url = db.Column(db.String(500))
    note = db.Column(db.Text)
    academic_year = db.Column(db.String(20), index=True)
    receiving_status = db.Column(db.Boolean)
    receipt_date = db.Column(db.Date)  # shown as "Date" on the form
    equipment_status = db.Column(db.String(30))  # working/partially/not working
    raw_material_availability = db.Column(db.String(60))  # available / not available
    raw_material_fund_status = db.Column(db.Boolean)
    details = db.Column(db.Text)  # shown as "Description" on the form


class EquipmentMaintenance(BaseModel):
    """Maintenance log entry - spec Part 3.15 (MoU requires logged repairs w/ cost)."""
    __tablename__ = "equipment_maintenance"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    equipment_id = db.Column(GUID(), db.ForeignKey("lab_equipment.id"), index=True)
    date = db.Column(db.Date)
    issue = db.Column(db.Text)
    action = db.Column(db.Text)
    cost_incurred = db.Column(db.Float)
    downtime_hours = db.Column(db.Float)
    resolved_by = db.Column(db.String(120))
    maintenance_status = db.Column(db.String(30), index=True)  # Reported / Under Progress / Resolved
    note = db.Column(db.Text)
