"""Security review: the controls the platform promises, exercised end to end."""

from __future__ import annotations

import io

from PIL import Image

from app import create_app
from app.extensions import db
from app.models import Course, Lesson, MediaFile, User
from app.services import certificate_service, progress_service, seed_service
from app.services.enrollment_service import enroll
from tests.conftest import get_csrf, login, logout, make_user, post, post_json

INLINE_JS = ("<script", "javascript:", "onerror=", "onload=", "onclick=")


def _demo() -> Course:
    seed_service.seed_demo_content()
    return db.session.query(Course).filter_by(slug="basic-cybersecurity").one()


# ---- authorisation ---------------------------------------------------------
def test_role_boundaries(client, student, instructor, admin):  # type: ignore[no-untyped-def]
    course = _demo()
    protected = {
        "/admin/": ("admin",),
        "/admin/users/": ("admin",),
        "/admin/settings/": ("admin",),
        "/admin/cyberhero/": ("admin",),
        "/instructor/": ("instructor", "admin"),
        f"/instructor/courses/{course.id}/builder": ("admin",),  # not this instructor's course
    }
    users = {"student": student, "instructor": instructor, "admin": admin}
    for role, user in users.items():
        login(client, user)
        for url, allowed in protected.items():
            code = client.get(url).status_code
            if role in allowed:
                assert code == 200, (role, url, code)
            else:
                assert code == 403, (role, url, code)
        logout(client)
    # anonymous users are redirected to login, never shown content
    for url in protected:
        response = client.get(url)
        assert response.status_code == 302 and "/auth/login" in response.headers["Location"], url


def test_admin_api_rejects_students(client, logged_in_student):  # type: ignore[no-untyped-def]
    # admin-only write paths behind the HTML panel
    assert post(client, "/admin/flags/", {"flag-CYBERHERO_ENABLED": "on"}).status_code == 403
    assert post(client, "/admin/users/new", {"email": "x@example.org"}).status_code == 403


def test_users_cannot_read_each_others_data(client, student, admin):  # type: ignore[no-untyped-def]
    course = _demo()
    other = make_user("other@example.org")
    enroll(other, course)
    login(client, student)
    export = client.get("/profile/export").get_data(as_text=True)
    assert student.email in export
    assert "other@example.org" not in export
    # a student cannot open another user's admin page
    assert client.get(f"/admin/users/{other.id}").status_code == 403


# ---- CSRF -----------------------------------------------------------------
def test_csrf_enforced_on_every_write(client, logged_in_student):  # type: ignore[no-untyped-def]
    course = _demo()
    for url in (f"/courses/{course.slug}/enroll", "/auth/logout", "/profile/deactivate"):
        response = client.post(url, data={})
        assert response.status_code == 400, url
    response = client.post("/api/v1/bookmarks", json={"type": "course", "id": course.id})
    assert response.status_code == 400
    # the JSON API accepts the token in the X-CSRFToken header only
    response = client.post(
        "/api/v1/bookmarks",
        json={"type": "course", "id": course.id, "csrf_token": get_csrf(client)},
    )
    assert response.status_code == 400
    assert post_json(
        client, "/api/v1/bookmarks", {"type": "course", "id": course.id}
    ).status_code in (200, 201)


# ---- sessions -------------------------------------------------------------
def test_password_change_invalidates_other_sessions(app, client, student):  # type: ignore[no-untyped-def]
    other = app.test_client()
    login(client, student)
    login(other, student)
    assert other.get("/dashboard/").status_code == 200
    response = post(
        client,
        "/auth/password",
        {
            "current_password": "CorrectHorse!Battery9",
            "password": "Another-Str0ng-Passphrase",
            "confirm": "Another-Str0ng-Passphrase",
        },
    )
    assert response.status_code in (200, 302)
    db.session.expire_all()
    assert db.session.get(User, student.id).check_password("Another-Str0ng-Passphrase")
    # the other browser's session is dead; this one survives
    assert other.get("/dashboard/").status_code == 302
    assert client.get("/dashboard/").status_code == 200


def test_session_cookie_flags(client, student):  # type: ignore[no-untyped-def]
    login(client, student)
    cookie = client.get_cookie("elearning_session")
    assert cookie is not None
    assert cookie.http_only is True
    assert (cookie.same_site or "").lower() == "lax"
    # production requires the Secure flag and refuses to start without it
    import pytest

    with pytest.raises(RuntimeError, match="Refusing to start"):
        create_app(
            "production",
            overrides={
                "SECRET_KEY": "x" * 64,
                "SQLALCHEMY_DATABASE_URI": "mysql+pymysql://u:p@db/el",
                "SESSION_COOKIE_SECURE": False,
            },
        )


def test_suspension_revokes_active_session(client, student, admin):  # type: ignore[no-untyped-def]
    login(client, student)
    assert client.get("/dashboard/").status_code == 200
    from app.services import user_service

    user_service.suspend(student, actor=admin, reason="test")
    assert client.get("/dashboard/").status_code == 302


