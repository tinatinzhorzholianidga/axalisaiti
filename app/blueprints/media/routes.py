"""Serves uploaded files through authorised endpoints (never from /static)."""

from __future__ import annotations

from flask import abort, send_from_directory
from flask_login import current_user

from app.blueprints.media import bp
from app.extensions import db
from app.models import MediaFile
from app.services import media_service

_DOWNLOAD_CSP = "default-src 'none'; sandbox"


def _send(media: MediaFile, as_attachment: bool):  # type: ignore[no-untyped-def]
    directory = media_service.upload_root() / media.folder
    response = send_from_directory(
        directory,
        media.stored_name,
        mimetype=media.mime_type,
        as_attachment=as_attachment,
        download_name=media.original_name,
        conditional=True,
        max_age=86400 if media.is_public else 0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    if not media.is_image or media.mime_type == "image/svg+xml":
        response.headers["Content-Security-Policy"] = _DOWNLOAD_CSP
    if not media.is_public:
        response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.get("/public/<int:media_id>")
def public_file(media_id: int):  # type: ignore[no-untyped-def]
    media = db.session.get(MediaFile, media_id)
    if media is None or not media.is_public:
        abort(404)
    return _send(media, as_attachment=False)


@bp.get("/files/<int:media_id>")
def protected_file(media_id: int):  # type: ignore[no-untyped-def]
    media = db.session.get(MediaFile, media_id)
    if media is None:
        abort(404)
    if not current_user.is_authenticated:
        abort(401)
    if not media_service.can_access(current_user, media):
        abort(403)
    return _send(media, as_attachment=not media.is_image)
