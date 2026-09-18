"""Shared admin helpers."""

from __future__ import annotations

from flask import abort, current_app, request
from flask_babel import get_locale

from app.extensions import db


def locale() -> str:
    return str(get_locale())


def page() -> int:
    return max(1, request.args.get("page", 1, type=int))


def per_page() -> int:
    return int(current_app.config.get("ADMIN_ITEMS_PER_PAGE", 25))


def get_or_404(model, obj_id: int):  # type: ignore[no-untyped-def]
    obj = db.session.get(model, obj_id)
    if obj is None:
        abort(404)
    return obj


def lines(text: str | None) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]
