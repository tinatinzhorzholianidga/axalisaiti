"""Security headers and Content Security Policy.

The whole platform runs without inline scripts, inline styles or CDN assets, so
the policy is strict: ``'self'`` everywhere, ``data:`` and ``blob:`` only for
images (used by generated thumbnails and the CyberHero canvas), and no framing.
"""

from __future__ import annotations

from flask import Flask, Response

CSP_DIRECTIVES: dict[str, str] = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self'",
    "font-src": "'self'",
    "connect-src": "'self'",
    "img-src": "'self' data: blob:",
    "media-src": "'self' blob:",
    "worker-src": "'self' blob:",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
    "frame-ancestors": "'none'",
    "manifest-src": "'self'",
}


def build_csp(directives: dict[str, str] | None = None) -> str:
    merged = {**CSP_DIRECTIVES, **(directives or {})}
    return "; ".join(f"{k} {v}" for k, v in merged.items())


def register_security_headers(app: Flask) -> None:
    csp_value = build_csp()
    csp_header = (
        "Content-Security-Policy-Report-Only"
        if app.config.get("CSP_REPORT_ONLY")
        else ("Content-Security-Policy")
    )
    hsts_enabled = bool(app.config.get("HSTS_ENABLED"))
    hsts_max_age = int(app.config.get("HSTS_MAX_AGE", 31536000))

    @app.after_request
    def _apply_headers(response: Response) -> Response:
        headers = response.headers
        headers.setdefault(csp_header, csp_value)
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Embedder-Policy", "credentialless")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if hsts_enabled:
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={hsts_max_age}; includeSubDomains",
            )
        if response.mimetype == "text/html":
            headers.setdefault("Cache-Control", "no-store")
        return response
