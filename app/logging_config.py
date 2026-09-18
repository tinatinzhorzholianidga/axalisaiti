"""Request-ID aware logging.

Every request gets ``g.request_id`` (taken from a trusted ``X-Request-ID``
header when nginx sets one, otherwise generated). The id is attached to every
log record and echoed back in the response so a user-reported request can be
found in the logs.
"""

from __future__ import annotations

import logging
import sys
import uuid

from flask import Flask, g, has_request_context, request

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = g.get("request_id", "-") if has_request_context() else "-"
        return True


def _sanitize_request_id(value: str | None) -> str | None:
    if not value or len(value) > 64 or any(ch not in _SAFE_ID_CHARS for ch in value):
        return None
    return value


def configure_logging(app: Flask) -> None:
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("werkzeug", "sqlalchemy.engine", "celery"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    @app.before_request
    def _assign_request_id() -> None:
        incoming = _sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
        g.request_id = incoming or uuid.uuid4().hex

    @app.after_request
    def _echo_request_id(response):  # type: ignore[no-untyped-def]
        response.headers[REQUEST_ID_HEADER] = g.get("request_id", "-")
        return response
