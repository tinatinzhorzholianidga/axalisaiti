"""Users, roles, permissions and auth tokens."""

from __future__ import annotations

from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask_login import UserMixin
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import JSONType, TimestampMixin, UserStatus, str_enum, utcnow

# Argon2id with parameters above the OWASP minimum recommendation.
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32)

user_roles = Table(
    "user_roles",
    db.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("granted_at", DateTime, default=utcnow, nullable=False),
    Column("granted_by_id", ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
)

role_permissions = Table(
    "role_permissions",
    db.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(db.Model):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions, back_populates="permissions"
    )


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )
    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        primaryjoin="Role.id == user_roles.c.role_id",
        secondaryjoin="User.id == user_roles.c.user_id",
        back_populates="roles",
    )

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for p in self.permissions}


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    organization: Mapped[str | None] = mapped_column(String(160))
    bio: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(5), default="ka", nullable=False)
    theme: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    avatar_media_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "media_files.id", ondelete="SET NULL", use_alter=True, name="fk_users_avatar_media"
        )
    )

    status: Mapped[UserStatus] = mapped_column(
        str_enum(UserStatus), default=UserStatus.ACTIVE, nullable=False
    )
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    security_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_ip: Mapped[str | None] = mapped_column(String(45))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime)

    notification_prefs: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        primaryjoin="User.id == user_roles.c.user_id",
        secondaryjoin="Role.id == user_roles.c.role_id",
        back_populates="users",
        lazy="selectin",
    )
    avatar = relationship("MediaFile", foreign_keys=[avatar_media_id])

    # ---- identity / security ------------------------------------------------
    def get_id(self) -> str:  # Flask-Login session identity includes the security stamp
        return f"{self.id}:{self.security_version}"

    def set_password(self, password: str) -> None:
        self.password_hash = password_hasher.hash(password)
        self.password_changed_at = utcnow()

    def check_password(self, password: str) -> bool:
        try:
            return password_hasher.verify(self.password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def needs_rehash(self) -> bool:
        try:
            return password_hasher.check_needs_rehash(self.password_hash)
        except InvalidHashError:
            return True

    def bump_security_version(self) -> None:
        self.security_version = (self.security_version or 1) + 1

    @property
    def is_active(self) -> bool:  # Flask-Login hook
        return self.status == UserStatus.ACTIVE

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > utcnow())

    # ---- RBAC ----------------------------------------------------------------
    @property
    def role_names(self) -> set[str]:
        return {r.name for r in self.roles}

    def has_role(self, *names: str) -> bool:
        return bool(self.role_names.intersection(names))

    @property
    def permission_codes(self) -> set[str]:
        codes: set[str] = set()
        for role in self.roles:
            codes.update(role.permission_codes)
        return codes

    def has_permission(self, *codes: str) -> bool:
        return bool(self.permission_codes.intersection(codes))

    @property
    def is_admin(self) -> bool:
        return self.has_role("admin")

    @property
    def is_instructor(self) -> bool:
        return self.has_role("instructor", "admin")

    # ---- presentation --------------------------------------------------------
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def name(self) -> str:
        return self.display_name or self.full_name or self.email

    @property
    def initials(self) -> str:
        parts = [self.first_name[:1], self.last_name[:1]]
        return "".join(p for p in parts if p).upper() or self.email[:1].upper()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.id} {self.email}>"


class AuthToken(db.Model):
    """Single-use, hashed tokens for email verification and password reset."""

    __tablename__ = "auth_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship()
