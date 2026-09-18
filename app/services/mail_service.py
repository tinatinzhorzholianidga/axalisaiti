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
