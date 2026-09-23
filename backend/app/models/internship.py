"""Internship / OJT / Placement - spec Part 4."""
from app.extensions import db
from app.models.base import BaseModel, GUID


class Employer(BaseModel):
    """Employer Details - spec Part 4.16."""
    __tablename__ = "employer"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    gender = db.Column(db.String(20))
    org_name = db.Column(db.String(200), nullable=False)
    business_description = db.Column(db.Text)
    employee_count = db.Column(db.String(20))  # 0-1/2-5/6-10/11-20/20+
    year_of_foundation = db.Column(db.Integer)
    sector_id = db.Column(GUID(), db.ForeignKey("sector.id"))
    is_active = db.Column(db.Boolean, default=True)
    branch_name = db.Column(db.String(160))
    branch_address = db.Column(db.Text)
    poc_mobile = db.Column(db.String(30))
    poc_email = db.Column(db.String(120))
    state = db.Column(db.String(120))
    district = db.Column(db.String(120))
    pincode = db.Column(db.String(12))


class EmployerStudentMap(BaseModel):
    """Employer-Student Mapping - spec Part 4.17."""
    __tablename__ = "employer_student_map"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    employer_id = db.Column(GUID(), db.ForeignKey("employer.id"), nullable=False, index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    academic_year = db.Column(db.String(20), index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="ongoing")  # ongoing/completed
    ojt_hours_target = db.Column(db.Integer)
    ojt_hours_logged = db.Column(db.Integer, default=0)


class DailyDiary(BaseModel):
    """Daily Diaries - spec Part 4.18."""
    __tablename__ = "daily_diary"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"))
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"))
    class_grade = db.Column(db.String(10))
    section = db.Column(db.String(10))
    employer_id = db.Column(GUID(), db.ForeignKey("employer.id"))
    learning = db.Column(db.Text)
    hours_spent = db.Column(db.Float)
    photo_url = db.Column(db.String(500))


class OJTPlacement(BaseModel):
    """OJT / Apprenticeship / Placement - spec Part 4.19."""
    __tablename__ = "ojt_placement"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    student_id = db.Column(GUID(), db.ForeignKey("student.id"), nullable=False, index=True)
    academic_year = db.Column(db.String(20), index=True)
    job_role_id = db.Column(GUID(), db.ForeignKey("job_role.id"))
    ojt_hours_logged = db.Column(db.Integer, default=0)
    ojt_hours_required = db.Column(db.Integer, default=50)
    ojt_establishment = db.Column(db.String(200))
    ojt_start = db.Column(db.Date)
    ojt_end = db.Column(db.Date)
    apprenticeship_interested = db.Column(db.Boolean)
    apprenticeship_placed = db.Column(db.Boolean)
    apprenticeship_employer_id = db.Column(GUID(), db.ForeignKey("employer.id"))
    placement_interested = db.Column(db.Boolean)
    placement_placed = db.Column(db.Boolean)
    placement_letter_date = db.Column(db.Date)
    placement_employer_id = db.Column(GUID(), db.ForeignKey("employer.id"))
    placement_letter_url = db.Column(db.String(500))
