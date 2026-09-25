"""trainer profile

A trainer's own service record: personal, address and bank details on
`trainer`, plus their qualifications, past jobs, trainings and NSQF postings.
Schools get a type (Boys / Girls / Co-education).

Revision ID: 0012_trainer_profile
Revises: 0011_student_promotion
Create Date: 2026-09-25 18:31:43.176980

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0012_trainer_profile'
down_revision = '0011_student_promotion'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('trainer_experience',
    sa.Column('organisation_name', sa.String(length=200), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('date_of_joining', sa.Date(), nullable=True),
    sa.Column('date_of_resignation', sa.Date(), nullable=True),
    sa.Column('last_designation', sa.String(length=120), nullable=True),
    sa.Column('last_salary', sa.Float(), nullable=True),
    sa.Column('job_type', sa.String(length=30), nullable=True),
    sa.Column('job_nature', sa.String(length=30), nullable=True),
    sa.Column('reason_for_resignation', sa.String(length=300), nullable=True),
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('trainer_id', app.models.base.GUID(), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('trainer_experience', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_trainer_experience_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_experience_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_experience_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_experience_trainer_id'), ['trainer_id'], unique=False)

    op.create_table('trainer_posting',
    sa.Column('vtp_name', sa.String(length=200), nullable=True),
    sa.Column('district', sa.String(length=120), nullable=True),
    sa.Column('block', sa.String(length=120), nullable=True),
    sa.Column('school_name', sa.String(length=200), nullable=True),
    sa.Column('school_year', sa.String(length=20), nullable=True),
    sa.Column('school_type', sa.String(length=20), nullable=True),
    sa.Column('date_of_joining', sa.Date(), nullable=True),
    sa.Column('date_of_relieving', sa.Date(), nullable=True),
    sa.Column('appointment_nature', sa.String(length=30), nullable=True),
    sa.Column('appointment_letter', sa.Boolean(), nullable=True),
    sa.Column('experience_certificate', sa.Boolean(), nullable=True),
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('trainer_id', app.models.base.GUID(), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('trainer_posting', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_trainer_posting_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_posting_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_posting_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_posting_trainer_id'), ['trainer_id'], unique=False)

    op.create_table('trainer_qualification',
    sa.Column('qualification', sa.String(length=60), nullable=True),
    sa.Column('course', sa.String(length=160), nullable=True),
    sa.Column('institution', sa.String(length=200), nullable=True),
    sa.Column('course_type', sa.String(length=30), nullable=True),
    sa.Column('passing_year', sa.Integer(), nullable=True),
    sa.Column('marksheet_date', sa.Date(), nullable=True),
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('trainer_id', app.models.base.GUID(), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('trainer_qualification', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_trainer_qualification_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_qualification_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_qualification_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_qualification_trainer_id'), ['trainer_id'], unique=False)

    op.create_table('trainer_training',
    sa.Column('training_type', sa.String(length=120), nullable=True),
    sa.Column('training_level', sa.String(length=120), nullable=True),
    sa.Column('venue', sa.String(length=200), nullable=True),
    sa.Column('from_date', sa.Date(), nullable=True),
    sa.Column('to_date', sa.Date(), nullable=True),
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('trainer_id', app.models.base.GUID(), nullable=False),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('trainer_training', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_trainer_training_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_training_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_training_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_trainer_training_trainer_id'), ['trainer_id'], unique=False)

    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.add_column(sa.Column('school_type', sa.String(length=20), nullable=True))

    with op.batch_alter_table('trainer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('father_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('mother_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('dob', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('domicile_state', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('social_category_id', app.models.base.GUID(), nullable=True))
        batch_op.add_column(sa.Column('marital_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('nationality', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('blood_group', sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column('aadhaar_number', sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column('vtp_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('correspondence_address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('permanent_address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('appointment_nature', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('beneficiary_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('bank_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('branch_address', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('account_number', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('ifsc_code', sa.String(length=11), nullable=True))
        batch_op.add_column(sa.Column('gross_salary', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('deduction_esi', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('deduction_epf', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('deduction_tds', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('deduction_other', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('pan_number', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('esi_number', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('uan_number', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('vt_signature_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('vtp_signature_url', sa.String(length=500), nullable=True))
        batch_op.create_foreign_key('fk_trainer_social_category_id_social_category', 'social_category', ['social_category_id'], ['id'])



def downgrade():
    with op.batch_alter_table('trainer', schema=None) as batch_op:
        batch_op.drop_constraint('fk_trainer_social_category_id_social_category', type_='foreignkey')
        batch_op.drop_column('vtp_signature_url')
        batch_op.drop_column('vt_signature_url')
        batch_op.drop_column('uan_number')
        batch_op.drop_column('esi_number')
        batch_op.drop_column('pan_number')
        batch_op.drop_column('deduction_other')
        batch_op.drop_column('deduction_tds')
        batch_op.drop_column('deduction_epf')
        batch_op.drop_column('deduction_esi')
        batch_op.drop_column('gross_salary')
        batch_op.drop_column('ifsc_code')
        batch_op.drop_column('account_number')
        batch_op.drop_column('branch_address')
        batch_op.drop_column('bank_name')
        batch_op.drop_column('beneficiary_name')
        batch_op.drop_column('appointment_nature')
        batch_op.drop_column('permanent_address')
        batch_op.drop_column('correspondence_address')
        batch_op.drop_column('vtp_name')
        batch_op.drop_column('aadhaar_number')
        batch_op.drop_column('blood_group')
        batch_op.drop_column('nationality')
        batch_op.drop_column('marital_status')
        batch_op.drop_column('social_category_id')
        batch_op.drop_column('domicile_state')
        batch_op.drop_column('dob')
        batch_op.drop_column('mother_name')
        batch_op.drop_column('father_name')
        batch_op.drop_column('photo_url')

    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.drop_column('school_type')

    with op.batch_alter_table('trainer_training', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_trainer_training_trainer_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_training_status'))
        batch_op.drop_index(batch_op.f('ix_trainer_training_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_training_is_deleted'))

    op.drop_table('trainer_training')
    with op.batch_alter_table('trainer_qualification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_trainer_qualification_trainer_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_qualification_status'))
        batch_op.drop_index(batch_op.f('ix_trainer_qualification_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_qualification_is_deleted'))

    op.drop_table('trainer_qualification')
    with op.batch_alter_table('trainer_posting', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_trainer_posting_trainer_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_posting_status'))
        batch_op.drop_index(batch_op.f('ix_trainer_posting_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_posting_is_deleted'))

    op.drop_table('trainer_posting')
    with op.batch_alter_table('trainer_experience', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_trainer_experience_trainer_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_experience_status'))
        batch_op.drop_index(batch_op.f('ix_trainer_experience_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_trainer_experience_is_deleted'))

    op.drop_table('trainer_experience')
