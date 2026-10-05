"""Self-hosted security code on the public auth forms."""

from __future__ import annotations

import re

import pytest

from app.extensions import db
from app.models.user import User
from app.services import captcha_service, settings_service
from tests.conftest import post

REGISTER = {
    "first_name": "Nino",
    "last_name": "Beridze",
    "email": "captcha@example.org",
    "organization": "",
    "locale": "en",
    "password": "CorrectHorse!Battery9",
    "confirm": "CorrectHorse!Battery9",
    "accept_terms": "y",
}


@pytest.fixture
def captcha_on(app):  # type: ignore[no-untyped-def]
    app.config["CAPTCHA_ENABLED"] = True
    yield
    app.config["CAPTCHA_ENABLED"] = False


def _token(page: str) -> str:
    match = re.search(r'name="captcha_token"[^>]*value="([^"]+)"', page)
    assert match, "no captcha token on the page"
    return match.group(1)


def _solved(client, url: str) -> dict:  # type: ignore[no-untyped-def]
    """Token and the correct answer for the code currently shown on ``url``."""
    token = _token(client.get(url).get_data(as_text=True))
    code = captcha_service.code_for(token)
    assert code
    return {"captcha_token": token, "captcha": code.lower()}


def test_forms_have_no_captcha_while_switched_off(client):  # type: ignore[no-untyped-def]
    page = client.get("/auth/register?lang=en").get_data(as_text=True)
    assert "data-captcha" not in page
    assert client.get("/auth/captcha/new").status_code == 404


def test_register_shows_a_code_and_the_picture_is_a_png(client, captcha_on):  # type: ignore[no-untyped-def]
    page = client.get("/auth/register?lang=en").get_data(as_text=True)
    assert "data-captcha" in page and "Security code" in page and "New code" in page
    token = _token(page)
    response = client.get(f"/auth/captcha/{token}.png")
    assert response.status_code == 200 and response.mimetype == "image/png"
    assert response.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/auth/captcha/not-a-token.png").status_code == 404


def test_registration_needs_the_right_code(client, captcha_on):  # type: ignore[no-untyped-def]
    page = client.get("/auth/register?lang=en").get_data(as_text=True)
    token = _token(page)
    response = post(
        client, "/auth/register", {**REGISTER, "captcha_token": token, "captcha": "WRONG"}
    )
    assert response.status_code == 200
    assert "security code is wrong or has expired" in response.get_data(as_text=True)
    assert db.session.query(User).filter_by(email=REGISTER["email"]).one_or_none() is None
    # a wrong answer retires the code: the right answer is no longer accepted for it
    assert captcha_service.code_for(token) is None

    response = post(client, "/auth/register", {**REGISTER, **_solved(client, "/auth/register")})
    assert response.status_code == 302
    assert db.session.query(User).filter_by(email=REGISTER["email"]).one().first_name == "Nino"


def test_a_code_answers_one_submission_only(client, captcha_on):  # type: ignore[no-untyped-def]
    client.get("/?lang=en")
    solved = _solved(client, "/auth/reset")
    assert post(client, "/auth/reset", {"email": "x@example.org", **solved}).status_code == 302
    response = post(client, "/auth/reset", {"email": "x@example.org", **solved})
    assert response.status_code == 200
    assert "security code is wrong or has expired" in response.get_data(as_text=True)


def test_new_code_endpoint_returns_a_fresh_token(client, captcha_on):  # type: ignore[no-untyped-def]
    data = client.get("/auth/captcha/new").get_json()
    assert data["url"].startswith("/auth/captcha/") and data["url"].endswith(".png")
    assert captcha_service.code_for(data["token"])
    assert client.get(data["url"]).status_code == 200


def test_sign_in_asks_for_the_code_after_two_failures(client, captcha_on, student):  # type: ignore[no-untyped-def]
    assert "data-captcha" not in client.get("/auth/login?lang=en").get_data(as_text=True)
    bad = {"email": student.email, "password": "nope-nope-nope"}
    post(client, "/auth/login", bad)
    assert "data-captcha" not in client.get("/auth/login").get_data(as_text=True)
    post(client, "/auth/login", bad)
    page = client.get("/auth/login?lang=en").get_data(as_text=True)
    assert "data-captcha" in page
    # right password, no code: still refused
    good = {"email": student.email, "password": "CorrectHorse!Battery9"}
    response = post(client, "/auth/login", good)
    assert response.status_code == 200
    assert "security code is wrong or has expired" in response.get_data(as_text=True)
    response = post(client, "/auth/login", {**good, **_solved(client, "/auth/login")})
    assert response.status_code == 302
    # the counter resets with a successful sign-in
    client.post("/auth/logout", data={"csrf_token": _csrf(client)})
    assert "data-captcha" not in client.get("/auth/login").get_data(as_text=True)


def _csrf(client) -> str:  # type: ignore[no-untyped-def]
    from tests.conftest import get_csrf

    return get_csrf(client)


def test_admin_setting_switches_the_code_off_and_changes_the_login_threshold(client, captcha_on):  # type: ignore[no-untyped-def]
    settings_service.set_value("auth.captcha_login_after_failures", 0)
    db.session.commit()
    assert "data-captcha" in client.get("/auth/login").get_data(as_text=True)
    settings_service.set_value("auth.captcha_enabled", False)
    db.session.commit()
    assert "data-captcha" not in client.get("/auth/login").get_data(as_text=True)
    assert "data-captcha" not in client.get("/auth/register").get_data(as_text=True)
    assert client.get("/auth/captcha/new").status_code == 404


def test_render_produces_distinct_pictures(app):  # type: ignore[no-untyped-def]
    first, second = captcha_service.render("AB3CD"), captcha_service.render("AB3CD")
    assert first[:8] == b"\x89PNG\r\n\x1a\n" and first != second
