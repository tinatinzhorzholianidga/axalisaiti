"""Phase 1: health, readiness, security headers, request ids, errors, config guard."""

from __future__ import annotations

import os

import pytest

from app import create_app
from app.config import ProductionConfig
from app.security import build_csp


def test_health(client):  # type: ignore[no-untyped-def]
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readiness_reports_checks_without_infra_details(client):  # type: ignore[no-untyped-def]
    response = client.get("/readiness")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["checks"]["database"] == "ok"
    assert "host" not in str(payload).lower()


def test_security_headers_present(client):  # type: ignore[no-untyped-def]
    response = client.get("/")
    headers = response.headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "frame-ancestors 'none'" in csp
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["Permissions-Policy"]
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "Strict-Transport-Security" not in headers


def test_hsts_when_enabled(upload_dir):  # type: ignore[no-untyped-def]
    app = create_app("testing", overrides={"HSTS_ENABLED": True, "UPLOAD_PATH": upload_dir})
    with app.app_context():
        response = app.test_client().get("/health")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_request_id_generated_and_echoed(client):  # type: ignore[no-untyped-def]
    response = client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"
    # Untrusted values are replaced.
    response = client.get("/health", headers={"X-Request-ID": "<script>bad</script>"})
    assert "<" not in response.headers["X-Request-ID"]


def test_404_branded_html_and_json(client):  # type: ignore[no-untyped-def]
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"404" in response.data
    assert "მოთხოვნის ID" in response.data.decode()  # Georgian is the default locale
    assert b"Request ID" in client.get("/does-not-exist?lang=en").data
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == 404


def test_csp_builder_overrides():  # type: ignore[no-untyped-def]
    csp = build_csp({"img-src": "'self'"})
    assert "img-src 'self';" in csp + ";"
    assert "object-src 'none'" in csp


def test_production_validation_rejects_weak_config(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "changeme")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///x.db")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.delenv("REDIS_URL", raising=False)
    problems = ProductionConfig.validate()
    assert any("SECRET_KEY" in p for p in problems)
    assert any("SQLite" in p for p in problems)
    assert any("SESSION_COOKIE_SECURE" in p for p in problems)
    assert any("REDIS_URL" in p for p in problems)


def test_production_app_refuses_to_start(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="Refusing to start"):
        create_app("production")


def test_production_validation_accepts_good_config(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", os.urandom(24).hex())
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "mysql+pymysql://u:p@db/el")
    monkeypatch.setattr(ProductionConfig, "MAIL_SUPPRESS_SEND", True)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert ProductionConfig.validate() == []


def test_html_responses_not_cached(client):  # type: ignore[no-untyped-def]
    response = client.get("/")
    assert response.headers["Cache-Control"] == "no-store"
