"""student leaving, step by step

A student leaves in three steps - the trainer marks them as leaving, the
principal records the Transfer Certificate, the org admin confirms - so the
steps and the TC are kept on the student.

Revision ID: 0019_student_leaving
Revises: 0018_no_returned_attendance
Create Date: 2026-09-28 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019_student_leaving'
down_revision = '0018_no_returned_attendance'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('leaving_stage', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('leaving_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('leave_requested_on', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('tc_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('tc_number', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('tc_issued_on', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('tc_verified_on', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_student_leaving_stage'), ['leaving_stage'], unique=False)
    # students who had already left before this: their leaving is complete
    op.execute("UPDATE student SET leaving_stage = 'left', leaving_type = enrolment_status "
               "WHERE enrolment_status IN ('Dropped Out', 'Transferred Out')")


def downgrade():
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_student_leaving_stage'))
        for col in ('tc_verified_on', 'tc_issued_on', 'tc_number', 'tc_url', 'leave_requested_on',
                    'leaving_type', 'leaving_stage'):
            batch_op.drop_column(col)
