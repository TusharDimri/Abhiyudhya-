"""MAPP - a trainer's monthly attendance, uploaded as one PDF

Maasik Anusaran Praman Patra: for an academic year and a month, the trainer
uploads the month's attendance document (Upload MAPP, below Daily Attendance).

Revision ID: 0022_monthly_attendance
Revises: 0021_visit_photos_report
Create Date: 2026-10-06 14:00:00

"""
from alembic import op
import sqlalchemy as sa

import app.models.base


# revision identifiers, used by Alembic.
revision = '0022_monthly_attendance'
down_revision = '0021_visit_photos_report'
branch_labels = None
depends_on = None

INDEXED = ('academic_year', 'is_deleted', 'month', 'organisation_id', 'school_id', 'status', 'trainer_id')


def upgrade():
    op.create_table('monthly_attendance_report',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('school_id', app.models.base.GUID(), nullable=True),
    sa.Column('trainer_id', app.models.base.GUID(), nullable=False),
    sa.Column('academic_year', sa.String(length=20), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('document_url', sa.String(length=500), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('monthly_attendance_report', schema=None) as batch_op:
        for col in INDEXED:
            batch_op.create_index(batch_op.f(f'ix_monthly_attendance_report_{col}'), [col], unique=False)


def downgrade():
    with op.batch_alter_table('monthly_attendance_report', schema=None) as batch_op:
        for col in INDEXED:
            batch_op.drop_index(batch_op.f(f'ix_monthly_attendance_report_{col}'))
    op.drop_table('monthly_attendance_report')
