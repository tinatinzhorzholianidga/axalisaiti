from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.celery_app import celery
from app.extensions import db

log = logging.getLogger(__name__)


@celery.task(name="maintenance.purge_expired_tokens")
def purge_expired_tokens() -> int:
    """Delete stale password-reset / verification tokens (housekeeping)."""
    from app.models.user import AuthToken

    cutoff = datetime.now(UTC) - timedelta(days=2)
    deleted = db.session.query(AuthToken).filter(AuthToken.expires_at < cutoff).delete()
    db.session.commit()
    log.info("Purged %s expired auth tokens", deleted)
    return int(deleted)


@celery.task(name="maintenance.expire_quiz_attempts")
def expire_quiz_attempts() -> int:
    """Close timed quiz attempts whose deadline passed without submission."""
    from app.services.quiz_service import expire_stale_attempts

    return expire_stale_attempts()
