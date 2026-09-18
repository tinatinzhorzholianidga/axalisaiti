from __future__ import annotations

from flask import abort, render_template
from flask_babel import get_locale
from flask_login import current_user, login_required

from app.blueprints.certificates import bp
from app.extensions import limiter
from app.services import certificate_service, settings_service


@bp.route("/")
@login_required
def mine():  # type: ignore[no-untyped-def]
    return render_template(
        "certificates/list.html",
        certificates=certificate_service.user_certificates(current_user),
        locale=str(get_locale()),
    )


@bp.route("/<public_id>/")
@login_required
def view(public_id: str):  # type: ignore[no-untyped-def]
    certificate = certificate_service.verify(public_id)
    if certificate is None or (
        certificate.user_id != current_user.id
        and not current_user.has_permission("certificates.manage")
    ):
        abort(404)
    return render_template(
        "certificates/certificate.html",
        certificate=certificate,
        locale=str(get_locale()),
        signatory=settings_service.get("certificates.signatory"),
    )


@bp.route("/verify/<public_id>")
@limiter.limit("60 per minute")
def verify(public_id: str):  # type: ignore[no-untyped-def]
    certificate = certificate_service.verify(public_id)
    cyber = None
    if certificate is None:
        from app.services import cyberhero_service

        cyber = cyberhero_service.verify_certificate(public_id)
    return render_template(
        "certificates/verify.html",
        certificate=certificate,
        cyber=cyber,
        public_id=public_id,
        locale=str(get_locale()),
    )
