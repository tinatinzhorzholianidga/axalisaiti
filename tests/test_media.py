"""Discussions, moderation, reports and protected media access."""

from __future__ import annotations

import io

import pytest
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Course, MediaKind
from app.services import media_service, seed_service
from app.services.media_service import UploadError
from tests.conftest import login


def _png() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()


@pytest.fixture
def demo(app):  # type: ignore[no-untyped-def]
    seed_service.seed_demo_content()
    return db.session.query(Course).filter_by(slug="phishing-awareness").one()


def test_media_validation_and_access(app, client, student, instructor, admin):  # type: ignore[no-untyped-def]
    with pytest.raises(UploadError, match="დაუშვებელია"):
        media_service.validate(
            FileStorage(stream=io.BytesIO(b"x"), filename="evil.php"), MediaKind.IMAGE
        )
    with pytest.raises(UploadError, match=r"არ შეესაბამება|სიგნატურა|დეკოდირება"):
        media_service.validate(
            FileStorage(stream=io.BytesIO(b"<html>hi</html>"), filename="x.png"), MediaKind.IMAGE
        )
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    with pytest.raises(UploadError, match="სკრიპტებს"):
        media_service.validate(
            FileStorage(stream=io.BytesIO(svg), filename="x.svg"), MediaKind.ICON
        )
    media = media_service.save_upload(
        FileStorage(stream=io.BytesIO(PNG), filename="../../cover.png"),
        kind=MediaKind.IMAGE,
        uploader=instructor,
    )
    db.session.commit()
    assert media.stored_name.endswith(".png") and "/" not in media.stored_name and media.width == 1
    assert media.mime_type == "image/png" and not media.is_public
    # anonymous and unrelated users cannot fetch a private file; the uploader and admins can
    assert client.get(f"/media/files/{media.id}").status_code == 401
    login(client, student)
    assert client.get(f"/media/files/{media.id}").status_code == 403
    assert client.get(f"/media/public/{media.id}").status_code == 404
    owner = app.test_client()
    login(owner, instructor)
    response = owner.get(f"/media/files/{media.id}")
    assert response.status_code == 200 and response.headers["X-Content-Type-Options"] == "nosniff"
    boss = app.test_client()
    login(boss, admin)
    assert boss.get(f"/media/files/{media.id}").status_code == 200
    media.is_public = True
    db.session.commit()
    response = client.get(f"/media/public/{media.id}")
    assert response.status_code == 200 and response.mimetype == "image/png"
