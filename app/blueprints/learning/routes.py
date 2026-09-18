"""Learner experience: dashboard, profile, lesson view, bookmarks."""

from __future__ import annotations

import json

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.learning import bp
from app.forms.profile import DeactivateForm, NotificationPrefsForm, ProfileForm
from app.models import BookmarkType, EnrollmentStatus, LessonType, ProgressStatus
from app.repositories import course_repository as repo
from app.services import (
    achievement_service,
    bookmark_service,
    certificate_service,
    course_service,
    enrollment_service,
    notification_service,
    progress_service,
    user_service,
)
from app.services.rbac import can_manage_course


def _course_or_404(slug: str):  # type: ignore[no-untyped-def]
    course = course_service.get_course(slug, published_only=False)
    if course is None:
        abort(404)
    return course


def _can_access(course, lesson) -> bool:  # type: ignore[no-untyped-def]
    if current_user.is_authenticated and can_manage_course(current_user, course):
        return True
    if not course.is_published:
        return False
    if lesson.is_free_preview:
        return True
    return enrollment_service.is_enrolled(current_user, course)


@bp.route("/dashboard/")
@login_required
def dashboard():  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    enrollments = enrollment_service.user_enrollments(
        current_user,
        statuses=(EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED, EnrollmentStatus.PENDING),
    )
    active = [e for e in enrollments if e.status == EnrollmentStatus.ACTIVE]
    completed = [e for e in enrollments if e.status == EnrollmentStatus.COMPLETED]
    pending = [e for e in enrollments if e.status == EnrollmentStatus.PENDING]
    progress_map = {
        e.course_id: progress_service.get_course_progress(current_user, e.course)
        for e in enrollments
    }
    continue_items = []
    for enrollment in active[:3]:
        lesson = progress_service.continue_lesson(current_user, enrollment.course)
        continue_items.append((enrollment, lesson, progress_map.get(enrollment.course_id)))
    recently_viewed = sorted(
        [e for e in enrollments if e.last_accessed_at],
        key=lambda e: e.last_accessed_at,
        reverse=True,
    )[:4]
    enrolled_ids = {e.course_id for e in enrollments}
    recommended = [c for c in course_service.featured_courses(limit=8) if c.id not in enrolled_ids][
        :3
    ]
    return render_template(
        "learning/dashboard.html",
        locale=locale,
        active=active,
        completed=completed,
        pending=pending,
        progress_map=progress_map,
        continue_items=continue_items,
        recently_viewed=recently_viewed,
        certificates=certificate_service.user_certificates(current_user)[:4],
        achievements=achievement_service.user_achievements(current_user)[:6],
        stats=progress_service.dashboard_summary(current_user),
        notifications=notification_service.recent(current_user, limit=5),
        recommended=recommended,
    )


@bp.route("/learn/<course_slug>/<lesson_slug>/")
def lesson(course_slug: str, lesson_slug: str):  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    course = _course_or_404(course_slug)
    lesson = repo.lesson_by_slugs(course_slug, lesson_slug)
    if lesson is None or (
        not lesson.is_published
        and not (current_user.is_authenticated and can_manage_course(current_user, course))
    ):
        abort(404)
    if not _can_access(course, lesson):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        flash(_("Enrol in the course to open this lesson."), "warning")
        return redirect(url_for("courses.detail", slug=course_slug))

    lesson_progress = {}
    progress = None
    if current_user.is_authenticated and enrollment_service.is_enrolled(current_user, course):
        progress_service.touch_lesson(current_user, course, lesson)
        lesson_progress = progress_service.lesson_progress_map(current_user, course)
        progress = progress_service.get_course_progress(current_user, course)
    lessons = course_service.visible_lessons(course)
    index = next((i for i, item in enumerate(lessons) if item.id == lesson.id), 0)
    prev_lesson, next_lesson = course_service.neighbours(course, lesson)
    state = lesson_progress.get(lesson.id)
    quiz_attempts = []
    if lesson.quiz and current_user.is_authenticated:
        from app.services import quiz_service

        quiz_attempts = quiz_service.user_attempts(current_user, lesson.quiz)
    submission = None
    if lesson.assignment and current_user.is_authenticated:
        from app.services import assignment_service

        submission = assignment_service.latest_submission(current_user, lesson.assignment)
    return render_template(
        "learning/lesson.html",
        course=course,
        lesson=lesson,
        tr=lesson.tr(locale),
        locale=locale,
        lessons=lessons,
        index=index + 1,
        total=len(lessons),
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
        lesson_progress=lesson_progress,
        progress=progress,
        is_completed=bool(state and state.status == ProgressStatus.COMPLETED),
        is_bookmarked=bookmark_service.is_bookmarked(current_user, BookmarkType.LESSON, lesson.id),
        quiz_attempts=quiz_attempts,
        submission=submission,
        LessonType=LessonType,
    )


