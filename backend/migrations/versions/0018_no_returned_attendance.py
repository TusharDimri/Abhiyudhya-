"""attendance is only verified - no "returned"

The Principal now only verifies attendance; there is no returning it for a
fix. Entries that had been returned go back to waiting for verification.
Data only; no schema change.

Revision ID: 0018_no_returned_attendance
Revises: 0017_principal_issues
Create Date: 2026-09-27 11:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '0018_no_returned_attendance'
down_revision = '0017_principal_issues'
branch_labels = None
depends_on = None


def upgrade():
    for table in ("daily_attendance", "class_attendance"):
        op.execute(f"UPDATE {table} SET endorsement_status = 'submitted' WHERE endorsement_status = 'returned'")


def downgrade():
    # which entries had been returned is not kept; nothing to put back
    pass
