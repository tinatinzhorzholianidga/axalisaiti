"""Forms for case studies, their categories and section titles, and platform resources."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms.authoring import SLUG
from app.forms.base import BaseForm

COLOURS = [("blue", "Blue"), ("purple", "Purple"), ("cyan", "Cyan"), ("green", "Green")]


class CaseCategoryForm(BaseForm):
    slug = StringField(_l("Slug"), validators=[DataRequired(), Length(max=80), SLUG])
    name_ka = StringField(_l("Name (Georgian)"), validators=[DataRequired(), Length(max=120)])
    name_en = StringField(_l("Name (English)"), validators=[DataRequired(), Length(max=120)])
    description_ka = TextAreaField(
        _l("Description (Georgian)"), validators=[Optional(), Length(max=1000)]
    )
    description_en = TextAreaField(
        _l("Description (English)"), validators=[Optional(), Length(max=1000)]
    )
    icon = StringField(
        _l("Icon"), validators=[Optional(), Length(max=40)], default="alert-triangle"
    )
    color = SelectField(_l("Colour"), choices=COLOURS)
    sort_order = IntegerField(_l("Order"), validators=[Optional(), NumberRange(min=0)], default=0)
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save category"))


class SectionTitleForm(BaseForm):
    name_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=120)])
    name_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=120)])
    sort_order = IntegerField(_l("Order"), validators=[Optional(), NumberRange(min=0)], default=0)
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save section title"))


class CaseStudyForm(BaseForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    slug = StringField(_l("Slug"), validators=[Optional(), Length(max=120), SLUG])
    category_id = SelectField(_l("Category"), coerce=int)
    description_ka = TextAreaField(
        _l("Description (Georgian, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    description_en = TextAreaField(
        _l("Description (English, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    about_ka = TextAreaField(
        _l("About (Georgian, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    about_en = TextAreaField(
        _l("About (English, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    cover = FileField(_l("Cover image"))
    sort_order = IntegerField(_l("Order"), validators=[Optional(), NumberRange(min=0)], default=0)
    is_published = BooleanField(_l("Published"))
    submit = SubmitField(_l("Save case study"))


class CaseSectionForm(BaseForm):
    title_id = SelectField(_l("Section title"), coerce=int)
    body_ka = TextAreaField(_l("Text (Georgian, HTML)"), validators=[Optional(), Length(max=50000)])
    body_en = TextAreaField(_l("Text (English, HTML)"), validators=[Optional(), Length(max=50000)])
    submit = SubmitField(_l("Add section"))


class CaseImageForm(BaseForm):
    file = FileField(_l("Image"))
    caption_ka = StringField(_l("Caption (Georgian)"), validators=[Optional(), Length(max=255)])
    caption_en = StringField(_l("Caption (English)"), validators=[Optional(), Length(max=255)])
    submit = SubmitField(_l("Add image"))


class CaseFilterForm(BaseForm):
    class Meta(BaseForm.Meta):
        csrf = False

    q = StringField(_l("Search"), validators=[Optional(), Length(max=100)])
    category = SelectField(_l("Category"), validators=[Optional()], validate_choice=False)
    sort = SelectField(
        _l("Sort"),
        choices=[
            ("newest", _l("Newest first")),
            ("oldest", _l("Oldest first")),
            ("title", _l("Title")),
        ],
        default="newest",
        validate_choice=False,
    )


class PlatformResourceForm(BaseForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    description_ka = TextAreaField(
        _l("Description (Georgian)"), validators=[Optional(), Length(max=2000)]
    )
    description_en = TextAreaField(
        _l("Description (English)"), validators=[Optional(), Length(max=2000)]
    )
    file = FileField(_l("PDF file"))
    is_visible = BooleanField(_l("Shown on the resources page"), default=True)
    sort_order = IntegerField(_l("Order"), validators=[Optional(), NumberRange(min=0)], default=0)
    submit = SubmitField(_l("Save resource"))
