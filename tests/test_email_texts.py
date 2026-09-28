"""Custom verification / reset email texts, delivered in the recipient's own language."""

from __future__ import annotations

import pytest

from app.extensions import db, mail
from app.models.user import User
from app.services import email_text_service, settings_service
from tests.conftest import post

REGISTER = {
    "first_name": "Nino",
    "last_name": "Beridze",
    "organization": "",
    "password": "CorrectHorse!Battery9",
    "confirm": "CorrectHorse!Battery9",
    "accept_terms": "y",
}


@pytest.fixture
def verification_required(app):  # type: ignore[no-untyped-def]
    settings_service.set_value("auth.email_verification_required", True)
    db.session.commit()


def _register(client, email: str, locale: str):  # type: ignore[no-untyped-def]
    with mail.record_messages() as outbox:
        response = post(client, "/auth/register", {**REGISTER, "email": email, "locale": locale})
    assert response.status_code == 302, response.data[:300]
    assert len(outbox) == 1
    return outbox[0]


def test_defaults_come_from_the_translated_templates(app):  # type: ignore[no-untyped-def]
    with app.test_request_context("/"):
        en = email_text_service.get("verify", "en")
        ka = email_text_service.get("verify", "ka")
    assert not en.custom and not ka.custom
    assert en.subject == "[{site}] Verify your email"
    assert "Hello {name}," in en.body and "{link}" in en.body
    assert ka.subject == "[{site}] დაადასტურეთ ელფოსტა"
    assert "{link}" in ka.body and "Hello" not in ka.body


def test_each_user_gets_the_email_in_their_own_language(client, verification_required):  # type: ignore[no-untyped-def]
    # the request runs in English, the Georgian account still gets Georgian text
    client.get("/?lang=en")  # the browser session is English …
    message = _register(client, "ka-user@example.org", "ka")  # … the account chose Georgian
    assert message.subject.startswith("[eLearning]")
    assert "დაადასტურეთ ელფოსტა" in message.subject
    assert "Hello" not in message.body and "/auth/verify/" in message.body

    message = _register(client, "en-user@example.org", "en")
    assert message.subject == "[eLearning] Verify your email"
    assert message.body.startswith("Hello Nino,") and "/auth/verify/" in message.body


def test_admin_saves_custom_texts_and_users_receive_them(client, logged_in_admin, student):  # type: ignore[no-untyped-def]
    page = client.get("/admin/settings/emails/?lang=en").get_data(as_text=True)
    assert "Email texts" in page and "Verification email" in page and "{link}" in page
    assert "built-in text" in page and "custom text" not in page

    form = {}
    for kind in ("verify", "reset"):
        for code in ("ka", "en"):
            text = email_text_service.get(kind, code)
            form[f"{kind}-{code}-subject"] = text.subject
            form[f"{kind}-{code}-body"] = text.body
    form["reset-ka-subject"] = "პაროლის აღდგენა {site}"
    form["reset-ka-body"] = (
        "გამარჯობა {name}!\r\n\r\nბმული: {link}\r\n\r\nთქვენი მისამართი: {email}"
    )
    form["reset-en-subject"] = "Reset link for {name}"
    form["reset-en-body"] = "Hi {name}, open {link} to choose a new password."
    response = post(client, "/admin/settings/emails/", form, follow_redirects=True)
    page = response.get_data(as_text=True)
    assert "Email texts saved." in page
    assert page.count("custom text") == 2  # reset ka + reset en; verify stays built-in
    # unchanged built-in wording is not stored as a custom value
    assert not email_text_service.get("verify", "ka").custom
    assert email_text_service.get("reset", "ka").custom

    student.locale = "ka"
    db.session.commit()
    with mail.record_messages() as outbox:
        post(client, "/auth/reset", {"email": student.email})
    assert len(outbox) == 1
    assert outbox[0].subject == "პაროლის აღდგენა eLearning"
    assert outbox[0].body.startswith(f"გამარჯობა {student.first_name}!\n\nბმული: http")
    assert "/auth/reset/" in outbox[0].body and outbox[0].body.endswith(student.email)

    student.locale = "en"
    db.session.commit()
    with mail.record_messages() as outbox:
        post(client, "/auth/reset", {"email": student.email})
    assert outbox[0].subject == f"Reset link for {student.first_name}"
    assert outbox[0].body.startswith(f"Hi {student.first_name}, open http")


