"""Course catalogue queries."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    Category,
    CategoryTranslation,
    Course,
    CourseStatus,
    CourseTranslation,
    Lesson,
    LessonTranslation,
    Module,
    Platform,
    course_categories,
)


@dataclass
class CatalogFilters:
    query: str | None = None
    category: str | None = None
    difficulty: str | None = None
    duration: str | None = None  # short (<2h) | medium (2–6h) | long (>6h)
    sort: str = "newest"
    platform: Platform = Platform.ELEARNING
    page: int = 1
    per_page: int = 12


def _platform_filter(stmt, platform: Platform):  # type: ignore[no-untyped-def]
    return stmt.where(Course.platform.in_([platform, Platform.BOTH]))


def published_query(platform: Platform = Platform.ELEARNING):  # type: ignore[no-untyped-def]
    stmt = select(Course).where(Course.status == CourseStatus.PUBLISHED)
    return _platform_filter(stmt, platform)


def get_by_slug(slug: str, *, published_only: bool = True) -> Course | None:
    stmt = (
        select(Course)
        .where(Course.slug == slug)
        .options(selectinload(Course.modules).selectinload(Module.lessons))
    )
    if published_only:
        stmt = stmt.where(Course.status == CourseStatus.PUBLISHED)
    return db.session.execute(stmt).scalar_one_or_none()


def get_by_id(course_id: int) -> Course | None:
    return db.session.get(Course, course_id)


def featured(platform: Platform = Platform.ELEARNING, limit: int = 6) -> list[Course]:
    stmt = (
        published_query(platform)
        .where(Course.is_featured.is_(True))
        .order_by(Course.sort_order, Course.published_at.desc())
        .limit(limit)
    )
    return list(db.session.execute(stmt).scalars())


def latest(platform: Platform = Platform.ELEARNING, limit: int = 6) -> list[Course]:
    stmt = published_query(platform).order_by(Course.published_at.desc()).limit(limit)
    return list(db.session.execute(stmt).scalars())


def catalog(filters: CatalogFilters, locale: str = "ka"):  # type: ignore[no-untyped-def]
    stmt = published_query(filters.platform)

    if filters.query:
        like = f"%{filters.query.lower()}%"
        matches = (
            select(CourseTranslation.course_id)
            .where(
                or_(
                    func.lower(CourseTranslation.title).like(like),
                    func.lower(CourseTranslation.short_description).like(like),
                )
            )
            .scalar_subquery()
        )
        stmt = stmt.where(or_(Course.id.in_(matches), func.lower(Course.tags).like(like)))

    if filters.category:
        stmt = stmt.where(
            Course.id.in_(
                select(course_categories.c.course_id)
                .join(Category, Category.id == course_categories.c.category_id)
                .where(Category.slug == filters.category)
            )
        )

    if filters.difficulty in {"beginner", "intermediate", "advanced"}:
        stmt = stmt.where(Course.difficulty == filters.difficulty)

    if filters.duration == "short":
        stmt = stmt.where(Course.estimated_minutes < 120)
    elif filters.duration == "medium":
        stmt = stmt.where(Course.estimated_minutes.between(120, 360))
    elif filters.duration == "long":
        stmt = stmt.where(Course.estimated_minutes > 360)

    if filters.sort == "popular":
        stmt = stmt.order_by(Course.enrollment_count.desc(), Course.published_at.desc())
    elif filters.sort == "rating":
        stmt = stmt.order_by(Course.rating_avg.desc(), Course.rating_count.desc())
    elif filters.sort == "title":
        title_sub = (
            select(CourseTranslation.title)
            .where(CourseTranslation.course_id == Course.id, CourseTranslation.locale == locale)
            .limit(1)
            .scalar_subquery()
        )
        stmt = stmt.order_by(title_sub)
    elif filters.sort == "duration":
        stmt = stmt.order_by(Course.estimated_minutes)
    else:
        stmt = stmt.order_by(Course.is_featured.desc(), Course.published_at.desc())

    return db.paginate(stmt, page=filters.page, per_page=filters.per_page, error_out=False)


def active_categories(platform: Platform = Platform.ELEARNING) -> list[Category]:
    stmt = (
        select(Category)
        .where(Category.is_active.is_(True), Category.platform.in_([platform, Platform.BOTH]))
        .order_by(Category.sort_order)
    )
    return list(db.session.execute(stmt).scalars())


def category_by_slug(slug: str) -> Category | None:
    return db.session.execute(select(Category).where(Category.slug == slug)).scalar_one_or_none()


def count_published(platform: Platform = Platform.ELEARNING) -> int:
    stmt = select(func.count()).select_from(published_query(platform).subquery())
    return int(db.session.execute(stmt).scalar_one())


def lesson_by_slugs(course_slug: str, lesson_slug: str) -> Lesson | None:
    stmt = (
        select(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .join(Course, Module.course_id == Course.id)
        .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def search_lessons(query: str, locale: str, limit: int = 10) -> list[tuple[Lesson, Course]]:
    like = f"%{query.lower()}%"
    stmt = (
        select(Lesson, Course)
        .join(LessonTranslation, LessonTranslation.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .join(Course, Module.course_id == Course.id)
        .where(
            Course.status == CourseStatus.PUBLISHED,
            Course.platform.in_([Platform.ELEARNING, Platform.BOTH]),
            Lesson.is_published.is_(True),
            or_(
                func.lower(LessonTranslation.title).like(like),
                func.lower(LessonTranslation.summary).like(like),
            ),
        )
        .limit(limit)
    )
    seen: set[int] = set()
    results: list[tuple[Lesson, Course]] = []
    for lesson, course in db.session.execute(stmt).all():
        if lesson.id not in seen:
            seen.add(lesson.id)
            results.append((lesson, course))
    return results


def search_categories(query: str, limit: int = 5) -> list[Category]:
    like = f"%{query.lower()}%"
    stmt = (
        select(Category)
        .join(CategoryTranslation)
        .where(func.lower(CategoryTranslation.name).like(like), Category.is_active.is_(True))
        .limit(limit)
    )
    return list(db.session.execute(stmt).scalars().unique())
