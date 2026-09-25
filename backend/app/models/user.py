"""User accounts + role/scope assignments - spec Part 0.2.

A user has exactly one role. Scope columns bind the user to their slice of the
hierarchy. District Managers can hold several districts via user_district.
"""
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models.base import BaseModel, GUID


# DM <-> district (a manager may hold one or more districts, spec 0.2)
user_district = db.Table(
    "user_district",
    db.Column("user_id", GUID(), db.ForeignKey("app_user.id"), primary_key=True),
    db.Column("district_id", GUID(), db.ForeignKey("district.id"), primary_key=True),
)

# VT <-> lab (a trainer may run one or more labs)
user_lab = db.Table(
    "user_lab",
    db.Column("user_id", GUID(), db.ForeignKey("app_user.id"), primary_key=True),
    db.Column("lab_id", GUID(), db.ForeignKey("lab.id"), primary_key=True),
)


class User(BaseModel):
    __tablename__ = "app_user"

    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), index=True)
    full_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(4), nullable=False, index=True)  # Role enum value

    # Direct single-value scope (used by PR/VT)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"), index=True)

    last_login_at = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=False)
    # brute-force protection (spec 7.8)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)

    districts = db.relationship("District", secondary=user_district, lazy="selectin")
    labs = db.relationship("Lab", secondary=user_lab, lazy="selectin")

    # --- password helpers (Werkzeug PBKDF2-SHA256; no native deps) ---
    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        if not self.password_hash:
            return False
        try:
            return check_password_hash(self.password_hash, raw)
        except (ValueError, TypeError):
            return False

    def scope_ids(self):
        """Convenience bag of the user's scope for the scoping engine."""
        return {
            "organisation_id": self.organisation_id,
            "district_ids": [d.id for d in self.districts],
            "school_id": self.school_id,
            "lab_ids": [l.id for l in self.labs],
        }

    def public_dict(self):
        return {
            "id": str(self.id),
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "organisation_id": str(self.organisation_id) if self.organisation_id else None,
            "school_id": str(self.school_id) if self.school_id else None,
            "district_ids": [str(d.id) for d in self.districts],
            "lab_ids": [str(l.id) for l in self.labs],
            "must_change_password": self.must_change_password,
        }

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
