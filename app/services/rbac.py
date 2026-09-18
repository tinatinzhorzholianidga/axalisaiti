"""Role-based access control: permission catalogue, role defaults and decorators."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import abort, current_app, redirect, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models.user import Permission, Role, User

# ---- permission catalogue ---------------------------------------------------
PERMISSIONS: dict[str, str] = {
    "courses.enroll": "Enrol in published courses",
    "learning.access": "Access enrolled course content",
    "quizzes.attempt": "Attempt quizzes",
    "assignments.submit": "Submit assignments",
    "discussions.participate": "Create threads and replies",
    "reviews.write": "Review courses",
    "courses.create": "Create courses",
    "courses.manage_own": "Manage own courses",
    "courses.manage_all": "Manage every course",
    "courses.publish": "Publish / archive courses",
    "assignments.grade": "Grade assignment submissions",
    "analytics.view_own": "View analytics for own courses",
    "analytics.view_all": "View platform analytics",
    "discussions.moderate_own": "Moderate discussions in own courses",
    "discussions.moderate_all": "Moderate every discussion",
    "reviews.moderate": "Approve / reject reviews",
    "users.manage": "Manage user accounts",
    "roles.manage": "Assign roles",
    "categories.manage": "Manage categories",
    "cyberhero.manage": "Manage CyberHero content",
    "certificates.manage": "Issue / revoke certificates",
    "media.manage": "Upload and manage media",
    "notifications.broadcast": "Send announcements",
    "settings.manage": "Change site settings",
    "flags.manage": "Toggle feature flags",
    "audit.view": "View the audit log",
    "admin.access": "Open the admin panel",
    "instructor.access": "Open the instructor panel",
}

STUDENT_PERMISSIONS = {
    "courses.enroll",
    "learning.access",
    "quizzes.attempt",
    "assignments.submit",
    "discussions.participate",
    "reviews.write",
}
INSTRUCTOR_PERMISSIONS = STUDENT_PERMISSIONS | {
    "courses.create",
    "courses.manage_own",
    "assignments.grade",
    "analytics.view_own",
    "discussions.moderate_own",
    "media.manage",
    "instructor.access",
}
MODERATOR_PERMISSIONS = STUDENT_PERMISSIONS | {
    "discussions.moderate_own",
    "discussions.moderate_all",
    "reviews.moderate",
    "admin.access",
}
ADMIN_PERMISSIONS = set(PERMISSIONS)

ROLE_DEFINITIONS: dict[str, tuple[str, set[str]]] = {
    "student": ("Learner with access to enrolled content", STUDENT_PERMISSIONS),
    "instructor": ("Creates and manages their own courses", INSTRUCTOR_PERMISSIONS),
    "moderator": ("Moderates discussions and reviews", MODERATOR_PERMISSIONS),
    "admin": ("Full platform administration", ADMIN_PERMISSIONS),
}


def seed_roles_and_permissions() -> dict[str, int]:
    """Idempotently create the permission catalogue and system roles."""
    created = {"permissions": 0, "roles": 0}
    existing = {p.code: p for p in db.session.query(Permission).all()}
    for code, description in PERMISSIONS.items():
        perm = existing.get(code)
        if perm is None:
            perm = Permission(code=code, description=description)
            db.session.add(perm)
            existing[code] = perm
            created["permissions"] += 1
        elif perm.description != description:
            perm.description = description
    db.session.flush()

    roles = {r.name: r for r in db.session.query(Role).all()}
    for name, (description, codes) in ROLE_DEFINITIONS.items():
        role = roles.get(name)
        if role is None:
            role = Role(name=name, description=description, is_system=True)
            db.session.add(role)
            created["roles"] += 1
        role.permissions = [existing[c] for c in sorted(codes)]
    db.session.commit()
    return created


def get_role(name: str) -> Role | None:
    return db.session.query(Role).filter_by(name=name).one_or_none()


def assign_role(user: User, role_name: str) -> bool:
    role = get_role(role_name)
    if role is None or role in user.roles:
        return False
    user.roles.append(role)
    user.bump_security_version()
    return True


def remove_role(user: User, role_name: str) -> bool:
    role = get_role(role_name)
    if role is None or role not in user.roles:
        return False
    user.roles.remove(role)
    user.bump_security_version()
    return True


# ---- decorators -------------------------------------------------------------
def _deny() -> Any:
    if not current_user.is_authenticated:
        if request.path.startswith("/api/"):
            abort(401)
        return redirect(
            url_for("auth.login", next=request.full_path if request.query_string else request.path)
        )
    abort(403)


def require_permission(*codes: str) -> Callable:
    """Allow the request when the user holds ANY of the given permissions."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated or not current_user.has_permission(*codes):
                return _deny()
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_all_permissions(*codes: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated or not all(
                current_user.has_permission(c) for c in codes
            ):
                return _deny()
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_role(*names: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated or not current_user.has_role(*names):
                return _deny()
            return view(*args, **kwargs)

        return wrapped

    return decorator


def can_manage_course(user: User, course: Any) -> bool:
    if not user.is_authenticated:
        return False
    if user.has_permission("courses.manage_all"):
        return True
    return bool(
        user.has_permission("courses.manage_own")
        and (course.instructor_id == user.id or course.created_by_id == user.id)
    )


def instructor_approval_required() -> bool:
    from app.services import settings_service

    return bool(
        settings_service.get(
            "courses.instructor_approval_required",
            current_app.config.get("INSTRUCTOR_APPROVAL_REQUIRED", True),
        )
    )
