"""Admin: quizzes, assignments, certificates, discussions, reviews, notifications."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import select

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale, page, per_page
from app.extensions import db
from app.forms.admin import BroadcastForm, IssueCertificateForm, RevokeForm
from app.models import (
    Assignment,
    AssignmentSubmission,
    Certificate,
    Course,
    CyberCertificate,
    Discussion,
    DiscussionReport,
    Quiz,
    Review,
    ReviewStatus,
    Role,
    SubmissionStatus,
    User,
    UserStatus,
    utcnow,
)
from app.services import (
    audit_service,
    certificate_service,
    discussion_service,
    notification_service,
    review_service,
)
from app.services.rbac import require_permission


@bp.route("/quizzes/")
@require_permission("courses.manage_all")
def quizzes():  # type: ignore[no-untyped-def]
    stmt = select(Quiz).join(Course).order_by(Course.slug, Quiz.is_final.desc())
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    return render_template("admin/quizzes.html", pagination=pagination, locale=locale())


@bp.route("/assignments/")
@require_permission("courses.manage_all")
def assignments():  # type: ignore[no-untyped-def]
    stmt = select(Assignment).join(Course).order_by(Course.slug)
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    pending = int(
        db.session.query(AssignmentSubmission).filter_by(status=SubmissionStatus.SUBMITTED).count()
    )
    return render_template(
        "admin/assignments.html", pagination=pagination, pending=pending, locale=locale()
    )


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


@bp.route("/discussions/")
@require_permission("discussions.moderate_all")
def discussions():  # type: ignore[no-untyped-def]
    reports = discussion_service.open_reports()
    stmt = select(Discussion).order_by(Discussion.last_post_at.desc().nullslast())
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    return render_template(
        "admin/discussions.html", reports=reports, pagination=pagination, locale=locale()
    )


@bp.route("/discussions/reports/<int:report_id>/<action>", methods=["POST"])
@require_permission("discussions.moderate_all")
def report_action(report_id: int, action: str):  # type: ignore[no-untyped-def]
    report = get_or_404(DiscussionReport, report_id)
    if action == "hide":
        discussion_service.hide_post(report.post, True, current_user)
    elif action != "dismiss":
        abort(400)
    discussion_service.resolve_report(report, current_user)
    flash(_("Report resolved."), "info")
    return redirect(url_for("admin.discussions"))


@bp.route("/reviews/")
@require_permission("reviews.moderate")
def reviews():  # type: ignore[no-untyped-def]
    status = request.args.get("status", "pending")
    stmt = select(Review).order_by(Review.created_at.desc())
    if status in {"pending", "approved", "rejected"}:
        stmt = stmt.where(Review.status == ReviewStatus(status))
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    return render_template(
        "admin/reviews.html", pagination=pagination, status=status, locale=locale()
    )


@bp.route("/reviews/<int:review_id>/<decision>", methods=["POST"])
@require_permission("reviews.moderate")
def review_decide(review_id: int, decision: str):  # type: ignore[no-untyped-def]
    review = get_or_404(Review, review_id)
    if decision not in {"approve", "reject"}:
        abort(400)
    review_service.moderate(
        review,
        ReviewStatus.APPROVED if decision == "approve" else ReviewStatus.REJECTED,
        current_user,
    )
    return redirect(url_for("admin.reviews", status=request.args.get("status", "pending")))


@bp.route("/notifications/", methods=["GET", "POST"])
@require_permission("notifications.broadcast")
def notifications():  # type: ignore[no-untyped-def]
    form = BroadcastForm()
    if form.validate_on_submit():
        stmt = select(User.id).where(User.status == UserStatus.ACTIVE)
        if form.audience.data in {"students", "instructors"}:
            role = "student" if form.audience.data == "students" else "instructor"
            stmt = stmt.join(User.roles).where(Role.name == role)
        user_ids = list(db.session.execute(stmt).scalars())
        link = (form.link.data or "").strip() or None
        if link and not link.startswith("/"):
            link = None
        count = notification_service.broadcast(
            kind="announcement",
            title=form.title.data,
            body=form.body.data,
            link=link,
            user_ids=user_ids,
        )
        if form.send_email.data:
            from app.services import mail_service

            emails = list(
                db.session.execute(select(User.email).where(User.id.in_(user_ids))).scalars()
            )
            for chunk in range(0, len(emails), 50):
                mail_service.send_email(
                    emails[chunk : chunk + 50],
                    form.title.data,
                    "announcement",
                    title=form.title.data,
                    body=form.body.data,
                    link=link,
                )
        audit_service.record(
            "notification.broadcast",
            actor=current_user,
            meta={
                "audience": form.audience.data,
                "recipients": count,
                "email": bool(form.send_email.data),
            },
            commit=True,
        )
        flash(_("Announcement sent to %(n)d users.", n=count), "success")
        return redirect(url_for("admin.notifications"))
    return render_template("admin/notifications.html", form=form, locale=locale())
