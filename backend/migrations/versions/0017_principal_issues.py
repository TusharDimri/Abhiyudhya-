"""principal issues

Issues a principal raises about their school - separate from trainers'
issues, which go to the admins.

Revision ID: 0017_principal_issues
Revises: 0016_promotion_history
Create Date: 2026-09-26 14:35:00.108238

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0017_principal_issues'
down_revision = '0016_promotion_history'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('principal_issue',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('school_id', app.models.base.GUID(), nullable=False),
    sa.Column('principal_id', app.models.base.GUID(), nullable=True),
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
    sa.ForeignKeyConstraint(['principal_id'], ['principal.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('principal_issue', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_principal_issue_academic_year'), ['academic_year'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_issue_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_issue_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_issue_principal_id'), ['principal_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_issue_school_id'), ['school_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_issue_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_issue_workflow_status'), ['workflow_status'], unique=False)



def downgrade():
    with op.batch_alter_table('principal_issue', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_principal_issue_workflow_status'))
        batch_op.drop_index(batch_op.f('ix_principal_issue_status'))
        batch_op.drop_index(batch_op.f('ix_principal_issue_school_id'))
        batch_op.drop_index(batch_op.f('ix_principal_issue_principal_id'))
        batch_op.drop_index(batch_op.f('ix_principal_issue_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_principal_issue_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_principal_issue_academic_year'))

    op.drop_table('principal_issue')
