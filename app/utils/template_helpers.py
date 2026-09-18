"""Jinja filters and globals shared by every template."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlencode

from flask import Flask, request
from flask_babel import format_date, format_datetime
from markupsafe import Markup

from app.services.sanitize import sanitize_html


def pct_bucket(value: float | int | None) -> int:
    """Round a percentage to the nearest 5 so it maps to a CSS class (CSP-safe)."""
    if value is None:
        return 0
    value = max(0, min(100, float(value)))
    return int(round(value / 5.0) * 5)


def duration_text(minutes: int | None) -> str:
    if not minutes:
        return ""
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def url_with_args(**updates: object) -> str:
    args = request.args.to_dict(flat=True)
    for key, value in updates.items():
        if value is None or value == "":
            args.pop(key, None)
        else:
            args[key] = str(value)
    query = urlencode(args)
    return f"{request.path}?{query}" if query else request.path


def humanize_dt(value: datetime | None) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return format_datetime(value, "d MMM yyyy, HH:mm")


def date_only(value: datetime | None) -> str:
    if not value:
        return ""
    return format_date(value, "d MMMM yyyy")


def safe_html(value: str | None) -> Markup:
    return Markup(sanitize_html(value or ""))  # noqa: S704 - sanitised by nh3


def register(app: Flask) -> None:
    app.jinja_env.filters["pct_bucket"] = pct_bucket
    app.jinja_env.filters["duration"] = duration_text
    app.jinja_env.filters["humanize_dt"] = humanize_dt
    app.jinja_env.filters["date_only"] = date_only
    app.jinja_env.filters["safe_html"] = safe_html
    app.jinja_env.globals["url_with_args"] = url_with_args
    app.jinja_env.globals["now"] = lambda: datetime.now(UTC)
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
