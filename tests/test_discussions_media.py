"""Discussions, moderation, reports and protected media access."""

from __future__ import annotations

import io

import pytest
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Course, Discussion, DiscussionReport, MediaKind
from app.services import discussion_service, media_service, seed_service
from app.services.media_service import UploadError
from tests.conftest import login, post


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


def test_discussion_thread_reply_moderation(client, demo, student, instructor):  # type: ignore[no-untyped-def]
    demo.instructor_id = instructor.id
    db.session.commit()
    login(client, student)
    # must be enrolled
    response = post(client, f"/discussions/{demo.slug}/", {"title": "Question", "body": "Hello?"})
    assert "პოსტის გამოქვეყნება არ შეგიძლიათ" in response.data.decode()
    post(client, f"/courses/{demo.slug}/enroll")
    response = post(
        client,
        f"/discussions/{demo.slug}/",
        {"title": "Question", "body": "<p>Hello <script>x</script></p>"},
    )
    thread = db.session.query(Discussion).one()
    assert response.status_code == 302 and "<script>" not in thread.posts[0].body
    # reply + notification to thread author is not sent to self
    response = post(client, f"/discussions/{demo.slug}/{thread.id}/", {"body": "Reply"})
    assert response.status_code == 302 and thread.post_count == 2
    # student cannot moderate
    response = post(client, f"/discussions/{demo.slug}/{thread.id}/moderate", {"action": "pin"})
    assert response.status_code == 403
    # instructor pins, locks and hides
    other = client.application.test_client()
    login(other, instructor)
    for action in ("pin", "lock"):
        assert (
            post(
                other, f"/discussions/{demo.slug}/{thread.id}/moderate", {"action": action}
            ).status_code
            == 302
        )
    db.session.refresh(thread)
    assert thread.is_pinned and thread.is_locked
    response = post(client, f"/discussions/{demo.slug}/{thread.id}/", {"body": "locked?"})
    assert "დაბლოკილია" in response.data.decode()
    # report + resolve
    post_id = thread.posts[0].id
    assert (
        post(
            other, f"/discussions/{demo.slug}/post/{post_id}/report", {"reason": "spam"}
        ).status_code
        == 302
    )
    report = db.session.query(DiscussionReport).one()
    assert report.status == "open"
    discussion_service.resolve_report(report, instructor)
    assert report.status == "resolved"
    assert (
        post(
            other, f"/discussions/{demo.slug}/{thread.id}/moderate", {"action": "hide"}
        ).status_code
        == 302
    )
    assert client.get(f"/discussions/{demo.slug}/{thread.id}/").status_code == 404
    assert other.get(f"/discussions/{demo.slug}/{thread.id}/").status_code == 200


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
