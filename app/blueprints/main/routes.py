"""Public pages: home, about, resources, search, health."""

from __future__ import annotations

from flask import current_app, jsonify, render_template, request
from flask_babel import get_locale
from sqlalchemy import text

from app.blueprints.main import bp
from app.extensions import csrf, db, limiter
from app.services import course_service, search_service


@bp.route("/health")
@csrf.exempt
@limiter.exempt
def health():  # type: ignore[no-untyped-def]
    return jsonify({"status": "ok"})


@bp.route("/readiness")
@csrf.exempt
@limiter.exempt
def readiness():  # type: ignore[no-untyped-def]
    checks: dict[str, str] = {}
    healthy = True
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        healthy = False
    if current_app.config.get("SESSION_TYPE") == "redis":
        try:
            current_app.config["SESSION_REDIS"].ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
            healthy = False
    else:
        checks["redis"] = "not-configured"
    missing = current_app.config.get("TRANSLATIONS_MISSING") or []
    checks["translations"] = "ok" if not missing else "missing: " + ", ".join(missing)
    status = 200 if healthy else 503
    return jsonify({"status": "ready" if healthy else "degraded", "checks": checks}), status


@bp.route("/")
def home():  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    featured = course_service.featured_courses(limit=6)
    categories = course_service.active_categories()
    stats = course_service.public_stats()
    return render_template(
        "main/home.html", featured=featured, categories=categories, stats=stats, locale=locale
    )


@bp.route("/about/")
def about():  # type: ignore[no-untyped-def]
    return render_template("main/about.html")


@bp.route("/resources/")
def resources():  # type: ignore[no-untyped-def]
    resources = course_service.public_resources(limit=60)
    return render_template("main/resources.html", resources=resources)


@bp.route("/search/")
def search():  # type: ignore[no-untyped-def]
    query = (request.args.get("q") or "").strip()[:100]
    results = search_service.search_all(query, locale=str(get_locale())) if query else None
    return render_template("main/search.html", query=query, results=results)
