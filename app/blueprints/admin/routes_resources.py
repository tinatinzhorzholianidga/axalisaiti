"""Admin: platform resources (PDFs shown on /resources/)."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale
from app.forms.cases import PlatformResourceForm
from app.models import Resource
from app.services import resource_service
from app.services.media_service import UploadError
from app.services.rbac import require_permission


def _fields(form: PlatformResourceForm) -> dict[str, object]:
    return {
        "title_ka": form.title_ka.data or "",
        "title_en": form.title_en.data or "",
        "description_ka": form.description_ka.data or "",
        "description_en": form.description_en.data or "",
        "sort_order": form.sort_order.data or 0,
    }


@bp.route("/resources/", methods=["GET", "POST"])
@require_permission("resources.manage")
def resources():  # type: ignore[no-untyped-def]
    form = PlatformResourceForm()
    if form.validate_on_submit():
        try:
            resource_service.create(
                file=form.file.data,
                actor=current_user,
                is_visible=bool(form.is_visible.data),
                **_fields(form),
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Resource published."), "success")
            return redirect(url_for("admin.resources"))
    return render_template(
        "admin/resources.html", items=resource_service.all_for_admin(), form=form, locale=locale()
    )


@bp.route("/resources/<int:resource_id>", methods=["GET", "POST"])
@require_permission("resources.manage")
def resource_edit(resource_id: int):  # type: ignore[no-untyped-def]
    resource = get_or_404(Resource, resource_id)
    form = PlatformResourceForm()
    if request.method == "GET":
        form.title_ka.data = resource.title_ka
        form.title_en.data = resource.title_en
        form.description_ka.data = resource.description_ka
        form.description_en.data = resource.description_en
        form.sort_order.data = resource.sort_order
        form.is_visible.data = resource.is_visible
    if form.validate_on_submit():
        try:
            resource_service.update(
                resource,
                actor=current_user,
                is_visible=bool(form.is_visible.data),
                file=form.file.data,
                **_fields(form),
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Resource saved."), "success")
            return redirect(url_for("admin.resources"))
    return render_template(
        "admin/resource_form.html", form=form, resource=resource, locale=locale()
    )


@bp.route("/resources/<int:resource_id>/toggle", methods=["POST"])
@require_permission("resources.manage")
def resource_toggle(resource_id: int):  # type: ignore[no-untyped-def]
    resource = get_or_404(Resource, resource_id)
    resource_service.set_visibility(resource, not resource.is_visible, actor=current_user)
    flash(
        _("Resource is now shown.") if resource.is_visible else _("Resource is now hidden."), "info"
    )
    return redirect(url_for("admin.resources"))


@bp.route("/resources/<int:resource_id>/delete", methods=["POST"])
@require_permission("resources.manage")
def resource_delete(resource_id: int):  # type: ignore[no-untyped-def]
    resource = get_or_404(Resource, resource_id)
    resource_service.delete(resource, actor=current_user)
    flash(_("Resource deleted."), "info")
    return redirect(url_for("admin.resources"))
