"""Understated achievements for the professional LMS (CyberHero has its own XP)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Achievement,
    Certificate,
    CourseProgress,
    Platform,
    QuizAttempt,
    User,
    UserAchievement,
)
from app.services import feature_flags, notification_service

DEFAULT_ACHIEVEMENTS: list[dict] = [
    {
        "code": "first_course",
        "name_ka": "პირველი კურსი",
        "name_en": "First course",
        "description_ka": "დაასრულე პირველი კურსი",
        "description_en": "Completed your first course",
        "icon": "flag",
        "criteria_type": "courses_completed",
        "criteria_value": 1,
    },
    {
        "code": "five_courses",
        "name_ka": "ხუთი კურსი",
        "name_en": "Five courses",
        "description_ka": "დაასრულე ხუთი კურსი",
        "description_en": "Completed five courses",
        "icon": "layers",
        "criteria_type": "courses_completed",
        "criteria_value": 5,
    },
    {
        "code": "first_certificate",
        "name_ka": "პირველი სერტიფიკატი",
        "name_en": "First certificate",
        "description_ka": "მიიღე პირველი სერტიფიკატი",
        "description_en": "Earned your first certificate",
        "icon": "award",
        "criteria_type": "certificates",
        "criteria_value": 1,
    },
    {
        "code": "quiz_streak_3",
        "name_ka": "ქვიზების სერია",
        "name_en": "Quiz streak",
        "description_ka": "ზედიზედ სამი ქვიზი ჩააბარე",
        "description_en": "Passed three quizzes in a row",
        "icon": "zap",
        "criteria_type": "quiz_streak",
        "criteria_value": 3,
    },
    {
        "code": "perfect_quiz",
        "name_ka": "უნაკლო შედეგი",
        "name_en": "Perfect score",
        "description_ka": "ქვიზი 100%-ით ჩააბარე",
        "description_en": "Scored 100% on a quiz",
        "icon": "star",
        "criteria_type": "perfect_quiz",
        "criteria_value": 1,
    },
]


def seed_defaults() -> int:
    existing = {a.code for a in db.session.query(Achievement.code).all()}
    created = 0
    for data in DEFAULT_ACHIEVEMENTS:
        if data["code"] in existing:
            continue
        db.session.add(Achievement(platform=Platform.ELEARNING, **data))
        created += 1
    db.session.commit()
    return created


def _award(user: User, code: str) -> bool:
    achievement = db.session.execute(
        select(Achievement).where(Achievement.code == code, Achievement.is_active.is_(True))
    ).scalar_one_or_none()
    if achievement is None:
        return False
    already = db.session.execute(
        select(UserAchievement.id).where(
            UserAchievement.user_id == user.id, UserAchievement.achievement_id == achievement.id
        )
    ).first()
    if already:
        return False
    db.session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
    db.session.commit()
    notification_service.notify(
        user.id,
        kind="achievement",
        title=f"Achievement unlocked: {achievement.name_en}",
        body=achievement.description_en,
        link="/profile/#achievements",
    )
    return True


def check_course_completion(user: User) -> list[str]:
    if not feature_flags.is_enabled("ACHIEVEMENTS_ENABLED"):
        return []
    completed = int(
        db.session.execute(
            select(func.count())
            .select_from(CourseProgress)
            .where(CourseProgress.user_id == user.id, CourseProgress.is_complete.is_(True))
        ).scalar_one()
    )
    awarded = []
    for code, threshold in (("first_course", 1), ("five_courses", 5)):
        if completed >= threshold and _award(user, code):
            awarded.append(code)
    return awarded


def check_certificates(user: User) -> list[str]:
    if not feature_flags.is_enabled("ACHIEVEMENTS_ENABLED"):
        return []
    count = int(
        db.session.execute(
            select(func.count()).select_from(Certificate).where(Certificate.user_id == user.id)
        ).scalar_one()
    )
    return ["first_certificate"] if count >= 1 and _award(user, "first_certificate") else []


def check_quiz(user: User, attempt: QuizAttempt) -> list[str]:
    if not feature_flags.is_enabled("ACHIEVEMENTS_ENABLED"):
        return []
    awarded = []
    if attempt.percent >= 100 and _award(user, "perfect_quiz"):
        awarded.append("perfect_quiz")
    recent = list(
        db.session.execute(
            select(QuizAttempt.passed)
            .where(QuizAttempt.user_id == user.id, QuizAttempt.submitted_at.is_not(None))
            .order_by(QuizAttempt.submitted_at.desc())
            .limit(3)
        ).scalars()
    )
    if len(recent) == 3 and all(recent) and _award(user, "quiz_streak_3"):
        awarded.append("quiz_streak_3")
    return awarded


def user_achievements(user: User) -> list[UserAchievement]:
    return list(
        db.session.execute(
            select(UserAchievement)
            .where(UserAchievement.user_id == user.id)
            .order_by(UserAchievement.earned_at.desc())
        ).scalars()
    )
