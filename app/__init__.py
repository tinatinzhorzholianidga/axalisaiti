"""Application factory for the eLearning / CyberHero platform."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import redis
from flask import Flask, g, request, session
from flask_babel import get_locale
from flask_bootstrap import Bootstrap5

from app.config import ProductionConfig, get_config
from app.errors import register_error_handlers
from app.extensions import babel, cache, csrf, db, limiter, login_manager, mail, migrate, sess
from app.logging_config import configure_logging
from app.security import register_security_headers

log = logging.getLogger(__name__)


def _check_translations(app: Flask) -> list[str]:
    """Languages other than the source language must have a compiled .mo file."""
    missing: list[str] = []
    base = Path(app.config["BABEL_TRANSLATION_DIRECTORIES"])
    for code in app.config["LANGUAGES"]:
        if code == "en":
            continue
        if not (base / code / "LC_MESSAGES" / "messages.mo").exists():
            missing.append(code)
    if missing:
        app.logger.warning(
            "No compiled translation catalogue for %s; run: pybabel compile -d app/translations -f",
            ", ".join(missing),
        )
    app.config["TRANSLATIONS_MISSING"] = missing
    return missing


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
        static_url_path="/static",
    )
    config_cls = get_config(config_name)
    app.config.from_object(config_cls)
    if overrides:
        app.config.update(overrides)

    if config_cls is ProductionConfig:
        problems = ProductionConfig.validate()
        if problems:
            raise RuntimeError("Refusing to start in production:\n - " + "\n - ".join(problems))

    configure_logging(app)
    _init_extensions(app)
    _check_translations(app)
    _register_blueprints(app)
    _register_context(app)
    register_security_headers(app)
    register_error_handlers(app)

    from app.cli import register_cli

    register_cli(app)

    upload_path = app.config.get("UPLOAD_PATH")
    if upload_path:
        Path(upload_path).mkdir(parents=True, exist_ok=True)

    log.info("Application created (env=%s)", app.config.get("APP_ENV"))
    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(app.root_path).parent / "migrations"))

    # Server-side sessions.
    if app.config.get("SESSION_TYPE") == "redis":
        app.config["SESSION_REDIS"] = redis.Redis.from_url(app.config["REDIS_URL"])
    elif app.config.get("SESSION_TYPE") == "cachelib":
        from cachelib import SimpleCache

        app.config["SESSION_CACHELIB"] = SimpleCache(threshold=5000, default_timeout=43200)
    sess.init_app(app)

    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    Bootstrap5(app)

    from app.utils.locale import select_locale

    babel.init_app(
        app,
        default_locale=app.config["BABEL_DEFAULT_LOCALE"],
        locale_selector=select_locale,
        default_translation_directories=app.config["BABEL_TRANSLATION_DIRECTORIES"],
    )

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = None
    login_manager.session_protection = "strong"

    from app.services.auth_service import load_user_from_session_id

    login_manager.user_loader(load_user_from_session_id)

    from app.celery_app import init_celery

    init_celery(app)


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.api import bp as api_bp
    from app.blueprints.assessments import bp as assessments_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.certificates import bp as certificates_bp
    from app.blueprints.courses import bp as courses_bp
    from app.blueprints.cyberhero import bp as cyberhero_bp
    from app.blueprints.discussions import bp as discussions_bp
    from app.blueprints.instructor import bp as instructor_bp
    from app.blueprints.learning import bp as learning_bp
    from app.blueprints.main import bp as main_bp
    from app.blueprints.media import bp as media_bp
    from app.blueprints.notifications import bp as notifications_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(courses_bp, url_prefix="/courses")
    app.register_blueprint(learning_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(certificates_bp, url_prefix="/certificates")
    app.register_blueprint(discussions_bp, url_prefix="/discussions")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(instructor_bp, url_prefix="/instructor")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(media_bp, url_prefix="/media")
    if app.config.get("CYBERHERO_ENABLED"):
        app.register_blueprint(cyberhero_bp, url_prefix="/cyberhero")


def _register_context(app: Flask) -> None:
    from app.services import feature_flags, settings_service
    from app.utils import template_helpers

    template_helpers.register(app)

    @app.before_request
    def _reset_request_caches() -> None:
        # ``g`` is per app-context; the test client reuses a pushed context, so
        # clear per-request caches explicitly (harmless in production).
        for key in list(vars(g)):
            if key != "request_id":
                g.pop(key, None)

    @app.before_request
    def _persist_locale_choice() -> None:
        lang = request.args.get("lang")
        if lang in app.config["LANGUAGES"]:
            session["locale"] = lang

    @app.context_processor
    def _inject_globals() -> dict:
        from flask_login import current_user

        from app.services import notification_service

        locale = str(get_locale() or app.config["BABEL_DEFAULT_LOCALE"])
        return {
            "unread_notifications": lambda: notification_service.unread_count(current_user),
            "support_email": settings_service.get("site.support_email", ""),
            "current_locale": locale,
            "available_languages": app.config["LANGUAGES"],
            "site_name": settings_service.get("site.title", app.config["SITE_NAME"]),
            "feature_enabled": feature_flags.is_enabled,
            "maintenance_banner": settings_service.get("site.maintenance_banner", ""),
            "request_id": g.get("request_id", ""),
            "cyberhero_enabled": feature_flags.is_enabled("CYBERHERO_ENABLED"),
        }


__all__ = ["create_app"]

# Ensure the package works when executed by gunicorn without APP_ENV.
os.environ.setdefault("APP_ENV", "development")
