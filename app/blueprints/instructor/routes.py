"""Instructor panel: own courses, builder, quizzes, assignments, grading, analytics."""

from __future__ import annotations

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.instructor import bp
from app.extensions import db
from app.forms.assessments import GradeForm
from app.forms.authoring import (
    AssignmentForm,
    CourseForm,
    LessonForm,
    ModuleForm,
    QuestionForm,
    QuizForm,
    ResourceForm,
)
from app.models import (
    Assignment,
    AssignmentSubmission,
    Course,
    CourseStatus,
    EnrollmentStatus,
    Lesson,
    LessonResource,
    Module,
    Question,
    Quiz,
)
from app.services import (
    assignment_service,
    authoring_service,
    course_service,
    discussion_service,
    enrollment_service,
    quiz_service,
    review_service,
)
from app.services.media_service import UploadError
from app.services.rbac import can_manage_course, require_permission

LOCALE = lambda: str(get_locale())  # noqa: E731


def _course(course_id: int) -> Course:
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    if not can_manage_course(current_user, course):
        abort(403)
    return course


def _child(course: Course, model, obj_id: int, *, via: str = "course_id"):  # type: ignore[no-untyped-def]
    obj = db.session.get(model, obj_id)
    if obj is None:
        abort(404)
    owner_course = obj.course if via == "course" else obj.module.course if via == "module" else None
    if owner_course is None or owner_course.id != course.id:
        abort(404)
    return obj


@bp.before_request
@login_required
@require_permission("instructor.access")
def _guard():  # type: ignore[no-untyped-def]
    return None


# ---- dashboard --------------------------------------------------------------
@bp.route("/")
def dashboard():  # type: ignore[no-untyped-def]
    courses = course_service.instructor_courses(current_user)
    pending = assignment_service.pending_for_instructor(current_user)
    stats = {
        "courses": len(courses),
        "published": sum(1 for c in courses if c.status == CourseStatus.PUBLISHED),
        "drafts": sum(
            1 for c in courses if c.status in {CourseStatus.DRAFT, CourseStatus.PENDING_REVIEW}
        ),
        "students": sum(c.enrollment_count for c in courses),
        "to_grade": len(pending),
    }
    return render_template(
        "instructor/dashboard.html",
        courses=courses,
        pending=pending[:8],
        stats=stats,
        locale=LOCALE(),
    )


# ---- courses ----------------------------------------------------------------
def _prepare_course_form(form: CourseForm) -> None:
    form.categories.choices = authoring_service.category_choices(LOCALE())
    form.instructor_id.choices = [(current_user.id, current_user.name)]
    form.cyber_track_id.choices = [(0, "—")]


@bp.route("/courses/")
def courses():  # type: ignore[no-untyped-def]
    return render_template(
        "instructor/courses.html",
        courses=course_service.instructor_courses(current_user),
        locale=LOCALE(),
    )


