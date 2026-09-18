"""Course discussions: threads, replies, moderation and reporting."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Course, Discussion, DiscussionPost, DiscussionReport, User, utcnow
from app.services import (
    audit_service,
    enrollment_service,
    feature_flags,
    notification_service,
    settings_service,
)
from app.services.rbac import can_manage_course
from app.services.sanitize import sanitize_html


class DiscussionError(Exception):
    pass


def enabled(course: Course) -> bool:
    return bool(
        course.discussions_enabled
        and feature_flags.is_enabled("DISCUSSIONS_ENABLED")
        and settings_service.get("courses.discussions_enabled", True)
    )


def can_participate(user: User, course: Course) -> bool:
    if not getattr(user, "is_authenticated", False) or not user.has_permission(
        "discussions.participate"
    ):
        return False
    return enrollment_service.is_enrolled(user, course) or can_manage_course(user, course)


def can_moderate(user: User, course: Course) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.has_permission("discussions.moderate_all"):
        return True
    return user.has_permission("discussions.moderate_own") and can_manage_course(user, course)


def threads(course: Course, *, include_hidden: bool = False) -> list[Discussion]:
    stmt = select(Discussion).where(Discussion.course_id == course.id)
    if not include_hidden:
        stmt = stmt.where(Discussion.is_hidden.is_(False))
    stmt = stmt.order_by(
        Discussion.is_pinned.desc(),
        Discussion.last_post_at.desc().nullslast(),
        Discussion.created_at.desc(),
    )
    return list(db.session.execute(stmt).scalars())


def create_thread(
    user: User, course: Course, *, title: str, body: str, lesson_id: int | None = None
) -> Discussion:
    if not enabled(course) or not can_participate(user, course):
        raise DiscussionError("You cannot post in this course.")
    title = (title or "").strip()[:200]
    if len(title) < 3:
        raise DiscussionError("Title is too short.")
    thread = Discussion(course_id=course.id, author_id=user.id, title=title, lesson_id=lesson_id)
    db.session.add(thread)
    db.session.flush()
    post = DiscussionPost(
        discussion_id=thread.id, author_id=user.id, body=sanitize_html(body)[:20000]
    )
    db.session.add(post)
    thread.post_count = 1
    thread.last_post_at = utcnow()
    audit_service.record(
        "discussion.created", target=thread, actor=user, meta={"course": course.slug}
    )
    db.session.commit()
    return thread


def reply(
    user: User, thread: Discussion, *, body: str, parent_id: int | None = None
) -> DiscussionPost:
    course = thread.course
    if not enabled(course) or not can_participate(user, course):
        raise DiscussionError("You cannot post in this course.")
    if thread.is_locked and not can_moderate(user, course):
        raise DiscussionError("This thread is locked.")
    clean = sanitize_html(body)[:20000]
    if len(clean.strip()) < 2:
        raise DiscussionError("Reply is empty.")
    parent = db.session.get(DiscussionPost, parent_id) if parent_id else None
    if parent is not None and parent.discussion_id != thread.id:
        parent = None
    post = DiscussionPost(
        discussion_id=thread.id,
        author_id=user.id,
        body=clean,
        parent_id=parent.id if parent else None,
    )
    db.session.add(post)
    thread.post_count = (thread.post_count or 0) + 1
    thread.last_post_at = utcnow()
    db.session.commit()
    recipients = {thread.author_id}
    if parent and parent.author_id:
        recipients.add(parent.author_id)
    for uid in {r for r in recipients if r is not None and r != user.id}:
        notification_service.notify(
            uid,
            kind="discussion_reply",
            title=f"New reply in: {thread.title}",
            body=f"{user.name} replied.",
            link=f"/discussions/{course.slug}/{thread.id}/",
        )
    return post


def set_pinned(thread: Discussion, pinned: bool, actor: User) -> None:
    thread.is_pinned = pinned
    audit_service.record(
        "discussion.pinned" if pinned else "discussion.unpinned", target=thread, actor=actor
    )
    db.session.commit()


def set_locked(thread: Discussion, locked: bool, actor: User) -> None:
    thread.is_locked = locked
    audit_service.record(
        "discussion.locked" if locked else "discussion.unlocked", target=thread, actor=actor
    )
    db.session.commit()


def set_hidden(thread: Discussion, hidden: bool, actor: User) -> None:
    thread.is_hidden = hidden
    audit_service.record(
        "discussion.hidden" if hidden else "discussion.unhidden", target=thread, actor=actor
    )
    db.session.commit()


def hide_post(post: DiscussionPost, hidden: bool, actor: User) -> None:
    post.is_hidden = hidden
    audit_service.record(
        "post.hidden" if hidden else "post.unhidden",
        target=post,
        actor=actor,
        meta={"discussion_id": post.discussion_id},
    )
    db.session.commit()


def delete_own_post(post: DiscussionPost, user: User) -> None:
    if post.author_id != user.id and not can_moderate(user, post.discussion.course):
        raise DiscussionError("You cannot delete this post.")
    post.is_deleted = True
    post.body = ""
    db.session.commit()


def report_post(post: DiscussionPost, reporter: User, reason: str) -> DiscussionReport:
    existing = db.session.execute(
        select(DiscussionReport).where(
            DiscussionReport.post_id == post.id, DiscussionReport.reporter_id == reporter.id
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    report = DiscussionReport(
        post_id=post.id, reporter_id=reporter.id, reason=(reason or "").strip()[:500] or "reported"
    )
    db.session.add(report)
    db.session.commit()
    course = post.discussion.course
    if course.instructor_id and course.instructor_id != reporter.id:
        notification_service.notify(
            course.instructor_id,
            kind="report",
            title="A post was reported",
            body=f"Thread: {post.discussion.title}",
            link=f"/discussions/{course.slug}/{post.discussion_id}/",
        )
    return report


def resolve_report(report: DiscussionReport, actor: User) -> None:
    report.status = "resolved"
    report.resolved_by_id = actor.id
    report.resolved_at = utcnow()
    db.session.commit()


def open_reports(limit: int = 100) -> list[DiscussionReport]:
    return list(
        db.session.execute(
            select(DiscussionReport)
            .where(DiscussionReport.status == "open")
            .order_by(DiscussionReport.created_at)
            .limit(limit)
        ).scalars()
    )
