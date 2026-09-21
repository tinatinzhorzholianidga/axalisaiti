from __future__ import annotations

from flask_babel import lazy_gettext as _l
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional

from app.forms.base import BaseForm


class ProfileForm(BaseForm):
    first_name = StringField(_l("First name"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Last name"), validators=[DataRequired(), Length(max=80)])
    display_name = StringField(
        _l("Display name (optional)"), validators=[Optional(), Length(max=120)]
    )
    organization = StringField(_l("Organisation"), validators=[Optional(), Length(max=160)])
    bio = TextAreaField(_l("About you"), validators=[Optional(), Length(max=1000)])
    locale = SelectField(_l("Language"), choices=[("ka", "ქართული"), ("en", "English")])
    theme = SelectField(
        _l("Theme"),
        choices=[("system", _l("System")), ("dark", _l("Dark")), ("light", _l("Light"))],
    )
    submit = SubmitField(_l("Save changes"))


class NotificationPrefsForm(BaseForm):
    email_assignment_feedback = BooleanField(_l("Email me assignment feedback"), default=True)
    email_quiz_result = BooleanField(_l("Email me quiz results"), default=True)
    email_certificate = BooleanField(_l("Email me when a certificate is issued"), default=True)
    email_announcement = BooleanField(_l("Email me platform announcements"), default=True)
    email_discussion_reply = BooleanField(_l("Email me discussion replies"), default=False)
    submit = SubmitField(_l("Save preferences"))


class DeactivateForm(BaseForm):
    password = PasswordField(_l("Confirm with your password"), validators=[DataRequired()])
    confirm = BooleanField(
        _l("I understand my account will be deactivated"), validators=[DataRequired()]
    )
    submit = SubmitField(_l("Deactivate account"))
