"""Editable master / reference data - spec Part 0.4.

Sectors, Job Roles (with QP code + NSQF level), Social categories, and the
Academic Year master. All admin-editable, none hardcoded.
"""
from app.extensions import db
from app.models.base import BaseModel, GUID


class AcademicYear(BaseModel):
    __tablename__ = "academic_year"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    label = db.Column(db.String(20), nullable=False)  # e.g. "2025-26"
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False, index=True)


class Sector(BaseModel):
    """Sector / Trade master - editable (spec 0.4)."""
    __tablename__ = "sector"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30))


class JobRole(BaseModel):
    """Job Role master - name, sector, QP code, NSQF level, class band (spec 0.4)."""
    __tablename__ = "job_role"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    sector_id = db.Column(GUID(), db.ForeignKey("sector.id"), nullable=False, index=True)
    qp_code = db.Column(db.String(40))
    nsqf_level = db.Column(db.Integer)  # 1-4
    class_band = db.Column(db.String(10))  # "9-10" or "11-12"
    sector = db.relationship("Sector", lazy="joined")


class SocialCategory(BaseModel):
    """General, SC, ST, OBC, VJ, SBC, NT-B/C/D - editable (spec 0.4)."""
    __tablename__ = "social_category"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
