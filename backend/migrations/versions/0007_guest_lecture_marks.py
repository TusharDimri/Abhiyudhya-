"""guest lecture student marks

Which students of the class attended each guest lecture (the Attend button).

Revision ID: 0007_guest_lecture_marks
Revises: 0006_field_visit_location
Create Date: 2026-09-25 08:16:37.926546

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0007_guest_lecture_marks'
down_revision = '0006_field_visit_location'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('guest_lecture_student_mark',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('guest_lecture_id', app.models.base.GUID(), nullable=False),
    sa.Column('student_id', app.models.base.GUID(), nullable=False),
    sa.Column('present', sa.Boolean(), nullable=True),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['guest_lecture_id'], ['guest_lecture.id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('guest_lecture_student_mark', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_guest_lecture_student_mark_guest_lecture_id'), ['guest_lecture_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_guest_lecture_student_mark_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_guest_lecture_student_mark_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_guest_lecture_student_mark_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_guest_lecture_student_mark_student_id'), ['student_id'], unique=False)



def downgrade():
    with op.batch_alter_table('guest_lecture_student_mark', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_guest_lecture_student_mark_student_id'))
        batch_op.drop_index(batch_op.f('ix_guest_lecture_student_mark_status'))
        batch_op.drop_index(batch_op.f('ix_guest_lecture_student_mark_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_guest_lecture_student_mark_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_guest_lecture_student_mark_guest_lecture_id'))

    op.drop_table('guest_lecture_student_mark')