def test_text_without_the_link_placeholder_is_rejected(client, logged_in_admin):  # type: ignore[no-untyped-def]
    client.get("/?lang=en")
    form = {
        "verify-en-subject": "Confirm please",
        "verify-en-body": "Hello {name}, welcome aboard.",
        "reset-en-subject": "Reset",
        "reset-en-body": "Open {link}",
    }
    page = post(client, "/admin/settings/emails/", form, follow_redirects=True).get_data(
        as_text=True
    )
    assert "must contain the {link} placeholder" in page and "Verification email (English)" in page
    assert not email_text_service.get("verify", "en").custom
    assert email_text_service.get("reset", "en").custom


def test_restore_puts_the_built_in_text_back(client, logged_in_admin):  # type: ignore[no-untyped-def]
    with client.application.test_request_context("/"):
        email_text_service.save("verify", "ka", "სათაური", "ბმული {link}")
        email_text_service.save("verify", "en", "Subject", "Link {link}")
        db.session.commit()
    assert email_text_service.custom_texts() == ["verify.ka", "verify.en"]
    client.get("/?lang=en")
    page = post(
        client, "/admin/settings/emails/", {"restore": "verify"}, follow_redirects=True
    ).get_data(as_text=True)
    assert "built-in text is back" in page
    assert email_text_service.custom_texts() == []


def test_preview_is_sent_to_the_administrator(client, logged_in_admin):  # type: ignore[no-untyped-def]
    form = {
        "reset-en-subject": "Reset for {name}",
        "reset-en-body": "Open {link}",
        "preview": "reset:en",
    }
    client.get("/?lang=en")
    # suppressed sending is reported, not treated as an error
    with mail.record_messages() as outbox:
        page = post(client, "/admin/settings/emails/", form, follow_redirects=True).get_data(
            as_text=True
        )
    assert outbox == [] and "MAIL_SUPPRESS_SEND" in page
    client.application.config["MAIL_SUPPRESS_SEND"] = False
    try:
        with mail.record_messages() as outbox:
            page = post(client, "/admin/settings/emails/", form, follow_redirects=True).get_data(
                as_text=True
            )
    finally:
        client.application.config["MAIL_SUPPRESS_SEND"] = True
    assert "Preview sent to" in page and len(outbox) == 1
    assert outbox[0].recipients == [logged_in_admin.email]
    assert outbox[0].subject == f"Reset for {logged_in_admin.first_name}"
    assert "/auth/reset/example" in outbox[0].body


def test_changing_the_language_in_profile_changes_the_email_language(client, logged_in_student):  # type: ignore[no-untyped-def]
    assert logged_in_student.locale == "ka"
    response = post(
        client,
        "/profile/",
        {
            "first_name": logged_in_student.first_name,
            "last_name": logged_in_student.last_name,
            "display_name": "",
            "organization": "",
            "bio": "",
            "locale": "en",
            "theme": "light",
            "submit": "1",
        },
    )
    assert response.status_code == 302
    assert db.session.get(User, logged_in_student.id).locale == "en"
    with mail.record_messages() as outbox:
        post(client, "/auth/reset?lang=ka", {"email": logged_in_student.email})
    assert len(outbox) == 1 and outbox[0].subject == "[eLearning] Reset your password"


def test_mail_group_is_hidden_from_the_general_settings_page(client, logged_in_admin):  # type: ignore[no-untyped-def]
    with client.application.test_request_context("/"):
        email_text_service.save("reset", "en", "S", "L {link}")
        db.session.commit()
    page = client.get("/admin/settings/?lang=en").get_data(as_text=True)
    assert "mail.reset.subject.en" not in page
    assert "Edit the email texts" in page
