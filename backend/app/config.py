"""Application configuration, loaded from environment variables.

All secrets and environment-specific values come from the environment so the
same image runs locally and in production with only env vars changing.
"""
import os
from datetime import timedelta


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes", "on")


class Config:
    # --- Core ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = _bool("FLASK_DEBUG", ENV != "production")

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://rnaf:rnaf@localhost:5432/rnaf"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_recycle": 1800,
    }

    # --- JWT ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_DAYS", "14"))
    )
    JWT_TOKEN_LOCATION = ["headers"]

    # --- CORS ---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL", "memory://")
    # Redis cache for read endpoints (services/cache.py)
    CACHE_ENABLED = _bool("CACHE_ENABLED", True)
    CACHE_PREFIX = os.getenv("CACHE_PREFIX", "rnaf")

    # --- Pagination ---
    DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "25"))
    MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "200"))

    # --- S3 / storage ---
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # set for MinIO locally
    # the same store as the browser reaches it (pre-signed upload links); blank = S3_ENDPOINT_URL
    S3_PUBLIC_ENDPOINT_URL = os.getenv("S3_PUBLIC_ENDPOINT_URL")
    S3_BUCKET = os.getenv("S3_BUCKET", "rnaf-media")
    S3_REGION = os.getenv("S3_REGION", "us-east-1")
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
    S3_PRESIGN_EXPIRY = int(os.getenv("S3_PRESIGN_EXPIRY", "3600"))

    # --- Celery / Redis ---
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)


def test_database_url() -> str:
    """Where the test suite runs - PostgreSQL, the same engine as production.

    This used to default to in-memory SQLite, which was faster but hid real
    defects: SQLite does not enforce foreign keys when creating tables, so a
    migration whose tables were created in an impossible order passed the
    whole suite and then failed on the first real deploy. A test that runs on
    a different database than you ship on is not testing what you ship.

    Set TEST_DATABASE_URL to point somewhere else (CI, a scratch server).
    """
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = os.getenv("DATABASE_URL", Config.SQLALCHEMY_DATABASE_URI)
    server, _, name = base.rpartition("/")
    return f"{server}/{name}_test"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = test_database_url()
    # A test run is one process; the production pool settings don't apply.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": False}
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    RATELIMIT_ENABLED = False
    # off unless a test switches it on (tests/test_cache.py)
    CACHE_ENABLED = False
    CACHE_PREFIX = "rnaf-test"


def get_config():
    return TestConfig if _bool("TESTING") else Config
