"""Enrolments, lesson/course progress and bookmarks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import (
    BookmarkType,
    EnrollmentStatus,
    ProgressStatus,
    TimestampMixin,
    str_enum,
    utcnow,
)


class Enrollment(TimestampMixin, Model):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_enrollment_user_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        str_enum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE, nullable=False
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL")
    )

    user = relationship("User", backref="enrollments")
    course = relationship("Course", backref="enrollments")
    last_lesson = relationship("Lesson", foreign_keys=[last_lesson_id])


class LessonProgress(TimestampMixin, Model):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ProgressStatus] = mapped_column(
        str_enum(ProgressStatus), default=ProgressStatus.IN_PROGRESS, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    seconds_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user = relationship("User")
    lesson = relationship("Lesson")


class CourseProgress(TimestampMixin, Model):
    __tablename__ = "course_progress"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_course_progress_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    completed_lessons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_lessons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quizzes_passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quizzes_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_score: Mapped[float | None] = mapped_column(Float)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    user = relationship("User")
    course = relationship("Course")


class Bookmark(Model):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_bookmark_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[BookmarkType] = mapped_column(str_enum(BookmarkType), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user = relationship("User")