@bp.route("/courses/new", methods=["GET", "POST"])
@require_permission("courses.create")
def course_new():  # type: ignore[no-untyped-def]
    form = CourseForm()
    _prepare_course_form(form)
    if form.validate_on_submit():
        try:
            course = authoring_service.create_course_from_form(
                form, current_user, allow_platform=False, allow_instructor=False
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Course created. Now add modules and lessons."), "success")
            return redirect(url_for("instructor.builder", course_id=course.id))
    return render_template("instructor/course_form.html", form=form, course=None, locale=LOCALE())


@bp.route("/courses/<int:course_id>/", methods=["GET", "POST"])
def course_edit(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    form = CourseForm()
    _prepare_course_form(form)
    if request.method == "GET":
        authoring_service.fill_course_form(form, course)
    if form.validate_on_submit():
        try:
            authoring_service.update_course_from_form(
                course, form, current_user, allow_platform=False, allow_instructor=False
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Course saved."), "success")
            return redirect(url_for("instructor.course_edit", course_id=course.id))
    return render_template("instructor/course_form.html", form=form, course=course, locale=LOCALE())


@bp.route("/courses/<int:course_id>/builder")
def builder(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    return render_template(
        "instructor/builder.html",
        course=course,
        module_form=ModuleForm(),
        locale=LOCALE(),
        can_publish=authoring_service.can_publish_directly(current_user),
    )


@bp.route("/courses/<int:course_id>/submit", methods=["POST"])
def course_submit(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    if not course.lessons:
        flash(_("Add at least one lesson before publishing."), "warning")
        return redirect(url_for("instructor.builder", course_id=course.id))
    authoring_service.submit_for_review(course, current_user)
    if course.status == CourseStatus.PUBLISHED:
        flash(_("Course published."), "success")
    else:
        flash(_("Course submitted for review. An administrator will publish it."), "info")
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/unpublish", methods=["POST"])
def course_unpublish(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    course_service.set_status(course, CourseStatus.DRAFT, actor=current_user)
    flash(_("Course moved back to draft."), "info")
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/delete", methods=["POST"])
def course_delete(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    if course.status == CourseStatus.PUBLISHED and not current_user.has_permission(
        "courses.manage_all"
    ):
        flash(_("Unpublish the course before deleting it."), "warning")
        return redirect(url_for("instructor.builder", course_id=course.id))
    course_service.delete_course(course, actor=current_user)
    flash(_("Course deleted."), "info")
    return redirect(url_for("instructor.courses"))


# ---- modules ----------------------------------------------------------------
@bp.route("/courses/<int:course_id>/modules", methods=["POST"])
def module_new(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    form = ModuleForm()
    if form.validate_on_submit():
        authoring_service.save_module(course, form, current_user)
        flash(_("Module added."), "success")
    else:
        flash(_("Module title is required."), "error")
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/modules/<int:module_id>", methods=["GET", "POST"])
def module_edit(course_id: int, module_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    module = _child(course, Module, module_id, via="course")
    form = ModuleForm()
    if request.method == "GET":
        authoring_service.fill_module_form(form, module)
    if form.validate_on_submit():
        authoring_service.save_module(course, form, current_user, module=module)
        flash(_("Module saved."), "success")
        return redirect(url_for("instructor.builder", course_id=course.id))
    return render_template(
        "instructor/module_form.html", form=form, course=course, module=module, locale=LOCALE()
    )


@bp.route("/courses/<int:course_id>/modules/<int:module_id>/delete", methods=["POST"])
def module_delete(course_id: int, module_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    module = _child(course, Module, module_id, via="course")
    course_service.delete_module(module, actor=current_user)
    flash(_("Module deleted."), "info")
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/modules/<int:module_id>/move/<direction>", methods=["POST"])
def module_move(course_id: int, module_id: int, direction: str):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    course_service.move(course.modules, module_id, -1 if direction == "up" else 1)
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/modules/reorder", methods=["POST"])
def modules_reorder(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    data = request.get_json(silent=True) or {}
    ids = [int(i) for i in data.get("order", []) if str(i).isdigit()]
    course_service.reorder(course.modules, ids)
    return jsonify({"ok": True})


# ---- lessons ----------------------------------------------------------------
@bp.route("/courses/<int:course_id>/modules/<int:module_id>/lessons/new", methods=["GET", "POST"])
def lesson_new(course_id: int, module_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    module = _child(course, Module, module_id, via="course")
    form = LessonForm()
    if form.validate_on_submit():
        try:
            lesson = authoring_service.save_lesson(module, form, current_user)
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Lesson created."), "success")
            return redirect(
                url_for("instructor.lesson_edit", course_id=course.id, lesson_id=lesson.id)
            )
    return render_template(
        "instructor/lesson_form.html",
        form=form,
        course=course,
        module=module,
        lesson=None,
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/lessons/<int:lesson_id>", methods=["GET", "POST"])
def lesson_edit(course_id: int, lesson_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    lesson = _child(course, Lesson, lesson_id, via="module")
    form = LessonForm()
    resource_form = ResourceForm(prefix="res")
    if request.method == "GET":
        authoring_service.fill_lesson_form(form, lesson)
    if form.submit.data and form.validate_on_submit():
        try:
            authoring_service.save_lesson(lesson.module, form, current_user, lesson=lesson)
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Lesson saved."), "success")
            return redirect(
                url_for("instructor.lesson_edit", course_id=course.id, lesson_id=lesson.id)
            )
    return render_template(
        "instructor/lesson_form.html",
        form=form,
        resource_form=resource_form,
        course=course,
        module=lesson.module,
        lesson=lesson,
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/lessons/<int:lesson_id>/resources", methods=["POST"])
def resource_add(course_id: int, lesson_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    lesson = _child(course, Lesson, lesson_id, via="module")
    form = ResourceForm(prefix="res")
    if form.validate_on_submit():
        try:
            authoring_service.add_resource_from_form(lesson, form, current_user)
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Resource added."), "success")
    else:
        flash(_("Resource title is required."), "error")
    return redirect(url_for("instructor.lesson_edit", course_id=course.id, lesson_id=lesson.id))


@bp.route("/courses/<int:course_id>/resources/<int:resource_id>/delete", methods=["POST"])
def resource_delete(course_id: int, resource_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    resource = db.session.get(LessonResource, resource_id)
    if resource is None or resource.lesson.course.id != course.id:
        abort(404)
    lesson_id = resource.lesson_id
    db.session.delete(resource)
    db.session.commit()
    return redirect(url_for("instructor.lesson_edit", course_id=course.id, lesson_id=lesson_id))


@bp.route("/courses/<int:course_id>/lessons/<int:lesson_id>/delete", methods=["POST"])
def lesson_delete(course_id: int, lesson_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    lesson = _child(course, Lesson, lesson_id, via="module")
    course_service.delete_lesson(lesson, actor=current_user)
    flash(_("Lesson deleted."), "info")
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/lessons/<int:lesson_id>/move/<direction>", methods=["POST"])
def lesson_move(course_id: int, lesson_id: int, direction: str):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    lesson = _child(course, Lesson, lesson_id, via="module")
    course_service.move(lesson.module.lessons, lesson_id, -1 if direction == "up" else 1)
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/modules/<int:module_id>/lessons/reorder", methods=["POST"])
def lessons_reorder(course_id: int, module_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    module = _child(course, Module, module_id, via="course")
    data = request.get_json(silent=True) or {}
    ids = [int(i) for i in data.get("order", []) if str(i).isdigit()]
    course_service.reorder(module.lessons, ids)
    return jsonify({"ok": True})


# ---- quizzes ----------------------------------------------------------------
@bp.route("/courses/<int:course_id>/quizzes/new", methods=["GET", "POST"])
def quiz_new(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    lesson = None
    lesson_id = request.args.get("lesson", type=int)
    if lesson_id:
        lesson = _child(course, Lesson, lesson_id, via="module")
        if lesson.quiz:
            return redirect(
                url_for("instructor.quiz_edit", course_id=course.id, quiz_id=lesson.quiz.id)
            )
    form = QuizForm()
    if form.validate_on_submit():
        quiz = authoring_service.save_quiz(course, form, current_user, lesson=lesson)
        flash(_("Quiz created. Add questions."), "success")
        return redirect(url_for("instructor.quiz_edit", course_id=course.id, quiz_id=quiz.id))
    return render_template(
        "instructor/quiz_form.html",
        form=form,
        course=course,
        quiz=None,
        lesson=lesson,
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/quizzes/<int:quiz_id>", methods=["GET", "POST"])
def quiz_edit(course_id: int, quiz_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    quiz = _child(course, Quiz, quiz_id, via="course")
    form = QuizForm()
    if request.method == "GET":
        authoring_service.fill_quiz_form(form, quiz)
    if form.validate_on_submit():
        authoring_service.save_quiz(course, form, current_user, quiz=quiz)
        flash(_("Quiz saved."), "success")
        return redirect(url_for("instructor.quiz_edit", course_id=course.id, quiz_id=quiz.id))
    return render_template(
        "instructor/quiz_form.html",
        form=form,
        course=course,
        quiz=quiz,
        lesson=quiz.lesson,
        stats=quiz_service.quiz_stats(quiz),
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/quizzes/<int:quiz_id>/delete", methods=["POST"])
def quiz_delete(course_id: int, quiz_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    quiz = _child(course, Quiz, quiz_id, via="course")
    db.session.delete(quiz)
    db.session.commit()
    flash(_("Quiz deleted."), "info")
    return redirect(url_for("instructor.builder", course_id=course.id))


@bp.route("/courses/<int:course_id>/quizzes/<int:quiz_id>/questions/new", methods=["GET", "POST"])
@bp.route(
    "/courses/<int:course_id>/quizzes/<int:quiz_id>/questions/<int:question_id>",
    methods=["GET", "POST"],
)
def question_edit(course_id: int, quiz_id: int, question_id: int | None = None):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    quiz = _child(course, Quiz, quiz_id, via="course")
    question = None
    if question_id is not None:
        question = db.session.get(Question, question_id)
        if question is None or question.quiz_id != quiz.id:
            abort(404)
    form = QuestionForm()
    if request.method == "GET" and question is not None:
        form.question_type.data = question.question_type.value
        form.prompt_ka.data = question.prompt_ka
        form.prompt_en.data = question.prompt_en
        form.explanation_ka.data = question.explanation_ka
        form.explanation_en.data = question.explanation_en
        form.points.data = question.points
        form.accepted_answers.data = "\n".join(question.accepted_answers or [])
    if form.validate_on_submit():
        question = authoring_service.save_question(
            quiz, form, request.form, current_user, question=question
        )
        flash(_("Question saved."), "success")
        return redirect(url_for("instructor.quiz_edit", course_id=course.id, quiz_id=quiz.id))
    return render_template(
        "instructor/question_form.html",
        form=form,
        course=course,
        quiz=quiz,
        question=question,
        locale=LOCALE(),
    )


@bp.route(
    "/courses/<int:course_id>/quizzes/<int:quiz_id>/questions/<int:question_id>/delete",
    methods=["POST"],
)
def question_delete(course_id: int, quiz_id: int, question_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    quiz = _child(course, Quiz, quiz_id, via="course")
    question = db.session.get(Question, question_id)
    if question is None or question.quiz_id != quiz.id:
        abort(404)
    authoring_service.delete_question(question, current_user)
    return redirect(url_for("instructor.quiz_edit", course_id=course.id, quiz_id=quiz.id))


@bp.route(
    "/courses/<int:course_id>/quizzes/<int:quiz_id>/questions/<int:question_id>/move/<direction>",
    methods=["POST"],
)
def question_move(course_id: int, quiz_id: int, question_id: int, direction: str):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    quiz = _child(course, Quiz, quiz_id, via="course")
    course_service.move(quiz.questions, question_id, -1 if direction == "up" else 1)
    return redirect(url_for("instructor.quiz_edit", course_id=course.id, quiz_id=quiz.id))


# ---- assignments ------------------------------------------------------------
@bp.route("/courses/<int:course_id>/assignments/new", methods=["GET", "POST"])
def assignment_new(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    lesson = None
    lesson_id = request.args.get("lesson", type=int)
    if lesson_id:
        lesson = _child(course, Lesson, lesson_id, via="module")
        if lesson.assignment:
            return redirect(
                url_for(
                    "instructor.assignment_edit",
                    course_id=course.id,
                    assignment_id=lesson.assignment.id,
                )
            )
    form = AssignmentForm()
    if form.validate_on_submit():
        assignment = authoring_service.save_assignment(course, form, current_user, lesson=lesson)
        flash(_("Assignment created."), "success")
        return redirect(
            url_for("instructor.assignment_edit", course_id=course.id, assignment_id=assignment.id)
        )
    return render_template(
        "instructor/assignment_form.html",
        form=form,
        course=course,
        assignment=None,
        lesson=lesson,
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/assignments/<int:assignment_id>", methods=["GET", "POST"])
def assignment_edit(course_id: int, assignment_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    assignment = _child(course, Assignment, assignment_id, via="course")
    form = AssignmentForm()
    if request.method == "GET":
        authoring_service.fill_assignment_form(form, assignment)
    if form.validate_on_submit():
        authoring_service.save_assignment(course, form, current_user, assignment=assignment)
        flash(_("Assignment saved."), "success")
        return redirect(
            url_for("instructor.assignment_edit", course_id=course.id, assignment_id=assignment.id)
        )
    return render_template(
        "instructor/assignment_form.html",
        form=form,
        course=course,
        assignment=assignment,
        lesson=assignment.lesson,
        submissions=assignment.submissions,
        locale=LOCALE(),
    )


# ---- students / grading / analytics ----------------------------------------
@bp.route("/courses/<int:course_id>/students")
def students(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    from app.services import progress_service

    rows = []
    for enrollment in enrollment_service.course_enrollments(course):
        rows.append((enrollment, progress_service.get_course_progress(enrollment.user, course)))
    return render_template(
        "instructor/students.html",
        course=course,
        rows=rows,
        locale=LOCALE(),
        EnrollmentStatus=EnrollmentStatus,
    )


@bp.route("/courses/<int:course_id>/students/<int:user_id>/approve", methods=["POST"])
def approve_student(course_id: int, user_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    enrollment = next(
        (e for e in enrollment_service.course_enrollments(course) if e.user_id == user_id), None
    )
    if enrollment is None:
        abort(404)
    enrollment_service.approve(enrollment, current_user)
    flash(_("Enrolment approved."), "success")
    return redirect(url_for("instructor.students", course_id=course.id))


@bp.route("/grading/")
def grading():  # type: ignore[no-untyped-def]
    pending = assignment_service.pending_for_instructor(
        current_user, all_courses=current_user.has_permission("courses.manage_all")
    )
    return render_template("instructor/grading.html", pending=pending, locale=LOCALE())


@bp.route("/grading/<int:submission_id>", methods=["GET", "POST"])
def grade_submission(submission_id: int):  # type: ignore[no-untyped-def]
    submission = db.session.get(AssignmentSubmission, submission_id)
    if submission is None:
        abort(404)
    course = submission.assignment.course
    if not can_manage_course(current_user, course):
        abort(403)
    form = GradeForm()
    if request.method == "GET" and submission.grade:
        form.points.data = submission.grade.points
        form.feedback.data = submission.grade.feedback
    if form.validate_on_submit():
        if form.return_for_revision.data:
            assignment_service.return_for_revision(
                submission, grader=current_user, feedback=form.feedback.data or ""
            )
            flash(_("Returned to the learner for revision."), "info")
        else:
            assignment_service.grade(
                submission,
                grader=current_user,
                points=float(form.points.data),
                feedback=form.feedback.data or "",
            )
            flash(_("Grade saved and the learner was notified."), "success")
        return redirect(url_for("instructor.grading"))
    history = assignment_service.submissions(submission.user, submission.assignment)
    return render_template(
        "instructor/grade.html",
        submission=submission,
        form=form,
        course=course,
        history=history,
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/analytics")
@require_permission("analytics.view_own", "analytics.view_all")
def analytics(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    return render_template(
        "instructor/analytics.html",
        course=course,
        data=authoring_service.course_analytics(course),
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/discussions")
def course_discussions(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    return render_template(
        "instructor/discussions.html",
        course=course,
        threads=discussion_service.threads(course, include_hidden=True),
        reports=[
            r for r in discussion_service.open_reports() if r.post.discussion.course_id == course.id
        ],
        locale=LOCALE(),
    )


@bp.route("/courses/<int:course_id>/reviews")
def course_reviews(course_id: int):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    from app.models import Review

    reviews = (
        db.session.query(Review)
        .filter_by(course_id=course.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return render_template(
        "instructor/reviews.html", course=course, reviews=reviews, locale=LOCALE()
    )


@bp.route("/courses/<int:course_id>/reviews/<int:review_id>/<decision>", methods=["POST"])
def review_decide(course_id: int, review_id: int, decision: str):  # type: ignore[no-untyped-def]
    course = _course(course_id)
    from app.models import Review, ReviewStatus

    review = db.session.get(Review, review_id)
    if review is None or review.course_id != course.id:
        abort(404)
    status = ReviewStatus.APPROVED if decision == "approve" else ReviewStatus.REJECTED
    review_service.moderate(review, status, current_user)
    return redirect(url_for("instructor.course_reviews", course_id=course.id))
