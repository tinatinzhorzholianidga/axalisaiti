"""Courses, categories, modules, lessons and their translations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import (
    CourseStatus,
    Difficulty,
    EnrollmentMode,
    LessonType,
    Platform,
    TimestampMixin,
    str_enum,
)

course_categories = Table(
    "course_categories",
    db.metadata,
    Column("course_id", ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class TranslatedMixin:
    """Access translations as ``obj.tr(locale)`` with Georgian fallback."""

    translations: Mapped[list]

    def tr(self, locale: str = "ka"):  # type: ignore[no-untyped-def]
        by_locale = {t.locale: t for t in self.translations}
        return (
            by_locale.get(locale)
            or by_locale.get("ka")
            or (self.translations[0] if self.translations else None)
        )

    def text(self, field: str, locale: str = "ka", default: str = "") -> str:
        tr = self.tr(locale)
        value = getattr(tr, field, None) if tr else None
        if not value:
            fallback = self.tr("ka")
            value = getattr(fallback, field, None) if fallback else None
        return value or default


class Category(TranslatedMixin, TimestampMixin, db.Model):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="shield", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="blue", nullable=False)
    platform: Mapped[Platform] = mapped_column(
        str_enum(Platform), default=Platform.ELEARNING, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    translations: Mapped[list[CategoryTranslation]] = relationship(
        back_populates="category", cascade="all, delete-orphan", lazy="selectin"
    )
    courses: Mapped[list[Course]] = relationship(
        secondary=course_categories, back_populates="categories"
    )

    def name(self, locale: str = "ka") -> str:
        return self.text("name", locale, self.slug)


class CategoryTranslation(db.Model):
    __tablename__ = "category_translations"
    __table_args__ = (UniqueConstraint("category_id", "locale", name="uq_category_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    category: Mapped[Category] = relationship(back_populates="translations")


class Course(TranslatedMixin, TimestampMixin, db.Model):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(
        str_enum(Platform), default=Platform.ELEARNING, nullable=False, index=True
    )
    status: Mapped[CourseStatus] = mapped_column(
        str_enum(CourseStatus), default=CourseStatus.DRAFT, nullable=False, index=True
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        str_enum(Difficulty), default=Difficulty.BEGINNER, nullable=False
    )
    enrollment_mode: Mapped[EnrollmentMode] = mapped_column(
        str_enum(EnrollmentMode), default=EnrollmentMode.OPEN, nullable=False
    )

    instructor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    cover_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )
    cyber_track_id: Mapped[int | None] = mapped_column(
        ForeignKey("cyber_tracks.id", ondelete="SET NULL")
    )

    icon: Mapped[str] = mapped_column(String(40), default="shield", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="blue", nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    certificate_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    certificate_pass_percent: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    discussions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reviews_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(Text)

    # denormalised counters kept up to date by services
    enrollment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    translations: Mapped[list[CourseTranslation]] = relationship(
        back_populates="course", cascade="all, delete-orphan", lazy="selectin"
    )
    categories: Mapped[list[Category]] = relationship(
        secondary=course_categories, back_populates="courses", lazy="selectin"
    )
    modules: Mapped[list[Module]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Module.sort_order",
    )
    instructor = relationship("User", foreign_keys=[instructor_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    cover = relationship("MediaFile", foreign_keys=[cover_media_id])
    cyber_track = relationship("CyberTrack", back_populates="courses")
    quizzes: Mapped[list] = relationship(
        "Quiz", back_populates="course", cascade="all, delete-orphan"
    )
    assignments: Mapped[list] = relationship(
        "Assignment", back_populates="course", cascade="all, delete-orphan"
    )
    missions: Mapped[list] = relationship(
        "CyberMission", back_populates="course", order_by="CyberMission.sort_order"
    )

    # ---- helpers -----------------------------------------------------------
    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, self.slug)

    @property
    def is_published(self) -> bool:
        return self.status == CourseStatus.PUBLISHED

    @property
    def primary_category(self) -> Category | None:
        return self.categories[0] if self.categories else None

    @property
    def lessons(self) -> list[Lesson]:
        return [lesson for module in self.modules for lesson in module.lessons]

    @property
    def lesson_count(self) -> int:
        return sum(len(m.lessons) for m in self.modules)

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def final_quiz(self):  # type: ignore[no-untyped-def]
        return next((q for q in self.quizzes if q.is_final), None)


class CourseTranslation(db.Model):
    __tablename__ = "course_translations"
    __table_args__ = (UniqueConstraint("course_id", "locale", name="uq_course_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    short_description: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML
    objectives: Mapped[str] = mapped_column(Text, default="", nullable=False)  # one per line
    prerequisites: Mapped[str] = mapped_column(Text, default="", nullable=False)
    audience: Mapped[str] = mapped_column(Text, default="", nullable=False)
    certificate_requirements: Mapped[str] = mapped_column(Text, default="", nullable=False)

    course: Mapped[Course] = relationship(back_populates="translations")

    @property
    def objective_list(self) -> list[str]:
        return [line.strip() for line in self.objectives.splitlines() if line.strip()]

    @property
    def prerequisite_list(self) -> list[str]:
        return [line.strip() for line in self.prerequisites.splitlines() if line.strip()]


class Module(TranslatedMixin, TimestampMixin, db.Model):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course: Mapped[Course] = relationship(back_populates="modules")
    translations: Mapped[list[ModuleTranslation]] = relationship(
        back_populates="module", cascade="all, delete-orphan", lazy="selectin"
    )
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="Lesson.sort_order",
        lazy="selectin",
    )

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, f"Module {self.sort_order}")

    @property
    def total_minutes(self) -> int:
        return sum(lesson.estimated_minutes for lesson in self.lessons)


class ModuleTranslation(db.Model):
    __tablename__ = "module_translations"
    __table_args__ = (UniqueConstraint("module_id", "locale", name="uq_module_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    module: Mapped[Module] = relationship(back_populates="translations")


class Lesson(TranslatedMixin, TimestampMixin, db.Model):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lesson_type: Mapped[LessonType] = mapped_column(
        str_enum(LessonType), default=LessonType.READING, nullable=False
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_free_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    video_url: Mapped[str | None] = mapped_column(String(500))
    video_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )

    module: Mapped[Module] = relationship(back_populates="lessons")
    translations: Mapped[list[LessonTranslation]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", lazy="selectin"
    )
    resources: Mapped[list[LessonResource]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonResource.sort_order",
        lazy="selectin",
    )
    quiz = relationship("Quiz", back_populates="lesson", uselist=False)
    assignment = relationship("Assignment", back_populates="lesson", uselist=False)
    video_media = relationship("MediaFile", foreign_keys=[video_media_id])

    __table_args__ = (UniqueConstraint("module_id", "slug", name="uq_lesson_module_slug"),)

    def title(self, locale: str = "ka") -> str:
        return self.text("title", locale, self.slug)

    @property
    def course(self) -> Course:
        return self.module.course


class LessonTranslation(db.Model):
    __tablename__ = "lesson_translations"
    __table_args__ = (UniqueConstraint("lesson_id", "locale", name="uq_lesson_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)  # sanitised HTML

    lesson: Mapped[Lesson] = relationship(back_populates="translations")


class LessonResource(TimestampMixin, db.Model):
    __tablename__ = "lesson_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title_ka: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="link", nullable=False)  # link|file
    url: Mapped[str | None] = mapped_column(String(500))
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media_files.id", ondelete="SET NULL"))

    lesson: Mapped[Lesson] = relationship(back_populates="resources")
    media = relationship("MediaFile", foreign_keys=[media_id])

    def title(self, locale: str = "ka") -> str:
        return (self.title_en if locale == "en" and self.title_en else self.title_ka) or ""
