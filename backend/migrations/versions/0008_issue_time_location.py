"""issue time and location

An issue is reported with the time it arose and where the trainer was (same
location columns as 0005/0006).

Revision ID: 0008_issue_time_location
Revises: 0007_guest_lecture_marks
Create Date: 2026-09-25 08:21:33.799632

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0008_issue_time_location'
down_revision = '0007_guest_lecture_marks'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vt_issue', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reporting_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeogFromText', name='geography'), nullable=True))
        batch_op.add_column(sa.Column('location_accuracy_m', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location_captured_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_vt_issue_location', ['location'], unique=False, postgresql_using='gist')



def downgrade():
    with op.batch_alter_table('vt_issue', schema=None) as batch_op:
        batch_op.drop_index('ix_vt_issue_location', postgresql_using='gist')
        batch_op.drop_column('location_captured_at')
        batch_op.drop_column('location_accuracy_m')
        batch_op.drop_column('location')
        batch_op.drop_column('reporting_time')

