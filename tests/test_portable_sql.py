"""The ORM must only emit SQL that every supported backend accepts.

Tests run on SQLite, but production runs on MariaDB, which has no
``NULLS LAST`` syntax; a statement carrying it 500s there while passing here.
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import Flask
from sqlalchemy import select
from sqlalchemy.dialects import mysql, postgresql, sqlite

from app.models import Discussion, Enrollment
from app.repositories.ordering import newest_first
from app.services import cyberhero_service

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_newest_first_avoids_nulls_clause_on_every_dialect() -> None:
    stmt = select(Enrollment).order_by(
        *newest_first(Enrollment.last_accessed_at), Enrollment.enrolled_at.desc()
    )
    for dialect in (mysql.dialect(), sqlite.dialect(), postgresql.dialect()):
        sql = str(stmt.compile(dialect=dialect))
        assert "NULLS" not in sql.upper()
        assert "last_accessed_at IS NULL" in sql
        assert "last_accessed_at DESC" in sql


def test_newest_first_orders_rows_with_values_first(app: Flask, student, db) -> None:
    from datetime import datetime, timedelta

    from app.models import EnrollmentStatus, Platform
    from app.services import course_service, enrollment_service

    stamps = [None, datetime(2026, 1, 2), datetime(2026, 1, 5)]
    for i, stamp in enumerate(stamps):
        course = course_service.create_course(
            actor=student,
            platform=Platform.ELEARNING,
            translations={"ka": {"title": f"კურსი {i}"}, "en": {"title": f"Course {i}"}},
            slug=f"order-{i}",
        )
        db.session.add(
            Enrollment(
                user_id=student.id,
                course_id=course.id,
                status=EnrollmentStatus.ACTIVE,
                last_accessed_at=stamp,
                enrolled_at=datetime(2025, 12, 1) + timedelta(days=i),
            )
        )
    db.session.commit()

    ordered = [e.course.slug for e in enrollment_service.user_enrollments(student)]
    # most recently opened first, never-opened courses last (not first, as
    # a plain DESC would put NULLs on SQLite/PostgreSQL)
    assert ordered == ["order-2", "order-1", "order-0"]


def test_discussion_ordering_compiles_for_mariadb() -> None:
    stmt = select(Discussion).order_by(
        Discussion.is_pinned.desc(), *newest_first(Discussion.last_post_at)
    )
    assert "NULLS" not in str(stmt.compile(dialect=mysql.dialect())).upper()


def test_no_nulls_ordering_in_source_tree() -> None:
    offenders = [
        str(path.relative_to(APP_DIR.parent))
        for path in APP_DIR.rglob("*.py")
        if re.search(r"\.nulls(last|first)\(", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_seed_cyberhero_if_empty_never_overwrites_admin_edits(app: Flask, db) -> None:
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-cyberhero", "--if-empty"])
    assert first.exit_code == 0, first.output
    assert "tracks:" in first.output
    tracks = cyberhero_service.tracks()
    assert tracks
    tracks[0].name_en = "Renamed by an administrator"
    db.session.commit()

    second = runner.invoke(args=["seed-cyberhero", "--if-empty"])
    assert second.exit_code == 0, second.output
    assert "skipping" in second.output
    db.session.expire_all()
    assert cyberhero_service.tracks()[0].name_en == "Renamed by an administrator"

    refresh = runner.invoke(args=["seed-cyberhero"])
    assert refresh.exit_code == 0, refresh.output
    db.session.expire_all()
    assert cyberhero_service.tracks()[0].name_en != "Renamed by an administrator"
