from __future__ import annotations

from flask import current_app
from flask_babel import lazy_gettext as _l
from wtforms import (
    BooleanField,
    Field,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from app.forms.base import BaseForm


def _min_password() -> int:
    return int(current_app.config.get("PASSWORD_MIN_LENGTH", 12))


class PasswordPolicy:
    """WTForms validator enforcing the platform password policy."""

    def __call__(self, form: BaseForm, field) -> None:  # type: ignore[no-untyped-def]
        from app.services.auth_service import validate_password_strength

        problem = validate_password_strength(field.data or "")
        if problem:
            raise ValidationError(problem)


class RecaptchaWidget:
    """The Google widget: its script tag (an external file, allowed by the CSP
    only when keys are configured) and the checkbox container."""

    def __call__(self, field, **kwargs):  # type: ignore[no-untyped-def]
        from flask_babel import get_locale
        from markupsafe import Markup

        from app.services import recaptcha_service

        locale = str(get_locale() or current_app.config["BABEL_DEFAULT_LOCALE"])
        return Markup(
            '<script src="%s" async defer></script>\n'
            '<div class="g-recaptcha" id="%s" data-sitekey="%s" data-theme="light"></div>'
        ) % (recaptcha_service.script_url(locale), field.id, recaptcha_service.site_key())


class RecaptchaField(Field):
    """Carries the widget and the error messages; the token itself arrives as
    ``g-recaptcha-response`` and is checked by ``CaptchaMixin.validate_recaptcha``."""

    widget = RecaptchaWidget()

    def process_formdata(self, valuelist) -> None:  # type: ignore[no-untyped-def]
        self.data = None

    def _value(self) -> str:
        return ""


class CaptchaMixin:
    """Google reCAPTCHA on a public form; ``captcha_required()`` says when."""

    recaptcha = RecaptchaField(_l("Security check"))

    def captcha_required(self) -> bool:
        from app.services import recaptcha_service

        return recaptcha_service.enabled()

    def validate_recaptcha(self, field) -> None:  # type: ignore[no-untyped-def]
        from flask import request

        from app.services import recaptcha_service

        if not self.captcha_required():
            return
        outcome = recaptcha_service.verify(
            request.form.get("g-recaptcha-response"), request.remote_addr
        )
        if outcome.ok:
            return
        if outcome.reason == "missing":
            raise ValidationError(_l("Please confirm that you are not a robot."))
        if outcome.reason == "unavailable":
            raise ValidationError(
                _l("The security check could not be verified right now. Please try again.")
            )
        raise ValidationError(_l("The security check failed. Please try again."))


class LoginForm(CaptchaMixin, BaseForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(_l("Password"), validators=[DataRequired(), Length(max=256)])
    remember = BooleanField(_l("Keep me signed in"))
    submit = SubmitField(_l("Sign in"))

    def captcha_required(self) -> bool:
        from app.services import recaptcha_service

        return recaptcha_service.login_needs_captcha()


class RegisterForm(CaptchaMixin, BaseForm):
    first_name = StringField(_l("First name"), validators=[DataRequired(), Length(min=1, max=80)])
    last_name = StringField(_l("Last name"), validators=[DataRequired(), Length(min=1, max=80)])
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    organization = StringField(_l("Organisation (optional)"), validators=[Length(max=160)])
    locale = SelectField(
        _l("Preferred language"), choices=[("ka", "ქართული"), ("en", "English")], default="ka"
    )
    password = PasswordField(
        _l("Password"), validators=[DataRequired(), Length(max=256), PasswordPolicy()]
    )
    confirm = PasswordField(
        _l("Confirm password"),
        validators=[DataRequired(), EqualTo("password", message=_l("Passwords must match."))],
    )
    accept_terms = BooleanField(
        _l("I accept the terms of use and privacy notice"), validators=[DataRequired()]
    )
    submit = SubmitField(_l("Create account"))


class ForgotPasswordForm(CaptchaMixin, BaseForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField(_l("Send reset link"))


class ResetPasswordForm(BaseForm):
    password = PasswordField(
        _l("New password"), validators=[DataRequired(), Length(max=256), PasswordPolicy()]
    )
    confirm = PasswordField(
        _l("Confirm new password"),
        validators=[DataRequired(), EqualTo("password", message=_l("Passwords must match."))],
    )
    submit = SubmitField(_l("Set new password"))


class ChangePasswordForm(BaseForm):
    current_password = PasswordField(_l("Current password"), validators=[DataRequired()])
    password = PasswordField(
        _l("New password"), validators=[DataRequired(), Length(max=256), PasswordPolicy()]
    )
    confirm = PasswordField(
        _l("Confirm new password"),
        validators=[DataRequired(), EqualTo("password", message=_l("Passwords must match."))],
    )
    submit = SubmitField(_l("Change password"))


class ResendVerificationForm(CaptchaMixin, BaseForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField(_l("Resend verification email"))
