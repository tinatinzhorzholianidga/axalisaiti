from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import utcnow


class Certificate(db.Model):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    recipient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    course_title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    course_title_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    final_score: Mapped[float | None] = mapped_column(Float)
    verification_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(300))

    user = relationship("User")
    course = relationship("Course")

    @property
    def is_valid(self) -> bool:
        return self.revoked_at is None

    def course_title(self, locale: str = "ka") -> str:
        return (
            self.course_title_en
            if locale == "en" and self.course_title_en
            else self.course_title_ka
        )
