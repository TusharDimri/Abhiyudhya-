"""org admins' own issues ("My Issues")

An org admin logs issues about their organisation - not one school - which
the super admin can see.

Revision ID: 0020_org_issues
Revises: 0019_student_leaving
Create Date: 2026-09-30 10:00:00

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0020_org_issues'
down_revision = '0019_student_leaving'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('org_issue',
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
    sa.ForeignKeyConstraint(['raised_by'], ['app_user.id'], name='fk_org_issue_raised_by_app_user'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('org_issue', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_org_issue_academic_year'), ['academic_year'], unique=False)
        batch_op.create_index(batch_op.f('ix_org_issue_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_org_issue_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_org_issue_raised_by'), ['raised_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_org_issue_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_org_issue_workflow_status'), ['workflow_status'], unique=False)


def downgrade():
    with op.batch_alter_table('org_issue', schema=None) as batch_op:
        for ix in ('workflow_status', 'status', 'raised_by', 'organisation_id', 'is_deleted', 'academic_year'):
            batch_op.drop_index(batch_op.f(f'ix_org_issue_{ix}'))
    op.drop_table('org_issue')
