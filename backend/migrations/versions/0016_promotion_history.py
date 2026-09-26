"""promotion keeps the year that ended

Each promotion now logs the student's record for the year that ended - roll
number, job role, lab, school, statuses and a snapshot of the whole record -
before the student is moved on, so earlier years are never lost.

Revision ID: 0016_promotion_history
Revises: 0015_student_admission_aadhaar
Create Date: 2026-09-26 06:56:32.202633

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0016_promotion_history'
down_revision = '0015_student_admission_aadhaar'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student_promotion', schema=None) as batch_op:
        batch_op.add_column(sa.Column('from_roll_number', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('from_job_role_id', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('from_lab_id', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('from_school_id', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('from_verification_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('from_enrolment_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('snapshot', sa.JSON(), nullable=True))
        batch_op.create_foreign_key('fk_student_promotion_from_school_id_school', 'school', ['from_school_id'], ['id'])
        batch_op.create_foreign_key('fk_student_promotion_from_job_role_id_job_role', 'job_role', ['from_job_role_id'], ['id'])
        batch_op.create_foreign_key('fk_student_promotion_from_lab_id_lab', 'lab', ['from_lab_id'], ['id'])



def downgrade():
    with op.batch_alter_table('student_promotion', schema=None) as batch_op:
        batch_op.drop_constraint('fk_student_promotion_from_lab_id_lab', type_='foreignkey')
        batch_op.drop_constraint('fk_student_promotion_from_job_role_id_job_role', type_='foreignkey')
        batch_op.drop_constraint('fk_student_promotion_from_school_id_school', type_='foreignkey')
        batch_op.drop_column('snapshot')
        batch_op.drop_column('from_enrolment_status')
        batch_op.drop_column('from_verification_status')
        batch_op.drop_column('from_school_id')
        batch_op.drop_column('from_lab_id')
        batch_op.drop_column('from_job_role_id')
        batch_op.drop_column('from_roll_number')

