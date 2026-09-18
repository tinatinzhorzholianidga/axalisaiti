"""Certificate issuance and public verification."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models import Certificate, Course, CourseProgress, User
from app.services import audit_service, notification_service, settings_service

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous characters


def _public_id(prefix: str = "EL") -> str:
    year = datetime.now(UTC).year
    while True:
        token = "".join(secrets.choice(ALPHABET) for _ in range(8))
        candidate = f"{prefix}-{year}-{token}"
        if (
            db.session.execute(
                select(Certificate.id).where(Certificate.public_id == candidate)
            ).first()
            is None
        ):
            return candidate


def _verification_hash(public_id: str, user_id: int, course_id: int) -> str:
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    payload = f"{public_id}:{user_id}:{course_id}".encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def get_for_user_course(user: User, course: Course) -> Certificate | None:
    return db.session.execute(
        select(Certificate).where(
            Certificate.user_id == user.id, Certificate.course_id == course.id
        )
    ).scalar_one_or_none()


def eligible(course: Course, progress: CourseProgress | None) -> bool:
    if not course.certificate_enabled or progress is None or not progress.is_complete:
        return False
    return not (course.final_quiz and (progress.final_score or 0) < course.certificate_pass_percent)


def issue_for_completion(
    user: User, course: Course, progress: CourseProgress
) -> Certificate | None:
    if not eligible(course, progress):
        return None
    existing = get_for_user_course(user, course)
    if existing:
        return existing
    return issue(user, course, final_score=progress.final_score)


def issue(
    user: User, course: Course, *, final_score: float | None = None, actor: User | None = None
) -> Certificate:
    public_id = _public_id()
    certificate = Certificate(
        public_id=public_id,
        user_id=user.id,
        course_id=course.id,
        recipient_name=user.full_name,
        course_title_ka=course.title("ka"),
        course_title_en=course.title("en"),
        organization=settings_service.certificate_org(),
        final_score=final_score,
        verification_hash=_verification_hash(public_id, user.id, course.id),
    )
    db.session.add(certificate)
    audit_service.record(
        "certificate.issued",
        target=certificate,
        actor=actor or user,
        meta={"user_id": user.id, "course": course.slug},
    )
    db.session.commit()
    notification_service.notify(
        user.id,
        kind="certificate",
        title="Certificate issued",
        body=f"Your certificate for {course.title('en') or course.slug} is ready.",
        link=f"/certificates/{certificate.public_id}/",
    )
    from app.services import achievement_service

    achievement_service.check_certificates(user)
    return certificate


def revoke(certificate: Certificate, *, actor: User, reason: str) -> None:
    from app.models import utcnow

    certificate.revoked_at = utcnow()
    certificate.revoke_reason = reason[:300]
    audit_service.record(
        "certificate.revoked", target=certificate, actor=actor, meta={"reason": reason}
    )
    db.session.commit()


def verify(public_id: str) -> Certificate | None:
    public_id = (public_id or "").strip().upper()[:40]
    certificate = db.session.execute(
        select(Certificate).where(Certificate.public_id == public_id)
    ).scalar_one_or_none()
    if certificate is None:
        return None
    expected = _verification_hash(certificate.public_id, certificate.user_id, certificate.course_id)
    if not hmac.compare_digest(expected, certificate.verification_hash):
        return None
    return certificate


def user_certificates(user: User) -> list[Certificate]:
    return list(
        db.session.execute(
            select(Certificate)
            .where(Certificate.user_id == user.id)
            .order_by(Certificate.issued_at.desc())
        ).scalars()
    )
