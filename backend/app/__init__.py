"""Application factory - spec Part 6.2."""
import logging

import click
from flask import Flask, jsonify
from sqlalchemy import text
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.extensions import db, migrate, jwt, cors, limiter


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())
    _refuse_development_secrets(app)

    # Nginx sits in front of the API: take the visitor's address (and http/https)
    # from the one X-Forwarded-For / X-Forwarded-Proto entry it adds, so login
    # limits and the audit log see people, not Nginx. One proxy, so x_for=1.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_cli(app)

    # Structured logging with request context (spec 6.9)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # security headers on every response (spec 7.8)
    from app.utils.security import apply_security_headers
    is_prod = app.config.get("ENV") == "production" or not app.config.get("DEBUG")

    @app.after_request
    def _security_headers(response):
        return apply_security_headers(response, is_prod)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/health/deep")
    def health_deep():
        """/health, plus the database and Redis - for the uptime alarm, which
        should go off when the API is up but can't do anything."""
        checks = {"database": "ok", "redis": "ok"}
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - any failure means "down"
            db.session.rollback()
            checks["database"] = "down"
        try:
            import redis
            redis.Redis.from_url(app.config["REDIS_URL"], socket_timeout=1,
                                 socket_connect_timeout=1).ping()
        except Exception:  # noqa: BLE001
            checks["redis"] = "down"
        healthy = all(v == "ok" for v in checks.values())
        return jsonify({"status": "ok" if healthy else "down", **checks}), 200 if healthy else 503

    return app


# what the Config class falls back to when a key is unset, and the .env example files' placeholders
_DEVELOPMENT_SECRET_MARKER = "change-me"


def _refuse_development_secrets(app):
    """Production must not start on a development key: they are written in
    this repository, so anyone who has read it could sign a login token."""
    if app.config.get("ENV") != "production" or app.config.get("TESTING"):
        return
    weak = [name for name in ("SECRET_KEY", "JWT_SECRET_KEY")
            if len(app.config.get(name) or "") < 32
            or _DEVELOPMENT_SECRET_MARKER in app.config.get(name)]
    if weak:
        raise RuntimeError(
            f"{' and '.join(weak)} must be set in .env.prod to a long random value, "
            "different for each - make one with: "
            "python3 -c \"import secrets; print(secrets.token_urlsafe(48))\"")


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
                  supports_credentials=True)
    limiter.init_app(app)
    from app.services import cache
    cache.init_app(app)

    # import models so metadata is populated
    from app import models  # noqa: F401


def _register_blueprints(app):
    from app.api.auth import bp as auth_bp
    from app.api.users import bp as users_bp
    from app.api.resource import bp as resource_bp
    from app.api.workflow import bp as workflow_bp
    from app.api.dashboard import bp as dashboard_bp
    from app.api.meta import bp as meta_bp
    from app.api.admin import bp as admin_bp
    from app.api.targets import bp as targets_bp
    from app.api.promotion import bp as promotion_bp
    from app.api.profile import bp as profile_bp
    from app.api.students import bp as students_admin_bp
    from app.api.my_notifications import bp as my_notifications_bp

    # meta + workflow + users + admin must register before the catch-all resource
    # bp, which owns /api/<resource>.
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(meta_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(targets_bp)
    app.register_blueprint(promotion_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(students_admin_bp)
    app.register_blueprint(my_notifications_bp)
    app.register_blueprint(resource_bp)


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http(exc):
        return jsonify({"error": exc.name, "message": exc.description}), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        app.logger.exception("Unhandled error")
        if app.config.get("DEBUG"):
            return jsonify({"error": "Internal Server Error", "message": str(exc)}), 500
        return jsonify({"error": "Internal Server Error"}), 500

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({"error": "Unauthorized", "message": reason}), 401

    @jwt.expired_token_loader
    def expired_token(header, payload):
        return jsonify({"error": "Unauthorized", "message": "Token expired"}), 401


def _register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables directly from the models - throwaway databases only.

        It records nothing in Alembic's history, so a database built this way
        cannot be upgraded later. Anything you intend to keep should be created
        with `flask db upgrade` instead.
        """
        db.create_all()
        print("Tables created. (No migration history - use `flask db upgrade` "
              "for any database you intend to keep.)")

    @app.cli.command("create-super-admin")
    @click.option("--email", required=True, help="Their email - also their username.")
    @click.option("--name", "full_name", required=True, help="Their full name.")
    def create_super_admin(email, full_name):
        """The first real login on a new site: one Super Admin, with a random
        password printed once. Refuses if a Super Admin already exists; they
        add the organisations, which brings their Org Admin logins."""
        from app.api.users import new_password
        from app.models.user import User
        from app.rbac.roles import Role
        from app.services import audit

        email = email.strip().lower()
        if db.session.query(User).filter(User.role == Role.SUPER_ADMIN.value).first():
            raise click.ClickException("A Super Admin already exists - nothing was created.")
        if db.session.query(User).filter(User.email == email).first():
            raise click.ClickException(f"A login with the email {email} already exists.")
        password = new_password(length=16)
        user = User(full_name=full_name.strip(), email=email, role=Role.SUPER_ADMIN.value,
                    must_change_password=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        audit.record(None, "create", "app_user", user.id, after=user.public_dict())
        db.session.commit()
        click.echo(f"Super Admin created.\n  Username: {email}\n  Password: {password}\n"
                   "This password is shown only now - put it in the password manager.")

    @app.cli.command("seed")
    def seed():
        from app.seed import run_seed
        run_seed()

    @app.cli.command("seed-demo")
    def seed_demo():
        """A complete demo site - every role, seven schools, a year and a bit
        of work. Run on a migrated database (`flask db upgrade`); safe to rerun."""
        from app.full_seed import run_full_seed
        run_full_seed()

    @app.cli.command("demo-data")
    def demo_data():
        """Older name for `flask seed-demo`."""
        from app.full_seed import run_full_seed
        run_full_seed()

    @app.cli.command("test-schools")
    def test_schools():
        """Three schools on known landmarks, each with a trainer and principal
        login - for trying out location tracking (run after `flask seed`)."""
        from app.test_schools import run_test_schools
        run_test_schools()
