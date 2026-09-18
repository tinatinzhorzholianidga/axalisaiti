"""Quizzes, questions, options, attempts and answers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import (
    AttemptStatus,
    FeedbackMode,
    JSONType,
    QuestionType,
    TimestampMixin,
    str_enum,
    utcnow,
)


class Quiz(TimestampMixin, Model):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"), unique=True
    )
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    max_attempts: Mapped[int | None] = mapped_column(Integer)  # None = unlimited
    pass_percent: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    feedback_mode: Mapped[FeedbackMode] = mapped_column(
        str_enum(FeedbackMode), default=FeedbackMode.INSTANT, nullable=False
    )
    show_explanations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course = relationship("Course", back_populates="quizzes")
    lesson = relationship("Lesson", back_populates="quiz")
    questions: Mapped[list[Question]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.sort_order",
        lazy="selectin",
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )

    def title(self, locale: str = "ka") -> str:
        return (self.title_en if locale == "en" and self.title_en else self.title_ka) or ""

    def description(self, locale: str = "ka") -> str:
        return (
            self.description_en if locale == "en" and self.description_en else self.description_ka
        ) or ""

    @property
    def max_points(self) -> float:
        return float(sum(q.points for q in self.questions))


class Question(TimestampMixin, Model):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        str_enum(QuestionType), default=QuestionType.SINGLE, nullable=False
    )
    prompt_ka: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    points: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    # short answer: JSON list of accepted answers (case-insensitive compare)
    accepted_answers: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media_files.id", ondelete="SET NULL"))

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.sort_order",
        lazy="selectin",
    )
    media = relationship("MediaFile", foreign_keys=[media_id])

    def prompt(self, locale: str = "ka") -> str:
        return (self.prompt_en if locale == "en" and self.prompt_en else self.prompt_ka) or ""

    def explanation(self, locale: str = "ka") -> str:
        return (
            self.explanation_en if locale == "en" and self.explanation_en else self.explanation_ka
        ) or ""


class QuestionOption(Model):
    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # matching: the right-hand side that pairs with this option
    match_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    match_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # ordering: the correct 1-based position of this option
    correct_position: Mapped[int | None] = mapped_column(Integer)

    question: Mapped[Question] = relationship(back_populates="options")

    def text(self, locale: str = "ka") -> str:
        return (self.text_en if locale == "en" and self.text_en else self.text_ka) or ""

    def match(self, locale: str = "ka") -> str:
        return (self.match_en if locale == "en" and self.match_en else self.match_ka) or ""


class QuizAttempt(TimestampMixin, Model):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", "user_id", "attempt_number", name="uq_attempt_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(
        str_enum(AttemptStatus), default=AttemptStatus.IN_PROGRESS, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    question_order: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    option_order: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    score_points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="attempts")
    user = relationship("User")
    answers: Mapped[list[QuizAnswer]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_open(self) -> bool:
        if self.status != AttemptStatus.IN_PROGRESS:
            return False
        return not (self.expires_at and self.expires_at < utcnow())


class QuizAnswer(Model):
    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[dict | list | str | None] = mapped_column(JSONType)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    points_awarded: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    attempt: Mapped[QuizAttempt] = relationship(back_populates="answers")
    question = relationship("Question")
