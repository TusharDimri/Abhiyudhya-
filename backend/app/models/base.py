"""Reusable model mixins: primary key, timestamps, soft-delete, tenant scope.

Every enterprise concern from spec Part 0.5 (audit trail, soft-delete + status,
tenant scoping) is expressed once here and mixed into every model.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR

from app.extensions import db


class GUID(TypeDecorator):
    """Portable UUID: native UUID on Postgres, CHAR(36) on anything else.

    Postgres is what runs everywhere that matters - locally, in tests and in
    production. The fallback only keeps the models loadable on a database
    without a UUID type.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def gen_uuid():
    return uuid.uuid4()


class PKMixin:
    id = db.Column(GUID(), primary_key=True, default=gen_uuid)


class TimestampMixin:
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_by = db.Column(GUID(), nullable=True)
    updated_by = db.Column(GUID(), nullable=True)


class SoftDeleteMixin:
    is_deleted = db.Column(Boolean, default=False, nullable=False, index=True)
    status = db.Column(String(30), default="active", nullable=False, index=True)


class TenantMixin:
    """Adds organisation_id to a model. Overridden as a real FK column in models."""

    @db.declared_attr
    def organisation_id(cls):
        return db.Column(
            GUID(), db.ForeignKey("organisation.id"), nullable=False, index=True
        )


class BaseModel(PKMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __abstract__ = True

    def to_dict(self, exclude=None):
        exclude = set(exclude or [])
        out = {}
        for col in self.__table__.columns:
            if col.name in exclude:
                continue
            val = getattr(self, col.name)
            if isinstance(val, uuid.UUID):
                val = str(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            out[col.name] = val
        return out
