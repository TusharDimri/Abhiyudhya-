"""student admission and aadhaar

Every student has the school's admission number and their Aadhaar number
(sent out masked - only the last four digits).

Revision ID: 0015_student_admission_aadhaar
Revises: 0014_principal_profile
Create Date: 2026-09-26 06:32:13.823547

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0015_student_admission_aadhaar'
down_revision = '0014_principal_profile'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('admission_number', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('aadhaar_number', sa.String(length=12), nullable=True))
        batch_op.create_index(batch_op.f('ix_student_admission_number'), ['admission_number'], unique=False)



def downgrade():
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_student_admission_number'))
        batch_op.drop_column('aadhaar_number')
        batch_op.drop_column('admission_number')

