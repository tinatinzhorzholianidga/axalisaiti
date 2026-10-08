"""Google reCAPTCHA on the public auth forms (siteverify is patched, never called)."""

from __future__ import annotations

import urllib.error

import pytest

from app import create_app
from app.extensions import db
from app.models.user import User
from app.services import recaptcha_service, settings_service
from tests.conftest import post

REGISTER = {
    "first_name": "Nino",
    "last_name": "Beridze",
    "email": "robot-check@example.org",
    "organization": "",
    "locale": "en",
    "password": "CorrectHorse!Battery9",
    "confirm": "CorrectHorse!Battery9",
    "accept_terms": "y",
}
SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
GOOD = {"g-recaptcha-response": "good-token"}
BAD = {"g-recaptcha-response": "bad-token"}


def fake_siteverify(payload: dict) -> dict:
    assert payload["secret"] == "secret-key"
    if payload["response"] == "good-token":
        return {"success": True, "hostname": "localhost"}
    return {"success": False, "error-codes": ["invalid-input-response"]}


@pytest.fixture
def recaptcha_on(app, monkeypatch):  # type: ignore[no-untyped-def]
    app.config["RECAPTCHA_SITE_KEY"] = SITE_KEY
    app.config["RECAPTCHA_SECRET_KEY"] = "secret-key"
    monkeypatch.setattr(recaptcha_service, "_siteverify", fake_siteverify)
    yield
    app.config["RECAPTCHA_SITE_KEY"] = ""
    app.config["RECAPTCHA_SECRET_KEY"] = ""


def test_no_keys_means_no_widget_and_no_check(client):  # type: ignore[no-untyped-def]
    page = client.get("/auth/register?lang=en").get_data(as_text=True)
    assert "g-recaptcha" not in page and "google.com/recaptcha" not in page
    assert post(client, "/auth/register", REGISTER).status_code == 302
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "google" not in csp and "frame-src" not in csp
    assert client.get("/").headers["Cross-Origin-Embedder-Policy"] == "credentialless"


def test_widget_is_rendered_with_the_site_key_and_locale(client, recaptcha_on):  # type: ignore[no-untyped-def]
    page = client.get("/auth/register?lang=en").get_data(as_text=True)
    assert f'class="g-recaptcha" id="recaptcha" data-sitekey="{SITE_KEY}"' in page
    assert '<script src="https://www.google.com/recaptcha/api.js?hl=en" async defer>' in page
    page = client.get("/auth/reset?lang=ka").get_data(as_text=True)
    assert "api.js?hl=ka" in page and "g-recaptcha" in page
    assert "g-recaptcha" in client.get("/auth/verify").get_data(as_text=True)


def test_csp_opens_only_googles_recaptcha_origins_when_keys_are_set(upload_dir):  # type: ignore[no-untyped-def]
    application = create_app(
        "testing",
        overrides={
            "UPLOAD_PATH": upload_dir,
            "RECAPTCHA_SITE_KEY": SITE_KEY,
            "RECAPTCHA_SECRET_KEY": "secret-key",
        },
    )
    with application.app_context():
        db.create_all()
        try:
            response = application.test_client().get("/auth/login")
        finally:
            db.session.remove()
            db.drop_all()
    csp = response.headers["Content-Security-Policy"]
    assert (
        "script-src 'self' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/"
        in csp
    )
    assert (
        "frame-src 'self' https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/"
        in csp
    )
    assert "style-src 'self'" in csp and "connect-src 'self'" in csp
    assert "Cross-Origin-Embedder-Policy" not in response.headers


def test_registration_needs_a_token_google_accepts(client, recaptcha_on):  # type: ignore[no-untyped-def]
    client.get("/?lang=en")
    response = post(client, "/auth/register", REGISTER)
    assert response.status_code == 200
    assert "Please confirm that you are not a robot." in response.get_data(as_text=True)
    response = post(client, "/auth/register", {**REGISTER, **BAD})
    assert response.status_code == 200
    assert "The security check failed." in response.get_data(as_text=True)
    assert db.session.query(User).filter_by(email=REGISTER["email"]).one_or_none() is None
    assert post(client, "/auth/register", {**REGISTER, **GOOD}).status_code == 302
    assert db.session.query(User).filter_by(email=REGISTER["email"]).one().first_name == "Nino"


def test_check_fails_closed_when_google_is_unreachable(client, recaptcha_on, monkeypatch):  # type: ignore[no-untyped-def]
    def down(payload: dict) -> dict:
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(recaptcha_service, "_siteverify", down)
    client.get("/?lang=en")
    response = post(client, "/auth/reset", {"email": "x@example.org", **GOOD})
    assert response.status_code == 200
    assert "could not be verified right now" in response.get_data(as_text=True)


def test_sign_in_asks_for_the_check_after_two_failures(client, recaptcha_on, student):  # type: ignore[no-untyped-def]
    assert "g-recaptcha" not in client.get("/auth/login?lang=en").get_data(as_text=True)
    bad = {"email": student.email, "password": "nope-nope-nope"}
    post(client, "/auth/login", bad)
    assert "g-recaptcha" not in client.get("/auth/login").get_data(as_text=True)
    post(client, "/auth/login", bad)
    assert "g-recaptcha" in client.get("/auth/login").get_data(as_text=True)
    good = {"email": student.email, "password": "CorrectHorse!Battery9"}
    response = post(client, "/auth/login", good)
    assert response.status_code == 200
    assert "Please confirm that you are not a robot." in response.get_data(as_text=True)
    assert post(client, "/auth/login", {**good, **GOOD}).status_code == 302
    # the counter resets with a successful sign-in
    from tests.conftest import get_csrf

    client.post("/auth/logout", data={"csrf_token": get_csrf(client)})
    assert "g-recaptcha" not in client.get("/auth/login").get_data(as_text=True)


def test_admin_switch_and_threshold(client, recaptcha_on):  # type: ignore[no-untyped-def]
    settings_service.set_value("auth.captcha_login_after_failures", 0)
    db.session.commit()
    assert "g-recaptcha" in client.get("/auth/login").get_data(as_text=True)
    settings_service.set_value("auth.captcha_enabled", False)
    db.session.commit()
    assert "g-recaptcha" not in client.get("/auth/login").get_data(as_text=True)
    assert "g-recaptcha" not in client.get("/auth/register").get_data(as_text=True)
    assert post(client, "/auth/register", REGISTER).status_code == 302


def test_settings_page_reports_the_key_status(client, logged_in_admin, recaptcha_on):  # type: ignore[no-untyped-def]
    page = client.get("/admin/settings/?lang=en").get_data(as_text=True)
    assert "Security check (Google reCAPTCHA)" in page and SITE_KEY in page
    assert ">active<" in page and "after 2 failed attempts" in page
    client.application.config["RECAPTCHA_SECRET_KEY"] = ""
    page = client.get("/admin/settings/?lang=en").get_data(as_text=True)
    assert "keys missing" in page


def test_verify_outcomes(app, monkeypatch):  # type: ignore[no-untyped-def]
    app.config["RECAPTCHA_SECRET_KEY"] = "secret-key"
    monkeypatch.setattr(recaptcha_service, "_siteverify", fake_siteverify)
    try:
        assert recaptcha_service.verify("", "1.2.3.4") == recaptcha_service.Outcome(
            False, "missing"
        )
        assert recaptcha_service.verify("x" * 5000, None).reason == "invalid"
        assert recaptcha_service.verify("bad-token", None).reason == "invalid"
        assert recaptcha_service.verify("good-token", "1.2.3.4").ok
    finally:
        app.config["RECAPTCHA_SECRET_KEY"] = ""
