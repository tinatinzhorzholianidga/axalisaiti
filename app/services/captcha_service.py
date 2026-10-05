"""Self-hosted image CAPTCHA for the public auth forms.

Nothing leaves the server: the code is drawn with Pillow, kept in the cache
under a random id for a few minutes and the browser only ever sees a signed
id.  One code answers one form submission, right or wrong.
"""

from __future__ import annotations

import io
import math
import random
import secrets

from flask import current_app, session
from itsdangerous import BadData, URLSafeTimedSerializer
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.extensions import cache
from app.services import settings_service

# No 0/O, 1/I/L or similar pairs: a code must be readable on the first try.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 5
TTL_SECONDS = 600
WIDTH, HEIGHT = 190, 64
_SALT = "captcha-token"
_SESSION_FAILURES = "login_failures"


def enabled() -> bool:
    """The hard switch in config and the admin setting must both be on."""
    if not current_app.config.get("CAPTCHA_ENABLED", True):
        return False
    return bool(settings_service.get("auth.captcha_enabled", True))


def login_after_failures() -> int:
    """Sign-in asks for a code after this many failed attempts in a browser (0 = always)."""
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


# ---- tokens -----------------------------------------------------------------
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def _key(challenge_id: str) -> str:
    return f"captcha:{challenge_id}"


def issue() -> str:
    """Create a code and return the signed token that identifies it."""
    challenge_id = secrets.token_urlsafe(16)
    code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    cache.set(_key(challenge_id), code, timeout=TTL_SECONDS)
    return _serializer().dumps(challenge_id)


def challenge_id(token: str) -> str | None:
    if not token or len(token) > 200:
        return None
    try:
        value = _serializer().loads(token, max_age=TTL_SECONDS)
    except BadData:
        return None
    return str(value)


def code_for(token: str) -> str | None:
    """The pending code behind a token, or None once used or expired."""
    cid = challenge_id(token)
    if cid is None:
        return None
    code = cache.get(_key(cid))
    return str(code) if code else None


def verify(token: str, answer: str) -> bool:
    """Compare the answer with the code and retire the code either way."""
    cid = challenge_id(token)
    if cid is None:
        return False
    code = cache.get(_key(cid))
    if not code:
        return False
    cache.delete(_key(cid))
    cleaned = "".join(ch for ch in (answer or "").upper() if not ch.isspace())
    return secrets.compare_digest(cleaned, str(code))


# ---- image ------------------------------------------------------------------
_INK = [(44, 62, 120), (27, 94, 100), (120, 40, 80), (50, 50, 60), (10, 85, 130)]


def image(token: str) -> bytes | None:
    code = code_for(token)
    if code is None:
        return None
    return render(code)


def render(code: str) -> bytes:
    rng = random.Random(secrets.randbits(64))  # visual noise only
    img = Image.new("RGB", (WIDTH, HEIGHT), (248, 249, 252))
    draw = ImageDraw.Draw(img)
    for _ in range(6):  # background strokes
        x1, y1 = rng.randint(0, WIDTH), rng.randint(0, HEIGHT)
        x2, y2 = rng.randint(0, WIDTH), rng.randint(0, HEIGHT)
        draw.line((x1, y1, x2, y2), fill=(200, 205, 220), width=rng.randint(1, 2))
    for _ in range(140):  # speckle
        draw.point((rng.randint(0, WIDTH - 1), rng.randint(0, HEIGHT - 1)), fill=(170, 176, 195))

    font = _font(34)
    slot = (WIDTH - 24) / len(code)
    for index, char in enumerate(code):
        glyph = Image.new("RGBA", (56, HEIGHT), (0, 0, 0, 0))
        glyph_draw = ImageDraw.Draw(glyph)
        glyph_draw.text((12, 10), char, font=font, fill=rng.choice(_INK))
        glyph = glyph.rotate(rng.uniform(-25, 25), resample=Image.BICUBIC, expand=False)
        x = int(12 + slot * index + rng.uniform(-4, 4))
        y = int(rng.uniform(-3, 3))
        img.paste(glyph, (x, y), glyph)

    # a wavy stroke across the characters defeats naive segmentation
    amplitude, period, offset = rng.uniform(3, 6), rng.uniform(40, 70), rng.uniform(0, 6)
    points = [
        (x, HEIGHT / 2 + amplitude * math.sin(x / period * math.tau + offset))
        for x in range(0, WIDTH, 3)
    ]
    draw.line(points, fill=rng.choice(_INK), width=2)
    img = img.filter(ImageFilter.SMOOTH)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except (OSError, TypeError):  # Pillow without FreeType: bitmap fallback
        return ImageFont.load_default()
