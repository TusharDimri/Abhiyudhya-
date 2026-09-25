"""Service records - the history tables behind the profile pages.

A person's single-value details (personal, address, ...) are columns on their
own record (`trainer`, `principal`); these hold the lists: education, past
jobs, trainings attended, postings. Each list is saved whole from the page.

The column sets are shared, so a principal's qualifications and trainings have
exactly the shape a trainer's do.
"""
from app.extensions import db
from app.models.base import BaseModel, GUID


# ------------------------------------------------------------ column sets
class _QualificationColumns:
    qualification = db.Column(db.String(60))   # 10th / 12th / Graduation / ...
    course = db.Column(db.String(160))         # e.g. B.Tech in Computer Engineering
    institution = db.Column(db.String(200))    # university / board / college
    course_type = db.Column(db.String(30))     # Full Time / Part Time / Distance
    passing_year = db.Column(db.Integer)
    marksheet_date = db.Column(db.Date)        # date on the final marksheet


class _TrainingColumns:
    training_type = db.Column(db.String(120))
    training_level = db.Column(db.String(120))
    venue = db.Column(db.String(200))
    from_date = db.Column(db.Date)
    to_date = db.Column(db.Date)


# ------------------------------------------------------------- a trainer's
class _TrainerRow:
    """Which trainer, in which organisation."""
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    trainer_id = db.Column(GUID(), db.ForeignKey("trainer.id"), nullable=False, index=True)


class TrainerQualification(_TrainerRow, _QualificationColumns, BaseModel):
    __tablename__ = "trainer_qualification"


class TrainerExperience(_TrainerRow, BaseModel):
    __tablename__ = "trainer_experience"
    organisation_name = db.Column(db.String(200))
    address = db.Column(db.String(300))
    date_of_joining = db.Column(db.Date)
    date_of_resignation = db.Column(db.Date)
    last_designation = db.Column(db.String(120))
    last_salary = db.Column(db.Float)
    job_type = db.Column(db.String(30))        # Full Time / Part Time
    job_nature = db.Column(db.String(30))      # Contractual / Adhoc / Permanent / Temporary
    reason_for_resignation = db.Column(db.String(300))


class TrainerTraining(_TrainerRow, _TrainingColumns, BaseModel):
    __tablename__ = "trainer_training"


class TrainerPosting(_TrainerRow, BaseModel):
    """NSQF history: each school the trainer was posted to, and by whom."""
    __tablename__ = "trainer_posting"
    vtp_name = db.Column(db.String(200))       # the Vocational Training Provider that employed them
    district = db.Column(db.String(120))
    block = db.Column(db.String(120))
    school_name = db.Column(db.String(200))
    school_year = db.Column(db.String(20))
    school_type = db.Column(db.String(20))     # Boys / Girls / Co-education
    date_of_joining = db.Column(db.Date)
    date_of_relieving = db.Column(db.Date)
    appointment_nature = db.Column(db.String(30))
    appointment_letter = db.Column(db.Boolean)
    experience_certificate = db.Column(db.Boolean)


# ------------------------------------------------------------ a principal's
class _PrincipalRow:
    """Which principal, in which organisation."""
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    principal_id = db.Column(GUID(), db.ForeignKey("principal.id"), nullable=False, index=True)


class PrincipalQualification(_PrincipalRow, _QualificationColumns, BaseModel):
    __tablename__ = "principal_qualification"


class PrincipalTraining(_PrincipalRow, _TrainingColumns, BaseModel):
    __tablename__ = "principal_training"


class PrincipalPosting(_PrincipalRow, BaseModel):
    """Service history: the schools they served in before, and as what."""
    __tablename__ = "principal_posting"
    school_name = db.Column(db.String(200))
    district = db.Column(db.String(120))
    block = db.Column(db.String(120))
    designation = db.Column(db.String(120))
    from_date = db.Column(db.Date)
    to_date = db.Column(db.Date)
