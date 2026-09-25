"""Lab and the merged Curriculum/Syllabus content tree - spec Part 1.3 & Part 1.4.

Content tree: Sector -> Job Role -> NSQF Level(->Grade) -> Module -> Unit -> Session.
Lab keeps TWO job-role slots (9-10 and 11-12), same or different (spec 1.3).
"""
from app.extensions import db
from app.models.base import BaseModel, GUID


class Lab(BaseModel):
    __tablename__ = "lab"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    sector_id = db.Column(GUID(), db.ForeignKey("sector.id"), index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), nullable=False, index=True)
    # Two job-role slots (spec 1.3 - safer for the 9-10 vs 11-12 case)
    job_role_9_10_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    job_role_11_12_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    curriculum_level = db.Column(db.String(20))  # e.g. "1-4"
    sections_per_class = db.Column(db.Integer, default=1)  # legacy count, kept
    # Per-class section lists (spec 1.3: each class may run different
    # sections). Comma-separated letters, e.g. "A,B". This is the single
    # source every section dropdown in the app reads from, so a trainer picks
    # a section instead of typing one.
    sections_9 = db.Column(db.String(80))
    sections_10 = db.Column(db.String(80))
    sections_11 = db.Column(db.String(80))
    sections_12 = db.Column(db.String(80))
    academic_year_of_setup = db.Column(db.String(20))

    def sections_for(self, class_grade):
        """Section letters configured for one class grade, as a list."""
        raw = getattr(self, f"sections_{class_grade}", None) or ""
        return [s.strip() for s in raw.split(",") if s.strip()]

    def job_role_for(self, class_grade):
        """The job-role slot that covers a class grade (9-10 vs 11-12)."""
        return self.job_role_9_10_id if str(class_grade) in ("9", "10") else self.job_role_11_12_id

    school = db.relationship("School", lazy="joined")
    sector = db.relationship("Sector", lazy="joined")


class Module(BaseModel):
    """Employability / Vocational module within a Job Role + NSQF level."""
    __tablename__ = "curriculum_module"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"), nullable=False, index=True)
    nsqf_level = db.Column(db.Integer)  # 1-4, maps to grade 9-12
    name = db.Column(db.String(200), nullable=False)
    module_type = db.Column(db.String(30))  # Employability / Vocational
    sort_order = db.Column(db.Integer, default=0)


class Unit(BaseModel):
    __tablename__ = "curriculum_unit"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    module_id = db.Column(GUID(), db.ForeignKey("curriculum_module.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Session(BaseModel):
    __tablename__ = "curriculum_session"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    unit_id = db.Column(GUID(), db.ForeignKey("curriculum_unit.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Trainer(BaseModel):
    """Vocational Trainer profile - spec Part 1.5."""
    __tablename__ = "trainer"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"), index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    gender = db.Column(db.String(20))
    date_of_joining = db.Column(db.Date)
    date_of_exit = db.Column(db.Date)
    trainer_status = db.Column(db.String(20), default="active")  # active/substitute/exited
    qualification = db.Column(db.String(200))

    # ---- profile: the trainer fills these in on their profile page --------
    photo_url = db.Column(db.String(500))
    father_name = db.Column(db.String(160))
    mother_name = db.Column(db.String(160))
    dob = db.Column(db.Date)
    domicile_state = db.Column(db.String(80))
    social_category_id = db.Column(GUID(), db.ForeignKey("social_category.id"))
    marital_status = db.Column(db.String(20))
    nationality = db.Column(db.String(60))
    blood_group = db.Column(db.String(5))
    # Sensitive: stored as given, never sent back whole - the API shows only
    # the last four characters (api/profile.py).
    aadhaar_number = db.Column(db.String(12))
    vtp_name = db.Column(db.String(200))       # Vocational Training Provider employing them
    correspondence_address = db.Column(db.Text)
    permanent_address = db.Column(db.Text)
    appointment_nature = db.Column(db.String(30))  # Contractual / Adhoc / Regular / Guest
    # bank & salary (account, PAN are sensitive - masked by the API as well)
    beneficiary_name = db.Column(db.String(160))
    bank_name = db.Column(db.String(120))
    branch_address = db.Column(db.String(300))
    account_number = db.Column(db.String(30))
    ifsc_code = db.Column(db.String(11))
    gross_salary = db.Column(db.Float)
    deduction_esi = db.Column(db.Float)
    deduction_epf = db.Column(db.Float)
    deduction_tds = db.Column(db.Float)
    deduction_other = db.Column(db.Float)
    pan_number = db.Column(db.String(10))
    esi_number = db.Column(db.String(30))
    uan_number = db.Column(db.String(30))
    vt_signature_url = db.Column(db.String(500))
    vtp_signature_url = db.Column(db.String(500))

    user_id = db.Column(
        GUID(),
        db.ForeignKey("app_user.id", use_alter=True, name="fk_trainer_user_id_app_user"),
    )

    school = db.relationship("School", lazy="joined")
    lab = db.relationship("Lab", lazy="joined")

    # Personal, bank and salary details live on the trainer's own profile
    # (api/profile.py). They never go out with the ordinary trainer list -
    # colleagues can read that list for their dropdowns - nor into audit logs.
    PRIVATE = {
        "photo_url", "father_name", "mother_name", "dob", "domicile_state", "social_category_id",
        "marital_status", "nationality", "blood_group", "aadhaar_number", "correspondence_address",
        "permanent_address", "beneficiary_name", "bank_name", "branch_address", "account_number",
        "ifsc_code", "gross_salary", "deduction_esi", "deduction_epf", "deduction_tds",
        "deduction_other", "pan_number", "esi_number", "uan_number", "vt_signature_url",
        "vtp_signature_url",
    }

    def to_dict(self, exclude=None):
        return super().to_dict(exclude=set(exclude or ()) | self.PRIVATE)
