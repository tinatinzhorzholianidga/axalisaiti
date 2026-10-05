from __future__ import annotations

from flask import current_app
from flask_babel import lazy_gettext as _l
from wtforms import (
    BooleanField,
    HiddenField,
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


class CaptchaMixin:
    """Security code fields for the public forms.

    ``captcha_required()`` decides whether the picture is shown and checked;
    ``refresh_captcha()`` issues a new code before the form is rendered.
    """

    captcha_token = HiddenField()
    # no Optional(): an empty answer must still reach validate_captcha
    captcha = StringField(_l("Security code"), validators=[Length(max=12)])

    def captcha_required(self) -> bool:
        from app.services import captcha_service

        return captcha_service.enabled()

    def refresh_captcha(self) -> None:
        from app.services import captcha_service

        if self.captcha_required():
            self.captcha_token.data = captcha_service.issue()
            self.captcha.data = ""

    def validate_captcha(self, field) -> None:  # type: ignore[no-untyped-def]
        from app.services import captcha_service

        if not self.captcha_required():
            return
        if not captcha_service.verify(self.captcha_token.data or "", field.data or ""):
            raise ValidationError(
                _l("The security code is wrong or has expired. Type the new one.")
            )


class LoginForm(CaptchaMixin, BaseForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(_l("Password"), validators=[DataRequired(), Length(max=256)])
    remember = BooleanField(_l("Keep me signed in"))
    submit = SubmitField(_l("Sign in"))

    def captcha_required(self) -> bool:
        from app.services import captcha_service

        return captcha_service.login_needs_captcha()


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
