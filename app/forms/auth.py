from __future__ import annotations

from flask import current_app
from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


def _min_password() -> int:
    return int(current_app.config.get("PASSWORD_MIN_LENGTH", 12))


class PasswordPolicy:
    """WTForms validator enforcing the platform password policy."""

    def __call__(self, form: FlaskForm, field) -> None:  # type: ignore[no-untyped-def]
        from app.services.auth_service import validate_password_strength

        problem = validate_password_strength(field.data or "")
        if problem:
            raise ValidationError(problem)


class LoginForm(FlaskForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(_l("Password"), validators=[DataRequired(), Length(max=256)])
    remember = BooleanField(_l("Keep me signed in"))
    submit = SubmitField(_l("Sign in"))


class RegisterForm(FlaskForm):
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


class ForgotPasswordForm(FlaskForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField(_l("Send reset link"))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        _l("New password"), validators=[DataRequired(), Length(max=256), PasswordPolicy()]
    )
    confirm = PasswordField(
        _l("Confirm new password"),
        validators=[DataRequired(), EqualTo("password", message=_l("Passwords must match."))],
    )
    submit = SubmitField(_l("Set new password"))


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(_l("Current password"), validators=[DataRequired()])
    password = PasswordField(
        _l("New password"), validators=[DataRequired(), Length(max=256), PasswordPolicy()]
    )
    confirm = PasswordField(
        _l("Confirm new password"),
        validators=[DataRequired(), EqualTo("password", message=_l("Passwords must match."))],
    )
    submit = SubmitField(_l("Change password"))


class ResendVerificationForm(FlaskForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField(_l("Resend verification email"))