@bp.route("/learn/<course_slug>/<lesson_slug>/complete", methods=["POST"])
@login_required
def complete_lesson(course_slug: str, lesson_slug: str):  # type: ignore[no-untyped-def]
    course = _course_or_404(course_slug)
    lesson = repo.lesson_by_slugs(course_slug, lesson_slug)
    if lesson is None:
        abort(404)
    if not enrollment_service.is_enrolled(current_user, course):
        abort(403)
    if (
        lesson.lesson_type == LessonType.QUIZ
        and lesson.quiz
        and not progress_service.quiz_passed(current_user, lesson.quiz)
    ):
        flash(_("Pass the quiz to complete this lesson."), "warning")
        return redirect(
            url_for("learning.lesson", course_slug=course_slug, lesson_slug=lesson_slug)
        )
    progress_service.complete_lesson(current_user, course, lesson)
    _prev, next_lesson = course_service.neighbours(course, lesson)
    if request.form.get("goto") == "next" and next_lesson:
        return redirect(
            url_for("learning.lesson", course_slug=course_slug, lesson_slug=next_lesson.slug)
        )
    flash(_("Lesson marked as complete."), "success")
    return redirect(url_for("learning.lesson", course_slug=course_slug, lesson_slug=lesson_slug))


@bp.route("/learn/<course_slug>/<lesson_slug>/bookmark", methods=["POST"])
@login_required
def bookmark_lesson(course_slug: str, lesson_slug: str):  # type: ignore[no-untyped-def]
    lesson = repo.lesson_by_slugs(course_slug, lesson_slug)
    if lesson is None:
        abort(404)
    added = bookmark_service.toggle(current_user, BookmarkType.LESSON, lesson.id)
    flash(_("Bookmarked.") if added else _("Bookmark removed."), "info")
    return redirect(url_for("learning.lesson", course_slug=course_slug, lesson_slug=lesson_slug))


@bp.route("/bookmarks/")
@login_required
def bookmarks():  # type: ignore[no-untyped-def]
    return render_template(
        "learning/bookmarks.html",
        items=bookmark_service.list_for_user(current_user),
        locale=str(get_locale()),
    )


@bp.route("/profile/", methods=["GET", "POST"])
@login_required
def profile():  # type: ignore[no-untyped-def]
    form = ProfileForm(obj=current_user)
    prefs_form = NotificationPrefsForm(prefix="prefs")
    if request.method == "GET":
        prefs = current_user.notification_prefs or {}
        for field in prefs_form:
            if field.name.startswith("prefs-email_"):
                key = field.name.replace("prefs-", "")
                field.data = prefs.get(key, field.default)
    if form.submit.data and form.validate_on_submit():
        user_service.update_profile(
            current_user,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            display_name=form.display_name.data,
            organization=form.organization.data,
            bio=form.bio.data,
            locale=form.locale.data,
            theme=form.theme.data,
        )
        flash(_("Profile saved."), "success")
        return redirect(url_for("learning.profile", lang=form.locale.data))
    if prefs_form.submit.data and prefs_form.validate_on_submit():
        user_service.update_notification_prefs(
            current_user,
            {
                f.name.replace("prefs-", ""): f.data
                for f in prefs_form
                if f.name.startswith("prefs-email_")
            },
        )
        flash(_("Notification preferences saved."), "success")
        return redirect(url_for("learning.profile") + "#notifications")
    enrollments = enrollment_service.user_enrollments(current_user)
    return render_template(
        "learning/profile.html",
        form=form,
        prefs_form=prefs_form,
        deactivate_form=DeactivateForm(prefix="deact"),
        enrollments=enrollments,
        certificates=certificate_service.user_certificates(current_user),
        achievements=achievement_service.user_achievements(current_user),
        locale=str(get_locale()),
    )


@bp.route("/profile/export")
@login_required
def export_data():  # type: ignore[no-untyped-def]
    payload = json.dumps(user_service.export_data(current_user), ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=my-data.json"},
    )


@bp.route("/profile/deactivate", methods=["POST"])
@login_required
def deactivate():  # type: ignore[no-untyped-def]
    form = DeactivateForm(prefix="deact")
    if not form.validate_on_submit() or not current_user.check_password(form.password.data):
        flash(_("Password confirmation failed."), "error")
        return redirect(url_for("learning.profile") + "#privacy")
    user_service.deactivate(current_user, actor=current_user)
    from app.services import auth_service

    auth_service.logout()
    flash(_("Your account has been deactivated. Contact support to restore it."), "info")
    return redirect(url_for("main.home"))
