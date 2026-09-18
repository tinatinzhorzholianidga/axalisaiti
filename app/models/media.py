from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import MediaKind, TimestampMixin, str_enum


class MediaFile(TimestampMixin, db.Model):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[MediaKind] = mapped_column(str_enum(MediaKind), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    folder: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    alt_text: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    uploader = relationship("User", foreign_keys=[uploader_id])

    @property
    def extension(self) -> str:
        return self.stored_name.rsplit(".", 1)[-1].lower() if "." in self.stored_name else ""

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def relative_path(self) -> str:
        return f"{self.folder}/{self.stored_name}"
