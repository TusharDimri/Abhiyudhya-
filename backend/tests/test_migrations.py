"""The migrations must describe the models - exactly.

This is the check that would have caught the situation these migrations were
written for: a column added to a model, and no migration to put it in the
database. It runs the whole migration history against an empty database and
asserts Alembic sees nothing left to generate.
"""
import os
import pathlib

import pytest

os.environ["TESTING"] = "1"

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from flask import Flask  # noqa: E402

from sqlalchemy import text  # noqa: E402

from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
import app.models  # noqa: F401,E402  - populates db.metadata


def _empty_the_database():
    """Start from nothing - including Alembic's own version table."""
    if db.engine.dialect.name == "postgresql":
        with db.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    else:
        db.drop_all()
        with db.engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations"


@pytest.fixture
def migrated_db(tmp_path):
    """An empty database brought up to date by `flask db upgrade`."""
    uri = TestConfig.SQLALCHEMY_DATABASE_URI
    flask_app = Flask(__name__)
    flask_app.config.from_object(TestConfig)
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = uri
    db.init_app(flask_app)
    with flask_app.app_context():
        _empty_the_database()

    cfg = Config(str(MIGRATIONS / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", uri)
    with flask_app.app_context():
        # env.py reads the app's engine/metadata through Flask-Migrate
        from flask_migrate import Migrate
        Migrate(flask_app, db, directory=str(MIGRATIONS))
        command.upgrade(cfg, "head")
        yield flask_app


def test_upgrade_runs_cleanly_from_empty(migrated_db):
    with migrated_db.app_context():
        from sqlalchemy import inspect
        tables = set(inspect(db.engine).get_table_names())
    assert "alembic_version" in tables, "migration history was not recorded"
    # a spot-check across the three things migration 0002 introduces
    assert "field_visit_student_mark" in tables
    assert "daily_attendance" in tables
    assert "lab" in tables


def test_no_model_change_is_missing_a_migration(migrated_db):
    """If this fails, a model changed without a migration. Generate one:
        flask --app app:create_app db migrate -m "what changed"
    then review the generated file before committing it."""
    with migrated_db.app_context():
        with db.engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn, opts={"compare_type": True, "target_metadata": db.metadata}
            )
            diff = compare_metadata(ctx, db.metadata)

    # indexes on SQLite reflect slightly differently; only structural drift matters
    interesting = [
        d for d in diff
        if not (isinstance(d, tuple) and d and str(d[0]).endswith("_index"))
    ]
    assert not interesting, (
        "models and migrations have drifted:\n  "
        + "\n  ".join(repr(d) for d in interesting)
    )


def test_foreign_keys_match_the_models(migrated_db, tmp_path):
    """Constraints, not just columns.

    Six foreign keys are declared `use_alter=True` to break a creation cycle
    (app_user -> school -> principal -> app_user). `op.create_table` leaves
    those OUT of the CREATE TABLE it emits, so the baseline has to add them
    back by hand - and if someone regenerates it and forgets, the columns all
    still line up and only the constraints quietly go missing. This is the
    check that notices.
    """
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.engine import make_url

    def fk_names(engine):
        insp = inspect(engine)
        out = set()
        for t in insp.get_table_names():
            for fk in insp.get_foreign_keys(t):
                out.add((t, tuple(fk["constrained_columns"]), fk["referred_table"]))
        return out

    with migrated_db.app_context():
        migrated = fk_names(db.engine)

    # build a second database straight from the models and compare
    modelled_url = make_url(TestConfig.SQLALCHEMY_DATABASE_URI)
    if modelled_url.get_backend_name() == "postgresql":
        modelled_url = modelled_url.set(database=f"{modelled_url.database}_models")
        admin = create_engine(modelled_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{modelled_url.database}"'))
            conn.execute(text(f'CREATE DATABASE "{modelled_url.database}"'))
        admin.dispose()
    else:
        modelled_url = make_url(f"sqlite+pysqlite:///{tmp_path / 'modelled.db'}")
    modelled_engine = create_engine(modelled_url)
    db.metadata.create_all(modelled_engine)
    modelled = fk_names(modelled_engine)
    modelled_engine.dispose()

    missing = modelled - migrated
    assert not missing, (
        "foreign keys the models have but the migrations do not create:\n  "
        + "\n  ".join(repr(m) for m in sorted(missing))
    )


def test_downgrade_then_upgrade_is_a_round_trip(migrated_db, tmp_path):
    cfg = Config(str(MIGRATIONS / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", migrated_db.config["SQLALCHEMY_DATABASE_URI"])
    with migrated_db.app_context():
        command.downgrade(cfg, "0001_baseline")
        from sqlalchemy import inspect
        assert "industry_name" not in {
            c["name"] for c in inspect(db.engine).get_columns("daily_attendance")
        }
        command.upgrade(cfg, "head")
        assert "industry_name" in {
            c["name"] for c in inspect(db.engine).get_columns("daily_attendance")
        }
