"""a department login's own issues ("My Issues")

A department login raises an issue with just its description; the date and
time are filled in when it is saved. The org admin resolves it.

Revision ID: 0024_dept_issue
Revises: 0023_school_board_prabhari
Create Date: 2026-10-12 12:00:00

"""
from alembic import op
import sqlalchemy as sa

import app.models.base


# revision identifiers, used by Alembic.
revision = '0024_dept_issue'
down_revision = '0023_school_board_prabhari'
branch_labels = None
depends_on = None

INDEXED = ('academic_year', 'is_deleted', 'organisation_id', 'raised_by', 'status', 'workflow_status')


def upgrade():
    op.create_table('dept_issue',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('raised_by', app.models.base.GUID(), nullable=True),
    sa.Column('academic_year', sa.String(length=20), nullable=True),
    sa.Column('reporting_date', sa.Date(), nullable=False),
    sa.Column('reporting_time', sa.Time(), nullable=True),
    sa.Column('details', sa.Text(), nullable=False),
    sa.Column('workflow_status', sa.String(length=20), server_default='open', nullable=True),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.Column('resolved_on', sa.DateTime(), nullable=True),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['raised_by'], ['app_user.id'], name='fk_dept_issue_raised_by_app_user'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('dept_issue', schema=None) as batch_op:
        for col in INDEXED:
            batch_op.create_index(batch_op.f(f'ix_dept_issue_{col}'), [col], unique=False)


def downgrade():
    with op.batch_alter_table('dept_issue', schema=None) as batch_op:
        for col in INDEXED:
            batch_op.drop_index(batch_op.f(f'ix_dept_issue_{col}'))
    op.drop_table('dept_issue')
