from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Model
from app.models.base import TimestampMixin


class SiteSetting(TimestampMixin, Model):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    value_type: Mapped[str] = mapped_column(String(10), default="string", nullable=False)
    group: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    label: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    description: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def typed_value(self) -> Any:
        if self.value_type == "bool":
            return self.value.strip().lower() in {"1", "true", "yes", "on"}
        if self.value_type == "int":
            try:
                return int(self.value)
            except ValueError:
                return 0
        if self.value_type == "json":
            try:
                return json.loads(self.value or "null")
            except ValueError:
                return None
        return self.value


class FeatureFlag(TimestampMixin, Model):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    updated_by = relationship("User")
