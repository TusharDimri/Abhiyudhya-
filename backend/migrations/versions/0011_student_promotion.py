"""student enrolment status and promotion history

A student is Studying, Completed (the course, via promotion), Dropped Out or
Transferred Out; existing students start as Studying. student_promotion keeps
each end-of-year outcome (Promoted / Held Back / Completed).

Revision ID: 0011_student_promotion
Revises: 0010_attendance_location
Create Date: 2026-09-25 10:12:18.284595

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0011_student_promotion'
down_revision = '0010_attendance_location'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('student_promotion',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('student_id', app.models.base.GUID(), nullable=False),
    sa.Column('from_academic_year', sa.String(length=20), nullable=False),
    sa.Column('to_academic_year', sa.String(length=20), nullable=True),
    sa.Column('from_class', sa.String(length=5), nullable=False),
    sa.Column('to_class', sa.String(length=5), nullable=True),
    sa.Column('section', sa.String(length=10), nullable=True),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('student_promotion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_student_promotion_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_student_promotion_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_student_promotion_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_student_promotion_student_id'), ['student_id'], unique=False)

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enrolment_status', sa.String(length=20), server_default='Studying', nullable=False))
        batch_op.add_column(sa.Column('left_on', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('left_reason', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_student_enrolment_status'), ['enrolment_status'], unique=False)



def downgrade():
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_student_enrolment_status'))
        batch_op.drop_column('left_reason')
        batch_op.drop_column('left_on')
        batch_op.drop_column('enrolment_status')

    with op.batch_alter_table('student_promotion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_student_promotion_student_id'))
        batch_op.drop_index(batch_op.f('ix_student_promotion_status'))
        batch_op.drop_index(batch_op.f('ix_student_promotion_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_student_promotion_is_deleted'))

    op.drop_table('student_promotion')
