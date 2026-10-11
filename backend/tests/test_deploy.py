"""What production on AWS relies on: real visitor addresses behind Nginx,
logins that survive Redis going down, refusing development keys, the deep
health check, and the command that makes the first Super Admin."""
import os

os.environ["TESTING"] = "1"

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db, limiter  # noqa: E402
from app.models.misc import AuditLog  # noqa: E402
from app.models.user import User  # noqa: E402
from tests.conftest import reset_schema  # noqa: E402

NGINX = {"REMOTE_ADDR": "172.18.0.5"}   # every request reaches gunicorn from the Nginx container
NOWHERE = "redis://127.0.0.1:1/0"       # nothing listens on port 1


def _make(config):
    app = create_app(config)
    with app.app_context():
        reset_schema()
    return app


def _bad_login(client, visitor):
    return client.post("/api/auth/login", json={"email": "nobody@x.com", "password": "wrong"},
                       headers={"X-Forwarded-For": visitor}, environ_base=NGINX)


# ------------------------------------------------------- real visitor address
class RateLimited(TestConfig):
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"


def test_login_limit_counts_each_visitor_not_nginx():
    client = _make(RateLimited).test_client()
    for _ in range(10):
        assert _bad_login(client, "203.0.113.1").status_code == 401
    assert _bad_login(client, "203.0.113.1").status_code == 429
    # someone else behind the same Nginx still gets their own ten tries
    assert _bad_login(client, "203.0.113.2").status_code == 401


def test_the_api_sees_the_address_nginx_saw_not_one_the_visitor_wrote():
    from flask import request
    app = _make(TestConfig)
    app.add_url_rule("/whoami", "whoami", lambda: request.remote_addr)   # what audit.record stores
    client = app.test_client()

    seen = client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.9"}, environ_base=NGINX)
    assert seen.get_data(as_text=True) == "203.0.113.9"
    # a made-up header from the browser comes first; Nginx appends the real address last
    spoofed = client.get("/whoami", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.9"}, environ_base=NGINX)
    assert spoofed.get_data(as_text=True) == "203.0.113.9"


# ------------------------------------------------------------ Redis outage
class RedisDown(TestConfig):
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = NOWHERE
    REDIS_URL = NOWHERE


@pytest.fixture
def redis_down():
    app = _make(RedisDown)
    yield app
    limiter._storage_dead = False   # the limiter is shared by every app in the test run


def test_logins_still_work_when_redis_is_down(redis_down):
    r = _bad_login(redis_down.test_client(), "203.0.113.1")
    assert r.status_code == 401, "a wrong password, not a server error"


def test_deep_health_reports_redis_down(redis_down):
    r = redis_down.test_client().get("/health/deep")
    assert r.status_code == 503
    assert r.get_json() == {"status": "down", "database": "ok", "redis": "down"}


def test_plain_health_does_not_touch_the_database(redis_down):
    assert redis_down.test_client().get("/health").get_json() == {"status": "ok"}


# --------------------------------------------------------- production keys
class Production(TestConfig):
    TESTING = False
    ENV = "production"


@pytest.mark.parametrize("secret", [None, "dev-secret-change-me", "change-me", "short-but-random-1234"])
def test_production_refuses_development_or_short_keys(secret):
    cfg = type("Weak", (Production,), {"SECRET_KEY": secret, "JWT_SECRET_KEY": "x" * 64})
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(cfg)


def test_production_starts_with_long_random_keys():
    cfg = type("Strong", (Production,), {"SECRET_KEY": "a" * 64, "JWT_SECRET_KEY": "b" * 64})
    assert create_app(cfg).config["ENV"] == "production"


def test_development_keys_are_fine_off_production():
    assert create_app(TestConfig).config["SECRET_KEY"] == "dev-secret-change-me"


# ------------------------------------------------------------ S3 settings
def test_blank_s3_settings_mean_unset(monkeypatch):
    """`S3_ACCESS_KEY=` in .env.prod must leave boto3 free to use the IAM role."""
    from app.config import _optional
    monkeypatch.setenv("S3_ACCESS_KEY", "")
    assert _optional("S3_ACCESS_KEY") is None
    monkeypatch.delenv("S3_ACCESS_KEY")
    assert _optional("S3_ACCESS_KEY") is None
    monkeypatch.setenv("S3_ACCESS_KEY", "minioadmin")
    assert _optional("S3_ACCESS_KEY") == "minioadmin"


# ----------------------------------------------------- the first Super Admin
@pytest.fixture
def app():
    app = _make(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()


def _create(app, email="Admin@RNAF.org ", name="Asha Rao"):
    return app.test_cli_runner().invoke(args=["create-super-admin", "--email", email, "--name", name])


def test_create_super_admin_prints_a_working_password_once(app):
    out = _create(app)
    assert out.exit_code == 0, out.output
    password = out.output.split("Password: ")[1].split()[0]

    user = db.session.query(User).filter_by(email="admin@rnaf.org").one()
    assert user.role == "SA" and user.organisation_id is None and user.must_change_password
    assert db.session.query(AuditLog).filter_by(entity="app_user", entity_id=user.id).count() == 1

    login = app.test_client().post("/api/auth/login", json={"email": "admin@rnaf.org", "password": password})
    assert login.status_code == 200
    assert login.get_json()["user"]["role"] == "SA"


def test_create_super_admin_refuses_a_second_one(app):
    assert _create(app).exit_code == 0
    again = _create(app, email="other@rnaf.org")
    assert again.exit_code != 0 and "already exists" in again.output
    assert db.session.query(User).count() == 1


def test_create_super_admin_refuses_a_taken_email(app):
    taken = User(full_name="T", email="admin@rnaf.org", role="OA")
    taken.set_password("Password@123")
    db.session.add(taken)
    db.session.commit()
    out = _create(app)
    assert out.exit_code != 0 and "admin@rnaf.org already exists" in out.output
