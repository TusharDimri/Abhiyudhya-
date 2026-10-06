"""four photos and a report on field visits and guest lectures; three
maintenance statuses

A field visit and a guest lecture are each recorded with four photos (the
first is the photo column they already had) and, optionally, a PDF report.
Maintenance status is cut down to Reported / Under Progress / Resolved, and
existing logs move onto the nearest of the three.

Revision ID: 0021_visit_photos_report
Revises: 0020_org_issues
Create Date: 2026-10-06 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0021_visit_photos_report'
down_revision = '0020_org_issues'
branch_labels = None
depends_on = None

NEW_COLUMNS = {
    "field_visit": ["picture_2_url", "picture_3_url", "picture_4_url", "report_url"],
    "guest_lecture": ["photo_2_url", "photo_3_url", "photo_4_url", "report_url"],
}
# the old maintenance statuses, on the nearest of the three that remain
UNDER_PROGRESS = ("Under Inspection", "Awaiting Spare Parts", "Sent for Repair", "Under Repair")
RESOLVED = ("Repaired", "Replaced", "Not Repairable")


def upgrade():
    for table, cols in NEW_COLUMNS.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for col in cols:
                batch_op.add_column(sa.Column(col, sa.String(length=500), nullable=True))
    em = sa.table("equipment_maintenance", sa.column("maintenance_status", sa.String))
    op.execute(em.update().where(em.c.maintenance_status.in_(UNDER_PROGRESS)).values(maintenance_status="Under Progress"))
    op.execute(em.update().where(em.c.maintenance_status.in_(RESOLVED)).values(maintenance_status="Resolved"))


def downgrade():
    em = sa.table("equipment_maintenance", sa.column("maintenance_status", sa.String))
    op.execute(em.update().where(em.c.maintenance_status == "Under Progress").values(maintenance_status="Under Repair"))
    for table, cols in NEW_COLUMNS.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for col in reversed(cols):
                batch_op.drop_column(col)
