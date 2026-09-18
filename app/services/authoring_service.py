"""Applies authoring forms to course content (shared by instructor and admin)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from flask import current_app
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    Assignment,
    Course,
    CourseStatus,
    Lesson,
    LessonType,
    MediaKind,
    Module,
    Platform,
    Question,
    QuestionOption,
    QuestionType,
    Quiz,
    User,
)
from app.services import audit_service, course_service, media_service, notification_service
from app.services.media_service import UploadError
from app.services.sanitize import sanitize_html


def _translations_from_form(form: Any, fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {"ka": {}, "en": {}}
    for field in fields:
        for locale in ("ka", "en"):
            attr = f"{field}_{locale}"
            if hasattr(form, attr):
                result[locale][field] = getattr(form, attr).data or ""
    return result


COURSE_FIELDS = (
    "title",
    "short_description",
    "description",
    "objectives",
    "prerequisites",
    "audience",
    "certificate_requirements",
)


def course_fields_from_form(form: Any) -> dict[str, Any]:
    return {
        "difficulty": form.difficulty.data,
        "icon": form.icon.data,
        "color": form.color.data,
        "estimated_minutes": form.estimated_minutes.data or 0,
        "age_min": form.age_min.data,
        "age_max": form.age_max.data,
        "tags": ",".join(t.strip() for t in (form.tags.data or "").split(",") if t.strip()),
        "is_featured": bool(form.is_featured.data),
        "is_free": bool(form.is_free.data),
        "certificate_enabled": bool(form.certificate_enabled.data),
        "certificate_pass_percent": form.certificate_pass_percent.data or 70,
        "enrollment_mode": form.enrollment_mode.data,
        "discussions_enabled": bool(form.discussions_enabled.data),
        "reviews_enabled": bool(form.reviews_enabled.data),
        "starts_at": form.starts_at.data,
        "ends_at": form.ends_at.data,
        "category_ids": list(form.categories.data or []),
        "slug": form.slug.data or None,
    }


def create_course_from_form(
    form: Any, actor: User, *, allow_platform: bool, allow_instructor: bool
) -> Course:
    fields = course_fields_from_form(form)
    platform = Platform(form.platform.data) if allow_platform else Platform.ELEARNING
    if allow_instructor and form.instructor_id.data:
        fields["instructor_id"] = form.instructor_id.data
    if allow_platform and form.cyber_track_id.data:
        fields["cyber_track_id"] = form.cyber_track_id.data
    course = course_service.create_course(
        actor=actor,
        platform=platform,
        translations=_translations_from_form(form, COURSE_FIELDS),
        **fields,
    )
    _apply_cover(course, form.cover.data, actor)
    db.session.commit()
    return course


def update_course_from_form(
    course: Course, form: Any, actor: User, *, allow_platform: bool, allow_instructor: bool
) -> Course:
    fields = course_fields_from_form(form)
    if allow_platform:
        fields["platform"] = Platform(form.platform.data)
        fields["cyber_track_id"] = form.cyber_track_id.data or None
    if allow_instructor and form.instructor_id.data:
        fields["instructor_id"] = form.instructor_id.data
    course_service.update_course(
        course, actor=actor, translations=_translations_from_form(form, COURSE_FIELDS), **fields
    )
    _apply_cover(course, form.cover.data, actor)
    db.session.commit()
    return course


def _apply_cover(course: Course, file: FileStorage | None, actor: User) -> None:
    if file and file.filename:
        media = media_service.save_upload(
            file,
            kind=MediaKind.IMAGE,
            uploader=actor,
            is_public=True,
            alt_text=course.title("en") or course.slug,
        )
        course.cover_media_id = media.id


def fill_course_form(form: Any, course: Course) -> None:
    for locale in ("ka", "en"):
        tr = course.tr(locale) if any(t.locale == locale for t in course.translations) else None
        for field in COURSE_FIELDS:
            getattr(form, f"{field}_{locale}").data = getattr(tr, field, "") if tr else ""
    form.slug.data = course.slug
    form.platform.data = course.platform.value
    form.categories.data = [c.id for c in course.categories]
    form.icon.data = course.icon
    form.color.data = course.color
    form.difficulty.data = course.difficulty.value
    form.estimated_minutes.data = course.estimated_minutes
    form.age_min.data = course.age_min
    form.age_max.data = course.age_max
    form.instructor_id.data = course.instructor_id
    form.tags.data = course.tags
    form.is_featured.data = course.is_featured
    form.is_free.data = course.is_free
    form.certificate_enabled.data = course.certificate_enabled
    form.certificate_pass_percent.data = course.certificate_pass_percent
    form.enrollment_mode.data = course.enrollment_mode.value
    form.discussions_enabled.data = course.discussions_enabled
    form.reviews_enabled.data = course.reviews_enabled
    form.starts_at.data = course.starts_at
    form.ends_at.data = course.ends_at
    form.cyber_track_id.data = course.cyber_track_id


# ---- modules / lessons --------------------------------------------------------
def save_module(course: Course, form: Any, actor: User, module: Module | None = None) -> Module:
    translations = _translations_from_form(form, ("title", "description"))
    if module is None:
        module = course_service.add_module(course, translations, actor=actor)
    course_service.update_module(
        module, translations, actor=actor, is_published=bool(form.is_published.data)
    )
    return module


def fill_module_form(form: Any, module: Module) -> None:
    for locale in ("ka", "en"):
        form[f"title_{locale}"].data = (
            module.text("title", locale)
            if any(t.locale == locale for t in module.translations)
            else ""
        )
        form[f"description_{locale}"].data = (
            module.text("description", locale)
            if any(t.locale == locale for t in module.translations)
            else ""
        )
    form.is_published.data = module.is_published


def save_lesson(module: Module, form: Any, actor: User, lesson: Lesson | None = None) -> Lesson:
    translations = _translations_from_form(form, ("title", "summary", "content"))
    fields: dict[str, Any] = {
        "estimated_minutes": form.estimated_minutes.data or 10,
        "is_published": bool(form.is_published.data),
        "is_free_preview": bool(form.is_free_preview.data),
        "video_url": (form.video_url.data or "").strip() or None,
        "slug": form.slug.data or None,
        "lesson_type": LessonType(form.lesson_type.data),
    }
    if lesson is None:
        lesson = course_service.add_lesson(module, translations, actor=actor, **fields)
    else:
        course_service.update_lesson(lesson, translations, actor=actor, **fields)
    if form.video.data and form.video.data.filename:
        media = media_service.save_upload(form.video.data, kind=MediaKind.RESOURCE, uploader=actor)
        lesson.video_media_id = media.id
        db.session.commit()
    return lesson


def fill_lesson_form(form: Any, lesson: Lesson) -> None:
    for locale in ("ka", "en"):
        present = any(t.locale == locale for t in lesson.translations)
        for field in ("title", "summary", "content"):
            form[f"{field}_{locale}"].data = lesson.text(field, locale) if present else ""
    form.slug.data = lesson.slug
    form.lesson_type.data = lesson.lesson_type.value
    form.estimated_minutes.data = lesson.estimated_minutes
    form.video_url.data = lesson.video_url
    form.is_published.data = lesson.is_published
    form.is_free_preview.data = lesson.is_free_preview


def add_resource_from_form(lesson: Lesson, form: Any, actor: User):  # type: ignore[no-untyped-def]
    media_id = None
    url = (form.url.data or "").strip() or None
    if form.file.data and form.file.data.filename:
        media = media_service.save_upload(form.file.data, kind=MediaKind.RESOURCE, uploader=actor)
        media_id = media.id
    if not media_id and not url:
        raise UploadError("Provide a link or a file.")
    if url and not url.startswith(("http://", "https://", "/")):
        raise UploadError("Links must start with http:// or https://.")
    return course_service.add_resource(
        lesson,
        title_ka=form.title_ka.data,
        title_en=form.title_en.data or "",
        url=url,
        media_id=media_id,
        actor=actor,
    )


# ---- quizzes ----------------------------------------------------------------
def save_quiz(
    course: Course, form: Any, actor: User, quiz: Quiz | None = None, lesson: Lesson | None = None
) -> Quiz:
    if quiz is None:
        quiz = Quiz(
            course_id=course.id, lesson_id=lesson.id if lesson else None, title_ka="", title_en=""
        )
        db.session.add(quiz)
        db.session.flush()
        audit_service.record("quiz.created", target=quiz, actor=actor, meta={"course": course.slug})
    quiz.title_ka = form.title_ka.data
    quiz.title_en = form.title_en.data or ""
    quiz.description_ka = form.description_ka.data or ""
    quiz.description_en = form.description_en.data or ""
    quiz.time_limit_minutes = form.time_limit_minutes.data or None
    quiz.max_attempts = form.max_attempts.data or None
    quiz.pass_percent = form.pass_percent.data or 70
    quiz.shuffle_questions = bool(form.shuffle_questions.data)
    quiz.shuffle_options = bool(form.shuffle_options.data)
    quiz.feedback_mode = form.feedback_mode.data
    quiz.show_explanations = bool(form.show_explanations.data)
    quiz.is_published = bool(form.is_published.data)
    if form.is_final.data:
        for other in course.quizzes:
            if other.id != quiz.id and other.is_final:
                other.is_final = False
        quiz.is_final = True
    else:
        quiz.is_final = False
    audit_service.record("quiz.updated", target=quiz, actor=actor)
    db.session.commit()
    return quiz


def fill_quiz_form(form: Any, quiz: Quiz) -> None:
    for name in (
        "title_ka",
        "title_en",
        "description_ka",
        "description_en",
        "time_limit_minutes",
        "max_attempts",
        "pass_percent",
        "shuffle_questions",
        "shuffle_options",
        "show_explanations",
        "is_final",
        "is_published",
    ):
        form[name].data = getattr(quiz, name)
    form.feedback_mode.data = quiz.feedback_mode.value


def save_question(
    quiz: Quiz, form: Any, request_form: Any, actor: User, question: Question | None = None
) -> Question:
    if question is None:
        question = Question(quiz_id=quiz.id, sort_order=len(quiz.questions) + 1, prompt_ka="")
        db.session.add(question)
        db.session.flush()
        quiz.questions.append(question)
    question.question_type = QuestionType(form.question_type.data)
    question.prompt_ka = form.prompt_ka.data
    question.prompt_en = form.prompt_en.data or ""
    question.explanation_ka = form.explanation_ka.data or ""
    question.explanation_en = form.explanation_en.data or ""
    question.points = float(form.points.data or Decimal(1))
    question.accepted_answers = [
        line.strip() for line in (form.accepted_answers.data or "").splitlines() if line.strip()
    ]
    texts_ka = request_form.getlist("opt_text_ka")
    texts_en = request_form.getlist("opt_text_en")
    match_ka = request_form.getlist("opt_match_ka")
    match_en = request_form.getlist("opt_match_en")
    positions = request_form.getlist("opt_position")
    correct = set(request_form.getlist("opt_correct"))
    question.options.clear()
    db.session.flush()
    if question.question_type == QuestionType.TRUE_FALSE:
        true_correct = request_form.get("tf_correct", "true") == "true"
        question.options = [
            QuestionOption(
                sort_order=1, text_ka="სიმართლე", text_en="True", is_correct=true_correct
            ),
            QuestionOption(
                sort_order=2, text_ka="ტყუილი", text_en="False", is_correct=not true_correct
            ),
        ]
    else:
        order = 0
        for index, text in enumerate(texts_ka):
            if not text.strip():
                continue
            order += 1
            question.options.append(
                QuestionOption(
                    sort_order=order,
                    text_ka=text.strip()[:2000],
                    text_en=(texts_en[index] if index < len(texts_en) else "").strip()[:2000],
                    is_correct=str(index) in correct,
                    match_ka=(match_ka[index] if index < len(match_ka) else "").strip()[:2000],
                    match_en=(match_en[index] if index < len(match_en) else "").strip()[:2000],
                    correct_position=int(positions[index])
                    if index < len(positions) and positions[index].isdigit()
                    else order,
                )
            )
    audit_service.record(
        "question.saved", target=quiz, actor=actor, meta={"question_id": question.id}
    )
    db.session.commit()
    return question


def delete_question(question: Question, actor: User) -> None:
    quiz = question.quiz
    quiz.questions.remove(question)
    db.session.delete(question)
    db.session.flush()
    course_service.renumber(quiz.questions)
    audit_service.record("question.deleted", target=quiz, actor=actor)
    db.session.commit()


# ---- assignments ------------------------------------------------------------
def save_assignment(
    course: Course,
    form: Any,
    actor: User,
    assignment: Assignment | None = None,
    lesson: Lesson | None = None,
) -> Assignment:
    if assignment is None:
        assignment = Assignment(
            course_id=course.id, lesson_id=lesson.id if lesson else None, title_ka="", title_en=""
        )
        db.session.add(assignment)
        db.session.flush()
        audit_service.record(
            "assignment.created", target=assignment, actor=actor, meta={"course": course.slug}
        )
    assignment.title_ka = form.title_ka.data
    assignment.title_en = form.title_en.data or ""
    assignment.instructions_ka = sanitize_html(form.instructions_ka.data or "")
    assignment.instructions_en = sanitize_html(form.instructions_en.data or "")
    assignment.submission_type = form.submission_type.data
    assignment.max_points = float(form.max_points.data or Decimal(100))
    assignment.due_at = form.due_at.data
    assignment.allow_late = bool(form.allow_late.data)
    assignment.late_penalty_percent = form.late_penalty_percent.data or 0
    assignment.max_resubmissions = form.max_resubmissions.data or 0
    assignment.allowed_extensions = form.allowed_extensions.data or "pdf,docx,txt"
    assignment.is_published = bool(form.is_published.data)
    audit_service.record("assignment.updated", target=assignment, actor=actor)
    db.session.commit()
    return assignment


def fill_assignment_form(form: Any, assignment: Assignment) -> None:
    for name in (
        "title_ka",
        "title_en",
        "instructions_ka",
        "instructions_en",
        "max_points",
        "due_at",
        "allow_late",
        "late_penalty_percent",
        "max_resubmissions",
        "allowed_extensions",
        "is_published",
    ):
        form[name].data = getattr(assignment, name)
    form.submission_type.data = assignment.submission_type.value


# ---- workflow ---------------------------------------------------------------
def submit_for_review(course: Course, actor: User) -> Course:
    from app.services.rbac import instructor_approval_required

    if instructor_approval_required() and not actor.has_permission("courses.publish"):
        course_service.set_status(course, CourseStatus.PENDING_REVIEW, actor=actor)
        from sqlalchemy import select

        from app.models import Role

        admins = (
            db.session.execute(select(User).join(User.roles).where(Role.name == "admin"))
            .scalars()
            .unique()
        )
        for admin in admins:
            notification_service.notify(
                admin.id,
                kind="review_request",
                title=f"Course awaiting review: {course.title('en') or course.slug}",
                body=f"Submitted by {actor.name}.",
                link=f"/admin/courses/{course.id}",
            )
    else:
        course_service.set_status(course, CourseStatus.PUBLISHED, actor=actor)
    return course


def can_publish_directly(actor: User) -> bool:
    from app.services.rbac import instructor_approval_required

    return actor.has_permission("courses.publish") or not instructor_approval_required()


def course_analytics(course: Course) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.models import (
        CourseProgress,
        Enrollment,
        EnrollmentStatus,
        LessonProgress,
        ProgressStatus,
        QuizAttempt,
    )

    enrollments = int(
        db.session.execute(
            select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course.id)
        ).scalar_one()
    )
    completed = int(
        db.session.execute(
            select(func.count())
            .select_from(Enrollment)
            .where(
                Enrollment.course_id == course.id, Enrollment.status == EnrollmentStatus.COMPLETED
            )
        ).scalar_one()
    )
    avg_progress = db.session.execute(
        select(func.avg(CourseProgress.percent)).where(CourseProgress.course_id == course.id)
    ).scalar_one()
    lessons = []
    for module in course.modules:
        for lesson in module.lessons:
            started = int(
                db.session.execute(
                    select(func.count())
                    .select_from(LessonProgress)
                    .where(LessonProgress.lesson_id == lesson.id)
                ).scalar_one()
            )
            done = int(
                db.session.execute(
                    select(func.count())
                    .select_from(LessonProgress)
                    .where(
                        LessonProgress.lesson_id == lesson.id,
                        LessonProgress.status == ProgressStatus.COMPLETED,
                    )
                ).scalar_one()
            )
            lessons.append(
                {
                    "lesson": lesson,
                    "started": started,
                    "completed": done,
                    "pct": round(100 * done / enrollments) if enrollments else 0,
                }
            )
    quizzes = []
    for quiz in course.quizzes:
        attempts = list(
            db.session.execute(
                select(QuizAttempt).where(
                    QuizAttempt.quiz_id == quiz.id, QuizAttempt.submitted_at.is_not(None)
                )
            ).scalars()
        )
        quizzes.append(
            {
                "quiz": quiz,
                "attempts": len(attempts),
                "pass_rate": round(100 * sum(1 for a in attempts if a.passed) / len(attempts))
                if attempts
                else 0,
                "average": round(sum(a.percent for a in attempts) / len(attempts), 1)
                if attempts
                else 0,
            }
        )
    return {
        "enrollments": enrollments,
        "completed": completed,
        "completion_rate": round(100 * completed / enrollments) if enrollments else 0,
        "avg_progress": round(float(avg_progress or 0), 1),
        "lessons": lessons,
        "quizzes": quizzes,
        "max_lesson_started": max((int(str(item["started"])) for item in lessons), default=0),
        "reviews": course.rating_count,
        "rating": course.rating_avg,
    }


def instructor_choices() -> list[tuple[int, str]]:
    from sqlalchemy import select

    from app.models import Role

    users = (
        db.session.execute(
            select(User).join(User.roles).where(Role.name.in_(["instructor", "admin"]))
        )
        .scalars()
        .unique()
    )
    return [(u.id, f"{u.name} ({u.email})") for u in sorted(users, key=lambda u: u.name)]


def category_choices(locale: str) -> list[tuple[int, str]]:
    from app.models import Category

    return [
        (c.id, c.name(locale)) for c in db.session.query(Category).order_by(Category.sort_order)
    ]


def track_choices() -> list[tuple[int, str]]:
    from app.models import CyberTrack

    return [(0, "—")] + [
        (t.id, t.name("en") or t.slug)
        for t in db.session.query(CyberTrack).order_by(CyberTrack.sort_order)
    ]


def upload_limit_mb() -> int:
    return int(current_app.config.get("MAX_UPLOAD_MB", 25))
