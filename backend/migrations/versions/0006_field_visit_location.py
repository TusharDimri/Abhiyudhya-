"""where a field visit was logged

Same three location columns guest lectures carry (see 0005): the point the
trainer's device reported on saving, its accuracy (metres), and when.

Revision ID: 0006_field_visit_location
Revises: 0005_guest_lecture_location
Create Date: 2026-09-25 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '0006_field_visit_location'
down_revision = '0005_guest_lecture_location'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('field_visit', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'location',
            geoalchemy2.Geography(geometry_type='POINT', srid=4326, spatial_index=False),
            nullable=True,
        ))
        batch_op.add_column(sa.Column('location_accuracy_m', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location_captured_at', sa.DateTime(), nullable=True))
    op.create_index('ix_field_visit_location', 'field_visit', ['location'],
                    unique=False, postgresql_using='gist')


def downgrade():
    op.drop_index('ix_field_visit_location', table_name='field_visit', postgresql_using='gist')
    with op.batch_alter_table('field_visit', schema=None) as batch_op:
        batch_op.drop_column('location_captured_at')
        batch_op.drop_column('location_accuracy_m')
        batch_op.drop_column('location')
