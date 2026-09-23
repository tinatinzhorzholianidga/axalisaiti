"""CyberHero-specific content.

The structures mirror the CyberHero content contract (tiers, missions built
from four round engines, parent/teacher articles made of blocks, the family
media agreement, mascot tips and the IO knowledge base). Every text field is
bilingual (``*_ka`` / ``*_en``). Courses with ``platform = cyberhero`` reuse
the shared Course / Module / Lesson models and link to a track.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import JSONType, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.course import Course

TONES = ("blue", "cyan", "green", "pink", "amber", "violet", "orange", "accent")


class BilingualMixin:
    """``obj.text("field", locale)`` with Georgian fallback and ``obj.pair("field")``."""

    def text(self, field: str, locale: str = "ka") -> str:
        value = getattr(self, f"{field}_{locale}", None) or getattr(self, f"{field}_ka", None)
        return value or ""

    def pair(self, field: str) -> dict[str, str]:
        return {
            "en": getattr(self, f"{field}_en", "") or "",
            "ka": getattr(self, f"{field}_ka", "") or "",
        }


class CyberTrack(BilingualMixin, TimestampMixin, Model):
    """An age track ("tier") such as Cyber Guardians or Teachers & Parents."""

    __tablename__ = "cyber_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="🛡️", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="blue", nullable=False)  # tone name
    audience: Mapped[str] = mapped_column(String(20), default="kids", nullable=False)
    route: Mapped[str | None] = mapped_column(String(80))  # e.g. /guardians when active
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # hidden tracks stay in the admin panel (missions, progress and
    # certificates intact) but never reach the public API / CyberHero app
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    certificate_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    illustration_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )

    tag_ka: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    tag_en: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    name_ka: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    desc_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    desc_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    intro_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    intro_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    topics_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # one per line
    topics_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    courses: Mapped[list[Course]] = relationship("Course", back_populates="cyber_track")
    missions: Mapped[list[CyberMission]] = relationship(
        back_populates="track", order_by="CyberMission.sort_order"
    )
    illustration = relationship("MediaFile", foreign_keys=[illustration_media_id])

    def name(self, locale: str = "ka") -> str:
        return self.text("name", locale)

    def topic_list(self, locale: str) -> list[str]:
        raw = getattr(self, f"topics_{locale}", "") or ""
        return [line.strip() for line in raw.splitlines() if line.strip()]


class CyberMission(BilingualMixin, TimestampMixin, Model):
    __tablename__ = "cyber_missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)  # g1 … g10
    track_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_tracks.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="⭐", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="blue", nullable=False)
    article_code: Mapped[str | None] = mapped_column(String(8))  # related parent article (a2 …)
    topics: Mapped[str] = mapped_column(String(200), default="", nullable=False)  # comma list
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timer_seconds: Mapped[int | None] = mapped_column(Integer)
    pass_ratio: Mapped[float | None] = mapped_column(Float)

    name_ka: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    desc_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    desc_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    brief_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    brief_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    help_strip_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    help_strip_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    track: Mapped[CyberTrack] = relationship(back_populates="missions")
    course = relationship("Course", back_populates="missions")
    notes: Mapped[list[CyberMissionNote]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="CyberMissionNote.sort_order",
    )
    rounds: Mapped[list[CyberMissionRound]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="CyberMissionRound.sort_order",
    )

    def name(self, locale: str = "ka") -> str:
        return self.text("name", locale)

    @property
    def topic_list(self) -> list[str]:
        return [t.strip() for t in self.topics.split(",") if t.strip()]

    @property
    def theory(self) -> list[CyberMissionNote]:
        return [n for n in self.notes if n.kind == "theory"]

    @property
    def takeaways(self) -> list[CyberMissionNote]:
        return [n for n in self.notes if n.kind == "takeaway"]

    @property
    def max_points(self) -> int:
        return sum(r.max_points for r in self.rounds)


class CyberMissionNote(BilingualMixin, Model):
    """Theory bullets (shown before the mission) and takeaways (shown after)."""

    __tablename__ = "cyber_mission_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_missions.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # theory | takeaway
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)

    mission: Mapped[CyberMission] = relationship(back_populates="notes")


class CyberMissionRound(BilingualMixin, Model):
    """One round of a mission. ``round_type`` selects the engine:
    choice (one question, options, optional message card), flags (tap every
    red flag), builder (toggle options until a meter reaches ``target``) or
    branch (a conversation tree of :class:`CyberBranch` nodes)."""

    __tablename__ = "cyber_mission_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_missions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    round_type: Mapped[str] = mapped_column(String(16), nullable=False)

    prompt_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # q / prompt
    prompt_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explain_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explain_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explain_negative_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explain_negative_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # choice: message card
    card_from_ka: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    card_from_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    card_meta_ka: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    card_meta_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    card_body_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    card_body_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # builder
    target: Mapped[int | None] = mapped_column(Integer)
    meter_low_ka: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    meter_low_en: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    meter_high_ka: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    meter_high_en: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # branch
    branch_start_key: Mapped[str | None] = mapped_column(String(40))
    branch_max: Mapped[int | None] = mapped_column(Integer)

    mission: Mapped[CyberMission] = relationship(back_populates="rounds")
    items: Mapped[list[CyberRoundItem]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="CyberRoundItem.sort_order",
        lazy="selectin",
    )
    branches: Mapped[list[CyberBranch]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="CyberBranch.sort_order",
        lazy="selectin",
    )

    @property
    def max_points(self) -> int:
        if self.round_type == "choice":
            return 10
        if self.round_type == "flags":
            return sum(5 for item in self.items if item.is_correct)
        if self.round_type == "builder":
            return 15
        if self.round_type == "branch":
            return int(self.branch_max or 0)
        return 0

    @property
    def has_card(self) -> bool:
        return bool(self.card_body_ka or self.card_body_en)


class CyberRoundItem(BilingualMixin, Model):
    """An option (choice), a flaggable item (flags) or a toggle (builder)."""

    __tablename__ = "cyber_round_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_mission_rounds.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label_ka: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    from_ka: Mapped[str] = mapped_column(String(200), default="", nullable=False)  # flags: sender
    from_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    note_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # builder: note
    note_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explain_ka: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )  # flags: per-item reveal
    explain_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # correct / flag
    value: Mapped[int | None] = mapped_column(Integer)  # builder: meter contribution

    round: Mapped[CyberMissionRound] = relationship(back_populates="items")


class CyberBranch(BilingualMixin, Model):
    """A node of a branching conversation."""

    __tablename__ = "cyber_branches"
    __table_args__ = (UniqueConstraint("round_id", "key", name="uq_cyber_branch_round_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_mission_rounds.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scene_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scene_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    round: Mapped[CyberMissionRound] = relationship(back_populates="branches")
    messages: Mapped[list[CyberBranchMessage]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        order_by="CyberBranchMessage.sort_order",
        lazy="selectin",
    )
    choices: Mapped[list[CyberBranchChoice]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        order_by="CyberBranchChoice.sort_order",
        lazy="selectin",
    )


class CyberBranchMessage(BilingualMixin, Model):
    __tablename__ = "cyber_branch_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_branches.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name_ka: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)

    branch: Mapped[CyberBranch] = relationship(back_populates="messages")


class CyberBranchChoice(BilingualMixin, Model):
    __tablename__ = "cyber_branch_choices"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_branches.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label_ka: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    next_key: Mapped[str | None] = mapped_column(String(40))
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feedback_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    feedback_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    branch: Mapped[CyberBranch] = relationship(back_populates="choices")


class CyberArticle(BilingualMixin, TimestampMixin, Model):
    """Parent / teacher article (shelves A understand · B act · C school)."""

    __tablename__ = "cyber_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)  # a1 … c4
    shelf: Mapped[str] = mapped_column(String(1), nullable=False)  # A | B | C
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="📖", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="blue", nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    mission_slug: Mapped[str | None] = mapped_column(String(80))  # related teen mission
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    title_ka: Mapped[str] = mapped_column(String(300), nullable=False)
    title_en: Mapped[str] = mapped_column(String(300), nullable=False)
    teaser_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    teaser_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    lead_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    lead_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    blocks: Mapped[list[CyberArticleBlock]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="CyberArticleBlock.sort_order",
    )
    sources: Mapped[list[CyberArticleSource]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="CyberArticleSource.sort_order",
        lazy="selectin",
    )

    @property
    def code(self) -> str:
        return self.slug.upper()

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale)


class CyberArticleBlock(BilingualMixin, Model):
    """Article body block: h2 | p | list | callout (variant script/do/dont/note/emergency)."""

    __tablename__ = "cyber_article_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_articles.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    block_type: Mapped[str] = mapped_column(String(16), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(16))
    ordered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    title_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # ordered bilingual list entries: [{"en": …, "ka": …}, …]
    items: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    paragraphs: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)

    article: Mapped[CyberArticle] = relationship(back_populates="blocks")


class CyberArticleSource(Model):
    __tablename__ = "cyber_article_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_articles.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    citation: Mapped[str] = mapped_column(String(500), nullable=False)

    article: Mapped[CyberArticle] = relationship(back_populates="sources")


class CyberSafetyResource(BilingualMixin, TimestampMixin, Model):
    """Emergency contacts, playbook entries, guides and the family media agreement."""

    __tablename__ = "cyber_safety_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="🆘", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="amber", nullable=False)
    contact_value: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    title_ka: Mapped[str] = mapped_column(String(300), nullable=False)
    title_en: Mapped[str] = mapped_column(String(300), nullable=False)
    summary_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    body_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    steps_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # one per line
    steps_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    sections: Mapped[list[CyberAgreementSection]] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
        order_by="CyberAgreementSection.sort_order",
    )

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale)

    def step_list(self, locale: str) -> list[str]:
        raw = getattr(self, f"steps_{locale}", "") or ""
        return [line.strip() for line in raw.splitlines() if line.strip()]


class CyberAgreementSection(BilingualMixin, Model):
    __tablename__ = "cyber_agreement_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_safety_resources.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    write_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    resource: Mapped[CyberSafetyResource] = relationship(back_populates="sections")
    clauses: Mapped[list[CyberAgreementClause]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="CyberAgreementClause.sort_order",
        lazy="selectin",
    )


class CyberAgreementClause(BilingualMixin, Model):
    __tablename__ = "cyber_agreement_clauses"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_agreement_sections.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)

    section: Mapped[CyberAgreementSection] = relationship(back_populates="clauses")


class CyberMascotTip(BilingualMixin, Model):
    """IO's contextual tips; ``topics`` decides where they are shown."""

    __tablename__ = "cyber_mascot_tips"

    id: Mapped[int] = mapped_column(primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topics: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def topic_list(self) -> list[str]:
        return [t.strip() for t in self.topics.split(",") if t.strip()]


class CyberMascotReaction(BilingualMixin, Model):
    """What IO says on achievements / contexts (mission, exam, cert, guardians, building)."""

    __tablename__ = "cyber_mascot_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_ka: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)


class CyberKnowledgeSection(BilingualMixin, Model):
    """IO tutor knowledge base: sections of the approved course material."""

    __tablename__ = "cyber_knowledge_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)

    chunks: Mapped[list[CyberKnowledgeChunk]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="CyberKnowledgeChunk.sort_order",
        lazy="selectin",
    )


class CyberKnowledgeChunk(Model):
    __tablename__ = "cyber_knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("cyber_knowledge_sections.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    section: Mapped[CyberKnowledgeSection] = relationship(back_populates="chunks")


class CyberProgress(TimestampMixin, Model):
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
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    best: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    user = relationship("User")
    mission: Mapped[CyberMission] = relationship()


class CyberCertificate(Model):
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
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user = relationship("User")
    track: Mapped[CyberTrack] = relationship()

    @property
    def is_valid(self) -> bool:
        return self.revoked_at is None
