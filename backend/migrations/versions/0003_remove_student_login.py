"""remove student login

Students are records kept by staff; they never sign in. Drops the two columns
that linked a student to a login (app_user.student_id and student.user_id),
and retires any Student (ST) accounts that already exist so they can no longer
authenticate.

Revision ID: 0003_remove_student_login
Revises: 0002_daily_entry
Create Date: 2026-09-24 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# The project's portable-UUID column type (native UUID on Postgres, CHAR(36)
# elsewhere) - autogenerate renders it by its full path, so it must be imported.
import app.models.base


# revision identifiers, used by Alembic.
revision = '0003_remove_student_login'
down_revision = '0002_daily_entry'
branch_labels = None
depends_on = None


def upgrade():
    # Soft-delete + disable, rather than delete: audit rows and diary entries
    # may still reference these users by id.
    app_user = sa.table(
        'app_user',
        sa.column('role', sa.String),
        sa.column('is_deleted', sa.Boolean),
        sa.column('status', sa.String),
    )
    op.execute(
        app_user.update()
        .where(app_user.c.role == 'ST')
        .values(is_deleted=True, status='disabled')
    )

    with op.batch_alter_table('app_user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_app_user_student_id_student', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_app_user_student_id'))
        batch_op.drop_column('student_id')

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_constraint('fk_student_user_id_app_user', type_='foreignkey')
        batch_op.drop_column('user_id')


def downgrade():
    # Restores the columns only; the links they held are not recoverable.
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', app.models.base.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_student_user_id_app_user', 'app_user', ['user_id'], ['id'])

    with op.batch_alter_table('app_user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('student_id', app.models.base.GUID(), nullable=True))
        batch_op.create_index(batch_op.f('ix_app_user_student_id'), ['student_id'], unique=False)
        batch_op.create_foreign_key('fk_app_user_student_id_student', 'student', ['student_id'], ['id'])
