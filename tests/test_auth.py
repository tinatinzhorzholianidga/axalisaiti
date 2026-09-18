"""Authentication: login, lockout, registration, reset, session invalidation, CSRF."""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.models import AuditLog, AuthToken, User, utcnow
from app.services import auth_service
from tests.conftest import get_csrf, login, post


def test_login_logout_flow(client, student):  # type: ignore[no-untyped-def]
    login(client, student)
    response = client.get("/dashboard/")
    assert response.status_code == 200
    response = post(client, "/auth/logout")
    assert response.status_code == 302
    assert client.get("/dashboard/").status_code == 302


def test_login_rejects_bad_password_generic_message(client, student):  # type: ignore[no-untyped-def]
    response = post(
        client, "/auth/login", {"email": student.email, "password": "wrong-password-123"}
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data
    response = post(
        client, "/auth/login", {"email": "nobody@example.org", "password": "wrong-password-123"}
    )
    assert b"Invalid email or password" in response.data


def test_csrf_required_on_login(client, student):  # type: ignore[no-untyped-def]
    response = client.post(
        "/auth/login", data={"email": student.email, "password": "CorrectHorse!Battery9"}
    )
    assert response.status_code == 400


def test_account_lockout_after_failed_attempts(app, client, student):  # type: ignore[no-untyped-def]
    for _ in range(app.config["LOGIN_MAX_FAILED"]):
        post(client, "/auth/login", {"email": student.email, "password": "wrong-password-123"})
    db.session.refresh(student)
    assert student.is_locked
    response = post(
        client, "/auth/login", {"email": student.email, "password": "CorrectHorse!Battery9"}
    )
    assert b"Too many failed attempts" in response.data
    assert db.session.query(AuditLog).filter_by(action="auth.account_locked").count() == 1
    # lock expires
    student.locked_until = utcnow() - timedelta(minutes=1)
    db.session.commit()
    login(client, student)


def test_registration_creates_student_with_argon2(client, app):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/auth/register",
        {
            "first_name": "ნინო",
            "last_name": "ბერიძე",
            "email": "Nino@Example.org",
            "organization": "",
            "locale": "ka",
            "password": "Strong-Passphrase-2026",
            "confirm": "Strong-Passphrase-2026",
            "accept_terms": "y",
        },
    )
    assert response.status_code == 302
    user = db.session.query(User).filter_by(email="nino@example.org").one()
    assert user.password_hash.startswith("$argon2id$")
    assert user.has_role("student") and not user.is_admin
    assert user.check_password("Strong-Passphrase-2026")


def test_registration_enforces_password_policy(client):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/auth/register",
        {
            "first_name": "A",
            "last_name": "B",
            "email": "weak@example.org",
            "locale": "en",
            "password": "short",
            "confirm": "short",
            "accept_terms": "y",
        },
    )
    assert response.status_code == 200
    assert b"at least 12 characters" in response.data
    assert db.session.query(User).filter_by(email="weak@example.org").count() == 0


def test_duplicate_registration_rejected(client, student):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/auth/register",
        {
            "first_name": "A",
            "last_name": "B",
            "email": student.email,
            "locale": "en",
            "password": "Strong-Passphrase-2026",
            "confirm": "Strong-Passphrase-2026",
            "accept_terms": "y",
        },
    )
    assert b"already exists" in response.data


def test_password_reset_flow_invalidates_sessions(app, client, student):  # type: ignore[no-untyped-def]
    login(client, student)
    other = app.test_client()
    login(other, student)
    version_before = student.security_version

    post(client, "/auth/reset", {"email": student.email})
    token = db.session.query(AuthToken).filter_by(user_id=student.id, purpose="reset").one()
    assert token.used_at is None
    # the raw token is only in the email; simulate by issuing one directly
    raw = auth_service.issue_token(student, "reset")
    response = post(
        other,
        f"/auth/reset/{raw}",
        {"password": "Another-Strong-Pass-1", "confirm": "Another-Strong-Pass-1"},
    )
    assert response.status_code == 302
    db.session.refresh(student)
    assert student.security_version == version_before + 1
    assert student.check_password("Another-Strong-Pass-1")
    # both old sessions are dead
    assert client.get("/dashboard/").status_code == 302
    assert other.get("/dashboard/").status_code == 302
    # token is single-use
    response = post(
        other,
        f"/auth/reset/{raw}",
        {"password": "Third-Strong-Pass-1", "confirm": "Third-Strong-Pass-1"},
    )
    assert response.status_code == 302
    db.session.refresh(student)
    assert student.check_password("Another-Strong-Pass-1")


def test_reset_request_does_not_reveal_accounts(client):  # type: ignore[no-untyped-def]
    response = post(client, "/auth/reset", {"email": "ghost@example.org"}, follow_redirects=True)
    assert b"If an account exists" in response.data


def test_change_password_requires_current(client, logged_in_student):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/auth/password",
        {
            "current_password": "nope-nope-nope",
            "password": "Another-Strong-Pass-1",
            "confirm": "Another-Strong-Pass-1",
        },
    )
    assert b"Current password is incorrect" in response.data
    response = post(
        client,
        "/auth/password",
        {
            "current_password": "CorrectHorse!Battery9",
            "password": "Another-Strong-Pass-1",
            "confirm": "Another-Strong-Pass-1",
        },
    )
    assert response.status_code == 302
    # still logged in on this session after the security version bump
    assert client.get("/dashboard/").status_code == 200


def test_suspended_user_cannot_login(client, student):  # type: ignore[no-untyped-def]
    from app.services import user_service

    user_service.suspend(student)
    response = post(
        client, "/auth/login", {"email": student.email, "password": "CorrectHorse!Battery9"}
    )
    assert b"suspended" in response.data


def test_open_redirect_blocked(client, student):  # type: ignore[no-untyped-def]
    token = get_csrf(client)
    response = client.post(
        "/auth/login?next=https://evil.example.com/",
        data={"email": student.email, "password": "CorrectHorse!Battery9", "csrf_token": token},
    )
    assert response.status_code == 302
    assert "evil.example.com" not in response.headers["Location"]


def test_unverified_user_blocked_when_verification_required(app, client, student):  # type: ignore[no-untyped-def]
    from app.services import settings_service

    settings_service.set_value("auth.email_verification_required", True)
    db.session.commit()
    student.is_email_verified = False
    db.session.commit()
    response = post(
        client, "/auth/login", {"email": student.email, "password": "CorrectHorse!Battery9"}
    )
    assert b"verify your email" in response.data
    raw = auth_service.issue_token(student, "verify")
    client.get(f"/auth/verify/{raw}")
    db.session.refresh(student)
    assert student.is_email_verified
