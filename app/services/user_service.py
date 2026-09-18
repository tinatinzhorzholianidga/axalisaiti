"""User administration: profile updates, suspension, deactivation, data export."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_

from app.extensions import db
from app.models.base import UserStatus, utcnow
from app.models.user import User
from app.services import audit_service
from app.services.rbac import assign_role, remove_role


def search_users(query: str | None, role: str | None = None, status: str | None = None):  # type: ignore[no-untyped-def]
    stmt = db.session.query(User)
    if query:
        like = f"%{query.strip().lower()}%"
        stmt = stmt.filter(
            or_(
                func.lower(User.email).like(like),
                func.lower(User.first_name).like(like),
                func.lower(User.last_name).like(like),
            )
        )
    if role:
        stmt = stmt.filter(User.roles.any(name=role))
    if status:
        stmt = stmt.filter(User.status == status)
    return stmt.order_by(User.created_at.desc())


def update_profile(user: User, **fields: Any) -> None:
    allowed = {"first_name", "last_name", "display_name", "organization", "bio", "locale", "theme"}
    for key, value in fields.items():
        if key in allowed:
            setattr(user, key, value.strip() if isinstance(value, str) else value)
    db.session.commit()


def update_notification_prefs(user: User, prefs: dict[str, bool]) -> None:
    user.notification_prefs = {k: bool(v) for k, v in prefs.items()}
    db.session.commit()


def set_roles(user: User, role_names: list[str], actor: User | None = None) -> None:
    current = user.role_names
    wanted = set(role_names)
    for name in current - wanted:
        remove_role(user, name)
    for name in wanted - current:
        assign_role(user, name)
    audit_service.record(
        "user.roles_changed", target=user, actor=actor, meta={"roles": sorted(wanted)}
    )
    db.session.commit()


def suspend(user: User, actor: User | None = None, reason: str = "") -> None:
    user.status = UserStatus.SUSPENDED
    user.bump_security_version()
    audit_service.record("user.suspended", target=user, actor=actor, meta={"reason": reason})
    db.session.commit()


def reinstate(user: User, actor: User | None = None) -> None:
    user.status = UserStatus.ACTIVE
    user.locked_until = None
    user.failed_login_count = 0
    audit_service.record("user.reinstated", target=user, actor=actor)
    db.session.commit()


def deactivate(user: User, actor: User | None = None) -> None:
    user.status = UserStatus.DEACTIVATED
    user.deactivated_at = utcnow()
    user.bump_security_version()
    audit_service.record("user.deactivated", target=user, actor=actor)
    db.session.commit()


def request_deletion(user: User) -> None:
    user.status = UserStatus.PENDING_DELETION
    user.deletion_requested_at = utcnow()
    user.bump_security_version()
    audit_service.record("user.deletion_requested", target=user, actor=user)
    db.session.commit()


def export_data(user: User) -> dict[str, Any]:
    """Portable snapshot of a user's data (GDPR-style export)."""
    from app.models import Certificate, CourseProgress, Enrollment, QuizAttempt, Review

    enrollments = db.session.query(Enrollment).filter_by(user_id=user.id).all()
    progress = db.session.query(CourseProgress).filter_by(user_id=user.id).all()
    attempts = db.session.query(QuizAttempt).filter_by(user_id=user.id).all()
    certificates = db.session.query(Certificate).filter_by(user_id=user.id).all()
    reviews = db.session.query(Review).filter_by(user_id=user.id).all()
    return {
        "profile": {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "display_name": user.display_name,
            "organization": user.organization,
            "locale": user.locale,
            "created_at": user.created_at.isoformat(),
        },
        "roles": sorted(user.role_names),
        "enrollments": [
            {
                "course": e.course.slug,
                "status": e.status.value,
                "enrolled_at": e.enrolled_at.isoformat(),
            }
            for e in enrollments
        ],
        "progress": [
            {"course": p.course.slug, "percent": p.percent, "complete": p.is_complete}
            for p in progress
        ],
        "quiz_attempts": [
            {
                "quiz": a.quiz_id,
                "percent": a.percent,
                "passed": a.passed,
                "at": a.started_at.isoformat(),
            }
            for a in attempts
        ],
        "certificates": [
            {
                "public_id": c.public_id,
                "course": c.course_title_ka,
                "issued_at": c.issued_at.isoformat(),
            }
            for c in certificates
        ],
        "reviews": [{"course": r.course.slug, "rating": r.rating, "body": r.body} for r in reviews],
    }


def create_user(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    roles: list[str],
    actor=None,  # type: ignore[no-untyped-def]
    verified: bool = True,
) -> User:
    from app.services.auth_service import AuthError, find_by_email, normalize_email

    if find_by_email(email):
        raise AuthError("An account with this email already exists.")
    user = User(
        email=normalize_email(email),
        first_name=first_name,
        last_name=last_name,
        is_email_verified=verified,
        email_verified_at=utcnow() if verified else None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    for role in roles:
        assign_role(user, role)
    user.security_version = 1
    audit_service.record("user.created", target=user, actor=actor, meta={"roles": roles})
    db.session.commit()
    return user
