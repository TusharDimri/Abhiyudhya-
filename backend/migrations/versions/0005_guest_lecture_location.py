"""postgis + where a guest lecture was logged

Turns on PostGIS and gives guest_lecture the point the trainer's device
reported when saving it, that fix's accuracy (metres) and when it was taken.
On RDS the extension is available out of the box; enabling it needs the
master user (rds_superuser), which is the user migrations run as.

Revision ID: 0005_guest_lecture_location
Revises: 0004_equipment_simplify
Create Date: 2026-09-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '0005_guest_lecture_location'
down_revision = '0004_equipment_simplify'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    with op.batch_alter_table('guest_lecture', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'location',
            geoalchemy2.Geography(geometry_type='POINT', srid=4326, spatial_index=False),
            nullable=True,
        ))
        batch_op.add_column(sa.Column('location_accuracy_m', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location_captured_at', sa.DateTime(), nullable=True))
    op.create_index('ix_guest_lecture_location', 'guest_lecture', ['location'],
                    unique=False, postgresql_using='gist')


def downgrade():
    op.drop_index('ix_guest_lecture_location', table_name='guest_lecture', postgresql_using='gist')
    with op.batch_alter_table('guest_lecture', schema=None) as batch_op:
        batch_op.drop_column('location_captured_at')
        batch_op.drop_column('location_accuracy_m')
        batch_op.drop_column('location')
    # the extension stays: dropping it would take any other spatial data with it
