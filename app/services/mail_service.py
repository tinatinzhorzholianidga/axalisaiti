"""Mail abstraction: renders templates and hands delivery to Celery."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator

from flask import current_app, render_template
from flask_babel import force_locale

log = logging.getLogger(__name__)


def _site_name() -> str:
    from app.services import settings_service

    return str(settings_service.get("site.title", current_app.config.get("SITE_NAME", "eLearning")))


@contextlib.contextmanager
def _in_locale(locale: str | None) -> Iterator[None]:
    """Render in the recipient's language when one is given, else the request's."""
    if locale and locale in current_app.config["LANGUAGES"]:
        with force_locale(locale):
            yield
    else:
        yield


def queue_message(
    recipients: list[str] | str,
    subject: str,
    body: str,
    html: str | None = None,
    *,
    async_send: bool = True,
) -> None:
    """Hand a finished message to the mail worker (or send inline when eager)."""
    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        return
    from app.tasks.mail_tasks import send_mail_task

    if async_send and not current_app.config["CELERY"].get("task_always_eager"):
        send_mail_task.delay(recipients, subject, body, html)
    else:
        send_mail_task.apply(args=(recipients, subject, body, html))
    log.info("Queued email '%s' to %s recipient(s)", subject, len(recipients))


def send_email(
    recipients: list[str] | str,
    subject: str,
    template: str,
    *,
    async_send: bool = True,
    locale: str | None = None,
    **context: object,
) -> None:
    """Render ``emails/<template>.txt`` (+ optional ``.html``) and queue delivery.

    ``locale`` picks the language of the rendered text (normally the
    recipient's ``user.locale``); without it the current request's language
    is used.  A lazy-translated ``subject`` is resolved in the same language.
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        return
    site_name = _site_name()
    with _in_locale(locale):
        subject = str(subject)
        body = render_template(f"emails/{template}.txt", site_name=site_name, **context)
        html: str | None
        try:
            html = render_template(f"emails/{template}.html", site_name=site_name, **context)
        except Exception:
            html = None
    queue_message(recipients, f"[{site_name}] {subject}", body, html, async_send=async_send)


def deliver_now(recipient: str, subject: str, body: str) -> None:
    """Send one finished message synchronously, letting SMTP errors surface."""
    from flask_mail import Message

    from app.extensions import mail

    mail.send(Message(subject=subject, recipients=[recipient], body=body))
    log.info("Sent email '%s' synchronously", subject)


def send_now(recipient: str, subject: str, template: str, **context: object) -> None:
    """Render and deliver one message synchronously.

    Used by the admin "send test email" button and the CLI so a wrong host,
    port or password is reported immediately instead of retried in the worker.
    """
    site_name = _site_name()
    body = render_template(f"emails/{template}.txt", site_name=site_name, **context)
    deliver_now(recipient, f"[{site_name}] {subject}", body)


def status() -> dict[str, object]:
    """What the running configuration would do with an outgoing message."""
    cfg = current_app.config
    return {
        "server": cfg.get("MAIL_SERVER") or "",
        "port": cfg.get("MAIL_PORT"),
        "tls": bool(cfg.get("MAIL_USE_TLS")),
        "ssl": bool(cfg.get("MAIL_USE_SSL")),
        "username": cfg.get("MAIL_USERNAME") or "",
        "sender": cfg.get("MAIL_DEFAULT_SENDER") or "",
        "suppressed": bool(cfg.get("MAIL_SUPPRESS_SEND")),
        "configured": bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_SERVER") != "localhost"),
    }
