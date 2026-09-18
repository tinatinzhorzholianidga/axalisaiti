"""Discussions, posts, reports and course reviews."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import ReviewStatus, TimestampMixin, str_enum, utcnow


class Discussion(TimestampMixin, Model):
    __tablename__ = "discussions"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime)

    course = relationship("Course", backref="discussions")
    author = relationship("User")
    lesson = relationship("Lesson")
    posts: Mapped[list[DiscussionPost]] = relationship(
        back_populates="discussion",
        cascade="all, delete-orphan",
        order_by="DiscussionPost.created_at",
    )


class DiscussionPost(TimestampMixin, Model):
    __tablename__ = "discussion_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    discussion_id: Mapped[int] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_posts.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)  # sanitised HTML
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime)

    discussion: Mapped[Discussion] = relationship(back_populates="posts")
    author = relationship("User")
    parent = relationship("DiscussionPost", remote_side=[id])
    reports: Mapped[list[DiscussionReport]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class DiscussionReport(Model):
    __tablename__ = "discussion_reports"
    __table_args__ = (UniqueConstraint("post_id", "reporter_id", name="uq_report_post_reporter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("discussion_posts.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    post: Mapped[DiscussionPost] = relationship(back_populates="reports")
    reporter = relationship("User", foreign_keys=[reporter_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])


class Review(TimestampMixin, Model):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_review_course_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        str_enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False
    )
    moderated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    course = relationship("Course", backref="reviews")
    user = relationship("User", foreign_keys=[user_id])
    moderated_by = relationship("User", foreign_keys=[moderated_by_id])
