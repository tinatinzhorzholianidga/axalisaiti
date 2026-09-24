"""Lesson and course progress, completion detection and certificate triggering."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Course,
    CourseProgress,
    Enrollment,
    EnrollmentStatus,
    Lesson,
    LessonProgress,
    ProgressStatus,
    Quiz,
    QuizAttempt,
    User,
    utcnow,
)
from app.services import achievement_service, certificate_service


def get_course_progress(user: User, course: Course) -> CourseProgress | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return db.session.execute(
        select(CourseProgress).where(
            CourseProgress.user_id == user.id, CourseProgress.course_id == course.id
        )
    ).scalar_one_or_none()


def lesson_progress_map(user: User, course: Course) -> dict[int, LessonProgress]:
    if not getattr(user, "is_authenticated", False):
        return {}
    lesson_ids = [lesson.id for lesson in course.lessons]
    if not lesson_ids:
        return {}
    rows = db.session.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id.in_(lesson_ids)
        )
    ).scalars()
    return {row.lesson_id: row for row in rows}


def touch_lesson(user: User, course: Course, lesson: Lesson) -> LessonProgress:
    """Record that a lesson was opened; also updates 'continue learning' pointers."""
    progress = db.session.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson.id
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = LessonProgress(user_id=user.id, lesson_id=lesson.id)
        db.session.add(progress)
    enrollment = db.session.execute(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
    ).scalar_one_or_none()
    if enrollment:
        enrollment.last_accessed_at = utcnow()
        enrollment.last_lesson_id = lesson.id
    db.session.commit()
    return progress


def complete_lesson(user: User, course: Course, lesson: Lesson) -> CourseProgress:
    progress = touch_lesson(user, course, lesson)
    if progress.status != ProgressStatus.COMPLETED:
        progress.status = ProgressStatus.COMPLETED
        progress.completed_at = utcnow()
    db.session.commit()
    return recalculate(user, course)


def quiz_passed(user: User, quiz: Quiz) -> bool:
    return (
        db.session.execute(
            select(QuizAttempt.id).where(
                QuizAttempt.user_id == user.id,
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.passed.is_(True),
            )
        ).first()
        is not None
    )


def recalculate(user: User, course: Course) -> CourseProgress:
    """Recompute course completion. Completion requires every published lesson
    completed and every published quiz (incl. final) passed."""
    course_progress = get_course_progress(user, course)
    if course_progress is None:
        course_progress = CourseProgress(user_id=user.id, course_id=course.id)
        db.session.add(course_progress)

    lessons = [
        lesson
        for m in course.modules
        if m.is_published
        for lesson in m.lessons
        if lesson.is_published
    ]
    done_map = lesson_progress_map(user, course)
    completed = sum(
        1
        for lesson in lessons
        if done_map.get(lesson.id) and done_map[lesson.id].status == ProgressStatus.COMPLETED
    )
    quizzes = [q for q in course.quizzes if q.is_published]
    passed = sum(1 for q in quizzes if quiz_passed(user, q))

    course_progress.total_lessons = len(lessons)
    course_progress.completed_lessons = completed
    course_progress.quizzes_total = len(quizzes)
    course_progress.quizzes_passed = passed
    units = len(lessons) + len(quizzes)
    course_progress.percent = round(100.0 * (completed + passed) / units, 1) if units else 0.0

    final_quiz = course.final_quiz
    if final_quiz:
        best = db.session.execute(
            select(QuizAttempt.percent)
            .where(QuizAttempt.user_id == user.id, QuizAttempt.quiz_id == final_quiz.id)
            .order_by(QuizAttempt.percent.desc())
            .limit(1)
        ).scalar_one_or_none()
        course_progress.final_score = best

    newly_complete = False
    if (
        units
        and completed == len(lessons)
        and passed == len(quizzes)
        and not course_progress.is_complete
    ):
        course_progress.is_complete = True
        course_progress.completed_at = utcnow()
        newly_complete = True
        enrollment = db.session.execute(
            select(Enrollment).where(
                Enrollment.user_id == user.id, Enrollment.course_id == course.id
            )
        ).scalar_one_or_none()
        if enrollment and enrollment.status != EnrollmentStatus.COMPLETED:
            enrollment.status = EnrollmentStatus.COMPLETED
            enrollment.completed_at = utcnow()
            course.completion_count = (course.completion_count or 0) + 1
    db.session.commit()

    if newly_complete:
        achievement_service.check_course_completion(user)
        if course.certificate_enabled:
            certificate_service.issue_for_completion(user, course, course_progress)
    return course_progress


def continue_lesson(user: User, course: Course) -> Lesson | None:
    """Next lesson to open: last accessed, else first incomplete, else first."""
    lessons = [
        lesson
        for m in course.modules
        if m.is_published
        for lesson in m.lessons
        if lesson.is_published
    ]
    if not lessons:
        return None
    enrollment = db.session.execute(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
    ).scalar_one_or_none()
    done_map = lesson_progress_map(user, course)
    for lesson in lessons:
        state = done_map.get(lesson.id)
        if not state or state.status != ProgressStatus.COMPLETED:
            if enrollment and enrollment.last_lesson_id in {lesson_.id for lesson_ in lessons}:
                last = next(
                    lesson_ for lesson_ in lessons if lesson_.id == enrollment.last_lesson_id
                )
                last_state = done_map.get(last.id)
                if not last_state or last_state.status != ProgressStatus.COMPLETED:
                    return last
            return lesson
    return lessons[0]


def dashboard_summary(user: User) -> dict:
    progresses = list(
        db.session.execute(
            select(CourseProgress).where(CourseProgress.user_id == user.id)
        ).scalars()
    )
    lessons_done = sum(p.completed_lessons for p in progresses)
    quizzes_passed = sum(p.quizzes_passed for p in progresses)
    completed = sum(1 for p in progresses if p.is_complete)
    minutes = int(
        db.session.execute(
            select(db.func.coalesce(db.func.sum(LessonProgress.seconds_spent), 0)).where(
                LessonProgress.user_id == user.id
            )
        ).scalar_one()
        // 60
    )
    return {
        "courses_in_progress": sum(1 for p in progresses if not p.is_complete and p.percent > 0),
        "courses_completed": completed,
        "lessons_completed": lessons_done,
        "quizzes_passed": quizzes_passed,
        "minutes_learned": minutes,
    }
