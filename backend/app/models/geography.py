"""Geographic + academic hierarchy - spec Part 0.3 and Part 1.

Organisation -> State -> District -> Block(field) -> School(UDISE) -> Lab
Block is a field on School (no login), used for filtering/rollups (spec 0.2).
"""
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
    phone = db.Column(db.String(30))
    enrolment_count = db.Column(db.Integer, default=0)  # derived, refreshed by service

    district = db.relationship("District", lazy="joined")


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
