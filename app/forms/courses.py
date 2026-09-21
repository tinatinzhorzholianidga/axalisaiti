from __future__ import annotations

from flask_babel import lazy_gettext as _l
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms.base import BaseForm


class ReviewForm(BaseForm):
    rating = SelectField(
        _l("Rating"),
        choices=[(5, "5"), (4, "4"), (3, "3"), (2, "2"), (1, "1")],
        coerce=int,
        validators=[DataRequired()],
    )
    body = TextAreaField(_l("Your review"), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l("Submit review"))


class CatalogFilterForm(BaseForm):
    class Meta(BaseForm.Meta):
        csrf = False

    q = StringField(_l("Search"), validators=[Optional(), Length(max=100)])
    category = SelectField(_l("Category"), validators=[Optional()], validate_choice=False)
    difficulty = SelectField(
        _l("Difficulty"),
        choices=[
            ("", _l("Any")),
            ("beginner", _l("Beginner")),
            ("intermediate", _l("Intermediate")),
            ("advanced", _l("Advanced")),
        ],
        validators=[Optional()],
    )
    duration = SelectField(
        _l("Duration"),
        choices=[
            ("", _l("Any")),
            ("short", _l("Under 2 hours")),
            ("medium", _l("2–6 hours")),
            ("long", _l("Over 6 hours")),
        ],
        validators=[Optional()],
    )
    sort = SelectField(
        _l("Sort"),
        choices=[
            ("newest", _l("Newest")),
            ("popular", _l("Most popular")),
            ("rating", _l("Top rated")),
            ("title", _l("Title")),
            ("duration", _l("Shortest first")),
        ],
        validators=[Optional()],
    )
    page = IntegerField(validators=[Optional(), NumberRange(min=1, max=10000)])
