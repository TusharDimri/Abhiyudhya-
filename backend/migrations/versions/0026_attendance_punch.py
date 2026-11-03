"""a trainer's daily attendance is marked twice: Punch In, then Punch Out

daily_attendance.punch is "in" or "out". Existing records: a trainer's
first record of a day becomes Punch In, any later one Punch Out.

Revision ID: 0026_attendance_punch
Revises: 0025_trainer_job_roles
Create Date: 2026-11-03 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0026_attendance_punch'
down_revision = '0025_trainer_job_roles'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('daily_attendance', sa.Column('punch', sa.String(length=10), nullable=True))
    op.create_index('ix_daily_attendance_punch', 'daily_attendance', ['punch'])
    # (deleted records are numbered apart, so they never push a live one to "out")
    op.execute("""
        UPDATE daily_attendance d SET punch = CASE WHEN o.n = 1 THEN 'in' ELSE 'out' END
        FROM (SELECT id, row_number() OVER (
                  PARTITION BY trainer_id, date, is_deleted
                  ORDER BY attendance_time NULLS LAST, created_at, id) AS n
              FROM daily_attendance) o
        WHERE d.id = o.id
    """)


def downgrade():
    op.drop_index('ix_daily_attendance_punch', table_name='daily_attendance')
    op.drop_column('daily_attendance', 'punch')
