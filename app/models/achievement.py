from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import Platform, str_enum, utcnow


class Achievement(db.Model):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    platform: Mapped[Platform] = mapped_column(
        str_enum(Platform), default=Platform.ELEARNING, nullable=False
    )
    name_ka: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    description_ka: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    description_en: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="award", nullable=False)
    criteria_type: Mapped[str] = mapped_column(String(40), nullable=False)
    criteria_value: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def name(self, locale: str = "ka") -> str:
        return self.name_en if locale == "en" else self.name_ka

    def description(self, locale: str = "ka") -> str:
        return self.description_en if locale == "en" else self.description_ka


class UserAchievement(db.Model):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user = relationship("User")
    achievement: Mapped[Achievement] = relationship(lazy="joined")
