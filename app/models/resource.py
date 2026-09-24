"""Platform resources: documents (PDFs) administrators publish on /resources/."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.media import MediaFile


class Resource(TimestampMixin, Model):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description_ka: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    media: Mapped[MediaFile] = relationship("MediaFile", foreign_keys=[media_id])

    def title(self, locale: str = "ka") -> str:
        return (self.title_en if locale == "en" and self.title_en else self.title_ka) or ""

    def description(self, locale: str = "ka") -> str:
        if locale == "en" and self.description_en:
            return self.description_en
        return self.description_ka or ""
