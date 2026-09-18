"""In-app notifications (+ optional email digests through the mail service)."""

from __future__ import annotations

from sqlalchemy import func, select, update

from app.extensions import db
from app.models import Notification, User, utcnow

EMAIL_KINDS = {"assignment_feedback", "certificate", "announcement", "quiz_result"}


def notify(
    user_id: int,
    *,
    kind: str,
    title: str,
    body: str = "",
    link: str | None = None,
    payload: dict | None = None,
    email: bool = False,
) -> Notification:
    note = Notification(
        user_id=user_id, kind=kind, title=title[:200], body=body, link=link, payload=payload or {}
    )
    db.session.add(note)
    db.session.commit()
    if email or kind in EMAIL_KINDS:
        user = db.session.get(User, user_id)
        prefs = (user.notification_prefs or {}) if user else {}
        if user and prefs.get(f"email_{kind}", True):
            from app.services import mail_service

            mail_service.send_email(
                user.email, title, "notification", user=user, title=title, body=body, link=link
            )
    return note


def broadcast(*, kind: str, title: str, body: str, link: str | None, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    db.session.bulk_save_objects(
        [
            Notification(user_id=uid, kind=kind, title=title[:200], body=body, link=link)
            for uid in user_ids
        ]
    )
    db.session.commit()
    return len(user_ids)


def unread_count(user: User) -> int:
    if not getattr(user, "is_authenticated", False):
        return 0
    return int(
        db.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        ).scalar_one()
    )


def recent(user: User, limit: int = 8) -> list[Notification]:
    return list(
        db.session.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def paginate(user: User, page: int, per_page: int = 20):  # type: ignore[no-untyped-def]
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def mark_read(user: User, notification_id: int) -> bool:
    note = db.session.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        return False
    if not note.is_read:
        note.is_read = True
        note.read_at = utcnow()
        db.session.commit()
    return True


def mark_all_read(user: User) -> int:
    result = db.session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=utcnow())
    )
    db.session.commit()
    return int(getattr(result, "rowcount", 0) or 0)
