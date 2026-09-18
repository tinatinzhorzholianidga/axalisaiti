"""Locale selection: explicit choice → user preference → Accept-Language → default."""

from __future__ import annotations

import contextlib

from flask import current_app, request, session
from flask_login import current_user


def select_locale() -> str:
    languages = current_app.config["LANGUAGES"]
    chosen = session.get("locale")
    if chosen in languages:
        return chosen
    with contextlib.suppress(Exception):  # user loader may not be ready in early requests
        if current_user.is_authenticated and current_user.locale in languages:
            return current_user.locale
    best = request.accept_languages.best_match(list(languages.keys()))
    return best or current_app.config["BABEL_DEFAULT_LOCALE"]


def other_locale(locale: str) -> str:
    return "en" if locale == "ka" else "ka"
