"""class attendance endorsement

The Principal endorses (or returns) class attendance as they do daily
attendance; existing entries start as submitted.

Revision ID: 0013_class_att_endorsement
Revises: 0012_trainer_profile
Create Date: 2026-09-25 19:09:34.861860

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0013_class_att_endorsement'
down_revision = '0012_trainer_profile'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('class_attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('endorsement_status', sa.String(length=20), server_default='submitted', nullable=True))
        batch_op.add_column(sa.Column('endorsed_by', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('endorsed_on', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('endorsement_remarks', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_class_attendance_endorsement_status'), ['endorsement_status'], unique=False)
        batch_op.create_foreign_key('fk_class_attendance_endorsed_by_app_user', 'app_user', ['endorsed_by'], ['id'])



def downgrade():
    with op.batch_alter_table('class_attendance', schema=None) as batch_op:
        batch_op.drop_constraint('fk_class_attendance_endorsed_by_app_user', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_class_attendance_endorsement_status'))
        batch_op.drop_column('endorsement_remarks')
        batch_op.drop_column('endorsed_on')
        batch_op.drop_column('endorsed_by')
        batch_op.drop_column('endorsement_status')

