"""Admin-editable texts for the verification and password-reset emails.

One subject and one message per language, shared by everyone; each recipient
gets the version in the language they chose as their main language
(``user.locale``, set at registration and editable under Profile → Language &
theme).  A field left at its default is stored as "use the built-in wording",
so the defaults keep coming from ``templates/emails/*.txt`` and stay
translated through the normal catalogue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from flask import current_app, render_template, url_for
from flask_babel import force_locale
from flask_babel import lazy_gettext as _l

from app.services import mail_service, settings_service

PLACEHOLDERS = ("name", "link", "site", "email")
_PLACEHOLDER_RE = re.compile(r"\{(name|link|site|email)\}")
SUBJECT_MAX = 200
BODY_MAX = 5000

# kind -> label, explanation, default subject, template that holds the default body
KINDS: dict[str, dict[str, Any]] = {
    "verify": {
        "label": _l("Verification email"),
        "help": _l(
            "Sent after registration when email verification is required, "
            "and from “Resend the verification email” on the login page."
        ),
        "subject": _l("Verify your email"),
        "template": "verify_email",
        "example_endpoint": "auth.verify_email",
    },
    "reset": {
        "label": _l("Password reset email"),
        "help": _l("Sent when someone asks for a password reset link."),
        "subject": _l("Reset your password"),
        "template": "reset_password",
        "example_endpoint": "auth.reset_password",
    },
}


@dataclass(frozen=True)
class EmailText:
    kind: str
    locale: str
    subject: str
    body: str
    custom: bool  # False when both fields come from the built-in wording


def languages() -> list[str]:
    return list(current_app.config["LANGUAGES"])


def user_locale(user: Any) -> str:
    """The language the account chose as its main one, or the site default."""
    locale = getattr(user, "locale", None)
    if locale in current_app.config["LANGUAGES"]:
        return str(locale)
    return str(current_app.config["BABEL_DEFAULT_LOCALE"])


def _key(kind: str, locale: str, part: str) -> str:
    return f"mail.{kind}.{part}.{locale}"


def default_subject(kind: str, locale: str) -> str:
    with force_locale(locale):
        return f"[{{site}}] {KINDS[kind]['subject']}"


def default_body(kind: str, locale: str) -> str:
    placeholder_user = SimpleNamespace(first_name="{name}", email="{email}")
    with force_locale(locale):
        rendered = render_template(
            f"emails/{KINDS[kind]['template']}.txt",
            user=placeholder_user,
            link="{link}",
            site_name="{site}",
        )
    return rendered.strip()


def get(kind: str, locale: str) -> EmailText:
    subject = str(settings_service.get(_key(kind, locale, "subject")) or "").strip()
    body = str(settings_service.get(_key(kind, locale, "body")) or "").strip()
    return EmailText(
        kind=kind,
        locale=locale,
        subject=subject or default_subject(kind, locale),
        body=body or default_body(kind, locale),
        custom=bool(subject or body),
    )


def missing_link(body: str) -> bool:
    return "{link}" not in body


def save(kind: str, locale: str, subject: str, body: str) -> bool:
    """Store the custom wording; text equal to the default means "use the default".

    Returns True when anything custom is stored for this kind and language.
    """
    subject = subject.strip()[:SUBJECT_MAX]
    body = body.replace("\r\n", "\n").strip()[:BODY_MAX]
    if subject == default_subject(kind, locale):
        subject = ""
    if body == default_body(kind, locale):
        body = ""
    for part, value in (("subject", subject), ("body", body)):
        key = _key(kind, locale, part)
        if value:
            settings_service.set_value(key, value, value_type="text", group="mail", label=key)
        else:
            settings_service.delete_value(key)
    return bool(subject or body)


def clear(kind: str, locale: str) -> None:
    for part in ("subject", "body"):
        settings_service.delete_value(_key(kind, locale, part))


def custom_texts() -> list[str]:
    """``kind.locale`` of every text that differs from the built-in wording."""
    return [
        f"{kind}.{locale}" for kind in KINDS for locale in languages() if get(kind, locale).custom
    ]


def _site_title() -> str:
    return str(settings_service.get("site.title", current_app.config.get("SITE_NAME", "eLearning")))


def _fill(text: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], text)


def render(kind: str, user: Any, link: str, locale: str | None = None) -> tuple[str, str]:
    """Subject and body for ``user`` with the placeholders filled in."""
    text = get(kind, locale or user_locale(user))
    values = {
        "name": str(getattr(user, "first_name", "") or user.email),
        "link": link,
        "site": _site_title(),
        "email": str(user.email),
    }
    return _fill(text.subject, values), _fill(text.body, values)


def send(kind: str, user: Any, link: str) -> None:
    """Queue the email in the recipient's own language."""
    subject, body = render(kind, user, link)
    mail_service.queue_message(user.email, subject, body)


def send_preview(kind: str, locale: str, user: Any) -> None:
    """Deliver the current text to ``user`` right away, with an example link."""
    example = "example"
    link = url_for(KINDS[kind]["example_endpoint"], token=example, _external=True)
    subject, body = render(kind, user, link, locale=locale)
    mail_service.deliver_now(user.email, subject, body)
