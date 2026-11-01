"""a trainer teaches one or both of their lab's job roles

trainer.job_role_id (one role) becomes trainer.job_role_ids ("id1,id2",
like a class's sections). Existing trainers keep the role they had.

Revision ID: 0025_trainer_job_roles
Revises: 0024_dept_issue
Create Date: 2026-11-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa

import app.models.base


# revision identifiers, used by Alembic.
revision = '0025_trainer_job_roles'
down_revision = '0024_dept_issue'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('trainer', sa.Column('job_role_ids', sa.Text(), nullable=True))
    op.execute("UPDATE trainer SET job_role_ids = job_role_id::text WHERE job_role_id IS NOT NULL")
    op.drop_constraint('trainer_job_role_id_fkey', 'trainer', type_='foreignkey')
    op.drop_column('trainer', 'job_role_id')


def downgrade():
    op.add_column('trainer', sa.Column('job_role_id', app.models.base.GUID(), nullable=True))
    # (a trainer on both roles keeps the first)
    op.execute("UPDATE trainer SET job_role_id = split_part(job_role_ids, ',', 1)::uuid "
               "WHERE coalesce(job_role_ids, '') <> ''")
    op.create_foreign_key('trainer_job_role_id_fkey', 'trainer', 'job_role', ['job_role_id'], ['id'])
    op.drop_column('trainer', 'job_role_ids')
