"""a lecture's / visit's academic year follows its date

Guest lectures and field visits used to be stamped with whichever academic
year was marked current when they were saved - wrong for anything back-dated,
or saved after the year rolled over but before anyone moved the flag. Yearly
targets are counted by that year (api/targets.py), so existing rows get the
year their own date falls in: the organisation's configured year, else the
June-May school year. Data only; no schema change.

Revision ID: 0009_year_follows_date
Revises: 0008_issue_time_location
Create Date: 2026-09-25 16:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '0009_year_follows_date'
down_revision = '0008_issue_time_location'
branch_labels = None
depends_on = None

_RECOMPUTE = """
UPDATE {table} t SET academic_year = COALESCE(
    (SELECT a.label FROM academic_year a
      WHERE a.organisation_id = t.organisation_id AND NOT a.is_deleted
        AND a.start_date <= t.reporting_date AND a.end_date >= t.reporting_date
      ORDER BY a.start_date DESC LIMIT 1),
    -- June-May school year, e.g. 2026-09-25 -> 2026-27
    (EXTRACT(YEAR FROM t.reporting_date)::int
        - CASE WHEN EXTRACT(MONTH FROM t.reporting_date) >= 6 THEN 0 ELSE 1 END)::text
    || '-' ||
    LPAD(((EXTRACT(YEAR FROM t.reporting_date)::int
        - CASE WHEN EXTRACT(MONTH FROM t.reporting_date) >= 6 THEN 0 ELSE 1 END + 1) % 100)::text, 2, '0')
)
WHERE t.reporting_date IS NOT NULL
"""


def upgrade():
    for table in ("guest_lecture", "field_visit"):
        op.execute(_RECOMPUTE.format(table=table))


def downgrade():
    # the old values were wrong; there is nothing worth restoring
    pass
