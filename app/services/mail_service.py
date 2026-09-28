"""Mail abstraction: renders templates and hands delivery to Celery."""

from __future__ import annotations

import logging

from flask import current_app, render_template

log = logging.getLogger(__name__)


def send_email(
    recipients: list[str] | str,
    subject: str,
    template: str,
    *,
    async_send: bool = True,
    **context: object,
) -> None:
    """Render ``emails/<template>.txt`` (+ optional ``.html``) and queue delivery."""
    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        return
    site_name = current_app.config.get("SITE_NAME", "eLearning")
    body = render_template(f"emails/{template}.txt", site_name=site_name, **context)
    html: str | None
    try:
        html = render_template(f"emails/{template}.html", site_name=site_name, **context)
    except Exception:
        html = None
    full_subject = f"[{site_name}] {subject}"

    from app.tasks.mail_tasks import send_mail_task

    if async_send and not current_app.config["CELERY"].get("task_always_eager"):
        send_mail_task.delay(recipients, full_subject, body, html)
    else:
        send_mail_task.apply(args=(recipients, full_subject, body, html))
    log.info("Queued email '%s' to %s recipient(s)", subject, len(recipients))


def send_now(recipient: str, subject: str, template: str, **context: object) -> None:
    """Render and deliver one message synchronously, letting SMTP errors surface.

    Used by the admin "send test email" button and the CLI so a wrong host,
    port or password is reported immediately instead of retried in the worker.
    """
    from flask_mail import Message

    from app.extensions import mail

    site_name = current_app.config.get("SITE_NAME", "eLearning")
    body = render_template(f"emails/{template}.txt", site_name=site_name, **context)
    mail.send(Message(subject=f"[{site_name}] {subject}", recipients=[recipient], body=body))
    log.info("Sent email '%s' synchronously", subject)


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
