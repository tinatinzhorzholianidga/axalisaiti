"""Shared mixins, enums and column helpers."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Naive UTC timestamp (stored as DATETIME; interpreted as UTC everywhere)."""
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


def str_enum(enum_cls: type[enum.Enum], length: int = 32) -> Enum:
    """Portable string enum column (works on MariaDB and SQLite)."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


JSONType: Any = JSON


class Platform(enum.StrEnum):
    ELEARNING = "elearning"
    CYBERHERO = "cyberhero"
    BOTH = "both"


class Locale(enum.StrEnum):
    KA = "ka"
    EN = "en"


class CourseStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Difficulty(enum.StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LessonType(enum.StrEnum):
    READING = "reading"
    VIDEO = "video"
    QUIZ = "quiz"
    LAB = "lab"
    ASSIGNMENT = "assignment"


class QuestionType(enum.StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ORDERING = "ordering"
    MATCHING = "matching"


class EnrollmentMode(enum.StrEnum):
    OPEN = "open"
    APPROVAL = "approval"
    INVITE = "invite"


class EnrollmentStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


class ProgressStatus(enum.StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
    PENDING_DELETION = "pending_deletion"


class AttemptStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"


class FeedbackMode(enum.StrEnum):
    INSTANT = "instant"
    DELAYED = "delayed"


class SubmissionType(enum.StrEnum):
    TEXT = "text"
    FILE = "file"
    BOTH = "both"


class SubmissionStatus(enum.StrEnum):
    SUBMITTED = "submitted"
    GRADED = "graded"
    RETURNED = "returned"


class ReviewStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MediaKind(enum.StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"
    ASSIGNMENT = "assignment"
    RESOURCE = "resource"
    ICON = "icon"
    CYBERHERO = "cyberhero"


class BookmarkType(enum.StrEnum):
    COURSE = "course"
    LESSON = "lesson"
    RESOURCE = "resource"
