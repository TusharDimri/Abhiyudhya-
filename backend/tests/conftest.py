"""Shared test setup.

The suite runs against PostgreSQL - the same engine production uses - so the
things Postgres enforces and SQLite does not (foreign keys at table-creation
time, column types, constraint names) are enforced here too.

This file makes that painless: it creates the test database if it isn't there
yet, and gives every test an empty schema to start from.
"""
import os

os.environ["TESTING"] = "1"

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402

TEST_URL = TestConfig.SQLALCHEMY_DATABASE_URI


def _is_postgres():
    return make_url(TEST_URL).get_backend_name() == "postgresql"


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_database():
    """Create the test database once, if it doesn't already exist."""
    if not _is_postgres():
        return
    url = make_url(TEST_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": url.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except Exception as exc:  # pragma: no cover - surfaced as a clear message
        pytest.exit(
            f"Cannot reach PostgreSQL at {url.set(password='***')}.\n"
            f"Start it with:  docker compose -f docker-compose.local.yml up -d postgres\n"
            f"({exc})",
            returncode=1,
        )
    finally:
        admin.dispose()


def reset_schema():
    """Empty the database. Faster and more thorough than drop_all(), and it
    doesn't care what order the tables were created in."""
    if _is_postgres():
        db.session.remove()
        with db.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    else:
        db.drop_all()
    db.create_all()
