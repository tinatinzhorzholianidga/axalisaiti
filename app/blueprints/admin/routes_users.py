from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale, page, per_page
from app.extensions import db
from app.forms.admin import UserCreateForm, UserEditForm
from app.models import AuditLog, Certificate, Enrollment, User, UserStatus
from app.services import audit_service, user_service
from app.services.auth_service import AuthError
from app.services.rbac import require_permission


@bp.route("/users/")
@require_permission("users.manage")
def users():  # type: ignore[no-untyped-def]
    query = (request.args.get("q") or "").strip()[:100]
    role = request.args.get("role") or None
    status = request.args.get("status") or None
    stmt = user_service.search_users(query, role, status)
    pagination = db.paginate(stmt, page=page(), per_page=per_page(), error_out=False)
    form = UserCreateForm()
    return render_template(
        "admin/users.html",
        pagination=pagination,
        form=form,
        q=query,
        role=role,
        status=status,
        locale=locale(),
    )


@bp.route("/users/new", methods=["POST"])
@require_permission("users.manage")
def user_create():  # type: ignore[no-untyped-def]
    form = UserCreateForm()
    if form.validate_on_submit():
        try:
            user = user_service.create_user(
                email=form.email.data,
                password=form.password.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                roles=form.roles.data,
                actor=current_user,
            )
        except AuthError as exc:
            flash(str(exc), "error")
        else:
            flash(_("User %(email)s created.", email=user.email), "success")
            return redirect(url_for("admin.user_detail", user_id=user.id))
    else:
        flash(
            _(
                "Please check the form: %(errors)s",
                errors="; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()),
            ),
            "error",
        )
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@require_permission("users.manage")
def user_detail(user_id: int):  # type: ignore[no-untyped-def]
    user = get_or_404(User, user_id)
    form = UserEditForm()
    if request.method == "GET":
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.organization.data = user.organization
        form.roles.data = sorted(user.role_names)
        form.is_email_verified.data = user.is_email_verified
    if form.validate_on_submit():
        if user.id == current_user.id and "admin" not in form.roles.data:
            flash(_("You cannot remove your own admin role."), "error")
            return redirect(url_for("admin.user_detail", user_id=user.id))
        if not current_user.has_permission("roles.manage"):
            form.roles.data = sorted(user.role_names)
        user_service.update_profile(
            user,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            organization=form.organization.data,
        )
        user.is_email_verified = bool(form.is_email_verified.data)
        user_service.set_roles(user, form.roles.data, actor=current_user)
        flash(_("User saved."), "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    enrollments = db.session.query(Enrollment).filter_by(user_id=user.id).all()
    certificates = db.session.query(Certificate).filter_by(user_id=user.id).all()
    audit = (
        db.session.query(AuditLog)
        .filter_by(actor_id=user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "admin/user_detail.html",
        user=user,
        form=form,
        enrollments=enrollments,
        certificates=certificates,
        audit=audit,
        locale=locale(),
        UserStatus=UserStatus,
    )


@bp.route("/users/<int:user_id>/<action>", methods=["POST"])
@require_permission("users.manage")
def user_action(user_id: int, action: str):  # type: ignore[no-untyped-def]
    user = get_or_404(User, user_id)
    if user.id == current_user.id:
        flash(_("You cannot change your own account status here."), "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    if action == "suspend":
        user_service.suspend(user, actor=current_user, reason=request.form.get("reason", ""))
        flash(_("User suspended and signed out everywhere."), "info")
    elif action == "reinstate":
        user_service.reinstate(user, actor=current_user)
        flash(_("User reinstated."), "success")
    elif action == "deactivate":
        user_service.deactivate(user, actor=current_user)
        flash(_("User deactivated."), "info")
    elif action == "unlock":
        user.locked_until = None
        user.failed_login_count = 0
        audit_service.record("user.unlocked", target=user, actor=current_user, commit=True)
        flash(_("Account unlocked."), "success")
    else:
        abort(400)
    return redirect(url_for("admin.user_detail", user_id=user.id))
