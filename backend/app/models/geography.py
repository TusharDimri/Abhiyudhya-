"""Geographic + academic hierarchy - spec Part 0.3 and Part 1.

Organisation -> State -> District -> Block(field) -> School(UDISE) -> Lab
Block is a field on School (no login), used for filtering/rollups (spec 0.2).
"""
from geoalchemy2 import Geography
from sqlalchemy import Index

from app.extensions import db
from app.models.base import BaseModel, GUID


class State(BaseModel):
    __tablename__ = "state"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(20))


class District(BaseModel):
    __tablename__ = "district"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    state_id = db.Column(GUID(), db.ForeignKey("state.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(20))
    state = db.relationship("State", lazy="joined")


class School(BaseModel):
    __tablename__ = "school"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    district_id = db.Column(GUID(), db.ForeignKey("district.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    udise_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    block = db.Column(db.String(120), index=True)  # field only, no login (spec 0.2)
    principal_id = db.Column(
        GUID(),
        db.ForeignKey("principal.id", use_alter=True, name="fk_school_principal_id_principal"),
    )
    address = db.Column(db.Text)
    email = db.Column(db.String(120))
    school_type = db.Column(db.String(20))  # Boys / Girls / Co-education
    board = db.Column(db.String(30))        # enums.SCHOOL_BOARDS: CBSE / RamNagar / PM Shri / UK Board
    # where the school is - trainers' attendance must be marked within 1 km
    location = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=False))
    phone = db.Column(db.String(30))
    enrolment_count = db.Column(db.Integer, default=0)  # derived, refreshed by service

    district = db.relationship("District", lazy="joined")



Index("ix_school_location", School.location, postgresql_using="gist")

class Principal(BaseModel):
    """Principal / Headmaster - spec Part 1.2 (also a user role)."""
    __tablename__ = "principal"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    mobile = db.Column(db.String(30))
    email = db.Column(db.String(120))
    gender = db.Column(db.String(20))
    years_in_school = db.Column(db.Integer)
    date_of_joining = db.Column(db.Date)
    date_of_resignation = db.Column(db.Date)
    linked_school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)
    user_id = db.Column(
        GUID(),
        db.ForeignKey("app_user.id", use_alter=True, name="fk_principal_user_id_app_user"),
    )

    # ---- set when they are taken on (admin) ---------------------------------
    designation = db.Column(db.String(60))      # Principal / Headmaster / ... (In-charge)
    employee_id = db.Column(db.String(40))
    appointment_nature = db.Column(db.String(30))

    # ---- profile: the principal fills these in on their profile page -------
    photo_url = db.Column(db.String(500))
    father_name = db.Column(db.String(160))
    dob = db.Column(db.Date)
    social_category_id = db.Column(
        GUID(), db.ForeignKey("social_category.id", name="fk_principal_social_category_id_social_category"))
    alternate_mobile = db.Column(db.String(30))
    correspondence_address = db.Column(db.Text)
    permanent_address = db.Column(db.Text)
    service_joining_date = db.Column(db.Date)   # first day in government service
    substantive_post = db.Column(db.String(120))  # e.g. Lecturer (PGT) Physics
    highest_qualification = db.Column(db.String(60))
    professional_qualification = db.Column(db.String(120))  # B.Ed / M.Ed / ...
    subject_specialisation = db.Column(db.String(120))
    signature_url = db.Column(db.String(500))
    school_seal_url = db.Column(db.String(500))

    # ---- the school's Vocational Prabhari (optional) - added with the
    # principal by the admin, or by the principal on their profile
    vocational_prabhari_name = db.Column(db.String(160))
    vocational_prabhari_mobile = db.Column(db.String(30))
    vocational_prabhari_email = db.Column(db.String(120))

    # Personal details stay on the principal's own profile (api/profile.py);
    # the ordinary principal list - readable by trainers - never carries them.
    PRIVATE = {
        "photo_url", "father_name", "dob", "social_category_id", "alternate_mobile",
        "correspondence_address", "permanent_address", "signature_url", "school_seal_url",
        "vocational_prabhari_name", "vocational_prabhari_mobile", "vocational_prabhari_email",
    }

    def to_dict(self, exclude=None):
        return super().to_dict(exclude=set(exclude or ()) | self.PRIVATE)
