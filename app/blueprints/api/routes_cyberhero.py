"""CyberHero JSON API (`/api/v1/cyberhero/*`), consumed by the React app."""

from __future__ import annotations

from flask import current_app, jsonify, request
from flask_login import current_user

from app.blueprints.api import bp
from app.blueprints.api.helpers import api_error, api_locale, json_body, login_required_json
from app.extensions import limiter
from app.repositories import course_repository as repo
from app.services import cyberhero_service as ch
from app.services import feature_flags, settings_service
from app.services.cyberhero_service import CyberHeroError

PREFIX = "/cyberhero"


@bp.before_request
def _cyberhero_enabled():  # type: ignore[no-untyped-def]
    if (request.endpoint or "").startswith("api.cyberhero_") and not feature_flags.is_enabled(
        "CYBERHERO_ENABLED"
    ):
        return api_error(404, "CyberHero is not enabled")
    return None


def _settings() -> dict:
    cybercrime = ""
    if settings_service.get("cyberhero.cybercrime_contact_verified", False):
        cybercrime = str(settings_service.get("cyberhero.cybercrime_contact", "") or "")
    return {
        "emergency_phone": str(settings_service.get("cyberhero.emergency_phone", "112")),
        "cybercrime_contact": cybercrime,
        "help_line": str(settings_service.get("cyberhero.help_line", "") or ""),
    }


@bp.get(f"{PREFIX}/bootstrap")
def cyberhero_bootstrap():  # type: ignore[no-untyped-def]
    tracks = ch.tracks()
    featured = [
        s.strip()
        for s in str(settings_service.get("cyberhero.featured_tracks", "guardians,parents")).split(
            ","
        )
        if s.strip()
    ]
    user = None
    if current_user.is_authenticated:
        user = {"id": current_user.id, "display_name": current_user.name}
    return jsonify(
        {
            "locale": api_locale(),
            "flags": {
                "CYBERHERO_IO_CHAT_ENABLED": feature_flags.is_enabled("CYBERHERO_IO_CHAT_ENABLED")
            },
            "user": user,
            "settings": _settings(),
            "featured_tracks": featured,
            "tiers": [ch.serialize_track(t) for t in tracks],
            "mascot": ch.mascot(),
        }
    )


@bp.get(f"{PREFIX}/tracks")
def cyberhero_tracks():  # type: ignore[no-untyped-def]
    return jsonify({"items": [ch.serialize_track(t) for t in ch.tracks()]})


@bp.get(f"{PREFIX}/tracks/<slug>")
def cyberhero_track(slug: str):  # type: ignore[no-untyped-def]
    track = next((t for t in ch.tracks() if t.slug == slug), None)
    if track is None:
        return api_error(404, "Track not found")
    data = ch.serialize_track(track)
    data["missions"] = [ch.serialize_mission_meta(m) for m in ch.missions(slug)]
    data["courses"] = [ch.serialize_course_meta(c) for c in ch.courses(slug)]
    return jsonify(data)


@bp.get(f"{PREFIX}/missions")
def cyberhero_missions():  # type: ignore[no-untyped-def]
    track = request.args.get("track") or None
    return jsonify({"items": [ch.serialize_mission_meta(m) for m in ch.missions(track)]})


@bp.get(f"{PREFIX}/missions/<slug>")
def cyberhero_mission(slug: str):  # type: ignore[no-untyped-def]
    mission = ch.mission_by_slug(slug)
    if mission is None or not mission.is_published or mission.track.is_hidden:
        return api_error(404, "Mission not found")
    return jsonify(ch.serialize_mission(mission))


@bp.get(f"{PREFIX}/articles")
def cyberhero_articles():  # type: ignore[no-untyped-def]
    shelf = request.args.get("shelf") or None
    return jsonify({"items": [ch.serialize_article_meta(a) for a in ch.articles(shelf)]})


