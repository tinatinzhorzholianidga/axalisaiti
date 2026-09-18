"""Secure upload handling.

Files are stored outside the web root under ``UPLOAD_PATH/<folder>/`` with
generated names and served only through authorised application routes.
Validation: extension allowlist per kind, declared size, libmagic MIME,
magic-byte consistency and, for images, a full Pillow decode.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path

import magic
from flask import current_app
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    AssignmentSubmission,
    Course,
    Enrollment,
    EnrollmentStatus,
    Lesson,
    LessonResource,
    MediaFile,
    MediaKind,
    Module,
    User,
)
from app.services import audit_service


class UploadError(Exception):
    pass


@dataclass(frozen=True)
class Policy:
    extensions: frozenset[str]
    mimes: frozenset[str]
    max_mb: int
    folder: str


IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"})
DOC_MIMES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "application/zip",
        "application/x-zip-compressed",
    }
)

POLICIES: dict[MediaKind, Policy] = {
    MediaKind.IMAGE: Policy(
        frozenset({"png", "jpg", "jpeg", "webp", "gif"}), IMAGE_MIMES, 8, "images"
    ),
    MediaKind.ICON: Policy(frozenset({"png", "svg", "webp"}), IMAGE_MIMES, 1, "icons"),
    MediaKind.CYBERHERO: Policy(
        frozenset({"png", "jpg", "jpeg", "webp", "svg"}), IMAGE_MIMES, 8, "cyberhero"
    ),
    MediaKind.DOCUMENT: Policy(
        frozenset({"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "zip"}),
        DOC_MIMES,
        25,
        "documents",
    ),
    MediaKind.RESOURCE: Policy(
        frozenset(
            {
                "pdf",
                "docx",
                "xlsx",
                "pptx",
                "txt",
                "csv",
                "zip",
                "png",
                "jpg",
                "jpeg",
                "webp",
                "mp4",
            }
        ),
        DOC_MIMES | IMAGE_MIMES | {"video/mp4"},
        200,
        "resources",
    ),
    MediaKind.ASSIGNMENT: Policy(
        frozenset(
            {"pdf", "doc", "docx", "txt", "zip", "png", "jpg", "jpeg", "csv", "xlsx", "pptx"}
        ),
        DOC_MIMES | IMAGE_MIMES,
        25,
        "assignments",
    ),
}

# extension -> acceptable libmagic results (mime sniffing may be generic for office/zip)
EXT_MIME: dict[str, frozenset[str]] = {
    "png": frozenset({"image/png"}),
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
    "webp": frozenset({"image/webp"}),
    "gif": frozenset({"image/gif"}),
    "svg": frozenset({"image/svg+xml", "text/xml", "text/plain", "application/xml"}),
    "pdf": frozenset({"application/pdf"}),
    "doc": frozenset({"application/msword", "application/x-ole-storage"}),
    "docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
    "xls": frozenset({"application/vnd.ms-excel", "application/x-ole-storage"}),
    "xlsx": frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"}
    ),
    "ppt": frozenset({"application/vnd.ms-powerpoint", "application/x-ole-storage"}),
    "pptx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
        }
    ),
    "txt": frozenset({"text/plain", "application/csv", "text/csv"}),
    "csv": frozenset({"text/csv", "text/plain", "application/csv"}),
    "zip": frozenset({"application/zip", "application/x-zip-compressed"}),
    "mp4": frozenset({"video/mp4", "video/quicktime"}),
}

MAGIC_PREFIXES: dict[str, tuple[bytes, ...]] = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),
    "pdf": (b"%PDF",),
    "zip": (b"PK\x03\x04",),
    "docx": (b"PK\x03\x04",),
    "xlsx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
    "doc": (b"\xd0\xcf\x11\xe0",),
    "xls": (b"\xd0\xcf\x11\xe0",),
    "ppt": (b"\xd0\xcf\x11\xe0",),
}

DANGEROUS_SVG_TOKENS = (
    b"<script",
    b"onload",
    b"onerror",
    b"javascript:",
    b"<foreignobject",
    b'xlink:href="http',
)


def _extension(filename: str) -> str:
    name = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def upload_root() -> Path:
    return Path(current_app.config["UPLOAD_PATH"])


def validate(
    file: FileStorage, kind: MediaKind, allowed_extensions: set[str] | None = None
) -> tuple[bytes, str, str]:
    """Return (data, extension, mime) or raise UploadError."""
    policy = POLICIES[kind]
    if file is None or not file.filename:
        raise UploadError("No file selected.")
    ext = _extension(file.filename)
    permitted = (
        policy.extensions
        if allowed_extensions is None
        else policy.extensions & {e.lower() for e in allowed_extensions}
    )
    if ext not in permitted:
        raise UploadError(f"File type .{ext or '?'} is not allowed.")
    data = file.read()
    file.stream.seek(0)
    if not data:
        raise UploadError("The file is empty.")
    if len(data) > policy.max_mb * 1024 * 1024:
        raise UploadError(f"The file is larger than {policy.max_mb} MB.")
    mime = magic.from_buffer(data[:8192], mime=True) or "application/octet-stream"
    if mime not in EXT_MIME.get(ext, frozenset()) or mime not in (
        policy.mimes
        | {
            "application/zip",
            "application/x-ole-storage",
            "text/xml",
            "application/xml",
            "text/plain",
            "application/csv",
        }
    ):
        raise UploadError("The file content does not match its extension.")
    prefixes = MAGIC_PREFIXES.get(ext)
    if prefixes and not data.startswith(prefixes):
        raise UploadError("The file signature is invalid.")
    if ext in {"png", "jpg", "jpeg", "webp", "gif"}:
        try:
            with Image.open(__import__("io").BytesIO(data)) as img:
                img.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise UploadError("The image could not be decoded.") from exc
    if ext == "svg":
        lowered = data.lower()
        if any(token in lowered for token in DANGEROUS_SVG_TOKENS):
            raise UploadError("SVG files must not contain scripts or event handlers.")
        mime = "image/svg+xml"
    return data, ext, mime


def save_upload(
    file: FileStorage,
    *,
    kind: MediaKind,
    uploader: User | None,
    is_public: bool = False,
    alt_text: str = "",
    allowed_extensions: set[str] | None = None,
) -> MediaFile:
    data, ext, mime = validate(file, kind, allowed_extensions)
    folder = POLICIES[kind].folder
    stored_name = f"{secrets.token_hex(16)}.{ext}"
    target_dir = upload_root() / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / stored_name).write_bytes(data)

    width = height = None
    if ext in {"png", "jpg", "jpeg", "webp", "gif"}:
        with Image.open(__import__("io").BytesIO(data)) as img:
            width, height = img.size

    media = MediaFile(
        uploader_id=uploader.id if uploader else None,
        kind=kind,
        original_name=(file.filename or stored_name)[:255],
        stored_name=stored_name,
        folder=folder,
        mime_type=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        width=width,
        height=height,
        alt_text=alt_text[:255],
        is_public=is_public,
    )
    db.session.add(media)
    db.session.flush()
    audit_service.record(
        "media.uploaded", target=media, actor=uploader, meta={"kind": kind.value, "size": len(data)}
    )
    return media


def delete_media(media: MediaFile, actor: User | None = None) -> None:
    path = upload_root() / media.folder / media.stored_name
    if path.exists():
        path.unlink()
    audit_service.record("media.deleted", target=media, actor=actor)
    db.session.delete(media)
    db.session.commit()


def absolute_path(media: MediaFile) -> Path:
    return upload_root() / media.folder / media.stored_name


def can_access(user: User, media: MediaFile) -> bool:
    """Authorisation for protected files."""
    if media.is_public:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if media.uploader_id == user.id or user.has_permission("media.manage", "courses.manage_all"):
        return True
    # lesson resource / lesson video of a course the user can access
    course_ids = set(
        db.session.execute(
            select(Enrollment.course_id).where(
                Enrollment.user_id == user.id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        ).scalars()
    )
    instructor_ids = set(
        db.session.execute(select(Course.id).where(Course.instructor_id == user.id)).scalars()
    )
    reachable = course_ids | instructor_ids
    if reachable:
        lesson_courses = (
            select(Module.course_id)
            .join(Lesson, Lesson.module_id == Module.id)
            .outerjoin(LessonResource, LessonResource.lesson_id == Lesson.id)
            .where((LessonResource.media_id == media.id) | (Lesson.video_media_id == media.id))
        )
        if reachable & set(db.session.execute(lesson_courses).scalars()):
            return True
    # assignment submissions: owner or instructor of the course
    submission = db.session.execute(
        select(AssignmentSubmission).where(AssignmentSubmission.file_media_id == media.id)
    ).scalar_one_or_none()
    return bool(
        submission
        and (submission.user_id == user.id or submission.assignment.course.instructor_id == user.id)
    )


def list_media(kind: str | None = None, query: str | None = None):  # type: ignore[no-untyped-def]
    stmt = select(MediaFile).order_by(MediaFile.created_at.desc())
    if kind:
        stmt = stmt.where(MediaFile.kind == kind)
    if query:
        stmt = stmt.where(MediaFile.original_name.ilike(f"%{query}%"))
    return stmt
