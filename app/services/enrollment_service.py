"""Enrolment lifecycle."""

from __future__ import annotations

from flask_babel import gettext as _
from sqlalchemy import select

from app.extensions import db
from app.models import (
    Course,
    CourseProgress,
    Enrollment,
    EnrollmentMode,
    EnrollmentStatus,
    User,
    utcnow,
)
from app.repositories.ordering import newest_first
from app.services import audit_service


class EnrollmentError(Exception):
    pass


def get_enrollment(user: User, course: Course) -> Enrollment | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return db.session.execute(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
    ).scalar_one_or_none()


def is_enrolled(user: User, course: Course) -> bool:
    enrollment = get_enrollment(user, course)
    return bool(
        enrollment and enrollment.status in {EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED}
    )


def enroll(user: User, course: Course) -> Enrollment:
    if not course.is_published:
        raise EnrollmentError(_("This course is not open for enrolment."))
    if course.enrollment_mode == EnrollmentMode.INVITE:
        raise EnrollmentError(_("This course is invitation only."))
    if course.starts_at and course.starts_at > utcnow():
        raise EnrollmentError(_("This course has not started yet."))
    if course.ends_at and course.ends_at < utcnow():
        raise EnrollmentError(_("Enrolment for this course has closed."))

    enrollment = get_enrollment(user, course)
    if enrollment:
        if enrollment.status == EnrollmentStatus.DROPPED:
            enrollment.status = EnrollmentStatus.ACTIVE
            enrollment.enrolled_at = utcnow()
            db.session.commit()
        return enrollment

    status = (
        EnrollmentStatus.PENDING
        if course.enrollment_mode == EnrollmentMode.APPROVAL
        else EnrollmentStatus.ACTIVE
    )
    enrollment = Enrollment(user_id=user.id, course_id=course.id, status=status)
    db.session.add(enrollment)
    course.enrollment_count = (course.enrollment_count or 0) + 1
    progress = CourseProgress(
        user_id=user.id, course_id=course.id, total_lessons=len(course.lessons)
    )
    db.session.add(progress)
    audit_service.record(
        "enrollment.created", target=course, actor=user, meta={"status": status.value}
    )
    db.session.commit()
    return enrollment


def approve(enrollment: Enrollment, actor: User) -> None:
    enrollment.status = EnrollmentStatus.ACTIVE
    audit_service.record(
        "enrollment.approved",
        target=enrollment.course,
        actor=actor,
        meta={"user_id": enrollment.user_id},
    )
    db.session.commit()


def drop(user: User, course: Course) -> None:
    enrollment = get_enrollment(user, course)
    if enrollment and enrollment.status != EnrollmentStatus.COMPLETED:
        enrollment.status = EnrollmentStatus.DROPPED
        course.enrollment_count = max(0, (course.enrollment_count or 0) - 1)
        audit_service.record("enrollment.dropped", target=course, actor=user)
        db.session.commit()


def user_enrollments(
    user: User, *, statuses: tuple[EnrollmentStatus, ...] | None = None
) -> list[Enrollment]:
    stmt = select(Enrollment).where(Enrollment.user_id == user.id)
    if statuses:
        stmt = stmt.where(Enrollment.status.in_(statuses))
    stmt = stmt.order_by(*newest_first(Enrollment.last_accessed_at), Enrollment.enrolled_at.desc())
    return list(db.session.execute(stmt).scalars())


def course_enrollments(course: Course, status: EnrollmentStatus | None = None) -> list[Enrollment]:
    stmt = select(Enrollment).where(Enrollment.course_id == course.id)
    if status:
        stmt = stmt.where(Enrollment.status == status)
    return list(db.session.execute(stmt.order_by(Enrollment.enrolled_at.desc())).scalars())
