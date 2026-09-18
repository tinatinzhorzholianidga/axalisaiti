"""Public course catalogue, course detail, enrolment, bookmarks and reviews."""

from __future__ import annotations

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.courses import bp
from app.forms.courses import CatalogFilterForm, ReviewForm
from app.models import BookmarkType, EnrollmentStatus
from app.repositories.course_repository import CatalogFilters
from app.services import (
    bookmark_service,
    course_service,
    enrollment_service,
    progress_service,
    review_service,
)
from app.services.enrollment_service import EnrollmentError
from app.services.rbac import require_permission
from app.services.review_service import ReviewError


@bp.route("/")
def catalog():  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    form = CatalogFilterForm(request.args, meta={"csrf": False})
    categories = course_service.active_categories()
    form.category.choices = [("", _("All categories"))] + [
        (c.slug, c.name(locale)) for c in categories
    ]
    filters = CatalogFilters(
        query=(form.q.data or "").strip()[:100] or None,
        category=form.category.data or None,
        difficulty=form.difficulty.data or None,
        duration=form.duration.data or None,
        sort=form.sort.data or "newest",
        page=max(1, request.args.get("page", 1, type=int)),
        per_page=current_app.config["ITEMS_PER_PAGE"],
    )
    pagination = course_service.catalog(filters, locale)
    progress_map = {}
    if current_user.is_authenticated:
        for course in pagination.items:
            progress = progress_service.get_course_progress(current_user, course)
            if progress:
                progress_map[course.id] = progress
    return render_template(
        "courses/catalog.html",
        form=form,
        pagination=pagination,
        categories=categories,
        filters=filters,
        progress_map=progress_map,
        locale=locale,
    )


@bp.route("/<slug>/")
def detail(slug: str):  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    course = course_service.get_course(slug, published_only=False)
    if course is None:
        abort(404)
    if not course.is_published and not (
        current_user.is_authenticated
        and (
            current_user.has_permission("courses.manage_all")
            or course.instructor_id == current_user.id
            or course.created_by_id == current_user.id
        )
    ):
        abort(404)
    enrollment = enrollment_service.get_enrollment(current_user, course)
    progress = progress_service.get_course_progress(current_user, course)
    lesson_progress = progress_service.lesson_progress_map(current_user, course)
    next_lesson = (
        progress_service.continue_lesson(current_user, course)
        if enrollment and enrollment.status in {EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED}
        else None
    )
    reviews = review_service.approved_reviews(course)
    review_form = ReviewForm()
    existing_review = review_service.user_review(current_user, course)
    if existing_review:
        review_form.rating.data = existing_review.rating
        review_form.body.data = existing_review.body
    return render_template(
        "courses/detail.html",
        course=course,
        tr=course.tr(locale),
        locale=locale,
        enrollment=enrollment,
        progress=progress,
        lesson_progress=lesson_progress,
        next_lesson=next_lesson,
        reviews=reviews,
        review_form=review_form,
        can_review=review_service.can_review(current_user, course),
        reviews_enabled=review_service.reviews_enabled(course),
        is_bookmarked=bookmark_service.is_bookmarked(current_user, BookmarkType.COURSE, course.id),
        active_tab=request.args.get("tab", "overview"),
    )


@bp.route("/<slug>/enroll", methods=["POST"])
@login_required
@require_permission("courses.enroll")
def enroll(slug: str):  # type: ignore[no-untyped-def]
    course = course_service.get_course(slug)
    if course is None:
        abort(404)
    try:
        enrollment = enrollment_service.enroll(current_user, course)
    except EnrollmentError as exc:
        flash(str(exc), "error")
        return redirect(url_for("courses.detail", slug=slug))
    if enrollment.status == EnrollmentStatus.PENDING:
        flash(_("Your enrolment request was sent to the instructor."), "info")
        return redirect(url_for("courses.detail", slug=slug))
    flash(_("You are enrolled. Let's start learning."), "success")
    lesson = progress_service.continue_lesson(current_user, course)
    if lesson:
        return redirect(url_for("learning.lesson", course_slug=slug, lesson_slug=lesson.slug))
    return redirect(url_for("courses.detail", slug=slug))


@bp.route("/<slug>/drop", methods=["POST"])
@login_required
def drop(slug: str):  # type: ignore[no-untyped-def]
    course = course_service.get_course(slug)
    if course is None:
        abort(404)
    enrollment_service.drop(current_user, course)
    flash(_("You left the course. Your progress is kept if you return."), "info")
    return redirect(url_for("courses.detail", slug=slug))


@bp.route("/<slug>/bookmark", methods=["POST"])
@login_required
def bookmark(slug: str):  # type: ignore[no-untyped-def]
    course = course_service.get_course(slug)
    if course is None:
        abort(404)
    added = bookmark_service.toggle(current_user, BookmarkType.COURSE, course.id)
    flash(_("Bookmarked.") if added else _("Bookmark removed."), "info")
    return redirect(request.referrer or url_for("courses.detail", slug=slug))


@bp.route("/<slug>/review", methods=["POST"])
@login_required
@require_permission("reviews.write")
def review(slug: str):  # type: ignore[no-untyped-def]
    course = course_service.get_course(slug)
    if course is None:
        abort(404)
    form = ReviewForm()
    if not form.validate_on_submit():
        flash(_("Please choose a rating."), "error")
        return redirect(url_for("courses.detail", slug=slug, tab="reviews"))
    try:
        review_service.submit_review(current_user, course, form.rating.data, form.body.data or "")
    except ReviewError as exc:
        flash(str(exc), "error")
    else:
        flash(_("Thank you! Your review will appear after moderation."), "success")
    return redirect(url_for("courses.detail", slug=slug, tab="reviews"))
