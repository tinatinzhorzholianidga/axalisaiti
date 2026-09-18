"""Authentication: login with lockout, registration, tokens, password changes,
session invalidation through the security version."""

from __future__ import annotations

import contextlib
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from flask import current_app, url_for
from flask_login import login_user, logout_user
from sqlalchemy import func

from app.extensions import db
from app.models.base import UserStatus, utcnow
from app.models.user import AuthToken, User
from app.services import audit_service, mail_service
from app.services.rbac import assign_role


class AuthError(Exception):
    """Raised with a user-safe message."""


@dataclass
class LoginResult:
    user: User | None
    error: str | None = None
    locked: bool = False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def load_user_from_session_id(session_id: str) -> User | None:
    """Flask-Login user loader: ``"<id>:<security_version>"`` must still match."""
    try:
        user_id, version = session_id.split(":", 1)
        user = db.session.get(User, int(user_id))
    except (ValueError, AttributeError):
        return None
    if user is None or str(user.security_version) != version:
        return None
    if user.status != UserStatus.ACTIVE:
        return None
    return user


def find_by_email(email: str) -> User | None:
    return (
        db.session.query(User)
        .filter(func.lower(User.email) == normalize_email(email))
        .one_or_none()
    )


def validate_password_strength(password: str) -> str | None:
    minimum = current_app.config.get("PASSWORD_MIN_LENGTH", 12)
    if len(password or "") < minimum:
        return f"Password must be at least {minimum} characters long."
    lowered = password.lower()
    if lowered in {"password1234", "123456789012", "qwertyuiop12"} or len(set(password)) < 4:
        return "Password is too predictable."
    return None


# ---- login / logout ---------------------------------------------------------
def authenticate(email: str, password: str, remember: bool = False) -> LoginResult:
    user = find_by_email(email)
    generic = "Invalid email or password."
    if user is None:
        # Constant-ish time: still run a hash verify to avoid timing enumeration.
        from app.models.user import password_hasher

        with contextlib.suppress(Exception):
            password_hasher.verify(password_hasher.hash("dummy-password-for-timing"), password)
        return LoginResult(None, generic)

    if user.is_locked:
        audit_service.record("auth.login_locked", target=user, actor=user, commit=True)
        return LoginResult(None, "Too many failed attempts. Try again later.", locked=True)

    if not user.check_password(password):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        max_failed = current_app.config.get("LOGIN_MAX_FAILED", 5)
        locked = False
        if user.failed_login_count >= max_failed:
            minutes = current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15)
            user.locked_until = utcnow() + timedelta(minutes=minutes)
            user.failed_login_count = 0
            locked = True
            audit_service.record("auth.account_locked", target=user, actor=user)
        else:
            audit_service.record("auth.login_failed", target=user, actor=user)
        db.session.commit()
        if locked:
            return LoginResult(None, "Too many failed attempts. Try again later.", locked=True)
        return LoginResult(None, generic)

    if user.status == UserStatus.SUSPENDED:
        return LoginResult(None, "This account is suspended.")
    if user.status in {UserStatus.DEACTIVATED, UserStatus.PENDING_DELETION}:
        return LoginResult(None, "This account is not active.")

    from app.services import settings_service

    verification_required = bool(
        settings_service.get(
            "auth.email_verification_required",
            current_app.config.get("EMAIL_VERIFICATION_REQUIRED", False),
        )
    )
    if verification_required and not user.is_email_verified:
        return LoginResult(None, "Please verify your email address before signing in.")

    if user.needs_rehash():
        user.set_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    user.last_login_ip = audit_service.client_ip()
    login_user(user, remember=remember)
    audit_service.record(
        "auth.login" if not user.is_admin else "auth.admin_login", target=user, actor=user
    )
    db.session.commit()
    return LoginResult(user)


def logout() -> None:
    logout_user()


