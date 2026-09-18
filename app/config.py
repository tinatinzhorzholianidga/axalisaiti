"""Application configuration.

Every setting comes from the environment. ``ProductionConfig.validate`` refuses
to start with insecure defaults (weak SECRET_KEY, debug, insecure cookies,
missing database).
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

WEAK_SECRETS = {
    "",
    "secret",
    "changeme",
    "change-me",
    "dev",
    "development",
    "password",
    "change-me-to-a-long-random-string-at-least-32-chars",
}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class BaseConfig:
    APP_ENV = os.environ.get("APP_ENV", "development")
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SITE_NAME = os.environ.get("SITE_NAME", "eLearning")
    SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
    CERTIFICATE_ORG_NAME = os.environ.get(
        "CERTIFICATE_ORG_NAME", "Digital Governance Agency of Georgia"
    )
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # --- database -----------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # --- redis --------------------------------------------------------------
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # --- sessions (server side, Redis) -------------------------------------
    SESSION_TYPE = "redis"
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_KEY_PREFIX = "elearning:session:"
    SESSION_COOKIE_NAME = "elearning_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    SESSION_REFRESH_EACH_REQUEST = False
    REMEMBER_COOKIE_NAME = "elearning_remember"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    # --- CSRF ---------------------------------------------------------------
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False  # nginx terminates TLS; Origin/Referer checked by SameSite + tokens

    # --- rate limiting ------------------------------------------------------
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", REDIS_URL)
    RATELIMIT_DEFAULT = "600 per minute"
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_KEY_PREFIX = "elearning:rl"
    RATELIMIT_AUTH = "10 per minute;50 per hour"
    RATELIMIT_REGISTER = "5 per minute;20 per hour"
    RATELIMIT_RESET = "5 per minute;20 per hour"
    RATELIMIT_API = "120 per minute"

    # --- cache --------------------------------------------------------------
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_KEY_PREFIX = "elearning:cache:"
    CACHE_DEFAULT_TIMEOUT = 300

    # --- celery -------------------------------------------------------------
    CELERY = {
        "broker_url": os.environ.get("CELERY_BROKER_URL", REDIS_URL),
        "result_backend": os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL),
        "task_always_eager": env_bool("CELERY_TASK_ALWAYS_EAGER", False),
        "task_ignore_result": True,
        "broker_connection_retry_on_startup": True,
        "task_serializer": "json",
        "accept_content": ["json"],
    }

    # --- i18n ---------------------------------------------------------------
    BABEL_DEFAULT_LOCALE = os.environ.get("DEFAULT_LOCALE", "ka")
    BABEL_DEFAULT_TIMEZONE = "Asia/Tbilisi"
    BABEL_TRANSLATION_DIRECTORIES = str(BASE_DIR / "app" / "translations")
    LANGUAGES = {"ka": "ქართული", "en": "English"}

    # --- mail ---------------------------------------------------------------
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@elearning.gov.ge")
    MAIL_SUPPRESS_SEND = env_bool("MAIL_SUPPRESS_SEND", False)

    # --- uploads ------------------------------------------------------------
    UPLOAD_PATH = os.environ.get("UPLOAD_PATH", str(BASE_DIR / "data" / "uploads"))
    MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 25)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

    # --- auth policy --------------------------------------------------------
    PASSWORD_MIN_LENGTH = env_int("PASSWORD_MIN_LENGTH", 12)
    LOGIN_MAX_FAILED = env_int("LOGIN_MAX_FAILED", 5)
    LOGIN_LOCKOUT_MINUTES = env_int("LOGIN_LOCKOUT_MINUTES", 15)
    TOKEN_MAX_AGE_SECONDS = 3600
    REGISTRATION_ENABLED = env_bool("REGISTRATION_ENABLED", True)
    EMAIL_VERIFICATION_REQUIRED = env_bool("EMAIL_VERIFICATION_REQUIRED", False)
    INSTRUCTOR_APPROVAL_REQUIRED = env_bool("INSTRUCTOR_APPROVAL_REQUIRED", True)

    # --- features -----------------------------------------------------------
    CYBERHERO_ENABLED = env_bool("CYBERHERO_ENABLED", True)
    CYBERHERO_IO_CHAT_ENABLED = env_bool("CYBERHERO_IO_CHAT_ENABLED", False)
    CYBERHERO_STATIC_DIR = str(BASE_DIR / "app" / "static" / "cyberhero")
    # Same-origin directory with an MLC-compiled model (+ model.wasm) for the
    # in-browser IO tutor. Empty = tutor runs in course-lookup mode only.
    CYBERHERO_TUTOR_MODEL_URL = os.environ.get("CYBERHERO_TUTOR_MODEL_URL", "")

    # --- security headers ---------------------------------------------------
    HSTS_ENABLED = env_bool("HSTS_ENABLED", False)
    HSTS_MAX_AGE = 31536000
    CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", False)

    # --- misc ---------------------------------------------------------------
    WORKER_COUNT = env_int("WORKER_COUNT", 4)
    ITEMS_PER_PAGE = 12
    ADMIN_ITEMS_PER_PAGE = 25
    BOOTSTRAP_SERVE_LOCAL = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-secret-key-not-for-production-use!"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'dev.sqlite3'}"
    )
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    MAIL_SUPPRESS_SEND = env_bool("MAIL_SUPPRESS_SEND", True)
    # Local development without Redis falls back to in-process stores.
    SESSION_TYPE = os.environ.get("SESSION_TYPE", "cachelib")
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    CELERY = {**BaseConfig.CELERY, "task_always_eager": env_bool("CELERY_TASK_ALWAYS_EAGER", True)}


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "testing-secret-key-that-is-long-enough-0123456789"  # noqa: S105
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}
    SESSION_TYPE = "cachelib"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    CACHE_TYPE = "SimpleCache"
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"
    WTF_CSRF_ENABLED = True
    MAIL_SUPPRESS_SEND = True
    CELERY = {**BaseConfig.CELERY, "task_always_eager": True, "broker_url": "memory://"}
    UPLOAD_PATH = ""  # set per test session by conftest
    CYBERHERO_ENABLED = True
    CYBERHERO_IO_CHAT_ENABLED = False
    REGISTRATION_ENABLED = True
    EMAIL_VERIFICATION_REQUIRED = False
    INSTRUCTOR_APPROVAL_REQUIRED = True
    HSTS_ENABLED = False
    SERVER_NAME = None


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of fatal misconfigurations (empty when safe)."""
        problems: list[str] = []
        secret = cls.SECRET_KEY
        if len(secret) < 32 or secret.strip().lower() in WEAK_SECRETS or "change" in secret.lower():
            problems.append("SECRET_KEY must be a random string of at least 32 characters")
        if env_bool("FLASK_DEBUG", False) or cls.DEBUG:
            problems.append("Debug mode must be disabled in production")
        if not env_bool("SESSION_COOKIE_SECURE", True):
            problems.append("SESSION_COOKIE_SECURE must be true in production")
        uri = cls.SQLALCHEMY_DATABASE_URI
        if not uri:
            problems.append("DATABASE_URL is not configured")
        elif uri.startswith("sqlite"):
            problems.append("SQLite is not supported in production; use MariaDB")
        if not os.environ.get("REDIS_URL"):
            problems.append("REDIS_URL is not configured")
        if cls.MAIL_SERVER in {"", "localhost"} and not cls.MAIL_SUPPRESS_SEND:
            problems.append("MAIL_SERVER is not configured (or set MAIL_SUPPRESS_SEND=true)")
        return problems


CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    key = (name or os.environ.get("APP_ENV") or "development").lower()
    return CONFIGS.get(key, DevelopmentConfig)
