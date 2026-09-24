"""Case studies: short, article-like write-ups of real incidents and threats.

A case study belongs to one case category (admin-managed, e.g. "Ongoing
threats"), always has a *Description* and an *About* section (the latter may
carry a picture gallery) and any number of extra sections whose headings
come from the admin-managed list of section titles ("Be careful of",
"How to identify", …).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import TimestampMixin
from app.models.course import TranslatedMixin

if TYPE_CHECKING:
    from app.models.media import MediaFile
    from app.models.user import User

_TAG = re.compile(r"<[^>]+>")


class CaseCategory(TranslatedMixin, TimestampMixin, Model):
    __tablename__ = "case_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="alert-triangle", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="blue", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    translations: Mapped[list[CaseCategoryTranslation]] = relationship(
        back_populates="category", cascade="all, delete-orphan", lazy="selectin"
    )
    cases: Mapped[list[CaseStudy]] = relationship(back_populates="category")

    def name(self, locale: str = "ka") -> str:
        return self.text("name", locale, self.slug)


class CaseCategoryTranslation(Model):
    __tablename__ = "case_category_translations"
    __table_args__ = (UniqueConstraint("category_id", "locale", name="uq_case_category_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("case_categories.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    category: Mapped[CaseCategory] = relationship(back_populates="translations")


class CaseSectionTitle(TimestampMixin, Model):
    """An optional section heading admins can pick for a case study."""

    __tablename__ = "case_section_titles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_ka: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def name(self, locale: str = "ka") -> str:
        return (self.name_en if locale == "en" and self.name_en else self.name_ka) or ""


class CaseStudy(TranslatedMixin, TimestampMixin, Model):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_categories.id", ondelete="SET NULL")
    )
    cover_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    translations: Mapped[list[CaseStudyTranslation]] = relationship(
        back_populates="case_study", cascade="all, delete-orphan", lazy="selectin"
    )
    sections: Mapped[list[CaseStudySection]] = relationship(
        back_populates="case_study",
        cascade="all, delete-orphan",
        order_by="CaseStudySection.sort_order",
    )
    images: Mapped[list[CaseStudyImage]] = relationship(
        back_populates="case_study",
        cascade="all, delete-orphan",
        order_by="CaseStudyImage.sort_order",
    )
    category: Mapped[CaseCategory | None] = relationship(back_populates="cases")
    cover: Mapped[MediaFile | None] = relationship("MediaFile", foreign_keys=[cover_media_id])
    created_by: Mapped[User | None] = relationship("User", foreign_keys=[created_by_id])

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, self.slug)

    def excerpt(self, locale: str = "ka", length: int = 180) -> str:
        """Plain-text opening of the description, for cards and search results."""
        text = _TAG.sub(" ", self.text("description", locale))
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= length else text[: length - 1].rstrip() + "…"

    @property
    def visible_sections(self) -> list[CaseStudySection]:
        return [s for s in self.sections if s.title is not None]


class CaseStudyTranslation(Model):
    __tablename__ = "case_study_translations"
    __table_args__ = (UniqueConstraint("case_study_id", "locale", name="uq_case_study_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_study_id: Mapped[int] = mapped_column(
        ForeignKey("case_studies.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    about: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML

    case_study: Mapped[CaseStudy] = relationship(back_populates="translations")


class CaseStudySection(TimestampMixin, Model):
    """An extra section: a heading from the admin list plus bilingual HTML."""

    __tablename__ = "case_study_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_study_id: Mapped[int] = mapped_column(
        ForeignKey("case_studies.id", ondelete="CASCADE"), nullable=False
    )
    title_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_section_titles.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    body_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    body_en: Mapped[str] = mapped_column(Text, default="", nullable=False)

    case_study: Mapped[CaseStudy] = relationship(back_populates="sections")
    title: Mapped[CaseSectionTitle | None] = relationship()

    def heading(self, locale: str = "ka") -> str:
        return self.title.name(locale) if self.title else ""

    def body(self, locale: str = "ka") -> str:
        return (self.body_en if locale == "en" and self.body_en else self.body_ka) or ""


class CaseStudyImage(TimestampMixin, Model):
    """A picture shown in the About section (gallery)."""

    __tablename__ = "case_study_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_study_id: Mapped[int] = mapped_column(
        ForeignKey("case_studies.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    caption_ka: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    caption_en: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    case_study: Mapped[CaseStudy] = relationship(back_populates="images")
    media: Mapped[MediaFile] = relationship("MediaFile", foreign_keys=[media_id])

    def caption(self, locale: str = "ka") -> str:
        return (self.caption_en if locale == "en" and self.caption_en else self.caption_ka) or ""
