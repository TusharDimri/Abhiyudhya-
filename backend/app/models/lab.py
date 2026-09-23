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
    user_id = db.Column(
        GUID(),
        db.ForeignKey("app_user.id", use_alter=True, name="fk_trainer_user_id_app_user"),
    )

    school = db.relationship("School", lazy="joined")
    lab = db.relationship("Lab", lazy="joined")