# ---- uploads --------------------------------------------------------------
def test_uploads_are_validated_and_served_only_through_authorised_endpoints(
    client, logged_in_admin, upload_dir
):  # type: ignore[no-untyped-def]
    # executables and mismatched signatures are refused regardless of extension
    for name, payload in (
        ("tool.exe", b"MZ\x90\x00"),
        ("shell.php.png", b"<?php echo 1;"),
        ("x.svg", b"<svg onload='alert(1)'></svg>"),
    ):
        response = post(
            client,
            "/admin/media/",
            {"file": (io.BytesIO(payload), name), "kind": "image", "is_public": "y"},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert db.session.query(MediaFile).count() == 0, name
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buffer, format="PNG")
    post(
        client,
        "/admin/media/",
        {"file": (io.BytesIO(buffer.getvalue()), "ok.png"), "kind": "image"},
        content_type="multipart/form-data",
    )
    media = db.session.query(MediaFile).one()
    # stored under a generated name outside the static tree
    from app.services import media_service

    assert media.stored_name.endswith(".png") and "ok" not in media.stored_name
    assert str(media_service.absolute_path(media)).startswith(upload_dir)
    assert "/static/" not in str(media_service.absolute_path(media))
    assert client.get(f"/static/{media.stored_name}").status_code == 404
    # private file: owner/admin only
    assert client.get(f"/media/files/{media.id}").status_code == 200
    assert client.get(f"/media/public/{media.id}").status_code == 404
    logout(client)
    assert client.get(f"/media/files/{media.id}").status_code in (302, 401, 403)
    response = client.get(f"/media/files/{media.id}")
    assert response.status_code != 200


# ---- XSS ------------------------------------------------------------------
def test_user_content_is_sanitised(client, student, instructor):  # type: ignore[no-untyped-def]
    login(client, student)
    # profile fields are escaped by Jinja autoescape
    post(
        client,
        "/profile/",
        {
            "first_name": "<b>Nino</b>",
            "last_name": "Beridze",
            "locale": "ka",
            "theme": "dark",
            "submit": "1",
        },
    )
    html = client.get("/profile/").get_data(as_text=True)
    assert "<b>Nino</b>" not in html and "&lt;b&gt;Nino" in html


def test_no_inline_javascript_on_pages(client, student, admin):  # type: ignore[no-untyped-def]
    course = _demo()
    enroll(student, course)
    lesson = db.session.query(Lesson).first()
    pages = [
        "/",
        "/courses/",
        f"/courses/{course.slug}/",
        "/auth/login",
        "/auth/register",
        "/certificates/verify/EL-2026-NOPE",
    ]
    for url in pages:
        html = client.get(url).get_data(as_text=True).lower()
        assert 'style="' not in html, url
        for marker in ("onclick=", "onload=", "javascript:"):
            assert marker not in html, (url, marker)
        assert "<script>" not in html, url
    login(client, admin)
    for url in (
        "/dashboard/",
        f"/learn/{course.slug}/{lesson.slug}/",
        "/admin/",
        "/admin/users/",
        "/instructor/",
    ):
        html = client.get(url).get_data(as_text=True).lower()
        assert 'style="' not in html and "<script>" not in html, url


# ---- rate limiting --------------------------------------------------------
def test_login_rate_limit(app, upload_dir):  # type: ignore[no-untyped-def]
    limited = create_app(
        "testing",
        overrides={
            "UPLOAD_PATH": upload_dir,
            "RATELIMIT_ENABLED": True,
            "RATELIMIT_AUTH": "3 per minute",
        },
    )
    with limited.app_context():
        db.create_all()
        client = limited.test_client()
        token = client.get("/api/v1/auth/csrf").get_json()["csrf_token"]
        codes = [
            client.post(
                "/auth/login",
                data={"email": "a@example.org", "password": "nope", "csrf_token": token},
            ).status_code
            for _ in range(5)
        ]
        assert 429 in codes
        html = client.post(
            "/auth/login", data={"email": "a@example.org", "password": "nope", "csrf_token": token}
        )
        assert html.status_code == 429 and b"429" in html.data
        db.session.remove()
        db.drop_all()


# ---- certificates ---------------------------------------------------------
def test_certificate_verification_is_public_and_tamper_evident(client, student, admin):  # type: ignore[no-untyped-def]
    course = _demo()
    enroll(student, course)
    for lesson in course.lessons:
        progress_service.complete_lesson(student, course, lesson)
    certificate = certificate_service.issue(student, course)
    public_id = certificate.public_id
    page = client.get(f"/certificates/verify/{public_id}")
    assert page.status_code == 200 and b"valid" in page.data.lower()
    assert student.email.encode() not in page.data  # no personal data beyond the name
    assert client.get("/certificates/verify/EL-2026-DOESNOTX").status_code == 200
    # tampering with the stored hash invalidates it
    certificate.verification_hash = "0" * 64
    db.session.commit()
    assert certificate_service.verify(public_id) is None
    # revoked certificates verify as invalid
    certificate.verification_hash = certificate_service._verification_hash(
        public_id, student.id, course.id
    )
    certificate_service.revoke(certificate, actor=admin, reason="test")
    page = client.get(f"/certificates/verify/{public_id}")
    assert (
        b"revoked" in page.data.lower()
        or b"not valid" in page.data.lower()
        or b"invalid" in page.data.lower()
    )


# ---- headers / logging ----------------------------------------------------
def test_security_headers_on_api_and_html(client):  # type: ignore[no-untyped-def]
    for url in ("/", "/api/v1/courses", "/health"):
        headers = client.get(url).headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Content-Security-Policy"].startswith("default-src 'self'")
        assert "unsafe-inline" not in headers["Content-Security-Policy"]
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_secrets_never_logged(client, caplog, student):  # type: ignore[no-untyped-def]
    with caplog.at_level("DEBUG"):
        token = get_csrf(client)
        client.post(
            "/auth/login",
            data={"email": student.email, "password": "CorrectHorse!Battery9", "csrf_token": token},
        )
        client.post("/auth/reset", data={"email": student.email, "csrf_token": token})
    text = caplog.text
    assert "CorrectHorse!Battery9" not in text
    assert "argon2" not in text
