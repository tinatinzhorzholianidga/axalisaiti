"""Shared JSON API helpers: error envelope, auth guard, locale."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import current_app, jsonify, request
from flask_babel import get_locale
from flask_login import current_user


def api_error(code: int, message: str, **extra: Any):  # type: ignore[no-untyped-def]
    payload = {"error": {"code": code, "message": message, **extra}}
    return jsonify(payload), code


def api_locale() -> str:
    requested = request.args.get("locale")
    languages = current_app.config["LANGUAGES"]
    if requested in languages:
        return requested
    return str(get_locale() or current_app.config["BABEL_DEFAULT_LOCALE"])


def login_required_json(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated:
            return api_error(401, "Authentication required")
        return view(*args, **kwargs)

    return wrapped


def permission_required_json(*codes: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                return api_error(401, "Authentication required")
            if not current_user.has_permission(*codes):
                return api_error(403, "Permission denied")
            return view(*args, **kwargs)

        return wrapped

    return decorator


def json_body(max_bytes: int = 256 * 1024) -> dict:
    if request.content_length and request.content_length > max_bytes:
        raise ValueError("Payload too large")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("JSON object expected")
    return data
