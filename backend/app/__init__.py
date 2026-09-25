"""Application factory - spec Part 6.2."""
import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.config import get_config
from app.extensions import db, migrate, jwt, cors, limiter


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

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

    return app


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

    @app.cli.command("seed")
    def seed():
        from app.seed import run_seed
        run_seed()
