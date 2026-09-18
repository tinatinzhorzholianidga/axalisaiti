"""Assignments, submissions and grades."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import SubmissionStatus, SubmissionType, TimestampMixin, str_enum, utcnow


class Assignment(TimestampMixin, Model):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"), unique=True
    )
    title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    instructions_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    instructions_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    submission_type: Mapped[SubmissionType] = mapped_column(
        str_enum(SubmissionType), default=SubmissionType.TEXT, nullable=False
    )
    max_points: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    allow_late: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    late_penalty_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_resubmissions: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    allowed_extensions: Mapped[str] = mapped_column(
        String(200), default="pdf,docx,txt,zip,png,jpg", nullable=False
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course = relationship("Course", back_populates="assignments")
    lesson = relationship("Lesson", back_populates="assignment")
    submissions: Mapped[list[AssignmentSubmission]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )

    def title(self, locale: str = "ka") -> str:
        return (self.title_en if locale == "en" and self.title_en else self.title_ka) or ""

    def instructions(self, locale: str = "ka") -> str:
        return (
            self.instructions_en
            if locale == "en" and self.instructions_en
            else self.instructions_ka
        ) or ""

    @property
    def allowed_extension_list(self) -> list[str]:
        return [
            e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()
        ]

    @property
    def is_past_due(self) -> bool:
        return bool(self.due_at and self.due_at < utcnow())


class AssignmentSubmission(TimestampMixin, Model):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "user_id", "attempt_number", name="uq_submission_attempt"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text)
    file_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        str_enum(SubmissionStatus), default=SubmissionStatus.SUBMITTED, nullable=False
    )

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    user = relationship("User")
    file = relationship("MediaFile", foreign_keys=[file_media_id])
    grade: Mapped[Grade | None] = relationship(
        back_populates="submission", uselist=False, cascade="all, delete-orphan"
    )


class Grade(Model):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_submissions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    grader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    points: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    graded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    submission: Mapped[AssignmentSubmission] = relationship(back_populates="grade")
    grader = relationship("User")
