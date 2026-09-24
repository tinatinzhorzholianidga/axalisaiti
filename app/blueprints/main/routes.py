"""Public pages: home, about, resources, search, health."""

from __future__ import annotations

from typing import Any

from flask import current_app, jsonify, render_template, request
from flask_babel import get_locale
from flask_login import current_user
from sqlalchemy import text

from app.blueprints.cyberhero import routes as cyberhero_routes
from app.blueprints.main import bp
from app.extensions import csrf, db, limiter
from app.services import (
    case_study_service,
    course_service,
    feature_flags,
    resource_service,
    search_service,
)


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


def io_host_context() -> dict[str, Any]:
    """IO, the platform's welcome host, floating in the corner of the home page.

    The 3D host ships in the CyberHero bundle (``cyberhero/src/io-host.jsx``) and
    reads its configuration from ``data-*`` attributes on ``#io-host-root``; without
    a build the widget is left out. His "doors" are the page's own buttons tagged
    ``data-io-path``: the course catalogue, and CyberHero while that product is
    enabled.
    """
    doors = ["basic"]
    if feature_flags.is_enabled("CYBERHERO_ENABLED"):
        doors.append("kids")
    return {
        "assets": cyberhero_routes.bundle_assets(cyberhero_routes.ENTRY_IO_HOST),
        "doors": ",".join(doors),
        "skin": "classic",
    }


@bp.route("/")
def home():  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    categories = course_service.active_categories()
    stats = course_service.public_stats()
    threats_slug = case_study_service.home_category_slug()
    stats["case_studies"] = case_study_service.count_published()
    stats["threats"] = case_study_service.count_in_category(threats_slug) if threats_slug else 0
    return render_template(
        "main/home.html",
        threats=case_study_service.home_picks(),
        threats_category=(
            case_study_service.category_by_slug(threats_slug) if threats_slug else None
        ),
        categories=categories,
        stats=stats,
        locale=locale,
        io_host=io_host_context(),
    )


@bp.route("/about/")
def about():  # type: ignore[no-untyped-def]
    return render_template("main/about.html")


@bp.route("/resources/")
def resources():  # type: ignore[no-untyped-def]
    return render_template(
        "main/resources.html",
        resources=resource_service.visible(),
        course_resources=resource_service.course_resources_for(current_user),
    )


@bp.route("/search/")
def search():  # type: ignore[no-untyped-def]
    query = (request.args.get("q") or "").strip()[:100]
    results = search_service.search_all(query, locale=str(get_locale())) if query else None
    return render_template("main/search.html", query=query, results=results)
