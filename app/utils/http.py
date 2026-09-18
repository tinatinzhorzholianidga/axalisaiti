"""Small HTTP helpers shared by blueprints."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import request, url_for


def is_safe_redirect(target: str | None) -> bool:
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def safe_next(default_endpoint: str = "learning.dashboard") -> str:
    target = request.args.get("next") or request.form.get("next")
    if (
        target
        and is_safe_redirect(target)
        and target.startswith("/")
        and not target.startswith("//")
    ):
        return target
    return url_for(default_endpoint)
