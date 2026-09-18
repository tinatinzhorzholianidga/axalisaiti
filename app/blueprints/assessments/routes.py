"""Quizzes and assignments for learners."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.assessments import bp
from app.extensions import db
from app.forms.assessments import SubmissionForm
from app.models import Assignment, Quiz, QuizAttempt
from app.services import assignment_service, enrollment_service, quiz_service
from app.services.assignment_service import AssignmentError
from app.services.quiz_service import QuizError
from app.services.rbac import can_manage_course, require_permission


def _quiz_or_404(quiz_id: int) -> Quiz:
    quiz = db.session.get(Quiz, quiz_id)
    if quiz is None or (not quiz.is_published and not can_manage_course(current_user, quiz.course)):
        abort(404)
    return quiz


def _require_access(course) -> None:  # type: ignore[no-untyped-def]
    if not (
        enrollment_service.is_enrolled(current_user, course)
        or can_manage_course(current_user, course)
    ):
        flash(_("Enrol in the course first."), "warning")
        abort(redirect(url_for("courses.detail", slug=course.slug)))


@bp.route("/quiz/<int:quiz_id>/")
@login_required
@require_permission("quizzes.attempt")
def quiz_intro(quiz_id: int):  # type: ignore[no-untyped-def]
    quiz = _quiz_or_404(quiz_id)
    _require_access(quiz.course)
    attempts = quiz_service.user_attempts(current_user, quiz)
    return render_template(
        "assessments/quiz_intro.html",
        quiz=quiz,
        course=quiz.course,
        locale=str(get_locale()),
        attempts=attempts,
        attempts_left=quiz_service.attempts_left(current_user, quiz),
        open_attempt=quiz_service.open_attempt(current_user, quiz),
        best=quiz_service.best_attempt(current_user, quiz),
    )


@bp.route("/quiz/<int:quiz_id>/start", methods=["POST"])
@login_required
@require_permission("quizzes.attempt")
def quiz_start(quiz_id: int):  # type: ignore[no-untyped-def]
    quiz = _quiz_or_404(quiz_id)
    _require_access(quiz.course)
    try:
        attempt = quiz_service.start_attempt(current_user, quiz)
    except QuizError as exc:
        flash(str(exc), "error")
        return redirect(url_for("assessments.quiz_intro", quiz_id=quiz.id))
    return redirect(url_for("assessments.quiz_attempt", attempt_id=attempt.id))


def _attempt_or_404(attempt_id: int) -> QuizAttempt:
    attempt = db.session.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != current_user.id:
        abort(404)
    return attempt


@bp.route("/quiz/attempt/<int:attempt_id>/", methods=["GET", "POST"])
@login_required
def quiz_attempt(attempt_id: int):  # type: ignore[no-untyped-def]
    attempt = _attempt_or_404(attempt_id)
    locale = str(get_locale())
    if attempt.status.value != "in_progress":
        return redirect(url_for("assessments.quiz_result", attempt_id=attempt.id))
    if not attempt.is_open:
        quiz_service.expire_stale_attempts()
        flash(_("Time is up for this attempt."), "warning")
        return redirect(url_for("assessments.quiz_intro", quiz_id=attempt.quiz_id))
    if request.method == "POST":
        try:
            quiz_service.submit_attempt(attempt, request.form)
        except QuizError as exc:
            flash(str(exc), "error")
            return redirect(url_for("assessments.quiz_intro", quiz_id=attempt.quiz_id))
        return redirect(url_for("assessments.quiz_result", attempt_id=attempt.id))
    questions = quiz_service.ordered_questions(attempt)
    return render_template(
        "assessments/quiz_attempt.html",
        attempt=attempt,
        quiz=attempt.quiz,
        course=attempt.quiz.course,
        questions=questions,
        options_for=lambda q: quiz_service.ordered_options(attempt, q),
        locale=locale,
    )


@bp.route("/quiz/result/<int:attempt_id>/")
@login_required
def quiz_result(attempt_id: int):  # type: ignore[no-untyped-def]
    attempt = _attempt_or_404(attempt_id)
    if attempt.status.value == "in_progress":
        return redirect(url_for("assessments.quiz_attempt", attempt_id=attempt.id))
    answers = {a.question_id: a for a in attempt.answers}
    return render_template(
        "assessments/quiz_result.html",
        attempt=attempt,
        quiz=attempt.quiz,
        course=attempt.quiz.course,
        questions=quiz_service.ordered_questions(attempt),
        answers=answers,
        show_details=quiz_service.show_details(current_user, attempt),
        attempts_left=quiz_service.attempts_left(current_user, attempt.quiz),
        locale=str(get_locale()),
    )


@bp.route("/assignment/<int:assignment_id>/", methods=["GET", "POST"])
@login_required
@require_permission("assignments.submit")
def assignment_view(assignment_id: int):  # type: ignore[no-untyped-def]
    assignment = db.session.get(Assignment, assignment_id)
    if assignment is None or (
        not assignment.is_published and not can_manage_course(current_user, assignment.course)
    ):
        abort(404)
    _require_access(assignment.course)
    form = SubmissionForm()
    if form.validate_on_submit():
        try:
            assignment_service.submit(
                current_user, assignment, text=form.text_content.data, file=form.file.data
            )
        except AssignmentError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Your work was submitted."), "success")
            return redirect(url_for("assessments.assignment_view", assignment_id=assignment.id))
    can_submit, reason = assignment_service.can_submit(current_user, assignment)
    return render_template(
        "assessments/assignment.html",
        assignment=assignment,
        course=assignment.course,
        form=form,
        submissions=assignment_service.submissions(current_user, assignment),
        can_submit=can_submit,
        reason=reason,
        locale=str(get_locale()),
    )
