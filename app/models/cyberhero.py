"""CyberHero-specific content: tracks, missions, rounds, questions, branching
conversations, articles, mascot tips, safety resources, progress and
certificates. Courses with ``platform = cyberhero`` reuse the shared Course /
Module / Lesson models and link to a track."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TimestampMixin, utcnow
from app.models.course import TranslatedMixin

cyber_article_missions = Table(
    "cyber_article_missions",
    db.metadata,
    Column("article_id", ForeignKey("cyber_articles.id", ondelete="CASCADE"), primary_key=True),
    Column("mission_id", ForeignKey("cyber_missions.id", ondelete="CASCADE"), primary_key=True),
)


class CyberTrack(TranslatedMixin, TimestampMixin, db.Model):
    """An age/audience track such as *Cyber Guardians* (10–14) or *Teachers & Parents*."""

    __tablename__ = "cyber_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    audience: Mapped[str] = mapped_column(
        String(20), default="kids", nullable=False
    )  # kids|teens|adults
    color: Mapped[str] = mapped_column(String(16), default="violet", nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="shield", nullable=False)
    character: Mapped[str] = mapped_column(String(20), default="io", nullable=False)  # io|hero|none
    illustration_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_coming_soon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certificate_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    translations: Mapped[list[CyberTrackTranslation]] = relationship(
        back_populates="track", cascade="all, delete-orphan", lazy="selectin"
    )
    courses: Mapped[list] = relationship("Course", back_populates="cyber_track")
    missions: Mapped[list[CyberMission]] = relationship(
        back_populates="track", order_by="CyberMission.sort_order"
    )
    illustration = relationship("MediaFile", foreign_keys=[illustration_media_id])

    def name(self, locale: str = "ka") -> str:
        return self.text("name", locale, self.slug)


class CyberTrackTranslation(db.Model):
    __tablename__ = "cyber_track_translations"
    __table_args__ = (UniqueConstraint("track_id", "locale", name="uq_cyber_track_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_tracks.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tagline: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    audience_label: Mapped[str] = mapped_column(String(80), default="", nullable=False)

    track: Mapped[CyberTrack] = relationship(back_populates="translations")


class CyberMission(TranslatedMixin, TimestampMixin, db.Model):
    __tablename__ = "cyber_missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_tracks.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mission_type: Mapped[str] = mapped_column(
        String(20), default="quiz", nullable=False
    )  # quiz|branching|mixed
    icon: Mapped[str] = mapped_column(String(40), default="star", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="violet", nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1..3
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    pass_percent: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    help_resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("cyber_safety_resources.id", ondelete="SET NULL")
    )

    track: Mapped[CyberTrack] = relationship(back_populates="missions")
    course = relationship("Course", back_populates="missions")
    translations: Mapped[list[CyberMissionTranslation]] = relationship(
        back_populates="mission", cascade="all, delete-orphan", lazy="selectin"
    )
    rounds: Mapped[list[CyberMissionRound]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="CyberMissionRound.sort_order",
    )
    branches: Mapped[list[CyberBranch]] = relationship(
        back_populates="mission", cascade="all, delete-orphan", order_by="CyberBranch.sort_order"
    )
    help_resource = relationship("CyberSafetyResource", foreign_keys=[help_resource_id])
    articles: Mapped[list[CyberArticle]] = relationship(
        secondary=cyber_article_missions, back_populates="missions"
    )

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, self.slug)

    @property
    def max_points(self) -> int:
        return sum(q.points for r in self.rounds for q in r.questions)


class CyberMissionTranslation(db.Model):
    __tablename__ = "cyber_mission_translations"
    __table_args__ = (UniqueConstraint("mission_id", "locale", name="uq_cyber_mission_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_missions.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    tagline: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    intro: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completion_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    help_note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    mission: Mapped[CyberMission] = relationship(back_populates="translations")


class CyberMissionRound(db.Model):
    __tablename__ = "cyber_mission_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_missions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    round_type: Mapped[str] = mapped_column(
        String(20), default="questions", nullable=False
    )  # questions|branch|info
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    title_ka: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    title_en: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    intro_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    intro_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    branch_start_key: Mapped[str | None] = mapped_column(String(60))

    mission: Mapped[CyberMission] = relationship(back_populates="rounds")
    questions: Mapped[list[CyberMissionQuestion]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="CyberMissionQuestion.sort_order",
        lazy="selectin",
    )


class CyberMissionQuestion(db.Model):
    __tablename__ = "cyber_mission_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_mission_rounds.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(20), default="single", nullable=False
    )  # single|multiple|true_false|spot
    prompt_ka: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scenario_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scenario_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    image_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )

    round: Mapped[CyberMissionRound] = relationship(back_populates="questions")
    options: Mapped[list[CyberQuestionOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="CyberQuestionOption.sort_order",
        lazy="selectin",
    )
    image = relationship("MediaFile", foreign_keys=[image_media_id])


class CyberQuestionOption(db.Model):
    __tablename__ = "cyber_question_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_mission_questions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    feedback_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    feedback_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    question: Mapped[CyberMissionQuestion] = relationship(back_populates="options")


class CyberBranch(db.Model):
    """A node in a branching conversation (e.g. a stranger messaging the child)."""

    __tablename__ = "cyber_branches"
    __table_args__ = (UniqueConstraint("mission_id", "key", name="uq_cyber_branch_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_missions.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    speaker: Mapped[str] = mapped_column(
        String(20), default="stranger", nullable=False
    )  # io|hero|stranger|friend|narrator
    mascot_mood: Mapped[str] = mapped_column(String(20), default="neutral", nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_start: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_ending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ending_kind: Mapped[str | None] = mapped_column(String(20))  # safe|risky|neutral

    mission: Mapped[CyberMission] = relationship(back_populates="branches")
    choices: Mapped[list[CyberBranchChoice]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        order_by="CyberBranchChoice.sort_order",
        lazy="selectin",
    )


class CyberBranchChoice(db.Model):
    __tablename__ = "cyber_branch_choices"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_branches.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_key: Mapped[str | None] = mapped_column(String(60))
    is_safe: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    feedback_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    feedback_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    branch: Mapped[CyberBranch] = relationship(back_populates="choices")


class CyberArticle(TranslatedMixin, TimestampMixin, db.Model):
    """Parent / teacher knowledge articles (A1–A7 understand, B1–B5 act, C1–C4 school)."""

    __tablename__ = "cyber_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)  # A1..C4
    section: Mapped[str] = mapped_column(String(20), nullable=False)  # understand|act|school
    audience: Mapped[str] = mapped_column(
        String(20), default="both", nullable=False
    )  # parents|teachers|both
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="book", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="violet", nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cover_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )

    translations: Mapped[list[CyberArticleTranslation]] = relationship(
        back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )
    sources: Mapped[list[CyberArticleSource]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="CyberArticleSource.sort_order",
        lazy="selectin",
    )
    missions: Mapped[list[CyberMission]] = relationship(
        secondary=cyber_article_missions, back_populates="articles"
    )
    cover = relationship("MediaFile", foreign_keys=[cover_media_id])

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, self.slug)


class CyberArticleTranslation(db.Model):
    __tablename__ = "cyber_article_translations"
    __table_args__ = (UniqueConstraint("article_id", "locale", name="uq_cyber_article_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_articles.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    key_takeaways: Mapped[str] = mapped_column(Text, default="", nullable=False)  # one per line

    article: Mapped[CyberArticle] = relationship(back_populates="translations")

    @property
    def takeaway_list(self) -> list[str]:
        return [line.strip() for line in self.key_takeaways.splitlines() if line.strip()]


class CyberArticleSource(db.Model):
    __tablename__ = "cyber_article_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_articles.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)

    article: Mapped[CyberArticle] = relationship(back_populates="sources")


class CyberMascotTip(db.Model):
    __tablename__ = "cyber_mascot_tips"

    id: Mapped[int] = mapped_column(primary_key=True)
    context_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    mood: Mapped[str] = mapped_column(String(20), default="happy", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def text(self, locale: str = "ka") -> str:
        return (self.text_en if locale == "en" and self.text_en else self.text_ka) or ""


class CyberSafetyResource(TranslatedMixin, TimestampMixin, db.Model):
    """Emergency contacts, playbook entries, the family media agreement and guides."""

    __tablename__ = "cyber_safety_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # emergency_contact|playbook|family_agreement|guide
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="lifebuoy", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="orange", nullable=False)
    contact_value: Mapped[str] = mapped_column(
        String(200), default="", nullable=False
    )  # phone/url/email
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    translations: Mapped[list[CyberSafetyResourceTranslation]] = relationship(
        back_populates="resource", cascade="all, delete-orphan", lazy="selectin"
    )

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, self.slug)


class CyberSafetyResourceTranslation(db.Model):
    __tablename__ = "cyber_safety_resource_translations"
    __table_args__ = (UniqueConstraint("resource_id", "locale", name="uq_cyber_resource_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_safety_resources.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    steps: Mapped[str] = mapped_column(Text, default="", nullable=False)  # one step per line

    resource: Mapped[CyberSafetyResource] = relationship(back_populates="translations")

    @property
    def step_list(self) -> list[str]:
        return [line.strip() for line in self.steps.splitlines() if line.strip()]


class CyberProgress(TimestampMixin, db.Model):
    """Server-side mission progress for signed-in users (anonymous users use localStorage)."""

    __tablename__ = "cyber_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "mission_id", name="uq_cyber_progress_user_mission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_missions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    best_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    user = relationship("User")
    mission = relationship("CyberMission")


class CyberCertificate(db.Model):
    __tablename__ = "cyber_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    track_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_tracks.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    track_name_ka: Mapped[str] = mapped_column(String(120), nullable=False)
    track_name_en: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    score_percent: Mapped[float | None] = mapped_column(Float)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user = relationship("User")
    track: Mapped[CyberTrack] = relationship()