@bp.get(f"{PREFIX}/articles/<slug>")
def cyberhero_article(slug: str):  # type: ignore[no-untyped-def]
    article = ch.article_by_slug(slug)
    if article is None or not article.is_published:
        return api_error(404, "Article not found")
    return jsonify(ch.serialize_article(article))


@bp.get(f"{PREFIX}/agreement")
def cyberhero_agreement():  # type: ignore[no-untyped-def]
    data = ch.agreement()
    if data is None:
        return api_error(404, "Agreement not configured")
    return jsonify(data)


@bp.get(f"{PREFIX}/resources/<kind>")
def cyberhero_resources(kind: str):  # type: ignore[no-untyped-def]
    if kind not in {"emergency_contact", "playbook", "guide"}:
        return api_error(404, "Unknown resource kind")
    return jsonify(
        {"items": [ch.serialize_resource(r) for r in ch.resources(kind)], "settings": _settings()}
    )


@bp.get(f"{PREFIX}/mascot")
def cyberhero_mascot():  # type: ignore[no-untyped-def]
    return jsonify(ch.mascot())


@bp.get(f"{PREFIX}/knowledge")
@limiter.limit("30 per minute")
def cyberhero_knowledge():  # type: ignore[no-untyped-def]
    if not feature_flags.is_enabled("CYBERHERO_IO_CHAT_ENABLED"):
        return api_error(404, "IO tutor is not enabled")
    return jsonify(ch.knowledge())


@bp.get(f"{PREFIX}/courses")
def cyberhero_courses():  # type: ignore[no-untyped-def]
    track = request.args.get("track") or None
    return jsonify({"items": [ch.serialize_course_meta(c) for c in ch.courses(track)]})


@bp.get(f"{PREFIX}/courses/<slug>")
def cyberhero_course(slug: str):  # type: ignore[no-untyped-def]
    course = ch.course_by_slug(slug)
    if course is None:
        return api_error(404, "Course not found")
    return jsonify(ch.serialize_course(course))


@bp.get(f"{PREFIX}/courses/<slug>/lessons/<lesson_slug>")
def cyberhero_lesson(slug: str, lesson_slug: str):  # type: ignore[no-untyped-def]
    course = ch.course_by_slug(slug)
    lesson = repo.lesson_by_slugs(slug, lesson_slug) if course else None
    if course is None or lesson is None or not lesson.is_published:
        return api_error(404, "Lesson not found")
    return jsonify(ch.serialize_lesson(course, lesson))


@bp.get(f"{PREFIX}/progress")
@login_required_json
def cyberhero_progress_get():  # type: ignore[no-untyped-def]
    return jsonify(ch.get_progress(current_user))


@bp.put(f"{PREFIX}/progress")
@login_required_json
@limiter.limit("60 per minute")
def cyberhero_progress_put():  # type: ignore[no-untyped-def]
    try:
        payload = json_body()
        return jsonify(ch.merge_progress(current_user, payload))
    except (ValueError, CyberHeroError) as exc:
        return api_error(400, str(exc))


@bp.post(f"{PREFIX}/certificates")
@limiter.limit(lambda: current_app.config["RATELIMIT_RESET"])
def cyberhero_certificate_create():  # type: ignore[no-untyped-def]
    try:
        payload = json_body()
        certificate = ch.issue_certificate(
            track_slug=str(payload.get("track", "guardians"))[:80],
            display_name=str(payload.get("display_name", "")),
            completed=payload.get("completed_missions") or {},
            user=current_user if current_user.is_authenticated else None,
        )
    except (ValueError, CyberHeroError) as exc:
        return api_error(400, str(exc))
    return jsonify(ch.serialize_certificate(certificate)), 201


@bp.get(f"{PREFIX}/certificates/<public_id>")
@limiter.limit("60 per minute")
def cyberhero_certificate_get(public_id: str):  # type: ignore[no-untyped-def]
    certificate = ch.verify_certificate(public_id)
    if certificate is None:
        return jsonify({"valid": False, "public_id": public_id[:40]}), 404
    return jsonify(ch.serialize_certificate(certificate))
