"""Organisation (tenant) - spec Part 0.1."""
from app.extensions import db
from app.models.base import BaseModel, GUID


class Organisation(BaseModel):
    __tablename__ = "organisation"

    name = db.Column(db.String(200), nullable=False)
    legal_name = db.Column(db.String(200))
    org_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    logo_url = db.Column(db.String(500))
    primary_contact_name = db.Column(db.String(120))
    primary_contact_email = db.Column(db.String(120))
    primary_contact_phone = db.Column(db.String(30))
    registered_address = db.Column(db.Text)
    affiliation_cert_number = db.Column(db.String(120))
    affiliation_valid_till = db.Column(db.Date)

    def __repr__(self):
        return f"<Organisation {self.org_code}>"
