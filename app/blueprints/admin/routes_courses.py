from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale, page, per_page
from app.extensions import db
from app.forms.authoring import CategoryForm, CourseForm, ReviewDecisionForm
from app.models import Category, Course, CourseStatus
from app.services import authoring_service, course_service, notification_service
from app.services.media_service import UploadError
from app.services.rbac import require_permission


def _prepare(form: CourseForm) -> None:
    form.categories.choices = authoring_service.category_choices(locale())
    form.instructor_id.choices = authoring_service.instructor_choices()
    form.cyber_track_id.choices = authoring_service.track_choices()


@bp.route("/courses/")
@require_permission("courses.manage_all")
def courses():  # type: ignore[no-untyped-def]
    status = request.args.get("status") or None
    platform = request.args.get("platform") or None
    query = (request.args.get("q") or "").strip()[:100]
    stmt = course_service.courses_for_admin(status=status, platform=platform, query=query or None)
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    return render_template(
        "admin/courses.html",
        pagination=pagination,
        status=status,
        platform=platform,
        q=query,
        locale=locale(),
    )


@bp.route("/courses/new", methods=["GET", "POST"])
@require_permission("courses.manage_all")
def course_new():  # type: ignore[no-untyped-def]
    form = CourseForm()
    _prepare(form)
    if form.validate_on_submit():
        try:
            course = authoring_service.create_course_from_form(
                form, current_user, allow_platform=True, allow_instructor=True
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Course created."), "success")
            return redirect(url_for("admin.course_detail", course_id=course.id))
    return render_template("admin/course_form.html", form=form, course=None, locale=locale())


@bp.route("/courses/<int:course_id>", methods=["GET", "POST"])
@require_permission("courses.manage_all")
def course_detail(course_id: int):  # type: ignore[no-untyped-def]
    course = get_or_404(Course, course_id)
    form = CourseForm()
    _prepare(form)
    decision = ReviewDecisionForm(prefix="review")
    if request.method == "GET":
        authoring_service.fill_course_form(form, course)
    if form.submit.data and form.validate_on_submit():
        try:
            authoring_service.update_course_from_form(
                course, form, current_user, allow_platform=True, allow_instructor=True
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Course saved."), "success")
            return redirect(url_for("admin.course_detail", course_id=course.id))
    return render_template(
        "admin/course_form.html", form=form, course=course, decision=decision, locale=locale()
    )


@bp.route("/courses/<int:course_id>/status", methods=["POST"])
@require_permission("courses.publish")
def course_status(course_id: int):  # type: ignore[no-untyped-def]
    course = get_or_404(Course, course_id)
    form = ReviewDecisionForm(prefix="review")
    if not form.validate_on_submit():
        abort(400)
    if form.approve.data:
        course_service.set_status(
            course, CourseStatus.PUBLISHED, actor=current_user, note=form.note.data or ""
        )
        message = _("Course published.")
        kind, title = "course_update", _("Your course was published")
    elif form.reject.data:
        course_service.set_status(
            course, CourseStatus.DRAFT, actor=current_user, note=form.note.data or ""
        )
        message = _("Course sent back to draft.")
        kind, title = "course_update", _("Your course needs changes")
    else:
        status = request.form.get("status", "")
        try:
            course_service.set_status(course, CourseStatus(status), actor=current_user)
        except ValueError:
            abort(400)
        message = _("Status updated.")
        kind, title = "course_update", _("Course status changed")
    if course.instructor_id and course.instructor_id != current_user.id:
        notification_service.notify(
            course.instructor_id,
            kind=kind,
            title=f"{title}: {course.title('en') or course.slug}",
            body=form.note.data or "",
            link=f"/instructor/courses/{course.id}/builder",
        )
    flash(message, "success")
    return redirect(url_for("admin.course_detail", course_id=course.id))


@bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@require_permission("courses.manage_all")
def course_delete(course_id: int):  # type: ignore[no-untyped-def]
    course = get_or_404(Course, course_id)
    course_service.delete_course(course, actor=current_user)
    flash(_("Course deleted."), "info")
    return redirect(url_for("admin.courses"))


@bp.route("/courses/<int:course_id>/feature", methods=["POST"])
@require_permission("courses.manage_all")
def course_feature(course_id: int):  # type: ignore[no-untyped-def]
    course = get_or_404(Course, course_id)
    course.is_featured = not course.is_featured
    db.session.commit()
    return redirect(request.referrer or url_for("admin.courses"))


# ---- categories -------------------------------------------------------------
@bp.route("/categories/", methods=["GET", "POST"])
@require_permission("categories.manage")
def categories():  # type: ignore[no-untyped-def]
    form = CategoryForm()
    if form.validate_on_submit():
        course_service.create_category(
            slug=form.slug.data,
            actor=current_user,
            translations={
                "ka": {"name": form.name_ka.data, "description": form.description_ka.data or ""},
                "en": {"name": form.name_en.data, "description": form.description_en.data or ""},
            },
            icon=form.icon.data or "shield",
            color=form.color.data,
            platform=form.platform.data,
            sort_order=form.sort_order.data or 0,
            is_active=bool(form.is_active.data),
        )
        flash(_("Category created."), "success")
        return redirect(url_for("admin.categories"))
    items = db.session.query(Category).order_by(Category.sort_order).all()
    return render_template("admin/categories.html", items=items, form=form, locale=locale())


@bp.route("/categories/<int:category_id>", methods=["GET", "POST"])
@require_permission("categories.manage")
def category_edit(category_id: int):  # type: ignore[no-untyped-def]
    category = get_or_404(Category, category_id)
    form = CategoryForm()
    if request.method == "GET":
        form.slug.data = category.slug
        form.name_ka.data = category.name("ka")
        form.name_en.data = (
            category.text("name", "en")
            if any(t.locale == "en" for t in category.translations)
            else ""
        )
        form.description_ka.data = category.text("description", "ka")
        form.description_en.data = (
            category.text("description", "en")
            if any(t.locale == "en" for t in category.translations)
            else ""
        )
        form.icon.data = category.icon
        form.color.data = category.color
        form.platform.data = category.platform.value
        form.sort_order.data = category.sort_order
        form.is_active.data = category.is_active
    if form.validate_on_submit():
        course_service.update_category(
            category,
            actor=current_user,
            translations={
                "ka": {"name": form.name_ka.data, "description": form.description_ka.data or ""},
                "en": {"name": form.name_en.data, "description": form.description_en.data or ""},
            },
            icon=form.icon.data or "shield",
            color=form.color.data,
            platform=form.platform.data,
            sort_order=form.sort_order.data or 0,
            is_active=bool(form.is_active.data),
        )
        flash(_("Category saved."), "success")
        return redirect(url_for("admin.categories"))
    return render_template(
        "admin/category_form.html", form=form, category=category, locale=locale()
    )


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@require_permission("categories.manage")
def category_delete(category_id: int):  # type: ignore[no-untyped-def]
    category = get_or_404(Category, category_id)
    db.session.delete(category)
    db.session.commit()
    flash(_("Category deleted."), "info")
    return redirect(url_for("admin.categories"))
