from __future__ import annotations

from flask import render_template
from flask_login import login_required
from sqlalchemy import func, select

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import locale
from app.blueprints.admin.routes_analytics import analytics_context
from app.extensions import db
from app.models import (
    AuditLog,
    Certificate,
    Course,
    CourseStatus,
    Enrollment,
    EnrollmentStatus,
    QuizAttempt,
    Role,
    User,
    UserStatus,
)
from app.services import cyberhero_service
from app.services.rbac import require_permission


@bp.before_request
@login_required
@require_permission("admin.access")
def _guard():  # type: ignore[no-untyped-def]
    return None


def _count(stmt) -> int:  # type: ignore[no-untyped-def]
    return int(db.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())


@bp.route("/")
def dashboard():  # type: ignore[no-untyped-def]
    metrics = {
        "active_students": _count(
            select(User.id)
            .join(User.roles)
            .where(Role.name == "student", User.status == UserStatus.ACTIVE)
        ),
        "active_instructors": _count(
            select(User.id)
            .join(User.roles)
            .where(Role.name == "instructor", User.status == UserStatus.ACTIVE)
        ),
        "published_courses": _count(
            select(Course.id).where(Course.status == CourseStatus.PUBLISHED)
        ),
        "draft_courses": _count(
            select(Course.id).where(
                Course.status.in_([CourseStatus.DRAFT, CourseStatus.PENDING_REVIEW])
            )
        ),
        "enrollments": _count(select(Enrollment.id)),
        "completed": _count(
            select(Enrollment.id).where(Enrollment.status == EnrollmentStatus.COMPLETED)
        ),
        "certificates": _count(select(Certificate.id)),
        "quiz_attempts": _count(
            select(QuizAttempt.id).where(QuizAttempt.submitted_at.is_not(None))
        ),
        "pending_courses": _count(
            select(Course.id).where(Course.status == CourseStatus.PENDING_REVIEW)
        ),
    }
    cyber = cyberhero_service.stats()
    recent_activity = list(
        db.session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(12)
        ).scalars()
    )
    pending_courses = list(
        db.session.execute(
            select(Course)
            .where(Course.status == CourseStatus.PENDING_REVIEW)
            .order_by(Course.updated_at)
        ).scalars()
    )
    return render_template(
        "admin/dashboard.html",
        metrics=metrics,
        cyber=cyber,
        recent_activity=recent_activity,
        pending_courses=pending_courses,
        locale=locale(),
        **analytics_context(),
    )
