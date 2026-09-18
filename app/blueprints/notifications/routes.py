from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.notifications import bp
from app.services import notification_service


@bp.route("/")
@login_required
def inbox():  # type: ignore[no-untyped-def]
    page = max(1, request.args.get("page", 1, type=int))
    pagination = notification_service.paginate(current_user, page)
    return render_template("notifications/inbox.html", pagination=pagination)


@bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id: int):  # type: ignore[no-untyped-def]
    notification_service.mark_read(current_user, notification_id)
    target = request.form.get("next")
    if target and target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect(url_for("notifications.inbox"))


@bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():  # type: ignore[no-untyped-def]
    count = notification_service.mark_all_read(current_user)
    flash(_("%(n)d notifications marked as read.", n=count), "info")
    return redirect(url_for("notifications.inbox"))
