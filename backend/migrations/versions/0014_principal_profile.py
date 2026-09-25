"""principal profile

A principal's own record: designation, employee ID and service details,
personal and address details, signature and school seal, plus their
qualifications, service history and trainings.

Revision ID: 0014_principal_profile
Revises: 0013_class_att_endorsement
Create Date: 2026-09-25 20:11:31.589631

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0014_principal_profile'
down_revision = '0013_class_att_endorsement'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('principal_posting',
    sa.Column('school_name', sa.String(length=200), nullable=True),
    sa.Column('district', sa.String(length=120), nullable=True),
    sa.Column('block', sa.String(length=120), nullable=True),
    sa.Column('designation', sa.String(length=120), nullable=True),
    sa.Column('from_date', sa.Date(), nullable=True),
    sa.Column('to_date', sa.Date(), nullable=True),
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('principal_id', app.models.base.GUID(), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['principal_id'], ['principal.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('principal_posting', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_principal_posting_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_posting_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_posting_principal_id'), ['principal_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_posting_status'), ['status'], unique=False)

    op.create_table('principal_qualification',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('principal_id', app.models.base.GUID(), nullable=False),
    sa.Column('qualification', sa.String(length=60), nullable=True),
    sa.Column('course', sa.String(length=160), nullable=True),
    sa.Column('institution', sa.String(length=200), nullable=True),
    sa.Column('course_type', sa.String(length=30), nullable=True),
    sa.Column('passing_year', sa.Integer(), nullable=True),
    sa.Column('marksheet_date', sa.Date(), nullable=True),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['principal_id'], ['principal.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('principal_qualification', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_principal_qualification_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_qualification_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_qualification_principal_id'), ['principal_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_qualification_status'), ['status'], unique=False)

    op.create_table('principal_training',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('principal_id', app.models.base.GUID(), nullable=False),
    sa.Column('training_type', sa.String(length=120), nullable=True),
    sa.Column('training_level', sa.String(length=120), nullable=True),
    sa.Column('venue', sa.String(length=200), nullable=True),
    sa.Column('from_date', sa.Date(), nullable=True),
    sa.Column('to_date', sa.Date(), nullable=True),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['principal_id'], ['principal.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('principal_training', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_principal_training_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_training_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_training_principal_id'), ['principal_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_principal_training_status'), ['status'], unique=False)

    with op.batch_alter_table('principal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('designation', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('employee_id', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('appointment_nature', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('father_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('dob', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('social_category_id', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('alternate_mobile', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('correspondence_address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('permanent_address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('service_joining_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('substantive_post', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('highest_qualification', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('professional_qualification', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('subject_specialisation', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('signature_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('school_seal_url', sa.String(length=500), nullable=True))
        batch_op.create_foreign_key('fk_principal_social_category_id_social_category', 'social_category', ['social_category_id'], ['id'])



def downgrade():
    with op.batch_alter_table('principal', schema=None) as batch_op:
        batch_op.drop_constraint('fk_principal_social_category_id_social_category', type_='foreignkey')
        batch_op.drop_column('school_seal_url')
        batch_op.drop_column('signature_url')
        batch_op.drop_column('subject_specialisation')
        batch_op.drop_column('professional_qualification')
        batch_op.drop_column('highest_qualification')
        batch_op.drop_column('substantive_post')
        batch_op.drop_column('service_joining_date')
        batch_op.drop_column('permanent_address')
        batch_op.drop_column('correspondence_address')
        batch_op.drop_column('alternate_mobile')
        batch_op.drop_column('social_category_id')
        batch_op.drop_column('dob')
        batch_op.drop_column('father_name')
        batch_op.drop_column('photo_url')
        batch_op.drop_column('appointment_nature')
        batch_op.drop_column('employee_id')
        batch_op.drop_column('designation')

    with op.batch_alter_table('principal_training', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_principal_training_status'))
        batch_op.drop_index(batch_op.f('ix_principal_training_principal_id'))
        batch_op.drop_index(batch_op.f('ix_principal_training_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_principal_training_is_deleted'))

    op.drop_table('principal_training')
    with op.batch_alter_table('principal_qualification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_principal_qualification_status'))
        batch_op.drop_index(batch_op.f('ix_principal_qualification_principal_id'))
        batch_op.drop_index(batch_op.f('ix_principal_qualification_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_principal_qualification_is_deleted'))

    op.drop_table('principal_qualification')
    with op.batch_alter_table('principal_posting', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_principal_posting_status'))
        batch_op.drop_index(batch_op.f('ix_principal_posting_principal_id'))
        batch_op.drop_index(batch_op.f('ix_principal_posting_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_principal_posting_is_deleted'))

    op.drop_table('principal_posting')
