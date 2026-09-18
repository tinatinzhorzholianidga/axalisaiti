"""Audit trail for security-relevant and administrative actions."""

from __future__ import annotations

import logging
from typing import Any

from flask import g, has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models.audit import AuditLog

log = logging.getLogger("audit")

SENSITIVE_KEYS = {"password", "password_hash", "token", "secret", "authorization", "cookie"}


def _scrub(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    return {k: ("[redacted]" if k.lower() in SENSITIVE_KEYS else v) for k, v in meta.items()}


def client_ip() -> str | None:
    if not has_request_context():
        return None
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.remote_addr or "")[:45] or None


def record(
    action: str,
    *,
    target: Any = None,
    target_type: str | None = None,
    target_id: int | None = None,
    target_label: str | None = None,
    meta: dict[str, Any] | None = None,
    actor: Any = None,
    commit: bool = False,
) -> AuditLog:
    """Append an audit entry. Flushes with the caller's transaction unless ``commit``."""
    if target is not None:
        target_type = target_type or target.__class__.__name__
        target_id = target_id if target_id is not None else getattr(target, "id", None)
        if target_label is None:
            for attr in ("slug", "email", "title_ka", "key", "public_id", "name"):
                value = getattr(target, attr, None)
                if isinstance(value, str) and value:
                    target_label = value
                    break
    if actor is None and has_request_context():
        try:
            actor = current_user if current_user.is_authenticated else None
        except Exception:
            actor = None

    entry = AuditLog(
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=(target_label or "")[:255] or None,
        ip_address=client_ip(),
        request_id=g.get("request_id") if has_request_context() else None,
        user_agent=(request.user_agent.string[:255] if has_request_context() else None),
        meta=_scrub(meta),
    )
    db.session.add(entry)
    log.info(
        "audit action=%s target=%s:%s actor=%s", action, target_type, target_id, entry.actor_email
    )
    if commit:
        db.session.commit()
    return entry
