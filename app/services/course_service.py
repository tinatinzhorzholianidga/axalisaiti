"""Course catalogue, authoring and lifecycle."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Category,
    CategoryTranslation,
    Certificate,
    Course,
    CourseStatus,
    CourseTranslation,
    Enrollment,
    EnrollmentStatus,
    Lesson,
    LessonResource,
    LessonTranslation,
    LessonType,
    Module,
    ModuleTranslation,
    Platform,
    User,
    utcnow,
)
from app.repositories import course_repository as repo
from app.repositories.course_repository import CatalogFilters
from app.services import audit_service
from app.services.sanitize import sanitize_html

LOCALES = ("ka", "en")

_GEORGIAN_TRANSLIT = {
    "ა": "a",
    "ბ": "b",
    "გ": "g",
    "დ": "d",
    "ე": "e",
    "ვ": "v",
    "ზ": "z",
    "თ": "t",
    "ი": "i",
    "კ": "k",
    "ლ": "l",
    "მ": "m",
    "ნ": "n",
    "ო": "o",
    "პ": "p",
    "ჟ": "zh",
    "რ": "r",
    "ს": "s",
    "ტ": "t",
    "უ": "u",
    "ფ": "p",
    "ქ": "q",
    "ღ": "gh",
    "ყ": "q",
    "შ": "sh",
    "ჩ": "ch",
    "ც": "ts",
    "ძ": "dz",
    "წ": "ts",
    "ჭ": "ch",
    "ხ": "kh",
    "ჯ": "j",
    "ჰ": "h",
}


def slugify(value: str, max_length: int = 100) -> str:
    value = "".join(_GEORGIAN_TRANSLIT.get(ch, ch) for ch in value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:max_length] or "item"


def unique_slug(base: str, model: Any, exclude_id: int | None = None, **scope: Any) -> str:
    slug = slugify(base)
    candidate = slug
    counter = 2
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        for key, value in scope.items():
            stmt = stmt.where(getattr(model, key) == value)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if db.session.execute(stmt).first() is None:
            return candidate
        candidate = f"{slug}-{counter}"
        counter += 1


# ---- read side --------------------------------------------------------------
def featured_courses(limit: int = 6, platform: Platform = Platform.ELEARNING) -> list[Course]:
    courses = repo.featured(platform, limit)
    if len(courses) < limit:
        seen = {c.id for c in courses}
        courses += [c for c in repo.latest(platform, limit) if c.id not in seen][
            : limit - len(courses)
        ]
    return courses


def active_categories(platform: Platform = Platform.ELEARNING) -> list[Category]:
    return repo.active_categories(platform)


def catalog(filters: CatalogFilters, locale: str):  # type: ignore[no-untyped-def]
    return repo.catalog(filters, locale)


def get_course(slug: str, *, published_only: bool = True) -> Course | None:
    return repo.get_by_slug(slug, published_only=published_only)


def public_stats() -> dict[str, int]:
    courses = repo.count_published()
    students = int(
        db.session.execute(
            select(func.count(func.distinct(Enrollment.user_id))).select_from(Enrollment)
        ).scalar_one()
    )
    total = int(db.session.execute(select(func.count()).select_from(Enrollment)).scalar_one())
    completed = int(
        db.session.execute(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.status == EnrollmentStatus.COMPLETED)
        ).scalar_one()
    )
    certificates = int(
        db.session.execute(select(func.count()).select_from(Certificate)).scalar_one()
    )
    completion = round(100 * completed / total) if total else 0
    return {
        "courses": courses,
        "students": students,
        "completion": completion,
        "certificates": certificates,
    }


def public_resources(limit: int = 60) -> list[LessonResource]:
    stmt = (
        select(LessonResource)
        .join(Lesson)
        .join(Module)
        .join(Course)
        .where(Course.status == CourseStatus.PUBLISHED, Lesson.is_published.is_(True))
        .order_by(Course.sort_order, LessonResource.sort_order)
        .limit(limit)
    )
    return list(db.session.execute(stmt).scalars())


def visible_lessons(course: Course) -> list[Lesson]:
    return [
        lesson
        for module in course.modules
        if module.is_published
        for lesson in module.lessons
        if lesson.is_published
    ]


def neighbours(course: Course, lesson: Lesson) -> tuple[Lesson | None, Lesson | None]:
    lessons = visible_lessons(course)
    ids = [lesson_.id for lesson_ in lessons]
    if lesson.id not in ids:
        return None, None
    index = ids.index(lesson.id)
    prev_lesson = lessons[index - 1] if index > 0 else None
    next_lesson = lessons[index + 1] if index + 1 < len(lessons) else None
    return prev_lesson, next_lesson


# ---- write side -------------------------------------------------------------
def _apply_translations(
    obj, translation_cls, fk: str, data: dict[str, dict[str, Any]], html_fields=()
):  # type: ignore[no-untyped-def]
    existing = {t.locale: t for t in obj.translations}
    for locale in LOCALES:
        values = data.get(locale) or {}
        if not any(str(v).strip() for v in values.values()):
            continue
        tr = existing.get(locale)
        if tr is None:
            tr = translation_cls(locale=locale)
            setattr(tr, fk, obj.id)
            obj.translations.append(tr)
        for key, value in values.items():
            if key in html_fields:
                value = sanitize_html(value or "")
            setattr(tr, key, value if value is not None else "")


def create_course(
    *, actor: User, platform: Platform, translations: dict[str, dict[str, Any]], **fields: Any
) -> Course:
    title = (
        translations.get("ka", {}).get("title")
        or translations.get("en", {}).get("title")
        or "course"
    )
    course = Course(
        slug=unique_slug(fields.pop("slug", None) or title, Course),
        platform=platform,
        created_by_id=actor.id,
        instructor_id=fields.pop("instructor_id", None) or actor.id,
    )
    category_ids = fields.pop("category_ids", [])
    for key, value in fields.items():
        if hasattr(course, key):
            setattr(course, key, value)
    db.session.add(course)
    db.session.flush()
    _apply_translations(
        course, CourseTranslation, "course_id", translations, html_fields=("description",)
    )
    if category_ids:
        course.categories = list(
            db.session.execute(select(Category).where(Category.id.in_(category_ids))).scalars()
        )
    audit_service.record(
        "course.created", target=course, actor=actor, meta={"platform": platform.value}
    )
    db.session.commit()
    return course


def update_course(
    course: Course, *, actor: User, translations: dict | None = None, **fields: Any
) -> Course:
    category_ids = fields.pop("category_ids", None)
    new_slug = fields.pop("slug", None)
    if new_slug and new_slug != course.slug:
        course.slug = unique_slug(new_slug, Course, exclude_id=course.id)
    for key, value in fields.items():
        if hasattr(course, key):
            setattr(course, key, value)
    if translations:
        _apply_translations(
            course, CourseTranslation, "course_id", translations, html_fields=("description",)
        )
    if category_ids is not None:
        course.categories = (
            list(
                db.session.execute(select(Category).where(Category.id.in_(category_ids))).scalars()
            )
            if category_ids
            else []
        )
    audit_service.record("course.updated", target=course, actor=actor)
    db.session.commit()
    return course


def set_status(
    course: Course, status: CourseStatus, *, actor: User, note: str | None = None
) -> Course:
    previous = course.status
    course.status = status
    if status == CourseStatus.PUBLISHED:
        course.published_at = course.published_at or utcnow()
        course.archived_at = None
    elif status == CourseStatus.ARCHIVED:
        course.archived_at = utcnow()
    if note is not None:
        course.review_note = note
    action = {
        CourseStatus.PUBLISHED: "course.published",
        CourseStatus.ARCHIVED: "course.archived",
        CourseStatus.PENDING_REVIEW: "course.submitted_for_review",
        CourseStatus.DRAFT: "course.unpublished",
    }[status]
    audit_service.record(action, target=course, actor=actor, meta={"from": previous.value})
    db.session.commit()
    return course


def delete_course(course: Course, *, actor: User) -> None:
    audit_service.record("course.deleted", target=course, actor=actor, meta={"slug": course.slug})
    db.session.delete(course)
    db.session.commit()


def add_module(course: Course, translations: dict, *, actor: User) -> Module:
    module = Module(course_id=course.id, sort_order=len(course.modules) + 1)
    db.session.add(module)
    db.session.flush()
    _apply_translations(module, ModuleTranslation, "module_id", translations)
    course.modules.append(module)
    audit_service.record("module.created", target=module, actor=actor, meta={"course": course.slug})
    db.session.commit()
    return module


def update_module(module: Module, translations: dict, *, actor: User, **fields: Any) -> Module:
    for key, value in fields.items():
        if hasattr(module, key):
            setattr(module, key, value)
    _apply_translations(module, ModuleTranslation, "module_id", translations)
    audit_service.record("module.updated", target=module, actor=actor)
    db.session.commit()
    return module


def delete_module(module: Module, *, actor: User) -> None:
    course = module.course
    audit_service.record("module.deleted", target=module, actor=actor, meta={"course": course.slug})
    db.session.delete(module)
    db.session.flush()
    renumber([m for m in course.modules if m is not module])
    db.session.commit()


def add_lesson(
    module: Module,
    translations: dict,
    *,
    actor: User,
    lesson_type: LessonType = LessonType.READING,
    **fields: Any,
) -> Lesson:
    title = (
        translations.get("ka", {}).get("title")
        or translations.get("en", {}).get("title")
        or "lesson"
    )
    lesson = Lesson(
        module_id=module.id,
        slug=unique_slug(fields.pop("slug", None) or title, Lesson, module_id=module.id),
        sort_order=len(module.lessons) + 1,
        lesson_type=lesson_type,
    )
    for key, value in fields.items():
        if hasattr(lesson, key):
            setattr(lesson, key, value)
    db.session.add(lesson)
    db.session.flush()
    _apply_translations(
        lesson, LessonTranslation, "lesson_id", translations, html_fields=("content",)
    )
    module.lessons.append(lesson)
    audit_service.record(
        "lesson.created", target=lesson, actor=actor, meta={"course": module.course.slug}
    )
    db.session.commit()
    return lesson


def update_lesson(lesson: Lesson, translations: dict, *, actor: User, **fields: Any) -> Lesson:
    new_slug = fields.pop("slug", None)
    if new_slug and new_slug != lesson.slug:
        lesson.slug = unique_slug(
            new_slug, Lesson, exclude_id=lesson.id, module_id=lesson.module_id
        )
    for key, value in fields.items():
        if hasattr(lesson, key):
            setattr(lesson, key, value)
    _apply_translations(
        lesson, LessonTranslation, "lesson_id", translations, html_fields=("content",)
    )
    audit_service.record("lesson.updated", target=lesson, actor=actor)
    db.session.commit()
    return lesson


def delete_lesson(lesson: Lesson, *, actor: User) -> None:
    module = lesson.module
    audit_service.record("lesson.deleted", target=lesson, actor=actor)
    db.session.delete(lesson)
    db.session.flush()
    renumber([lsn for lsn in module.lessons if lsn is not lesson])
    db.session.commit()


def renumber(items: list) -> None:
    for index, item in enumerate(sorted(items, key=lambda i: i.sort_order), start=1):
        item.sort_order = index


def reorder(items: list, ordered_ids: list[int]) -> None:
    """Apply a new order given a list of ids (ids not listed keep relative order at the end)."""
    by_id = {item.id: item for item in items}
    position = 1
    for item_id in ordered_ids:
        item = by_id.pop(item_id, None)
        if item is not None:
            item.sort_order = position
            position += 1
    for item in sorted(by_id.values(), key=lambda i: i.sort_order):
        item.sort_order = position
        position += 1
    db.session.commit()


def move(items: list, item_id: int, direction: int) -> None:
    """Accessible, non-drag reorder: move one item up (-1) or down (+1)."""
    ordered = sorted(items, key=lambda i: i.sort_order)
    ids = [i.id for i in ordered]
    if item_id not in ids:
        return
    index = ids.index(item_id)
    target = index + direction
    if 0 <= target < len(ids):
        ids[index], ids[target] = ids[target], ids[index]
    reorder(items, ids)


def add_resource(
    lesson: Lesson,
    *,
    title_ka: str,
    title_en: str = "",
    url: str | None = None,
    media_id: int | None = None,
    actor: User,
) -> LessonResource:
    resource = LessonResource(
        lesson_id=lesson.id,
        title_ka=title_ka,
        title_en=title_en,
        kind="file" if media_id else "link",
        url=url,
        media_id=media_id,
        sort_order=len(lesson.resources) + 1,
    )
    db.session.add(resource)
    audit_service.record("resource.created", target=resource, actor=actor)
    db.session.commit()
    return resource


# ---- categories -------------------------------------------------------------
def create_category(
    *, slug: str, translations: dict, actor: User | None = None, **fields: Any
) -> Category:
    category = Category(slug=unique_slug(slug, Category))
    for key, value in fields.items():
        if hasattr(category, key):
            setattr(category, key, value)
    db.session.add(category)
    db.session.flush()
    _apply_translations(category, CategoryTranslation, "category_id", translations)
    audit_service.record("category.created", target=category, actor=actor)
    db.session.commit()
    return category


def update_category(
    category: Category, translations: dict, *, actor: User, **fields: Any
) -> Category:
    for key, value in fields.items():
        if hasattr(category, key):
            setattr(category, key, value)
    _apply_translations(category, CategoryTranslation, "category_id", translations)
    audit_service.record("category.updated", target=category, actor=actor)
    db.session.commit()
    return category


def instructor_courses(user: User):  # type: ignore[no-untyped-def]
    stmt = (
        select(Course)
        .where((Course.instructor_id == user.id) | (Course.created_by_id == user.id))
        .order_by(Course.updated_at.desc())
    )
    return list(db.session.execute(stmt).scalars())


def courses_for_admin(
    status: str | None = None, platform: str | None = None, query: str | None = None
):  # type: ignore[no-untyped-def]
    stmt = select(Course).order_by(Course.updated_at.desc())
    if status:
        stmt = stmt.where(Course.status == status)
    if platform:
        stmt = stmt.where(Course.platform == platform)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            Course.id.in_(
                select(CourseTranslation.course_id).where(
                    func.lower(CourseTranslation.title).like(like)
                )
            )
            | func.lower(Course.slug).like(like)
        )
    return stmt
