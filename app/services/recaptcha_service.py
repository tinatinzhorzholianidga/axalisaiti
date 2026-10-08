"""Google reCAPTCHA v2 ("I'm not a robot") on the public auth forms.

The checkbox widget and its challenge come from Google; the token it produces
is checked here against Google's siteverify endpoint.  Both keys live in
``.env`` (``RECAPTCHA_SITE_KEY`` / ``RECAPTCHA_SECRET_KEY``).  Without them the
forms show no widget and nothing is checked, which the admin settings page
reports.  The admin setting ``auth.captcha_enabled`` switches the check off at
runtime; ``auth.captcha_login_after_failures`` decides when sign-in asks for it.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from flask import current_app, session

from app.services import settings_service

log = logging.getLogger(__name__)

SITEVERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
SCRIPT_URL = "https://www.google.com/recaptcha/api.js"
# Hosts the browser must be allowed to reach for the widget (see app/security.py).
SCRIPT_HOSTS = "https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/"
FRAME_HOSTS = "https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/"
TIMEOUT_SECONDS = 6
TOKEN_MAX_LENGTH = 4000
_SESSION_FAILURES = "login_failures"


def site_key() -> str:
    return str(current_app.config.get("RECAPTCHA_SITE_KEY") or "").strip()


def secret_key() -> str:
    return str(current_app.config.get("RECAPTCHA_SECRET_KEY") or "").strip()


def configured() -> bool:
    return bool(site_key() and secret_key())


def enabled() -> bool:
    """Keys present and the admin switch on."""
    return configured() and bool(settings_service.get("auth.captcha_enabled", True))


def login_after_failures() -> int:
    """Sign-in asks for the check after this many failed attempts in a browser (0 = always)."""
    try:
        return max(0, int(settings_service.get("auth.captcha_login_after_failures", 2)))
    except (TypeError, ValueError):
        return 2


def login_needs_captcha() -> bool:
    return enabled() and int(session.get(_SESSION_FAILURES, 0)) >= login_after_failures()


def note_login_failure() -> None:
    session[_SESSION_FAILURES] = int(session.get(_SESSION_FAILURES, 0)) + 1


def clear_login_failures() -> None:
    session.pop(_SESSION_FAILURES, None)


def script_url(locale: str) -> str:
    return f"{SCRIPT_URL}?{urllib.parse.urlencode({'hl': locale})}"


def status() -> dict[str, object]:
    return {
        "configured": configured(),
        "site_key": site_key(),
        "enabled": enabled(),
        "login_after_failures": login_after_failures(),
    }


@dataclass(frozen=True)
class Outcome:
    ok: bool
    reason: str = ""  # "missing" | "invalid" | "unavailable"


def verify(token: str | None, remote_ip: str | None) -> Outcome:
    """Check one widget token with Google. Fails closed when Google cannot be reached."""
    token = (token or "").strip()
    if not token:
        return Outcome(False, "missing")
    if len(token) > TOKEN_MAX_LENGTH:
        return Outcome(False, "invalid")
    payload = {"secret": secret_key(), "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        data = _siteverify(payload)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        log.warning("reCAPTCHA siteverify unavailable: %s", exc.__class__.__name__)
        return Outcome(False, "unavailable")
    if data.get("success") is True:
        return Outcome(True)
    log.info("reCAPTCHA rejected a token: %s", ", ".join(data.get("error-codes") or ["?"]))
    return Outcome(False, "invalid")


def _siteverify(payload: dict[str, str]) -> dict:
    """POST to Google's siteverify endpoint (patched in tests)."""
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(SITEVERIFY_URL, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))
