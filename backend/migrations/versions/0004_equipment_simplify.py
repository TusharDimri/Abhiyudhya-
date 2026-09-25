"""equipment trainer name photo note, maintenance status note

Lab equipment is now named, photographed and owned by a trainer; a
maintenance entry carries a status and a note. The older columns stay in
place so existing records keep their data.

Revision ID: 0004_equipment_simplify
Revises: 0003_remove_student_login
Create Date: 2026-09-25 07:02:25.929478

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0004_equipment_simplify'
down_revision = '0003_remove_student_login'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('equipment_maintenance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('maintenance_status', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_equipment_maintenance_maintenance_status'), ['maintenance_status'], unique=False)

    # entries saved while the status list was open / in progress / resolved
    for old, new in (("open", "Reported"), ("in progress", "Under Repair"), ("resolved", "Repaired")):
        op.execute(sa.text("UPDATE equipment_maintenance SET maintenance_status = :new "
                           "WHERE maintenance_status = :old").bindparams(old=old, new=new))

    with op.batch_alter_table('lab_equipment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trainer_id', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_lab_equipment_trainer_id'), ['trainer_id'], unique=False)
        batch_op.create_foreign_key('fk_lab_equipment_trainer_id_trainer', 'trainer', ['trainer_id'], ['id'])



def downgrade():
    with op.batch_alter_table('lab_equipment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lab_equipment_trainer_id_trainer', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_lab_equipment_trainer_id'))
        batch_op.drop_column('note')
        batch_op.drop_column('photo_url')
        batch_op.drop_column('name')
        batch_op.drop_column('trainer_id')

    with op.batch_alter_table('equipment_maintenance', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_equipment_maintenance_maintenance_status'))
        batch_op.drop_column('note')
        batch_op.drop_column('maintenance_status')

