"""Render every eLearning page with seeded content in both languages and check CSP hygiene."""

from __future__ import annotations

import re

import pytest

from app.extensions import db
from app.models import Course
from app.services import enrollment_service, seed_service
from tests.conftest import login, post

INLINE_STYLE = re.compile(r"<[a-z][^>]*\sstyle=", re.I)
INLINE_HANDLER = re.compile(r"<[a-z][^>]*\son[a-z]+=", re.I)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\ssrc=)[^>]*>", re.I)


@pytest.fixture
def demo(app):  # type: ignore[no-untyped-def]
    seed_service.seed_demo_content()
    return db.session.query(Course).filter_by(slug="basic-cybersecurity").one()


def assert_clean(html: str) -> None:
    assert not INLINE_STYLE.search(html), "inline style attribute found"
    assert not INLINE_HANDLER.search(html), "inline event handler found"
    assert not INLINE_SCRIPT.search(html), "inline script found"


@pytest.mark.parametrize("lang", ["ka", "en"])
def test_public_pages_render(client, demo, lang):  # type: ignore[no-untyped-def]
    lesson = demo.modules[0].lessons[0]
    pages = [
        "/",
        "/about/",
        "/resources/",
        "/search/?q=phishing",
        "/courses/",
        f"/courses/?category=cybersecurity&difficulty=beginner&sort=title&q={'კიბერ' if lang == 'ka' else 'cyber'}",
        f"/courses/{demo.slug}/",
        f"/courses/{demo.slug}/?tab=syllabus",
        f"/learn/{demo.slug}/{lesson.slug}/",  # free preview lesson
        "/auth/login",
        "/auth/register",
        "/auth/reset",
        "/certificates/verify/EL-0000-NOPE",
    ]
    for path in pages:
        sep = "&" if "?" in path else "?"
        response = client.get(f"{path}{sep}lang={lang}")
        assert response.status_code == 200, path
        html = response.data.decode()
        assert f'<html lang="{lang}"' in html, path
        assert_clean(html)
    # Georgian is the default and the catalogue shows the Georgian title
    response = client.get("/courses/?lang=ka")
    assert "კიბერუსაფრთხოების საბაზისო კურსი" in response.data.decode()


def test_preview_gating(client, demo, student):  # type: ignore[no-untyped-def]
    locked = demo.modules[1].lessons[0]
    response = client.get(f"/learn/{demo.slug}/{locked.slug}/")
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]
    login(client, student)
    response = client.get(f"/learn/{demo.slug}/{locked.slug}/", follow_redirects=True)
    assert "დარეგისტრირდით კურსზე" in response.data.decode()


def test_learner_pages_render(client, demo, student):  # type: ignore[no-untyped-def]
    login(client, student)
    response = post(client, f"/courses/{demo.slug}/enroll")
    assert response.status_code == 302
    assert enrollment_service.is_enrolled(student, demo)
    lesson = demo.modules[1].lessons[0]
    for path in [
        "/dashboard/",
        "/profile/",
        "/bookmarks/",
        "/notifications/",
        "/certificates/",
        f"/courses/{demo.slug}/",
        f"/learn/{demo.slug}/{lesson.slug}/",
        "/auth/password",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert_clean(response.data.decode())
    # complete a lesson and bookmark things
    response = post(client, f"/learn/{demo.slug}/{lesson.slug}/complete", {"goto": "next"})
    assert response.status_code == 302
    response = post(client, f"/learn/{demo.slug}/{lesson.slug}/bookmark")
    assert response.status_code == 302
    response = post(client, f"/courses/{demo.slug}/bookmark")
    assert response.status_code == 302
    html = client.get("/bookmarks/").data.decode()
    assert lesson.title("ka") in html
    html = client.get("/dashboard/").data.decode()
    assert "Continue" in html or "გაგრძელება" in html
    # data export
    data = client.get("/profile/export").get_json()
    assert data["enrollments"][0]["course"] == demo.slug


def test_review_requires_enrollment_and_is_moderated(client, demo, student):  # type: ignore[no-untyped-def]
    login(client, student)
    response = post(
        client,
        f"/courses/{demo.slug}/review",
        {"rating": 5, "body": "Great"},
        follow_redirects=True,
    )
    assert "დარეგისტრირდით კურსზე" in response.data.decode()
    post(client, f"/courses/{demo.slug}/enroll")
    response = post(
        client,
        f"/courses/{demo.slug}/review",
        {"rating": 5, "body": "Great"},
        follow_redirects=True,
    )
    assert "მოდერაციის შემდეგ" in response.data.decode()
    from app.models import Review, ReviewStatus

    review = db.session.query(Review).one()
    assert review.status == ReviewStatus.PENDING
    # a second submission updates instead of duplicating
    post(client, f"/courses/{demo.slug}/review", {"rating": 4, "body": "Good"})
    assert db.session.query(Review).count() == 1
