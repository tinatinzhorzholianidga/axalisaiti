from __future__ import annotations

import logging

from flask import current_app
from flask_mail import Message

from app.celery_app import celery
from app.extensions import mail

log = logging.getLogger(__name__)


@celery.task(name="mail.send", bind=True, max_retries=3, default_retry_delay=30)
def send_mail_task(self, recipients: list[str], subject: str, body: str, html: str | None) -> None:
    to: list[str | tuple[str, str]] = list(recipients)
    msg = Message(subject=subject, recipients=to, body=body, html=html)
    try:
        mail.send(msg)
    except Exception as exc:  # pragma: no cover - network failure path
        log.warning("Mail delivery failed, retrying: %s", exc.__class__.__name__)
        if current_app.config.get("TESTING"):
            raise
        raise self.retry(exc=exc) from exc
