from __future__ import annotations

from datetime import timedelta

from flask import redirect, url_for
from sqlalchemy import func, select

from app.blueprints.admin import bp
from app.extensions import db
from app.models import (
    Certificate,
    Course,
    CourseStatus,
    CyberMission,
    CyberProgress,
    Enrollment,
    EnrollmentStatus,
    LessonProgress,
    QuizAttempt,
    User,
    utcnow,
)
from app.services.rbac import require_permission


def analytics_context() -> dict:
    """Platform analytics, shown on the admin dashboard."""
    since = utcnow() - timedelta(days=30)
    total_enrollments = int(
        db.session.execute(select(func.count()).select_from(Enrollment)).scalar_one()
    )
    completed = int(
        db.session.execute(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.status == EnrollmentStatus.COMPLETED)
        ).scalar_one()
    )
    active_learners = int(
        db.session.execute(
            select(func.count(func.distinct(LessonProgress.user_id))).where(
                LessonProgress.updated_at >= since
            )
        ).scalar_one()
    )
    new_users = int(
        db.session.execute(
            select(func.count()).select_from(User).where(User.created_at >= since)
        ).scalar_one()
    )
    attempts = list(
        db.session.execute(
            select(QuizAttempt.passed).where(QuizAttempt.submitted_at.is_not(None))
        ).scalars()
    )
    quiz_pass_rate = round(100 * sum(1 for p in attempts if p) / len(attempts)) if attempts else 0
    certificates = int(
        db.session.execute(select(func.count()).select_from(Certificate)).scalar_one()
    )
    popularity = list(
        db.session.execute(
            select(Course)
            .where(Course.status == CourseStatus.PUBLISHED)
            .order_by(Course.enrollment_count.desc())
            .limit(10)
        ).scalars()
    )
    max_enroll = max((c.enrollment_count for c in popularity), default=0) or 1
    missions = list(
        db.session.execute(select(CyberMission).order_by(CyberMission.sort_order)).scalars()
    )
    mission_rows = []
    for mission in missions:
        done = int(
            db.session.execute(
                select(func.count())
                .select_from(CyberProgress)
                .where(CyberProgress.mission_id == mission.id, CyberProgress.done.is_(True))
            ).scalar_one()
        )
        mission_rows.append((mission, done))
    max_done = max((d for _, d in mission_rows), default=0) or 1
    return {
        "totals": {
            "enrollments": total_enrollments,
            "completed": completed,
            "completion_rate": round(100 * completed / total_enrollments)
            if total_enrollments
            else 0,
            "active_learners": active_learners,
            "new_users": new_users,
            "quiz_pass_rate": quiz_pass_rate,
            "certificates": certificates,
        },
        "popularity": popularity,
        "max_enroll": max_enroll,
        "mission_rows": mission_rows,
        "max_done": max_done,
    }


@bp.route("/analytics/")
@require_permission("analytics.view_all")
def analytics():  # type: ignore[no-untyped-def]
    """Analytics live on the dashboard now; old links land on that section."""
    return redirect(url_for("admin.dashboard") + "#analytics")