# ---- registration -----------------------------------------------------------
def register(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    locale: str = "ka",
    organization: str | None = None,
    send_verification: bool | None = None,
) -> User:
    email = normalize_email(email)
    if find_by_email(email):
        raise AuthError("An account with this email already exists.")
    problem = validate_password_strength(password)
    if problem:
        raise AuthError(problem)
    user = User(
        email=email,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        locale=locale if locale in current_app.config["LANGUAGES"] else "ka",
        organization=(organization or "").strip() or None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    assign_role(user, "student")
    user.security_version = 1
    audit_service.record("user.registered", target=user, actor=user)
    db.session.commit()

    from app.services import settings_service

    if send_verification is None:
        send_verification = bool(
            settings_service.get(
                "auth.email_verification_required",
                current_app.config.get("EMAIL_VERIFICATION_REQUIRED", False),
            )
        )
    if send_verification:
        send_verification_email(user)
    else:
        mail_service.send_email(user.email, "Welcome", "welcome", user=user)
    return user


# ---- tokens -----------------------------------------------------------------
def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(user: User, purpose: str, max_age: int | None = None) -> str:
    max_age = max_age or current_app.config.get("TOKEN_MAX_AGE_SECONDS", 3600)
    raw = secrets.token_urlsafe(32)
    # Invalidate previous tokens for the same purpose.
    db.session.query(AuthToken).filter_by(user_id=user.id, purpose=purpose, used_at=None).delete()
    db.session.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_hash_token(raw),
            expires_at=utcnow() + timedelta(seconds=max_age),
        )
    )
    db.session.commit()
    return raw


def consume_token(raw: str, purpose: str) -> User | None:
    if not raw or len(raw) > 128:
        return None
    token = (
        db.session.query(AuthToken)
        .filter_by(token_hash=_hash_token(raw), purpose=purpose, used_at=None)
        .one_or_none()
    )
    if token is None or token.expires_at < utcnow():
        return None
    token.used_at = utcnow()
    return token.user


def send_verification_email(user: User) -> None:
    raw = issue_token(user, "verify", max_age=86400)
    link = url_for("auth.verify_email", token=raw, _external=True)
    mail_service.send_email(user.email, "Verify your email", "verify_email", user=user, link=link)


def verify_email(raw: str) -> User | None:
    user = consume_token(raw, "verify")
    if user is None:
        return None
    user.is_email_verified = True
    user.email_verified_at = utcnow()
    audit_service.record("user.email_verified", target=user, actor=user)
    db.session.commit()
    return user


def request_password_reset(email: str) -> None:
    """Always succeeds from the caller's perspective (no account enumeration)."""
    user = find_by_email(email)
    if user is None or user.status != UserStatus.ACTIVE:
        return
    raw = issue_token(user, "reset")
    link = url_for("auth.reset_password", token=raw, _external=True)
    mail_service.send_email(
        user.email, "Reset your password", "reset_password", user=user, link=link
    )
    audit_service.record("auth.password_reset_requested", target=user, actor=user, commit=True)


def reset_password(raw: str, new_password: str) -> User:
    user = consume_token(raw, "reset")
    if user is None:
        raise AuthError("This reset link is invalid or has expired.")
    problem = validate_password_strength(new_password)
    if problem:
        raise AuthError(problem)
    user.set_password(new_password)
    user.bump_security_version()  # invalidates every existing session
    user.failed_login_count = 0
    user.locked_until = None
    audit_service.record("auth.password_reset", target=user, actor=user)
    db.session.commit()
    return user


def change_password(user: User, current_password: str, new_password: str) -> None:
    if not user.check_password(current_password):
        raise AuthError("Current password is incorrect.")
    problem = validate_password_strength(new_password)
    if problem:
        raise AuthError(problem)
    if user.check_password(new_password):
        raise AuthError("New password must differ from the current one.")
    user.set_password(new_password)
    user.bump_security_version()
    audit_service.record("auth.password_changed", target=user, actor=user)
    db.session.commit()
    # Re-login the current session with the new security version.
    login_user(user)
    mail_service.send_email(user.email, "Your password was changed", "password_changed", user=user)
