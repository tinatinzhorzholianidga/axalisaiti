from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Bookmark, BookmarkType, Course, Lesson, LessonResource, User


def toggle(user: User, target_type: BookmarkType, target_id: int) -> bool:
    """Return True when the bookmark now exists, False when it was removed."""
    existing = db.session.execute(
        select(Bookmark).where(
            Bookmark.user_id == user.id,
            Bookmark.target_type == target_type,
            Bookmark.target_id == target_id,
        )
    ).scalar_one_or_none()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return False
    db.session.add(Bookmark(user_id=user.id, target_type=target_type, target_id=target_id))
    db.session.commit()
    return True


def is_bookmarked(user: User, target_type: BookmarkType, target_id: int) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return (
        db.session.execute(
            select(Bookmark.id).where(
                Bookmark.user_id == user.id,
                Bookmark.target_type == target_type,
                Bookmark.target_id == target_id,
            )
        ).first()
        is not None
    )


def list_for_user(user: User) -> dict[str, list]:
    rows = list(
        db.session.execute(
            select(Bookmark).where(Bookmark.user_id == user.id).order_by(Bookmark.created_at.desc())
        ).scalars()
    )
    result: dict[str, list] = {"courses": [], "lessons": [], "resources": []}
    for row in rows:
        if row.target_type == BookmarkType.COURSE:
            course = db.session.get(Course, row.target_id)
            if course and course.is_published:
                result["courses"].append((row, course))
        elif row.target_type == BookmarkType.LESSON:
            lesson = db.session.get(Lesson, row.target_id)
            if lesson and lesson.course.is_published:
                result["lessons"].append((row, lesson))
        else:
            resource = db.session.get(LessonResource, row.target_id)
            if resource:
                result["resources"].append((row, resource))
    return result
