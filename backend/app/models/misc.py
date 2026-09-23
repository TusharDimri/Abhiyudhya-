"""Cross-cutting - spec Part 5 (feedback, notifications, audit log)."""
from datetime import datetime

from app.extensions import db
from app.models.base import BaseModel, GUID


class Feedback(BaseModel):
    """Feedback module - spec Part 5.22."""
    __tablename__ = "feedback"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    source = db.Column(db.String(40))  # student/teacher/inspection team
    subject = db.Column(db.String(200))
    rating = db.Column(db.Integer)
    comments = db.Column(db.Text)
    date = db.Column(db.Date)
    school_id = db.Column(GUID(), db.ForeignKey("school.id"))
    lab_id = db.Column(GUID(), db.ForeignKey("lab.id"))


class Notification(BaseModel):
    """Notifications - spec Part 5.25."""
    __tablename__ = "notification"
    organisation_id = db.Column(GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True)
    user_id = db.Column(GUID(), db.ForeignKey("app_user.id"), index=True)
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    category = db.Column(db.String(40))  # issue/verification/endorsement/sla
    is_read = db.Column(db.Boolean, default=False, index=True)
    link = db.Column(db.String(300))


class AuditLog(db.Model):
    """Global audit log (who/when/before-after) - spec Part 5.25.

    Append-only; deliberately NOT a soft-delete/tenant BaseModel so it can never
    be edited away. organisation_id kept for scoped inspection.
    """
    __tablename__ = "audit_log"
    id = db.Column(GUID(), primary_key=True)
    organisation_id = db.Column(GUID(), index=True)
    actor_id = db.Column(GUID(), index=True)
    actor_email = db.Column(db.String(160))
    actor_role = db.Column(db.String(4))
    action = db.Column(db.String(20))  # create/update/delete
    entity = db.Column(db.String(80), index=True)
    entity_id = db.Column(GUID(), index=True)
    before = db.Column(db.Text)
    after = db.Column(db.Text)
    ip = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
