"""school location, vt daily and class attendance

Schools get a location (admins enter it); a trainer's daily attendance and the
new class attendance record where they were, and how far that was from the
school - attendance is only accepted within 1 km. Class attendance carries
which students attended.

Revision ID: 0010_attendance_location
Revises: 0009_year_follows_date
Create Date: 2026-09-25 09:48:39.633280

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0010_attendance_location'
down_revision = '0009_year_follows_date'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('class_attendance',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('trainer_id', app.models.base.GUID(), nullable=True),
    sa.Column('school_id', app.models.base.GUID(), nullable=True),
    sa.Column('lab_id', app.models.base.GUID(), nullable=True),
    sa.Column('job_role_id', app.models.base.GUID(), nullable=True),
    sa.Column('academic_year', sa.String(length=20), nullable=True),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('time', sa.Time(), nullable=True),
    sa.Column('class_grade', sa.String(length=10), nullable=True),
    sa.Column('sections', sa.String(length=80), nullable=True),
    sa.Column('activity', sa.Text(), nullable=True),
    sa.Column('photo_url', sa.String(length=500), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('distance_from_school_m', sa.Float(), nullable=True),
    sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeogFromText', name='geography'), nullable=True),
    sa.Column('location_accuracy_m', sa.Float(), nullable=True),
    sa.Column('location_captured_at', sa.DateTime(), nullable=True),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['job_role_id'], ['job_role.id'], ),
    sa.ForeignKeyConstraint(['lab_id'], ['lab.id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('class_attendance', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_class_attendance_academic_year'), ['academic_year'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_lab_id'), ['lab_id'], unique=False)
        batch_op.create_index('ix_class_attendance_location', ['location'], unique=False, postgresql_using='gist')
        batch_op.create_index(batch_op.f('ix_class_attendance_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_school_id'), ['school_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_trainer_id'), ['trainer_id'], unique=False)

    op.create_table('class_attendance_student_mark',
    sa.Column('organisation_id', app.models.base.GUID(), nullable=False),
    sa.Column('class_attendance_id', app.models.base.GUID(), nullable=False),
    sa.Column('student_id', app.models.base.GUID(), nullable=False),
    sa.Column('present', sa.Boolean(), nullable=True),
    sa.Column('id', app.models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', app.models.base.GUID(), nullable=True),
    sa.Column('updated_by', app.models.base.GUID(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['class_attendance_id'], ['class_attendance.id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisation.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('class_attendance_student_mark', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_class_attendance_student_mark_class_attendance_id'), ['class_attendance_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_student_mark_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_student_mark_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_student_mark_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_class_attendance_student_mark_student_id'), ['student_id'], unique=False)

    with op.batch_alter_table('daily_attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attendance_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('distance_from_school_m', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeogFromText', name='geography'), nullable=True))
        batch_op.add_column(sa.Column('location_accuracy_m', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location_captured_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_daily_attendance_location', ['location'], unique=False, postgresql_using='gist')

    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeogFromText', name='geography'), nullable=True))
        batch_op.create_index('ix_school_location', ['location'], unique=False, postgresql_using='gist')



def downgrade():
    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.drop_index('ix_school_location', postgresql_using='gist')
        batch_op.drop_column('location')

    with op.batch_alter_table('daily_attendance', schema=None) as batch_op:
        batch_op.drop_index('ix_daily_attendance_location', postgresql_using='gist')
        batch_op.drop_column('location_captured_at')
        batch_op.drop_column('location_accuracy_m')
        batch_op.drop_column('location')
        batch_op.drop_column('distance_from_school_m')
        batch_op.drop_column('photo_url')
        batch_op.drop_column('attendance_time')

    with op.batch_alter_table('class_attendance_student_mark', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_class_attendance_student_mark_student_id'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_student_mark_status'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_student_mark_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_student_mark_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_student_mark_class_attendance_id'))

    op.drop_table('class_attendance_student_mark')
    with op.batch_alter_table('class_attendance', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_class_attendance_trainer_id'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_status'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_school_id'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_organisation_id'))
        batch_op.drop_index('ix_class_attendance_location', postgresql_using='gist')
        batch_op.drop_index(batch_op.f('ix_class_attendance_lab_id'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_date'))
        batch_op.drop_index(batch_op.f('ix_class_attendance_academic_year'))

    op.drop_table('class_attendance')
