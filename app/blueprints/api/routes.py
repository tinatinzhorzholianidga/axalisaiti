"""JSON API v1: session, courses, search, progress, notifications, bookmarks."""

from __future__ import annotations

from flask import current_app, jsonify, request
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from app.blueprints.api import bp
from app.blueprints.api.helpers import api_error, api_locale, json_body, login_required_json
from app.extensions import limiter
from app.models import BookmarkType
from app.repositories import course_repository as repo
from app.repositories.course_repository import CatalogFilters
from app.services import (
    bookmark_service,
    course_service,
    enrollment_service,
    notification_service,
    progress_service,
    search_service,
)


@bp.before_request
def _rate_limit_api():  # type: ignore[no-untyped-def]
    return None


@bp.get("/auth/csrf")
@limiter.exempt
def csrf_token():  # type: ignore[no-untyped-def]
    return jsonify({"csrf_token": generate_csrf()})


@bp.get("/auth/session")
def session_info():  # type: ignore[no-untyped-def]
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False, "locale": api_locale()})
    return jsonify(
        {
            "authenticated": True,
            "locale": api_locale(),
            "user": {
                "id": current_user.id,
                "name": current_user.name,
                "email": current_user.email,
                "roles": sorted(current_user.role_names),
                "permissions": sorted(current_user.permission_codes),
            },
            "unread_notifications": notification_service.unread_count(current_user),
        }
    )


def _course_json(course, locale: str) -> dict:  # type: ignore[no-untyped-def]
    tr = course.tr(locale)
    return {
        "slug": course.slug,
        "title": course.title(locale),
        "short_description": tr.short_description if tr else "",
        "difficulty": course.difficulty.value,
        "estimated_minutes": course.estimated_minutes,
        "lesson_count": course.lesson_count,
        "categories": [c.slug for c in course.categories],
        "icon": course.icon,
        "is_featured": course.is_featured,
        "certificate_enabled": course.certificate_enabled,
        "rating": course.rating_avg,
        "enrollments": course.enrollment_count,
        "url": f"/courses/{course.slug}/",
    }


@bp.get("/courses")
@limiter.limit(lambda: current_app.config["RATELIMIT_API"])
def list_courses():  # type: ignore[no-untyped-def]
    locale = api_locale()
    filters = CatalogFilters(
        query=(request.args.get("q") or "").strip()[:100] or None,
        category=request.args.get("category") or None,
        difficulty=request.args.get("difficulty") or None,
        duration=request.args.get("duration") or None,
        sort=request.args.get("sort") or "newest",
        page=max(1, request.args.get("page", 1, type=int)),
        per_page=min(50, max(1, request.args.get("per_page", 12, type=int))),
    )
    pagination = course_service.catalog(filters, locale)
    return jsonify(
        {
            "items": [_course_json(c, locale) for c in pagination.items],
            "page": pagination.page,
            "pages": pagination.pages,
            "total": pagination.total,
        }
    )


@bp.get("/courses/<slug>")
def course_detail(slug: str):  # type: ignore[no-untyped-def]
    locale = api_locale()
    course = course_service.get_course(slug)
    if course is None:
        return api_error(404, "Course not found")
    data = _course_json(course, locale)
    tr = course.tr(locale)
    data["description_html"] = tr.description if tr else ""
    data["objectives"] = tr.objective_list if tr else []
    data["modules"] = [
        {
            "id": m.id,
            "title": m.title(locale),
            "lessons": [
                {
                    "slug": lesson.slug,
                    "title": lesson.title(locale),
                    "type": lesson.lesson_type.value,
                    "minutes": lesson.estimated_minutes,
                    "free_preview": lesson.is_free_preview,
                }
                for lesson in m.lessons
                if lesson.is_published
            ],
        }
        for m in course.modules
        if m.is_published
    ]
    if current_user.is_authenticated:
        progress = progress_service.get_course_progress(current_user, course)
        data["enrolled"] = enrollment_service.is_enrolled(current_user, course)
        data["progress_percent"] = progress.percent if progress else 0
    return jsonify(data)


