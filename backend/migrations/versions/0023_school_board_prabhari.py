"""a school's board; a principal's Vocational Prabhari

A school is added with its board (CBSE / RamNagar / PM Shri / UK Board). A
principal can have their school's Vocational Prabhari on record - name,
mobile and email - added with them, or later on their profile.

Revision ID: 0023_school_board_prabhari
Revises: 0022_monthly_attendance
Create Date: 2026-10-06 18:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0023_school_board_prabhari'
down_revision = '0022_monthly_attendance'
branch_labels = None
depends_on = None

PRABHARI = (("vocational_prabhari_name", 160), ("vocational_prabhari_mobile", 30), ("vocational_prabhari_email", 120))


def upgrade():
    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.add_column(sa.Column('board', sa.String(length=30), nullable=True))
    with op.batch_alter_table('principal', schema=None) as batch_op:
        for col, size in PRABHARI:
            batch_op.add_column(sa.Column(col, sa.String(length=size), nullable=True))


def downgrade():
    with op.batch_alter_table('principal', schema=None) as batch_op:
        for col, _ in reversed(PRABHARI):
            batch_op.drop_column(col)
    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.drop_column('board')
