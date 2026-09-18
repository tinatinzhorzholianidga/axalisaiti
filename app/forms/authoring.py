"""Forms for course authoring (instructor + admin)."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    DecimalField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp

SLUG = Regexp(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$", message=_l("Use lowercase letters, digits and hyphens.")
)


class CourseForm(FlaskForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    slug = StringField(_l("Slug"), validators=[Optional(), Length(max=120), SLUG])
    platform = SelectField(
        _l("Platform"),
        choices=[("elearning", "eLearning"), ("cyberhero", "CyberHero"), ("both", _l("Both"))],
    )
    categories = SelectMultipleField(_l("Categories"), coerce=int, validators=[Optional()])
    short_description_ka = TextAreaField(
        _l("Short description (Georgian)"), validators=[Optional(), Length(max=400)]
    )
    short_description_en = TextAreaField(
        _l("Short description (English)"), validators=[Optional(), Length(max=400)]
    )
    description_ka = TextAreaField(
        _l("Description (Georgian, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    description_en = TextAreaField(
        _l("Description (English, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    objectives_ka = TextAreaField(
        _l("Learning objectives (Georgian, one per line)"), validators=[Optional()]
    )
    objectives_en = TextAreaField(
        _l("Learning objectives (English, one per line)"), validators=[Optional()]
    )
    prerequisites_ka = TextAreaField(
        _l("Prerequisites (Georgian, one per line)"), validators=[Optional()]
    )
    prerequisites_en = TextAreaField(
        _l("Prerequisites (English, one per line)"), validators=[Optional()]
    )
    audience_ka = TextAreaField(
        _l("Who this course is for (Georgian)"), validators=[Optional(), Length(max=2000)]
    )
    audience_en = TextAreaField(
        _l("Who this course is for (English)"), validators=[Optional(), Length(max=2000)]
    )
    certificate_requirements_ka = TextAreaField(
        _l("Certificate requirements (Georgian)"), validators=[Optional(), Length(max=2000)]
    )
    certificate_requirements_en = TextAreaField(
        _l("Certificate requirements (English)"), validators=[Optional(), Length(max=2000)]
    )
    icon = SelectField(
        _l("Icon"),
        choices=[
            (i, i)
            for i in (
                "shield",
                "lock",
                "globe",
                "network",
                "activity",
                "cloud",
                "code",
                "book",
                "search",
                "terminal",
                "target",
                "layers",
            )
        ],
    )
    color = SelectField(
        _l("Colour"),
        choices=[("blue", "Blue"), ("purple", "Purple"), ("cyan", "Cyan"), ("green", "Green")],
    )
    cover = FileField(_l("Cover image"))
    difficulty = SelectField(
        _l("Difficulty"),
        choices=[
            ("beginner", _l("Beginner")),
            ("intermediate", _l("Intermediate")),
            ("advanced", _l("Advanced")),
        ],
    )
    estimated_minutes = IntegerField(
        _l("Estimated duration (minutes)"),
        validators=[Optional(), NumberRange(min=0, max=100000)],
        default=60,
    )
    age_min = IntegerField(_l("Minimum age"), validators=[Optional(), NumberRange(min=0, max=120)])
    age_max = IntegerField(_l("Maximum age"), validators=[Optional(), NumberRange(min=0, max=120)])
    instructor_id = SelectField(
        _l("Instructor"), coerce=int, validators=[Optional()], validate_choice=False
    )
    tags = StringField(_l("Tags (comma separated)"), validators=[Optional(), Length(max=255)])
    is_featured = BooleanField(_l("Featured on the home page"))
    is_free = BooleanField(_l("Free access"), default=True)
    certificate_enabled = BooleanField(_l("Certificate on completion"), default=True)
    certificate_pass_percent = IntegerField(
        _l("Certificate pass mark (%)"), validators=[NumberRange(min=0, max=100)], default=70
    )
    enrollment_mode = SelectField(
        _l("Enrolment"),
        choices=[
            ("open", _l("Open")),
            ("approval", _l("Requires approval")),
            ("invite", _l("Invitation only")),
        ],
    )
    discussions_enabled = BooleanField(_l("Discussions"), default=True)
    reviews_enabled = BooleanField(_l("Reviews"), default=True)
    starts_at = DateTimeLocalField(_l("Starts"), validators=[Optional()], format="%Y-%m-%dT%H:%M")
    ends_at = DateTimeLocalField(_l("Ends"), validators=[Optional()], format="%Y-%m-%dT%H:%M")
    cyber_track_id = SelectField(
        _l("CyberHero track"), coerce=int, validators=[Optional()], validate_choice=False
    )
    submit = SubmitField(_l("Save course"))


class ModuleForm(FlaskForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    description_ka = TextAreaField(
        _l("Description (Georgian)"), validators=[Optional(), Length(max=2000)]
    )
    description_en = TextAreaField(
        _l("Description (English)"), validators=[Optional(), Length(max=2000)]
    )
    is_published = BooleanField(_l("Visible to learners"), default=True)
    submit = SubmitField(_l("Save module"))


class LessonForm(FlaskForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    slug = StringField(_l("Slug"), validators=[Optional(), Length(max=120), SLUG])
    lesson_type = SelectField(
        _l("Type"),
        choices=[
            ("reading", _l("Reading")),
            ("video", _l("Video")),
            ("quiz", _l("Quiz")),
            ("lab", _l("Lab")),
            ("assignment", _l("Assignment")),
        ],
    )
    estimated_minutes = IntegerField(
        _l("Duration (minutes)"), validators=[NumberRange(min=1, max=600)], default=10
    )
    summary_ka = TextAreaField(_l("Summary (Georgian)"), validators=[Optional(), Length(max=500)])
    summary_en = TextAreaField(_l("Summary (English)"), validators=[Optional(), Length(max=500)])
    content_ka = TextAreaField(
        _l("Content (Georgian, HTML)"), validators=[Optional(), Length(max=200000)]
    )
    content_en = TextAreaField(
        _l("Content (English, HTML)"), validators=[Optional(), Length(max=200000)]
    )
    video_url = StringField(_l("Video URL"), validators=[Optional(), Length(max=500)])
    video = FileField(_l("Video file"))
    is_published = BooleanField(_l("Visible to learners"), default=True)
    is_free_preview = BooleanField(_l("Free preview (no enrolment needed)"))
    submit = SubmitField(_l("Save lesson"))


class ResourceForm(FlaskForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    url = StringField(_l("Link"), validators=[Optional(), Length(max=500)])
    file = FileField(_l("File"))
    submit = SubmitField(_l("Add resource"))


class QuizForm(FlaskForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    description_ka = TextAreaField(
        _l("Description (Georgian)"), validators=[Optional(), Length(max=2000)]
    )
    description_en = TextAreaField(
        _l("Description (English)"), validators=[Optional(), Length(max=2000)]
    )
    time_limit_minutes = IntegerField(
        _l("Time limit (minutes, empty = none)"),
        validators=[Optional(), NumberRange(min=1, max=600)],
    )
    max_attempts = IntegerField(
        _l("Maximum attempts (empty = unlimited)"),
        validators=[Optional(), NumberRange(min=1, max=100)],
    )
    pass_percent = IntegerField(
        _l("Pass mark (%)"), validators=[NumberRange(min=0, max=100)], default=70
    )
    shuffle_questions = BooleanField(_l("Shuffle questions"))
    shuffle_options = BooleanField(_l("Shuffle options"))
    feedback_mode = SelectField(
        _l("Feedback"),
        choices=[("instant", _l("Instant")), ("delayed", _l("After passing / last attempt"))],
    )
    show_explanations = BooleanField(_l("Show explanations"), default=True)
    is_final = BooleanField(_l("Final assessment for the course"))
    is_published = BooleanField(_l("Published"), default=True)
    submit = SubmitField(_l("Save quiz"))


class QuestionForm(FlaskForm):
    question_type = SelectField(
        _l("Type"),
        choices=[
            ("single", _l("Single choice")),
            ("multiple", _l("Multiple choice")),
            ("true_false", _l("True / false")),
            ("short_answer", _l("Short answer")),
            ("ordering", _l("Ordering")),
            ("matching", _l("Matching")),
        ],
    )
    prompt_ka = TextAreaField(
        _l("Question (Georgian)"), validators=[DataRequired(), Length(max=5000)]
    )
    prompt_en = TextAreaField(_l("Question (English)"), validators=[Optional(), Length(max=5000)])
    explanation_ka = TextAreaField(
        _l("Explanation (Georgian)"), validators=[Optional(), Length(max=5000)]
    )
    explanation_en = TextAreaField(
        _l("Explanation (English)"), validators=[Optional(), Length(max=5000)]
    )
    points = DecimalField(
        _l("Points"), validators=[NumberRange(min=0, max=100)], default=1, places=1
    )
    accepted_answers = TextAreaField(
        _l("Accepted answers (short answer, one per line)"),
        validators=[Optional(), Length(max=2000)],
    )
    # Options are posted as parallel arrays (opt_text_ka, opt_text_en, opt_correct,
    # opt_match_ka, opt_match_en, opt_position); see authoring_service.save_question.
    submit = SubmitField(_l("Save question"))


class AssignmentForm(FlaskForm):
    title_ka = StringField(_l("Title (Georgian)"), validators=[DataRequired(), Length(max=200)])
    title_en = StringField(_l("Title (English)"), validators=[Optional(), Length(max=200)])
    instructions_ka = TextAreaField(
        _l("Instructions (Georgian, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    instructions_en = TextAreaField(
        _l("Instructions (English, HTML)"), validators=[Optional(), Length(max=50000)]
    )
    submission_type = SelectField(
        _l("Submission"),
        choices=[("text", _l("Text")), ("file", _l("File")), ("both", _l("Text and file"))],
    )
    max_points = DecimalField(
        _l("Maximum points"), validators=[NumberRange(min=1, max=1000)], default=100, places=1
    )
    due_at = DateTimeLocalField(_l("Deadline"), validators=[Optional()], format="%Y-%m-%dT%H:%M")
    allow_late = BooleanField(_l("Allow late submissions"), default=True)
    late_penalty_percent = IntegerField(
        _l("Late penalty (%)"), validators=[NumberRange(min=0, max=100)], default=0
    )
    max_resubmissions = IntegerField(
        _l("Resubmissions allowed"), validators=[NumberRange(min=0, max=20)], default=2
    )
    allowed_extensions = StringField(
        _l("Allowed file extensions"),
        validators=[Optional(), Length(max=200)],
        default="pdf,docx,txt,zip,png,jpg",
    )
    is_published = BooleanField(_l("Published"), default=True)
    submit = SubmitField(_l("Save assignment"))


class CategoryForm(FlaskForm):
    slug = StringField(_l("Slug"), validators=[DataRequired(), Length(max=80), SLUG])
    name_ka = StringField(_l("Name (Georgian)"), validators=[DataRequired(), Length(max=120)])
    name_en = StringField(_l("Name (English)"), validators=[DataRequired(), Length(max=120)])
    description_ka = TextAreaField(
        _l("Description (Georgian)"), validators=[Optional(), Length(max=1000)]
    )
    description_en = TextAreaField(
        _l("Description (English)"), validators=[Optional(), Length(max=1000)]
    )
    icon = StringField(_l("Icon"), validators=[Optional(), Length(max=40)], default="shield")
    color = SelectField(
        _l("Colour"),
        choices=[("blue", "Blue"), ("purple", "Purple"), ("cyan", "Cyan"), ("green", "Green")],
    )
    platform = SelectField(
        _l("Platform"),
        choices=[("elearning", "eLearning"), ("cyberhero", "CyberHero"), ("both", _l("Both"))],
    )
    sort_order = IntegerField(_l("Order"), validators=[NumberRange(min=0, max=1000)], default=0)
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save category"))


class ReviewDecisionForm(FlaskForm):
    note = TextAreaField(_l("Note to the instructor"), validators=[Optional(), Length(max=2000)])
    approve = SubmitField(_l("Approve & publish"))
    reject = SubmitField(_l("Send back to draft"))
