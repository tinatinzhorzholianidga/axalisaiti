"""Branded error pages and JSON errors for the API."""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    accept = request.accept_mimetypes
    return accept.best == "application/json" and accept["application/json"] > accept["text/html"]


def register_error_handlers(app: Flask) -> None:
    def render(code: int, error: HTTPException | Exception):
        description = getattr(error, "description", None)
        if _wants_json():
            payload = {"error": {"code": code, "message": _default_message(code, description)}}
            return jsonify(payload), code
        return render_template(f"errors/{code}.html", error=error), code

    @app.errorhandler(400)
    def bad_request(error):  # type: ignore[no-untyped-def]
        return render(400, error)

    @app.errorhandler(403)
    def forbidden(error):  # type: ignore[no-untyped-def]
        return render(403, error)

    @app.errorhandler(404)
    def not_found(error):  # type: ignore[no-untyped-def]
        return render(404, error)

    @app.errorhandler(413)
    def too_large(error):  # type: ignore[no-untyped-def]
        return render(413, error)

    @app.errorhandler(429)
    def too_many(error):  # type: ignore[no-untyped-def]
        return render(429, error)

    @app.errorhandler(500)
    def server_error(error):  # type: ignore[no-untyped-def]
        log.exception("Unhandled server error")
        return render(500, error)

    @app.errorhandler(Exception)
    def unexpected(error):  # type: ignore[no-untyped-def]
        if isinstance(error, HTTPException):
            code = error.code or 500
            if code in {400, 403, 404, 413, 429, 500}:
                return render(code, error)
            if _wants_json():
                return jsonify({"error": {"code": code, "message": error.name}}), code
            return error
        log.exception("Unhandled exception")
        if app.debug or app.testing:
            raise error
        return render(500, error)


def _default_message(code: int, description: str | None) -> str:
    defaults = {
        400: "Bad request",
        403: "Forbidden",
        404: "Not found",
        413: "Payload too large",
        429: "Too many requests",
        500: "Internal server error",
    }
    if code == 500:
        return defaults[500]
    return description or defaults.get(code, "Error")
