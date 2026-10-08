"""Security headers and Content Security Policy.

The whole platform runs without inline scripts, inline styles or CDN assets, so
the policy is strict: ``'self'`` everywhere, ``data:`` and ``blob:`` only for
images (used by generated thumbnails and the CyberHero canvas), and no framing.
The one exception is Google reCAPTCHA, whose script and iframe origins are
allowed only while its keys are configured (``recaptcha_directives``).
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


def recaptcha_directives(app: Flask) -> dict[str, str]:
    """Open the policy for Google's widget only when reCAPTCHA keys are set.

    The widget is an external script plus an iframe from Google, so those two
    origins join ``script-src`` and ``frame-src``; nothing else changes.
    """
    if not (app.config.get("RECAPTCHA_SITE_KEY") and app.config.get("RECAPTCHA_SECRET_KEY")):
        return {}
    from app.services.recaptcha_service import FRAME_HOSTS, SCRIPT_HOSTS

    return {
        "script-src": f"'self' {SCRIPT_HOSTS}",
        "frame-src": f"'self' {FRAME_HOSTS}",
    }


def register_security_headers(app: Flask) -> None:
    extra = recaptcha_directives(app)
    csp_value = build_csp(extra)
    # COEP would refuse Google's challenge iframe, which does not opt in to it
    embedder_policy = None if extra else "credentialless"
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
        if embedder_policy:
            headers.setdefault("Cross-Origin-Embedder-Policy", embedder_policy)
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if hsts_enabled:
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={hsts_max_age}; includeSubDomains",
            )
        if response.mimetype == "text/html":
            headers.setdefault("Cache-Control", "no-store")
        return response
