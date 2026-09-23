"""Admin-editable site settings with a per-request cache and env fallbacks."""

from __future__ import annotations

from typing import Any

from flask import current_app, g

from app.extensions import db
from app.models.settings import SiteSetting

# key -> (default, type, group, label, description, public)
DEFAULT_SETTINGS: dict[str, tuple[Any, str, str, str, str, bool]] = {
    "site.title": (
        "eLearning",
        "string",
        "general",
        "Site title",
        "Shown in the navbar and emails",
        True,
    ),
    "site.support_email": (
        "support@elearning.gov.ge",
        "string",
        "general",
        "Support email",
        "",
        True,
    ),
    "site.default_language": ("ka", "string", "general", "Default language", "ka or en", True),
    "site.maintenance_banner": (
        "",
        "text",
        "general",
        "Maintenance banner",
        "Shown at the top of every page when set",
        True,
    ),
    "site.home_featured_limit": (6, "int", "general", "Featured courses on home page", "", True),
    "site.home_basic_course": (
        "basic-cybersecurity",
        "string",
        "general",
        "Home page: basic course",
        "Slug of the course IO's first door leads to; empty or unknown = the catalogue",
        True,
    ),
    "auth.registration_enabled": (True, "bool", "auth", "Allow self-registration", "", True),
    "auth.email_verification_required": (
        False,
        "bool",
        "auth",
        "Require email verification",
        "",
        False,
    ),
    "courses.instructor_approval_required": (
        True,
        "bool",
        "courses",
        "Instructor courses need admin approval",
        "",
        False,
    ),
    "courses.reviews_enabled": (True, "bool", "courses", "Course reviews", "", True),
    "courses.discussions_enabled": (True, "bool", "courses", "Course discussions", "", True),
    "certificates.organization": (
        "Digital Governance Agency of Georgia",
        "string",
        "certificates",
        "Issuing organisation",
        "",
        True,
    ),
    "certificates.signatory": (
        "Head of Cybersecurity Education",
        "string",
        "certificates",
        "Signatory title",
        "",
        True,
    ),
    "cyberhero.featured_tracks": (
        "cyber-guardians,teachers-parents",
        "string",
        "cyberhero",
        "Featured CyberHero tracks",
        "Comma separated slugs",
        True,
    ),
    "cyberhero.emergency_phone": (
        "112",
        "string",
        "cyberhero",
        "Emergency number",
        "Georgia emergency service",
        True,
    ),
    "cyberhero.cybercrime_contact": (
        "",
        "string",
        "cyberhero",
        "Cybercrime unit contact",
        "Only shown when set and verified",
        True,
    ),
    "cyberhero.cybercrime_contact_verified": (
        False,
        "bool",
        "cyberhero",
        "Cybercrime contact verified",
        "",
        False,
    ),
    "cyberhero.help_line": (
        "",
        "string",
        "cyberhero",
        "Child help line",
        "Shown in emergency playbook when set",
        True,
    ),
}


def _cache() -> dict[str, Any]:
    if "site_settings" not in g:
        try:
            g.site_settings = {s.key: s.typed_value() for s in db.session.query(SiteSetting).all()}
        except Exception:
            g.site_settings = {}
            db.session.rollback()
    return g.site_settings


def invalidate() -> None:
    g.pop("site_settings", None)


def get(key: str, default: Any = None) -> Any:
    values = _cache()
    if key in values:
        return values[key]
    if key in DEFAULT_SETTINGS:
        return DEFAULT_SETTINGS[key][0] if default is None else default
    return default


def set_value(key: str, value: Any, *, value_type: str | None = None) -> SiteSetting:
    setting = db.session.query(SiteSetting).filter_by(key=key).one_or_none()
    if setting is None:
        meta = DEFAULT_SETTINGS.get(key)
        setting = SiteSetting(
            key=key,
            value_type=value_type or (meta[1] if meta else "string"),
            group=meta[2] if meta else "general",
            label=meta[3] if meta else key,
            description=meta[4] if meta else "",
            is_public=meta[5] if meta else False,
        )
        db.session.add(setting)
    if setting.value_type == "bool":
        setting.value = "true" if value in (True, "true", "1", "on", "yes") else "false"
    elif setting.value_type == "json":
        import json

        setting.value = json.dumps(value)
    else:
        setting.value = "" if value is None else str(value)
    invalidate()
    return setting


def seed_defaults() -> int:
    created = 0
    existing = {s.key for s in db.session.query(SiteSetting.key).all()}
    for key, (default, vtype, group, label, description, public) in DEFAULT_SETTINGS.items():
        if key in existing:
            continue
        setting = SiteSetting(
            key=key,
            value_type=vtype,
            group=group,
            label=label,
            description=description,
            is_public=public,
        )
        db.session.add(setting)
        if vtype == "bool":
            setting.value = "true" if default else "false"
        else:
            setting.value = str(default)
        created += 1
    db.session.commit()
    invalidate()
    return created


def all_settings() -> list[SiteSetting]:
    return db.session.query(SiteSetting).order_by(SiteSetting.group, SiteSetting.key).all()


def public_settings() -> dict[str, Any]:
    return {s.key: s.typed_value() for s in db.session.query(SiteSetting).filter_by(is_public=True)}


def certificate_org() -> str:
    return str(get("certificates.organization") or current_app.config["CERTIFICATE_ORG_NAME"])
