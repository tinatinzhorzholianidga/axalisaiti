"""Global search over courses, lessons, case studies and resources (published only)."""

from __future__ import annotations

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import Course, CourseStatus, Lesson, LessonResource, Module
from app.repositories import course_repository as repo
from app.repositories.course_repository import CatalogFilters
from app.services import case_study_service


def search_all(query: str, locale: str = "ka", limit: int = 10) -> dict:
    query = query.strip()
    if len(query) < 2:
        return {"courses": [], "lessons": [], "cases": [], "resources": [], "categories": []}
    courses = repo.catalog(CatalogFilters(query=query, per_page=limit), locale).items
    lessons = repo.search_lessons(query, locale, limit)
    like = f"%{query.lower()}%"
    resources = list(
        db.session.execute(
            select(LessonResource)
            .join(Lesson)
            .join(Module)
            .join(Course)
            .where(
                Course.status == CourseStatus.PUBLISHED,
                or_(
                    func.lower(LessonResource.title_ka).like(like),
                    func.lower(LessonResource.title_en).like(like),
                ),
            )
            .limit(limit)
        ).scalars()
    )
    categories = repo.search_categories(query)
    return {
        "courses": courses,
        "lessons": lessons,
        "cases": case_study_service.search(query, locale, limit),
        "resources": resources,
        "categories": categories,
    }
