"""Admin forms."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, Regexp

from app.forms.base import BaseForm

SLUG = Regexp(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$", message=_l("Use lowercase letters, digits and hyphens.")
)
TONES = [
    ("blue", "Blue"),
    ("cyan", "Cyan"),
    ("green", "Green"),
    ("pink", "Pink"),
    ("amber", "Amber"),
    ("violet", "Violet"),
    ("orange", "Orange"),
    ("accent", "Accent"),
]


class UserCreateForm(BaseForm):
    email = StringField(_l("Email"), validators=[DataRequired(), Email(), Length(max=255)])
    first_name = StringField(_l("First name"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Last name"), validators=[DataRequired(), Length(max=80)])
    password = PasswordField(
        _l("Temporary password"), validators=[DataRequired(), Length(min=12, max=256)]
    )
    roles = SelectMultipleField(
        _l("Roles"),
        choices=[
            ("student", "student"),
            ("instructor", "instructor"),
            ("moderator", "moderator"),
            ("admin", "admin"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField(_l("Create user"))


class UserEditForm(BaseForm):
    first_name = StringField(_l("First name"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Last name"), validators=[DataRequired(), Length(max=80)])
    organization = StringField(_l("Organisation"), validators=[Optional(), Length(max=160)])
    roles = SelectMultipleField(
        _l("Roles"),
        choices=[
            ("student", "student"),
            ("instructor", "instructor"),
            ("moderator", "moderator"),
            ("admin", "admin"),
        ],
    )
    is_email_verified = BooleanField(_l("Email verified"))
    submit = SubmitField(_l("Save user"))


class BroadcastForm(BaseForm):
    title = StringField(_l("Title"), validators=[DataRequired(), Length(max=200)])
    body = TextAreaField(_l("Message"), validators=[DataRequired(), Length(max=2000)])
    link = StringField(_l("Link (optional)"), validators=[Optional(), Length(max=500)])
    audience = SelectField(
        _l("Audience"),
        choices=[
            ("all", _l("All users")),
            ("students", _l("Students")),
            ("instructors", _l("Instructors")),
        ],
    )
    send_email = BooleanField(_l("Also send by email"))
    submit = SubmitField(_l("Send announcement"))


class RevokeForm(BaseForm):
    reason = StringField(_l("Reason"), validators=[DataRequired(), Length(min=3, max=300)])
    submit = SubmitField(_l("Revoke"))


class IssueCertificateForm(BaseForm):
    user_id = IntegerField(_l("User ID"), validators=[DataRequired()])
    course_id = IntegerField(_l("Course ID"), validators=[DataRequired()])
    submit = SubmitField(_l("Issue certificate"))


class MediaUploadForm(BaseForm):
    file = FileField(_l("File"), validators=[DataRequired()])
    kind = SelectField(
        _l("Kind"),
        choices=[
            ("image", _l("Image")),
            ("document", _l("Document")),
            ("resource", _l("Resource")),
            ("icon", _l("Icon")),
            ("cyberhero", _l("CyberHero illustration")),
        ],
    )
    alt_text = StringField(_l("Alt text"), validators=[Optional(), Length(max=255)])
    is_public = BooleanField(_l("Publicly accessible"))
    submit = SubmitField(_l("Upload"))


class FlagForm(BaseForm):
    enabled = BooleanField(_l("Enabled"))
    submit = SubmitField(_l("Save"))


class NoteForm(BaseForm):
    note = TextAreaField(_l("Note"), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l("Save"))


# ---- CyberHero -------------------------------------------------------------
class TrackForm(BaseForm):
    slug = StringField(_l("Slug"), validators=[DataRequired(), Length(max=80), SLUG])
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=0)
    emoji = StringField(_l("Emoji"), validators=[DataRequired(), Length(max=16)])
    color = SelectField(_l("Colour"), choices=TONES)
    audience = SelectField(
        _l("Audience"),
        choices=[
            ("kids", "kids"),
            ("teens", "teens"),
            ("adults", "adults"),
            ("parents", "parents"),
        ],
    )
    route = StringField(_l("Route (when active)"), validators=[Optional(), Length(max=80)])
    is_active = BooleanField(_l("Active (otherwise 'coming soon')"))
    is_featured = BooleanField(_l("Featured"))
    is_hidden = BooleanField(_l("Hidden (not shown to visitors)"))
    certificate_enabled = BooleanField(_l("Certificate"))
    tag_ka = StringField(_l("Tag (Georgian)"), validators=[Optional(), Length(max=120)])
    tag_en = StringField(_l("Tag (English)"), validators=[Optional(), Length(max=120)])
    name_ka = StringField(_l("Name (Georgian)"), validators=[DataRequired(), Length(max=120)])
    name_en = StringField(_l("Name (English)"), validators=[DataRequired(), Length(max=120)])
    desc_ka = TextAreaField(_l("Description (Georgian)"), validators=[Optional()])
    desc_en = TextAreaField(_l("Description (English)"), validators=[Optional()])
    intro_ka = TextAreaField(_l("Intro (Georgian)"), validators=[Optional()])
    intro_en = TextAreaField(_l("Intro (English)"), validators=[Optional()])
    topics_ka = TextAreaField(_l("Topics (Georgian, one per line)"), validators=[Optional()])
    topics_en = TextAreaField(_l("Topics (English, one per line)"), validators=[Optional()])
    submit = SubmitField(_l("Save track"))


class MissionForm(BaseForm):
    slug = StringField(_l("Slug"), validators=[DataRequired(), Length(max=80), SLUG])
    track_id = SelectField(_l("Track"), coerce=int)
    course_id = SelectField(
        _l("Course"), coerce=int, validators=[Optional()], validate_choice=False
    )
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=1)
    emoji = StringField(_l("Emoji"), validators=[DataRequired(), Length(max=16)])
    color = SelectField(_l("Colour"), choices=TONES)
    article_code = StringField(
        _l("Related article code (a1…c4)"), validators=[Optional(), Length(max=8)]
    )
    topics = StringField(_l("Topics (comma separated)"), validators=[Optional(), Length(max=200)])
    is_priority = BooleanField(_l("Priority"))
    is_sensitive = BooleanField(_l("Sensitive topic (shows the help strip)"))
    is_final = BooleanField(_l("Final exam"))
    is_published = BooleanField(_l("Published"), default=True)
    timer_seconds = IntegerField(
        _l("Timer per question (seconds, exam only)"),
        validators=[Optional(), NumberRange(min=5, max=600)],
    )
    pass_ratio = StringField(
        _l("Pass ratio (e.g. 0.8, exam only)"), validators=[Optional(), Length(max=5)]
    )
    name_ka = StringField(_l("Name (Georgian)"), validators=[DataRequired(), Length(max=160)])
    name_en = StringField(_l("Name (English)"), validators=[DataRequired(), Length(max=160)])
    desc_ka = TextAreaField(_l("Card description (Georgian)"), validators=[DataRequired()])
    desc_en = TextAreaField(_l("Card description (English)"), validators=[DataRequired()])
    brief_ka = TextAreaField(_l("Briefing (Georgian)"), validators=[DataRequired()])
    brief_en = TextAreaField(_l("Briefing (English)"), validators=[DataRequired()])
    help_strip_ka = TextAreaField(_l("Help strip (Georgian)"), validators=[Optional()])
    help_strip_en = TextAreaField(_l("Help strip (English)"), validators=[Optional()])
    theory_ka = TextAreaField(
        _l("Theory bullets (Georgian, one per line)"), validators=[Optional()]
    )
    theory_en = TextAreaField(_l("Theory bullets (English, one per line)"), validators=[Optional()])
    takeaways_ka = TextAreaField(_l("Takeaways (Georgian, one per line)"), validators=[Optional()])
    takeaways_en = TextAreaField(_l("Takeaways (English, one per line)"), validators=[Optional()])
    submit = SubmitField(_l("Save mission"))


class RoundForm(BaseForm):
    round_type = SelectField(
        _l("Type"),
        choices=[
            ("choice", _l("Choice (one correct)")),
            ("flags", _l("Flags (tap every red flag)")),
            ("builder", _l("Builder (reach a target)")),
            ("branch", _l("Branching conversation")),
        ],
    )
    prompt_ka = TextAreaField(_l("Question / prompt (Georgian)"), validators=[Optional()])
    prompt_en = TextAreaField(_l("Question / prompt (English)"), validators=[Optional()])
    explain_ka = TextAreaField(_l("Explanation (Georgian)"), validators=[Optional()])
    explain_en = TextAreaField(_l("Explanation (English)"), validators=[Optional()])
    explain_negative_ka = TextAreaField(
        _l("Explanation when a negative option was picked (Georgian)"), validators=[Optional()]
    )
    explain_negative_en = TextAreaField(
        _l("Explanation when a negative option was picked (English)"), validators=[Optional()]
    )
    card_from_ka = StringField(
        _l("Message card: from (Georgian)"), validators=[Optional(), Length(max=200)]
    )
    card_from_en = StringField(
        _l("Message card: from (English)"), validators=[Optional(), Length(max=200)]
    )
    card_meta_ka = StringField(
        _l("Message card: meta (Georgian)"), validators=[Optional(), Length(max=200)]
    )
    card_meta_en = StringField(
        _l("Message card: meta (English)"), validators=[Optional(), Length(max=200)]
    )
    card_body_ka = TextAreaField(_l("Message card: body (Georgian)"), validators=[Optional()])
    card_body_en = TextAreaField(_l("Message card: body (English)"), validators=[Optional()])
    target = IntegerField(
        _l("Builder target"), validators=[Optional(), NumberRange(min=1, max=1000)]
    )
    meter_low_ka = StringField(
        _l("Meter label low (Georgian)"), validators=[Optional(), Length(max=120)]
    )
    meter_low_en = StringField(
        _l("Meter label low (English)"), validators=[Optional(), Length(max=120)]
    )
    meter_high_ka = StringField(
        _l("Meter label high (Georgian)"), validators=[Optional(), Length(max=120)]
    )
    meter_high_en = StringField(
        _l("Meter label high (English)"), validators=[Optional(), Length(max=120)]
    )
    branch_start_key = StringField(
        _l("Branch start node key"), validators=[Optional(), Length(max=40)]
    )
    branch_max = IntegerField(
        _l("Branch max points"), validators=[Optional(), NumberRange(min=0, max=1000)]
    )
    submit = SubmitField(_l("Save round"))


class BranchNodeForm(BaseForm):
    key = StringField(_l("Node key"), validators=[DataRequired(), Length(max=40)])
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=1)
    is_end = BooleanField(_l("Ending node"))
    scene_ka = TextAreaField(_l("Scene (Georgian)"), validators=[Optional()])
    scene_en = TextAreaField(_l("Scene (English)"), validators=[Optional()])
    submit = SubmitField(_l("Save node"))


class ArticleForm(BaseForm):
    slug = StringField(
        _l("Code / slug (a1 … c4)"), validators=[DataRequired(), Length(max=80), SLUG]
    )
    shelf = SelectField(
        _l("Shelf"),
        choices=[
            ("A", _l("A · Understand the risks")),
            ("B", _l("B · Act")),
            ("C", _l("C · For school")),
        ],
    )
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=1)
    emoji = StringField(_l("Emoji"), validators=[DataRequired(), Length(max=16)])
    color = SelectField(_l("Colour"), choices=TONES)
    minutes = IntegerField(
        _l("Reading minutes"), validators=[NumberRange(min=1, max=60)], default=6
    )
    mission_slug = StringField(_l("Related mission slug"), validators=[Optional(), Length(max=80)])
    is_priority = BooleanField(_l("Priority"))
    is_published = BooleanField(_l("Published"), default=True)
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=300)])
    title_en = StringField(_l("Title (English)"), validators=[DataRequired(), Length(max=300)])
    teaser_ka = TextAreaField(_l("Teaser (Georgian)"), validators=[Optional()])
    teaser_en = TextAreaField(_l("Teaser (English)"), validators=[Optional()])
    lead_ka = TextAreaField(_l("Lead (Georgian)"), validators=[Optional()])
    lead_en = TextAreaField(_l("Lead (English)"), validators=[Optional()])
    sources = TextAreaField(_l("Sources (one per line)"), validators=[Optional()])
    submit = SubmitField(_l("Save article"))


class BlockForm(BaseForm):
    block_type = SelectField(
        _l("Block"),
        choices=[
            ("h2", _l("Heading")),
            ("p", _l("Paragraph")),
            ("list", _l("List")),
            ("callout", _l("Callout")),
        ],
    )
    variant = SelectField(
        _l("Callout variant"),
        choices=[
            ("note", "note"),
            ("script", "script"),
            ("do", "do"),
            ("dont", "dont"),
            ("emergency", "emergency"),
        ],
    )
    ordered = BooleanField(_l("Ordered list"))
    title_ka = StringField(_l("Callout title (Georgian)"), validators=[Optional(), Length(max=300)])
    title_en = StringField(_l("Callout title (English)"), validators=[Optional(), Length(max=300)])
    text_ka = TextAreaField(_l("Text (Georgian)"), validators=[Optional()])
    text_en = TextAreaField(_l("Text (English)"), validators=[Optional()])
    items_ka = TextAreaField(_l("List items (Georgian, one per line)"), validators=[Optional()])
    items_en = TextAreaField(_l("List items (English, one per line)"), validators=[Optional()])
    paragraphs_ka = TextAreaField(
        _l("Callout paragraphs (Georgian, one per line)"), validators=[Optional()]
    )
    paragraphs_en = TextAreaField(
        _l("Callout paragraphs (English, one per line)"), validators=[Optional()]
    )
    submit = SubmitField(_l("Save block"))


class SafetyResourceForm(BaseForm):
    kind = SelectField(
        _l("Kind"),
        choices=[
            ("emergency_contact", _l("Emergency contact")),
            ("playbook", _l("Playbook entry")),
            ("guide", _l("Guide")),
            ("family_agreement", _l("Family agreement")),
        ],
    )
    slug = StringField(_l("Slug"), validators=[DataRequired(), Length(max=100), SLUG])
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=1)
    emoji = StringField(_l("Emoji"), validators=[Optional(), Length(max=16)])
    color = SelectField(_l("Colour"), choices=TONES)
    contact_value = StringField(
        _l("Contact value (phone / URL)"), validators=[Optional(), Length(max=200)]
    )
    is_verified = BooleanField(_l("Verified (contacts are only shown when verified)"))
    is_active = BooleanField(_l("Active"), default=True)
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=300)])
    title_en = StringField(_l("Title (English)"), validators=[DataRequired(), Length(max=300)])
    summary_ka = TextAreaField(_l("Summary (Georgian)"), validators=[Optional()])
    summary_en = TextAreaField(_l("Summary (English)"), validators=[Optional()])
    body_ka = TextAreaField(_l("Body (Georgian, HTML)"), validators=[Optional()])
    body_en = TextAreaField(_l("Body (English, HTML)"), validators=[Optional()])
    steps_ka = TextAreaField(_l("Steps (Georgian, one per line)"), validators=[Optional()])
    steps_en = TextAreaField(_l("Steps (English, one per line)"), validators=[Optional()])
    submit = SubmitField(_l("Save"))


class AgreementSectionForm(BaseForm):
    title_ka = StringField(
        _l("Section title (Georgian)"), validators=[DataRequired(), Length(max=200)]
    )
    title_en = StringField(
        _l("Section title (English)"), validators=[DataRequired(), Length(max=200)]
    )
    write_lines = IntegerField(
        _l("Blank lines to write on"), validators=[NumberRange(min=0, max=10)], default=0
    )
    clauses_ka = TextAreaField(_l("Clauses (Georgian, one per line)"), validators=[Optional()])
    clauses_en = TextAreaField(_l("Clauses (English, one per line)"), validators=[Optional()])
    submit = SubmitField(_l("Save section"))


class TipForm(BaseForm):
    topics = StringField(_l("Topics (comma separated)"), validators=[Optional(), Length(max=200)])
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=1000)], default=0)
    text_ka = TextAreaField(_l("Tip (Georgian)"), validators=[DataRequired(), Length(max=300)])
    text_en = TextAreaField(_l("Tip (English)"), validators=[DataRequired(), Length(max=300)])
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save tip"))


class ReactionForm(BaseForm):
    # choices are filled per request (fixed moments + "track.<slug>" for every
    # track, see cyberhero_service.reaction_keys)
    key = SelectField(_l("Moment"), choices=[])
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=1)
    text_ka = TextAreaField(_l("Text (Georgian)"), validators=[DataRequired(), Length(max=300)])
    text_en = TextAreaField(_l("Text (English)"), validators=[DataRequired(), Length(max=300)])
    submit = SubmitField(_l("Save"))


class KnowledgeSectionForm(BaseForm):
    title_ka = StringField(_l("Section (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Section (English)"), validators=[DataRequired(), Length(max=200)])
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=100)], default=1)
    chunks = TextAreaField(_l("Text chunks (separate with a blank line)"), validators=[Optional()])
    submit = SubmitField(_l("Save section"))
