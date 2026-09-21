from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf.file import FileField
from wtforms import DecimalField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms.base import BaseForm


class SubmissionForm(BaseForm):
    text_content = TextAreaField(_l("Your answer"), validators=[Optional(), Length(max=20000)])
    file = FileField(_l("File"))
    submit = SubmitField(_l("Submit"))


class GradeForm(BaseForm):
    points = DecimalField(_l("Points"), validators=[DataRequired(), NumberRange(min=0)], places=1)
    feedback = TextAreaField(_l("Feedback"), validators=[Optional(), Length(max=10000)])
    submit = SubmitField(_l("Save grade"))
    return_for_revision = SubmitField(_l("Return for revision"))


class ThreadForm(BaseForm):
    title = StringField(_l("Title"), validators=[DataRequired(), Length(min=3, max=200)])
    body = TextAreaField(_l("Message"), validators=[DataRequired(), Length(min=2, max=20000)])
    submit = SubmitField(_l("Post thread"))


class ReplyForm(BaseForm):
    body = TextAreaField(_l("Reply"), validators=[DataRequired(), Length(min=2, max=20000)])
    submit = SubmitField(_l("Reply"))


class ReportForm(BaseForm):
    reason = StringField(_l("Reason"), validators=[DataRequired(), Length(min=3, max=500)])
    submit = SubmitField(_l("Report"))
