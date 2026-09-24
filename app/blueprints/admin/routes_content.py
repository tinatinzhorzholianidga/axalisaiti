"""Admin: quizzes and certificates."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import select

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale, page, per_page
from app.extensions import db
from app.forms.admin import IssueCertificateForm, RevokeForm
from app.models import (
    Certificate,
    Course,
    CyberCertificate,
    Quiz,
    User,
    utcnow,
)
from app.services import (
    audit_service,
    certificate_service,
)
from app.services.rbac import require_permission


@bp.route("/quizzes/")
@require_permission("courses.manage_all")
def quizzes():  # type: ignore[no-untyped-def]
    stmt = select(Quiz).join(Course).order_by(Course.slug, Quiz.is_final.desc())
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    return render_template("admin/quizzes.html", pagination=pagination, locale=locale())


@bp.route("/certificates/", methods=["GET", "POST"])
@require_permission("certificates.manage")
def certificates():  # type: ignore[no-untyped-def]
    form = IssueCertificateForm()
    if form.validate_on_submit():
        user = db.session.get(User, form.user_id.data)
        course = db.session.get(Course, form.course_id.data)
        if user is None or course is None:
            flash(_("User or course not found."), "error")
        elif certificate_service.get_for_user_course(user, course):
            flash(_("This learner already has a certificate for the course."), "warning")
        else:
            certificate_service.issue(user, course, actor=current_user)
            flash(_("Certificate issued."), "success")
        return redirect(url_for("admin.certificates"))
    query = (request.args.get("q") or "").strip()[:60]
    stmt = select(Certificate).order_by(Certificate.issued_at.desc())
    if query:
        stmt = stmt.where(
            Certificate.public_id.ilike(f"%{query}%")
            | Certificate.recipient_name.ilike(f"%{query}%")
        )
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    cyber = list(
        db.session.execute(
            select(CyberCertificate).order_by(CyberCertificate.issued_at.desc()).limit(50)
        ).scalars()
    )
    return render_template(
        "admin/certificates.html",
        pagination=pagination,
        cyber=cyber,
        form=form,
        revoke_form=RevokeForm(),
        q=query,
        locale=locale(),
    )


@bp.route("/certificates/<int:certificate_id>/revoke", methods=["POST"])
@require_permission("certificates.manage")
def certificate_revoke(certificate_id: int):  # type: ignore[no-untyped-def]
    certificate = get_or_404(Certificate, certificate_id)
    form = RevokeForm()
    if form.validate_on_submit():
        certificate_service.revoke(certificate, actor=current_user, reason=form.reason.data)
        flash(_("Certificate revoked."), "info")
    return redirect(url_for("admin.certificates"))


@bp.route("/certificates/cyber/<int:certificate_id>/revoke", methods=["POST"])
@require_permission("certificates.manage")
def cyber_certificate_revoke(certificate_id: int):  # type: ignore[no-untyped-def]
    certificate = get_or_404(CyberCertificate, certificate_id)
    certificate.revoked_at = utcnow()
    audit_service.record(
        "cyberhero.certificate_revoked", target=certificate, actor=current_user, commit=True
    )
    flash(_("Certificate revoked."), "info")
    return redirect(url_for("admin.certificates"))