@bp.get("/search")
@limiter.limit(lambda: current_app.config["RATELIMIT_API"])
def search():  # type: ignore[no-untyped-def]
    locale = api_locale()
    query = (request.args.get("q") or "").strip()[:100]
    results = search_service.search_all(query, locale, limit=8) if query else {}
    return jsonify(
        {
            "query": query,
            "courses": [_course_json(c, locale) for c in results.get("courses", [])],
            "lessons": [
                {
                    "title": lesson.title(locale),
                    "course": course.title(locale),
                    "url": f"/learn/{course.slug}/{lesson.slug}/",
                }
                for lesson, course in results.get("lessons", [])
            ],
            "resources": [
                {
                    "title": r.title(locale),
                    "url": r.url or f"/learn/{r.lesson.course.slug}/{r.lesson.slug}/",
                }
                for r in results.get("resources", [])
            ],
        }
    )


@bp.post("/progress/lessons/<int:lesson_id>/complete")
@login_required_json
def complete_lesson(lesson_id: int):  # type: ignore[no-untyped-def]
    from app.models import Lesson

    lesson = repo.db.session.get(Lesson, lesson_id)
    if lesson is None or not lesson.is_published:
        return api_error(404, "Lesson not found")
    course = lesson.course
    if not enrollment_service.is_enrolled(current_user, course):
        return api_error(403, "Not enrolled")
    progress = progress_service.complete_lesson(current_user, course, lesson)
    return jsonify(
        {"completed": True, "course_percent": progress.percent, "is_complete": progress.is_complete}
    )


@bp.post("/progress/lessons/<int:lesson_id>/heartbeat")
@login_required_json
def lesson_heartbeat(lesson_id: int):  # type: ignore[no-untyped-def]
    """Adds time-on-lesson (capped per call) for learning statistics."""
    from app.extensions import db
    from app.models import Lesson

    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        return api_error(404, "Lesson not found")
    try:
        seconds = int(json_body().get("seconds", 0))
    except (ValueError, TypeError):
        return api_error(400, "Invalid payload")
    seconds = max(0, min(seconds, 300))
    if enrollment_service.is_enrolled(current_user, lesson.course):
        state = progress_service.touch_lesson(current_user, lesson.course, lesson)
        state.seconds_spent = (state.seconds_spent or 0) + seconds
        db.session.commit()
    return jsonify({"ok": True})


@bp.get("/notifications")
@login_required_json
def notifications():  # type: ignore[no-untyped-def]
    items = notification_service.recent(current_user, limit=10)
    return jsonify(
        {
            "unread": notification_service.unread_count(current_user),
            "items": [
                {
                    "id": n.id,
                    "kind": n.kind,
                    "title": n.title,
                    "body": n.body,
                    "link": n.link,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat(),
                }
                for n in items
            ],
        }
    )


@bp.post("/notifications/<int:notification_id>/read")
@login_required_json
def notification_read(notification_id: int):  # type: ignore[no-untyped-def]
    if not notification_service.mark_read(current_user, notification_id):
        return api_error(404, "Notification not found")
    return jsonify({"ok": True, "unread": notification_service.unread_count(current_user)})


@bp.post("/notifications/read-all")
@login_required_json
def notifications_read_all():  # type: ignore[no-untyped-def]
    return jsonify({"ok": True, "marked": notification_service.mark_all_read(current_user)})


@bp.post("/bookmarks")
@login_required_json
def toggle_bookmark():  # type: ignore[no-untyped-def]
    try:
        data = json_body()
        target_type = BookmarkType(str(data.get("type")))
        target_id = int(data.get("id") or 0)
    except (ValueError, TypeError):
        return api_error(400, "Invalid payload")
    added = bookmark_service.toggle(current_user, target_type, target_id)
    return jsonify({"bookmarked": added})
