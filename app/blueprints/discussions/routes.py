"""Course discussions."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.discussions import bp
from app.extensions import db
from app.forms.assessments import ReplyForm, ReportForm, ThreadForm
from app.models import Discussion, DiscussionPost
from app.services import course_service, discussion_service
from app.services.discussion_service import DiscussionError


def _course(slug: str):  # type: ignore[no-untyped-def]
    course = course_service.get_course(slug, published_only=False)
    if course is None or not discussion_service.enabled(course):
        abort(404)
    if not course.is_published and not discussion_service.can_moderate(current_user, course):
        abort(404)
    return course


def _thread(course, thread_id: int) -> Discussion:  # type: ignore[no-untyped-def]
    thread = db.session.get(Discussion, thread_id)
    if thread is None or thread.course_id != course.id:
        abort(404)
    if thread.is_hidden and not discussion_service.can_moderate(current_user, course):
        abort(404)
    return thread


@bp.route("/<slug>/", methods=["GET", "POST"])
@login_required
def list_threads(slug: str):  # type: ignore[no-untyped-def]
    course = _course(slug)
    can_post = discussion_service.can_participate(current_user, course)
    form = ThreadForm()
    if form.validate_on_submit():
        try:
            thread = discussion_service.create_thread(
                current_user, course, title=form.title.data, body=form.body.data
            )
        except DiscussionError as exc:
            flash(str(exc), "error")
        else:
            return redirect(url_for("discussions.thread", slug=slug, thread_id=thread.id))
    return render_template(
        "discussions/list.html",
        course=course,
        threads=discussion_service.threads(
            course, include_hidden=discussion_service.can_moderate(current_user, course)
        ),
        form=form,
        can_post=can_post,
        can_moderate=discussion_service.can_moderate(current_user, course),
        locale=str(get_locale()),
    )


@bp.route("/<slug>/<int:thread_id>/", methods=["GET", "POST"])
@login_required
def thread(slug: str, thread_id: int):  # type: ignore[no-untyped-def]
    course = _course(slug)
    thread = _thread(course, thread_id)
    form = ReplyForm()
    if form.validate_on_submit():
        parent_id = request.form.get("parent_id", type=int)
        try:
            discussion_service.reply(current_user, thread, body=form.body.data, parent_id=parent_id)
        except DiscussionError as exc:
            flash(str(exc), "error")
        else:
            return redirect(
                url_for("discussions.thread", slug=slug, thread_id=thread.id) + "#latest"
            )
    posts = [
        p
        for p in thread.posts
        if not p.is_hidden or discussion_service.can_moderate(current_user, course)
    ]
    return render_template(
        "discussions/thread.html",
        course=course,
        thread=thread,
        posts=posts,
        form=form,
        report_form=ReportForm(),
        can_post=discussion_service.can_participate(current_user, course),
        can_moderate=discussion_service.can_moderate(current_user, course),
        locale=str(get_locale()),
    )


@bp.route("/<slug>/<int:thread_id>/moderate", methods=["POST"])
@login_required
def moderate(slug: str, thread_id: int):  # type: ignore[no-untyped-def]
    course = _course(slug)
    thread = _thread(course, thread_id)
    if not discussion_service.can_moderate(current_user, course):
        abort(403)
    action = request.form.get("action", "")
    if action in {"pin", "unpin"}:
        discussion_service.set_pinned(thread, action == "pin", current_user)
    elif action in {"lock", "unlock"}:
        discussion_service.set_locked(thread, action == "lock", current_user)
    elif action in {"hide", "unhide"}:
        discussion_service.set_hidden(thread, action == "hide", current_user)
    else:
        abort(400)
    flash(_("Thread updated."), "info")
    return redirect(url_for("discussions.thread", slug=slug, thread_id=thread.id))


@bp.route("/<slug>/post/<int:post_id>/<action>", methods=["POST"])
@login_required
def post_action(slug: str, post_id: int, action: str):  # type: ignore[no-untyped-def]
    course = _course(slug)
    post = db.session.get(DiscussionPost, post_id)
    if post is None or post.discussion.course_id != course.id:
        abort(404)
    if action == "report":
        form = ReportForm()
        if not form.validate_on_submit():
            flash(_("Please give a reason."), "error")
        else:
            discussion_service.report_post(post, current_user, form.reason.data)
            flash(_("Thank you. A moderator will review the post."), "info")
    elif action == "delete":
        try:
            discussion_service.delete_own_post(post, current_user)
        except DiscussionError as exc:
            flash(str(exc), "error")
    elif action in {"hide", "unhide"}:
        if not discussion_service.can_moderate(current_user, course):
            abort(403)
        discussion_service.hide_post(post, action == "hide", current_user)
    else:
        abort(400)
    return redirect(url_for("discussions.thread", slug=slug, thread_id=post.discussion_id))
