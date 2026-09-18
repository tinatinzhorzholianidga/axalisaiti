"""Feature flags: database rows override environment defaults."""

from __future__ import annotations

from flask import current_app, g

from app.extensions import db
from app.models.settings import FeatureFlag

DEFAULT_FLAGS: dict[str, tuple[str, str]] = {
    # key: (config attribute or literal default, description)
    "CYBERHERO_ENABLED": ("CYBERHERO_ENABLED", "Serve the CyberHero youth/family product"),
    "CYBERHERO_IO_CHAT_ENABLED": (
        "CYBERHERO_IO_CHAT_ENABLED",
        "Experimental in-browser IO tutor (WebLLM)",
    ),
    "COURSE_REVIEWS_ENABLED": ("true", "Learners can review courses"),
    "DISCUSSIONS_ENABLED": ("true", "Course discussions"),
    "REGISTRATIONS_ENABLED": ("REGISTRATION_ENABLED", "Self-service account registration"),
    "ACHIEVEMENTS_ENABLED": ("true", "Award achievements"),
    "BOOKMARKS_ENABLED": ("true", "Bookmarks"),
}


def _env_default(key: str) -> bool:
    source, _ = DEFAULT_FLAGS.get(key, ("false", ""))
    if source in current_app.config:
        return bool(current_app.config[source])
    return str(source).lower() in {"1", "true", "yes", "on"}


def _cache() -> dict[str, bool]:
    if "feature_flags" not in g:
        try:
            g.feature_flags = {f.key: f.enabled for f in db.session.query(FeatureFlag).all()}
        except Exception:
            g.feature_flags = {}
            db.session.rollback()
    return g.feature_flags


def invalidate() -> None:
    g.pop("feature_flags", None)


def is_enabled(key: str) -> bool:
    flags = _cache()
    if key in flags:
        return flags[key]
    return _env_default(key)


def set_flag(key: str, enabled: bool, updated_by_id: int | None = None) -> FeatureFlag:
    flag = db.session.query(FeatureFlag).filter_by(key=key).one_or_none()
    if flag is None:
        flag = FeatureFlag(key=key, description=DEFAULT_FLAGS.get(key, ("", ""))[1])
        db.session.add(flag)
    flag.enabled = bool(enabled)
    flag.updated_by_id = updated_by_id
    invalidate()
    return flag


def seed_defaults() -> int:
    created = 0
    existing = {f.key for f in db.session.query(FeatureFlag.key).all()}
    for key, (_, description) in DEFAULT_FLAGS.items():
        if key in existing:
            continue
        db.session.add(FeatureFlag(key=key, enabled=_env_default(key), description=description))
        created += 1
    db.session.commit()
    invalidate()
    return created


def all_flags() -> list[FeatureFlag]:
    return db.session.query(FeatureFlag).order_by(FeatureFlag.key).all()


def public_flags() -> dict[str, bool]:
    return {key: is_enabled(key) for key in DEFAULT_FLAGS}
