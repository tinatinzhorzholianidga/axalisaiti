"""Assignment submissions and grading."""

from __future__ import annotations

from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    Assignment,
    AssignmentSubmission,
    Course,
    Grade,
    MediaKind,
    SubmissionStatus,
    SubmissionType,
    User,
    utcnow,
)
from app.services import audit_service, media_service, notification_service
from app.services.media_service import UploadError
from app.services.sanitize import sanitize_html


class AssignmentError(Exception):
    pass


def submissions(user: User, assignment: Assignment) -> list[AssignmentSubmission]:
    return list(
        db.session.execute(
            select(AssignmentSubmission)
            .where(
                AssignmentSubmission.user_id == user.id,
                AssignmentSubmission.assignment_id == assignment.id,
            )
            .order_by(AssignmentSubmission.attempt_number)
        ).scalars()
    )


def latest_submission(user: User, assignment: Assignment) -> AssignmentSubmission | None:
    rows = submissions(user, assignment)
    return rows[-1] if rows else None


def can_submit(user: User, assignment: Assignment) -> tuple[bool, str | None]:
    if not assignment.is_published:
        return False, "This assignment is not open."
    if assignment.is_past_due and not assignment.allow_late:
        return False, "The deadline has passed."
    count = len(submissions(user, assignment))
    if count > assignment.max_resubmissions:
        return False, "You have used all submission attempts."
    return True, None


def submit(
    user: User, assignment: Assignment, *, text: str | None, file: FileStorage | None
) -> AssignmentSubmission:
    ok, reason = can_submit(user, assignment)
    if not ok:
        raise AssignmentError(reason or "Submission not allowed.")
    text = (text or "").strip()
    needs_text = assignment.submission_type in {SubmissionType.TEXT, SubmissionType.BOTH}
    needs_file = assignment.submission_type in {SubmissionType.FILE, SubmissionType.BOTH}
    has_file = bool(file and file.filename)
    if (
        needs_text
        and not text
        and not (assignment.submission_type == SubmissionType.BOTH and has_file)
    ):
        raise AssignmentError("Please write your answer.")
    if (
        needs_file
        and not has_file
        and not (assignment.submission_type == SubmissionType.BOTH and text)
    ):
        raise AssignmentError("Please attach a file.")
    if has_file and assignment.submission_type == SubmissionType.TEXT:
        raise AssignmentError("This assignment accepts text only.")

    media = None
    if has_file:
        try:
            media = media_service.save_upload(
                file,
                kind=MediaKind.ASSIGNMENT,
                uploader=user,
                allowed_extensions=set(assignment.allowed_extension_list),
            )
        except UploadError as exc:
            raise AssignmentError(str(exc)) from exc

    submission = AssignmentSubmission(
        assignment_id=assignment.id,
        user_id=user.id,
        attempt_number=len(submissions(user, assignment)) + 1,
        text_content=text[:20000] or None,
        file_media_id=media.id if media else None,
        is_late=assignment.is_past_due,
    )
    db.session.add(submission)
    audit_service.record(
        "assignment.submitted",
        target=assignment,
        actor=user,
        meta={"attempt": submission.attempt_number, "late": submission.is_late},
    )
    db.session.commit()
    course: Course = assignment.course
    if course.instructor_id:
        notification_service.notify(
            course.instructor_id,
            kind="submission",
            title=f"New submission: {assignment.title('en') or assignment.title_ka}",
            body=f"{user.name} submitted attempt {submission.attempt_number}.",
            link=f"/instructor/grading/{submission.id}",
        )
    return submission


def grade(submission: AssignmentSubmission, *, grader: User, points: float, feedback: str) -> Grade:
    assignment = submission.assignment
    points = max(0.0, min(float(points), float(assignment.max_points)))
    if submission.is_late and assignment.late_penalty_percent:
        points = round(points * (1 - assignment.late_penalty_percent / 100.0), 2)
    if submission.grade is None:
        submission.grade = Grade(
            grader_id=grader.id, points=points, feedback=sanitize_html(feedback)
        )
    else:
        submission.grade.grader_id = grader.id
        submission.grade.points = points
        submission.grade.feedback = sanitize_html(feedback)
        submission.grade.graded_at = utcnow()
    submission.status = SubmissionStatus.GRADED
    audit_service.record(
        "assignment.graded",
        target=assignment,
        actor=grader,
        meta={"submission_id": submission.id, "points": points},
    )
    db.session.commit()
    notification_service.notify(
        submission.user_id,
        kind="assignment_feedback",
        title=f"Assignment graded: {points:g}/{assignment.max_points:g}",
        body=f"{assignment.title('en') or assignment.title_ka} - feedback from {grader.name}.",
        link=f"/assignment/{assignment.id}/",
    )
    if assignment.lesson:
        from app.services import progress_service

        progress_service.complete_lesson(submission.user, assignment.course, assignment.lesson)
    return submission.grade


def return_for_revision(submission: AssignmentSubmission, *, grader: User, feedback: str) -> None:
    submission.status = SubmissionStatus.RETURNED
    if submission.grade is None:
        submission.grade = Grade(grader_id=grader.id, points=0, feedback=sanitize_html(feedback))
    else:
        submission.grade.feedback = sanitize_html(feedback)
    audit_service.record(
        "assignment.returned",
        target=submission.assignment,
        actor=grader,
        meta={"submission_id": submission.id},
    )
    db.session.commit()
    notification_service.notify(
        submission.user_id,
        kind="assignment_feedback",
        title="Assignment returned for revision",
        body=submission.assignment.title("en") or submission.assignment.title_ka,
        link=f"/assignment/{submission.assignment_id}/",
    )


def pending_for_instructor(user: User, *, all_courses: bool = False) -> list[AssignmentSubmission]:
    stmt = (
        select(AssignmentSubmission)
        .join(Assignment)
        .join(Course)
        .where(AssignmentSubmission.status == SubmissionStatus.SUBMITTED)
        .order_by(AssignmentSubmission.submitted_at)
    )
    if not all_courses:
        stmt = stmt.where(Course.instructor_id == user.id)
    return list(db.session.execute(stmt).scalars())


def course_submissions(course: Course) -> list[AssignmentSubmission]:
    return list(
        db.session.execute(
            select(AssignmentSubmission)
            .join(Assignment)
            .where(Assignment.course_id == course.id)
            .order_by(AssignmentSubmission.submitted_at.desc())
        ).scalars()
    )
