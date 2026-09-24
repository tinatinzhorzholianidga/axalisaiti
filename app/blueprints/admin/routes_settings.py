"""Admin: site settings, feature flags, localisation, audit log."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import select

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import locale, page, per_page
from app.extensions import db
from app.models import AuditLog
from app.services import audit_service, feature_flags, settings_service
from app.services.rbac import require_permission


@bp.route("/settings/", methods=["GET", "POST"])
@require_permission("settings.manage")
def settings():  # type: ignore[no-untyped-def]
    if request.method == "POST":
        from flask_wtf.csrf import validate_csrf

        validate_csrf(request.form.get("csrf_token"))
        changed = []
        for setting in settings_service.all_settings():
            raw = request.form.get(f"setting-{setting.key}")
            if setting.value_type == "bool":
                value = raw == "on"
                if value != setting.typed_value():
                    settings_service.set_value(setting.key, value)
                    changed.append(setting.key)
            elif raw is not None and raw != setting.value:
                settings_service.set_value(setting.key, raw[:5000])
                changed.append(setting.key)
        if changed:
            audit_service.record("settings.changed", actor=current_user, meta={"keys": changed})
        if current_user.has_permission("flags.manage"):
            _apply_flags(request.form)
        db.session.commit()
        settings_service.invalidate()
        feature_flags.invalidate()
        flash(_("Settings saved."), "success")
        return redirect(url_for("admin.settings"))
    items = settings_service.all_settings()
    groups: dict[str, list] = {}
    for item in items:
        groups.setdefault(item.group, []).append(item)
    return render_template(
        "admin/settings.html",
        groups=groups,
        flags=feature_flags.all_flags(),
        locale=locale(),
    )


def _apply_flags(form) -> None:  # type: ignore[no-untyped-def]
    """Checkbox form for feature flags.

    Only the flags listed in the hidden ``flag-keys`` field are touched (an
    unchecked box means "off"); without that field every flag is in scope, as
    the original flags page worked.
    """
    scope = [k for k in (form.get("flag-keys") or "").split(",") if k]
    for flag in feature_flags.all_flags():
        if scope and flag.key not in scope:
            continue
        enabled = form.get(f"flag-{flag.key}") == "on"
        if enabled != flag.enabled:
            feature_flags.set_flag(flag.key, enabled, updated_by_id=current_user.id)
            audit_service.record(
                "flag.changed", actor=current_user, meta={"key": flag.key, "enabled": enabled}
            )


@bp.route("/flags/", methods=["GET", "POST"])
@require_permission("flags.manage")
def flags():  # type: ignore[no-untyped-def]
    """Flags are edited on the settings page (and the IO page); POST still works."""
    if request.method == "POST":
        from flask_wtf.csrf import validate_csrf

        validate_csrf(request.form.get("csrf_token"))
        _apply_flags(request.form)
        db.session.commit()
        feature_flags.invalidate()
        flash(_("Feature flags saved."), "success")
        return redirect(request.form.get("next") or url_for("admin.settings") + "#flags")
    return redirect(url_for("admin.settings") + "#flags")


@bp.route("/io/")
@require_permission("cyberhero.manage")
def io():  # type: ignore[no-untyped-def]
    """IO, the mascot: where his texts live and what he is allowed to do."""
    from sqlalchemy import func, select

    from app.models import CyberKnowledgeSection, CyberMascotReaction, CyberMascotTip

    counts = {
        "tips": int(
            db.session.execute(select(func.count()).select_from(CyberMascotTip)).scalar_one()
        ),
        "reactions": int(
            db.session.execute(select(func.count()).select_from(CyberMascotReaction)).scalar_one()
        ),
        "knowledge": int(
            db.session.execute(select(func.count()).select_from(CyberKnowledgeSection)).scalar_one()
        ),
    }
    io_flags = [f for f in feature_flags.all_flags() if f.key == "CYBERHERO_IO_CHAT_ENABLED"]
    return render_template("admin/io.html", counts=counts, io_flags=io_flags, locale=locale())


@bp.route("/audit/")
@require_permission("audit.view")
def audit():  # type: ignore[no-untyped-def]
    action = (request.args.get("action") or "").strip()[:64]
    actor = (request.args.get("actor") or "").strip()[:255]
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor}%"))
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    return render_template(
        "admin/audit.html", pagination=pagination, action=action, actor=actor, locale=locale()
    )


@bp.route("/localization/")
@require_permission("settings.manage")
def localization():  # type: ignore[no-untyped-def]
    """Overview of translation coverage: UI catalogue + content translations."""
    from app.services import localization_service

    return render_template(
        "admin/localization.html", stats=localization_service.stats(), locale=locale()
    )
