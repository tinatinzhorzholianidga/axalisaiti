"""Platform resources (admin-published PDFs) and course files a learner may see."""

from __future__ import annotations

from typing import Any

from flask_babel import gettext as _
from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    Course,
    CourseStatus,
    Enrollment,
    EnrollmentStatus,
    Lesson,
    LessonResource,
    MediaKind,
    Module,
    Resource,
    User,
)
from app.services import audit_service, media_service
from app.services.media_service import UploadError

PDF_ONLY = {"pdf"}


def visible() -> list[Resource]:
    stmt = (
        select(Resource)
        .where(Resource.is_visible.is_(True))
        .order_by(Resource.sort_order, Resource.created_at.desc())
    )
    return list(db.session.execute(stmt).scalars())


def all_for_admin() -> list[Resource]:
    stmt = select(Resource).order_by(Resource.sort_order, Resource.created_at.desc())
    return list(db.session.execute(stmt).scalars())


def create(*, file: FileStorage | None, actor: User, is_visible: bool, **fields: Any) -> Resource:
    if not file or not file.filename:
        raise UploadError(_("Choose a PDF file."))
    media = media_service.save_upload(
        file,
        kind=MediaKind.RESOURCE,
        uploader=actor,
        is_public=bool(is_visible),
        allowed_extensions=PDF_ONLY,
    )
    resource = Resource(media_id=media.id, created_by_id=actor.id, is_visible=bool(is_visible))
    for key, value in fields.items():
        if hasattr(resource, key):
            setattr(resource, key, value if value is not None else "")
    db.session.add(resource)
    db.session.flush()
    audit_service.record("resource.created", target=resource, actor=actor)
    db.session.commit()
    return resource


def update(
    resource: Resource,
    *,
    actor: User,
    is_visible: bool,
    file: FileStorage | None = None,
    **fields: Any,
) -> Resource:
    for key, value in fields.items():
        if hasattr(resource, key):
            setattr(resource, key, value if value is not None else "")
    if file and file.filename:
        old = resource.media
        media = media_service.save_upload(
            file,
            kind=MediaKind.RESOURCE,
            uploader=actor,
            is_public=bool(is_visible),
            allowed_extensions=PDF_ONLY,
        )
        resource.media_id = media.id
        db.session.flush()
        media_service.delete_media(old, actor=actor)
    set_visibility(resource, is_visible, actor=actor, commit=False)
    audit_service.record("resource.updated", target=resource, actor=actor)
    db.session.commit()
    return resource


def set_visibility(
    resource: Resource, is_visible: bool, *, actor: User, commit: bool = True
) -> None:
    """Hidden resources are also no longer served as public files."""
    resource.is_visible = bool(is_visible)
    resource.media.is_public = bool(is_visible)
    if commit:
        audit_service.record(
            "resource.visibility",
            target=resource,
            actor=actor,
            meta={"visible": resource.is_visible},
        )
        db.session.commit()


def delete(resource: Resource, *, actor: User) -> None:
    media = resource.media
    audit_service.record("resource.deleted", target=resource, actor=actor)
    db.session.delete(resource)
    db.session.flush()
    media_service.delete_media(media, actor=actor)


def course_resources_for(user: User) -> list[tuple[Course, list[LessonResource]]]:
    """Files and links from the published lessons of courses the learner has taken."""
    if not getattr(user, "is_authenticated", False):
        return []
    stmt = (
        select(LessonResource, Course)
        .join(Lesson, LessonResource.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .join(Course, Module.course_id == Course.id)
        .join(
            Enrollment,
            (Enrollment.course_id == Course.id) & (Enrollment.user_id == user.id),
        )
        .where(
            Course.status == CourseStatus.PUBLISHED,
            Module.is_published.is_(True),
            Lesson.is_published.is_(True),
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
        .order_by(
            Course.sort_order,
            Course.id,
            Module.sort_order,
            Lesson.sort_order,
            LessonResource.sort_order,
        )
    )
    grouped: dict[int, tuple[Course, list[LessonResource]]] = {}
    for resource, course in db.session.execute(stmt).all():
        grouped.setdefault(course.id, (course, []))[1].append(resource)
    return list(grouped.values())
