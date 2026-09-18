from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale, page
from app.extensions import db
from app.forms.admin import MediaUploadForm
from app.models import MediaFile, MediaKind
from app.services import media_service
from app.services.media_service import UploadError
from app.services.rbac import require_permission


@bp.route("/media/", methods=["GET", "POST"])
@require_permission("media.manage")
def media():  # type: ignore[no-untyped-def]
    form = MediaUploadForm()
    if form.validate_on_submit():
        try:
            media_service.save_upload(
                form.file.data,
                kind=MediaKind(form.kind.data),
                uploader=current_user,
                is_public=bool(form.is_public.data),
                alt_text=form.alt_text.data or "",
            )
            db.session.commit()
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("File uploaded."), "success")
        return redirect(url_for("admin.media"))
    kind = request.args.get("kind") or None
    query = (request.args.get("q") or "").strip()[:100]
    pagination = db.paginate(
        media_service.list_media(kind, query or None), page=page(), per_page=48, error_out=False
    )
    return render_template(
        "admin/media.html",
        pagination=pagination,
        form=form,
        kind=kind,
        q=query,
        locale=locale(),
        kinds=[k.value for k in MediaKind],
    )


@bp.route("/media/<int:media_id>/delete", methods=["POST"])
@require_permission("media.manage")
def media_delete(media_id: int):  # type: ignore[no-untyped-def]
    item = get_or_404(MediaFile, media_id)
    media_service.delete_media(item, actor=current_user)
    flash(_("File deleted."), "info")
    return redirect(url_for("admin.media"))


@bp.route("/media/<int:media_id>/toggle-public", methods=["POST"])
@require_permission("media.manage")
def media_toggle_public(media_id: int):  # type: ignore[no-untyped-def]
    item = get_or_404(MediaFile, media_id)
    item.is_public = not item.is_public
    db.session.commit()
    return redirect(url_for("admin.media"))
