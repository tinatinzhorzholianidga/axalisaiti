"""JSON API v1 (filled in during later phases)."""

from __future__ import annotations

from flask import jsonify
from flask_wtf.csrf import generate_csrf

from app.blueprints.api import bp


@bp.get("/auth/csrf")
def csrf_token():  # type: ignore[no-untyped-def]
    return jsonify({"csrf_token": generate_csrf()})
