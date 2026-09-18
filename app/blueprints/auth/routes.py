"""Authentication routes."""

from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.auth import bp
from app.extensions import limiter
from app.forms.auth import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    RegisterForm,
    ResendVerificationForm,
    ResetPasswordForm,
)
from app.services import auth_service, feature_flags, settings_service
from app.services.auth_service import AuthError
from app.utils.http import safe_next


def _registration_open() -> bool:
    return bool(
        feature_flags.is_enabled("REGISTRATIONS_ENABLED")
        and settings_service.get("auth.registration_enabled", True)
    )


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"], methods=["POST"])
def login():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated:
        return redirect(safe_next())
    form = LoginForm()
    if form.validate_on_submit():
        result = auth_service.authenticate(form.email.data, form.password.data, form.remember.data)
        if result.user:
            flash(_("Welcome back, %(name)s.", name=result.user.first_name), "success")
            return redirect(safe_next())
        flash(result.error or _("Invalid email or password."), "error")
    return render_template("auth/login.html", form=form, registration_open=_registration_open())


@bp.route("/logout", methods=["POST"])
@login_required
def logout():  # type: ignore[no-untyped-def]
    auth_service.logout()
    flash(_("You have been signed out."), "info")
    return redirect(url_for("main.home"))


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_REGISTER"], methods=["POST"])
def register():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated:
        return redirect(url_for("learning.dashboard"))
    if not _registration_open():
        flash(_("Registration is currently closed."), "warning")
        return redirect(url_for("auth.login"))
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user = auth_service.register(
                email=form.email.data,
                password=form.password.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                locale=form.locale.data,
                organization=form.organization.data,
            )
        except AuthError as exc:
            flash(str(exc), "error")
        else:
            verification = settings_service.get(
                "auth.email_verification_required",
                current_app.config.get("EMAIL_VERIFICATION_REQUIRED", False),
            )
            if verification:
                flash(_("Account created. Check your email to verify your address."), "success")
                return redirect(url_for("auth.login"))
            result = auth_service.authenticate(user.email, form.password.data)
            if result.user:
                flash(_("Welcome to %(site)s!", site=settings_service.get("site.title")), "success")
                return redirect(url_for("learning.dashboard"))
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/verify/<token>")
@limiter.limit(lambda: current_app.config["RATELIMIT_RESET"])
def verify_email(token: str):  # type: ignore[no-untyped-def]
    user = auth_service.verify_email(token)
    if user is None:
        flash(_("This verification link is invalid or has expired."), "error")
        return redirect(url_for("auth.resend_verification"))
    flash(_("Your email address is verified. You can sign in now."), "success")
    return redirect(url_for("auth.login"))


@bp.route("/verify", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_RESET"], methods=["POST"])
def resend_verification():  # type: ignore[no-untyped-def]
    form = ResendVerificationForm()
    if form.validate_on_submit():
        user = auth_service.find_by_email(form.email.data)
        if user and not user.is_email_verified:
            auth_service.send_verification_email(user)
        flash(_("If that address needs verification, a new email is on its way."), "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/resend_verification.html", form=form)


@bp.route("/reset", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_RESET"], methods=["POST"])
def forgot_password():  # type: ignore[no-untyped-def]
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        auth_service.request_password_reset(form.email.data)
        flash(_("If an account exists for that email, a reset link has been sent."), "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset/<token>", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_RESET"], methods=["POST"])
def reset_password(token: str):  # type: ignore[no-untyped-def]
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            auth_service.reset_password(token, form.password.data)
        except AuthError as exc:
            flash(str(exc), "error")
            return redirect(url_for("auth.forgot_password"))
        flash(_("Your password has been reset. Please sign in."), "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():  # type: ignore[no-untyped-def]
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            auth_service.change_password(
                current_user._get_current_object(),
                form.current_password.data,
                form.password.data,
            )
        except AuthError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Password changed. Other sessions have been signed out."), "success")
            return redirect(url_for("learning.profile"))
    return render_template("auth/change_password.html", form=form)


@bp.app_context_processor
def _auth_context():  # type: ignore[no-untyped-def]
    return {"registration_open": _registration_open, "request_args": request.args}
