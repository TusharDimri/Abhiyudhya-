"""Student lifecycle - spec Part 2 (registration, verification, assessment)."""
from app.extensions import db
from app.models.base import BaseModel, GUID


class Student(BaseModel):
    """Student Registration - spec Part 2.6 (Class 9 & 11 entry). No Aadhaar."""
    __tablename__ = "student"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), nullable=False, index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"), index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"), index=True)
    academic_year = db.Column(db.String(20), index=True)

    class_grade = db.Column(db.String(5))   # 9/10/11/12
    section = db.Column(db.String(10))
    roll_number = db.Column(db.String(30))
    admission_number = db.Column(db.String(30), index=True)   # the school's own register number
    # Sensitive (a child's Aadhaar): never sent out whole - see to_dict
    aadhaar_number = db.Column(db.String(12))

    first_name = db.Column(db.String(80), nullable=False)
    middle_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    gender = db.Column(db.String(20))
    dob = db.Column(db.Date)
    email = db.Column(db.String(120))

    father_name = db.Column(db.String(120))
    mother_name = db.Column(db.String(120))
    guardian_name = db.Column(db.String(120))
    stream = db.Column(db.String(80))

    mobile_primary = db.Column(db.String(30))
    mobile_secondary = db.Column(db.String(30))
    whatsapp_number = db.Column(db.String(30))

    cwsn = db.Column(db.Boolean, default=False)  # Children With Special Needs
    social_category_id = db.Column(GUID(), db.ForeignKey("social_category.id"))
    date_of_enrolment = db.Column(db.Date)
    photo_url = db.Column(db.String(500))  # optional

    # Class 11 only
    had_vocational_9_10 = db.Column(db.Boolean)
    continuing_same_trade = db.Column(db.Boolean)

    # Verification (spec Part 2.7)
    verification_status = db.Column(db.String(20), default="pending", index=True)
    verified_by = db.Column(
        GUID(),
        db.ForeignKey("app_user.id", use_alter=True, name="fk_student_verified_by_app_user"),
    )
    verified_on = db.Column(db.DateTime)
    verification_remarks = db.Column(db.Text)

    # Where the student is now: studying, finished the course, or left.
    # Changed by promotion (Completed) or the Change Status action - never
    # by editing the record (api/promotion.py).
    enrolment_status = db.Column(db.String(20), default="Studying", server_default="Studying",
                                 nullable=False, index=True)
    left_on = db.Column(db.Date)
    left_reason = db.Column(db.Text)

    school = db.relationship("School", lazy="joined")

    @property
    def full_name(self):
        return " ".join(p for p in [self.first_name, self.middle_name, self.last_name] if p)

    def to_dict(self, exclude=None):
        # lists, edit forms and audit logs only ever see the last four digits
        from app.utils.masking import mask
        out = super().to_dict(exclude=exclude)
        if "aadhaar_number" in out:
            out["aadhaar_number"] = mask(self.aadhaar_number)
        return out


class Assessment(BaseModel):
    """Assessment / Marks / Certification - spec Part 2.10."""
    __tablename__ = "assessment"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    academic_year = db.Column(db.String(20), index=True)
    class_grade = db.Column(db.String(5))
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    nsqf_level = db.Column(db.Integer)
    assessment_type = db.Column(db.String(30))  # internal/continuous/year-end board
    name = db.Column(db.String(160))
    date = db.Column(db.Date)
    max_marks = db.Column(db.Float)
    marks_obtained = db.Column(db.Float)
    result = db.Column(db.String(10))  # pass/fail
    level_certification_status = db.Column(db.String(20))  # L1-L4
    certificate_number = db.Column(db.String(80))
    remarks = db.Column(db.Text)
    evidence_url = db.Column(db.String(500))


class StudentPromotion(BaseModel):
    """One student's end-of-year outcome: moved up a class, held back to
    repeat it, or completed the course - and, kept alongside, the year that
    ended exactly as it was. The student stays one record (their attendance,
    marks and OJT point at it, each with its own year); this is the log of
    what their record said before each promotion changed it."""
    __tablename__ = "student_promotion"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    from_academic_year = db.Column(db.String(20), nullable=False)
    to_academic_year = db.Column(db.String(20))
    from_class = db.Column(db.String(5), nullable=False)
    to_class = db.Column(db.String(5))  # none when the course is completed
    section = db.Column(db.String(10))
    outcome = db.Column(db.String(20), nullable=False)  # Promoted / Held Back / Completed

    # the year that ended, as it stood - never overwritten
    from_roll_number = db.Column(db.String(30))
    from_job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id", name="fk_student_promotion_from_job_role_id_job_role"))
    from_lab_id = db.Column(GUID(), db.ForeignKey("lab.id", name="fk_student_promotion_from_lab_id_lab"))
    from_school_id = db.Column(GUID(), db.ForeignKey("school.id", name="fk_student_promotion_from_school_id_school"))
    from_verification_status = db.Column(db.String(20))
    from_enrolment_status = db.Column(db.String(20))
    snapshot = db.Column(db.JSON)   # the whole record before the change (Aadhaar masked)
