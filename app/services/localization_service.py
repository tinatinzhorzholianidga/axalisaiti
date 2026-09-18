"""Translation coverage statistics for the admin localisation page."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from app.config import BASE_DIR
from app.extensions import db
from app.models import (
    Course,
    CyberArticle,
    CyberMission,
    Lesson,
    LessonTranslation,
)


def _catalog_stats(locale: str) -> dict[str, int]:
    path = BASE_DIR / "app" / "translations" / locale / "LC_MESSAGES" / "messages.po"
    if not path.exists():
        return {"total": 0, "translated": 0, "fuzzy": 0}
    text = path.read_text(encoding="utf-8")
    entries = re.findall(r'msgid "(.*)"\nmsgstr "(.*)"', text)
    total = sum(1 for msgid, _ in entries if msgid)
    translated = sum(1 for msgid, msgstr in entries if msgid and msgstr)
    fuzzy = text.count("#, fuzzy")
    return {"total": total, "translated": translated, "fuzzy": fuzzy}


def stats() -> dict[str, Any]:
    courses = list(db.session.execute(select(Course)).scalars())
    course_en = sum(1 for c in courses if any(t.locale == "en" and t.title for t in c.translations))
    lessons_total = int(db.session.query(Lesson).count())
    lessons_en = int(
        db.session.query(LessonTranslation)
        .filter(LessonTranslation.locale == "en", LessonTranslation.content != "")
        .count()
    )
    missions = list(db.session.execute(select(CyberMission)).scalars())
    articles = list(db.session.execute(select(CyberArticle)).scalars())
    return {
        "ui": {"ka": _catalog_stats("ka"), "en": _catalog_stats("en")},
        "courses": {"total": len(courses), "en": course_en},
        "lessons": {"total": lessons_total, "en": lessons_en},
        "missions": {
            "total": len(missions),
            "en": sum(1 for m in missions if m.name_en and m.brief_en),
        },
        "articles": {"total": len(articles), "en": sum(1 for a in articles if a.title_en)},
        "course_rows": [
            (
                c,
                any(t.locale == "en" and t.title for t in c.translations),
                sum(
                    1
                    for tr in db.session.query(LessonTranslation)
                    .join(Lesson)
                    .join(Lesson.module)
                    .filter(LessonTranslation.locale == "en", LessonTranslation.content != "")
                    .all()
                    if tr.lesson.module.course_id == c.id
                ),
            )
            for c in courses
        ],
    }
