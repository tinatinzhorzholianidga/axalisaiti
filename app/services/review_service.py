"""Course reviews with moderation and duplicate prevention."""

from __future__ import annotations

from sqlalchemy import func, select

from app.extensions import db
from app.models import Course, Enrollment, EnrollmentStatus, Review, ReviewStatus, User
from app.services import audit_service, feature_flags, settings_service


class ReviewError(Exception):
    pass


def reviews_enabled(course: Course) -> bool:
    return bool(
        course.reviews_enabled
        and feature_flags.is_enabled("COURSE_REVIEWS_ENABLED")
        and settings_service.get("courses.reviews_enabled", True)
    )


def approved_reviews(course: Course, limit: int = 20) -> list[Review]:
    return list(
        db.session.execute(
            select(Review)
            .where(Review.course_id == course.id, Review.status == ReviewStatus.APPROVED)
            .order_by(Review.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def user_review(user: User, course: Course) -> Review | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return db.session.execute(
        select(Review).where(Review.course_id == course.id, Review.user_id == user.id)
    ).scalar_one_or_none()


def can_review(user: User, course: Course) -> bool:
    if not reviews_enabled(course) or not getattr(user, "is_authenticated", False):
        return False
    enrollment = db.session.execute(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
    ).scalar_one_or_none()
    return bool(
        enrollment and enrollment.status in {EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED}
    )


def submit_review(user: User, course: Course, rating: int, body: str) -> Review:
    if not can_review(user, course):
        raise ReviewError("You need to be enrolled to review this course.")
    if not 1 <= int(rating) <= 5:
        raise ReviewError("Rating must be between 1 and 5.")
    review = user_review(user, course)
    if review is not None:
        review.rating = int(rating)
        review.body = (body or "").strip()[:2000]
        review.status = ReviewStatus.PENDING
    else:
        review = Review(
            course_id=course.id,
            user_id=user.id,
            rating=int(rating),
            body=(body or "").strip()[:2000],
        )
        db.session.add(review)
    audit_service.record("review.submitted", target=course, actor=user, meta={"rating": rating})
    db.session.commit()
    return review


def moderate(review: Review, status: ReviewStatus, actor: User) -> None:
    review.status = status
    review.moderated_by_id = actor.id
    audit_service.record(
        "review.moderated", target=review, actor=actor, meta={"status": status.value}
    )
    db.session.flush()
    _refresh_rating(review.course)
    db.session.commit()


def _refresh_rating(course: Course) -> None:
    avg, count = db.session.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.course_id == course.id, Review.status == ReviewStatus.APPROVED
        )
    ).one()
    course.rating_avg = round(float(avg or 0), 2)
    course.rating_count = int(count or 0)


def pending_reviews(limit: int = 100) -> list[Review]:
    return list(
        db.session.execute(
            select(Review)
            .where(Review.status == ReviewStatus.PENDING)
            .order_by(Review.created_at)
            .limit(limit)
        ).scalars()
    )
