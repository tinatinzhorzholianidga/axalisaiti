"""Shared pytest fixtures: an isolated app + in-memory SQLite database per test."""

from __future__ import annotations

import re
import tempfile
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db as _db
from app.models import Role, User
from app.services import achievement_service, feature_flags, settings_service
from app.services.rbac import seed_roles_and_permissions

CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


@pytest.fixture(scope="session")
def upload_dir() -> Iterator[str]:
    with tempfile.TemporaryDirectory(prefix="elearning-uploads-") as tmp:
        yield tmp


@pytest.fixture
def app(upload_dir: str) -> Iterator[Flask]:
    application = create_app("testing", overrides={"UPLOAD_PATH": upload_dir})
    with application.app_context():
        _db.create_all()
        seed_roles_and_permissions()
        settings_service.seed_defaults()
        feature_flags.seed_defaults()
        achievement_service.seed_defaults()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app: Flask):  # type: ignore[no-untyped-def]
    return _db


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def make_user(
    email: str,
    password: str = "CorrectHorse!Battery9",
    roles: tuple[str, ...] = ("student",),
    **extra,
) -> User:  # type: ignore[no-untyped-def]
    user = User(
        email=email,
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", "User"),
        is_email_verified=True,
        **extra,
    )
    user.set_password(password)
    user.roles = [_db.session.query(Role).filter_by(name=r).one() for r in roles]
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture
def student(app: Flask) -> User:
    return make_user("student@example.org", first_name="Nino", last_name="Beridze")


@pytest.fixture
def instructor(app: Flask) -> User:
    return make_user(
        "instructor@example.org",
        roles=("instructor", "student"),
        first_name="Giorgi",
        last_name="Kapanadze",
    )


@pytest.fixture
def admin(app: Flask) -> User:
    return make_user("admin@example.org", roles=("admin",), first_name="Ana", last_name="Admin")


@pytest.fixture
def moderator(app: Flask) -> User:
    return make_user("moderator@example.org", roles=("moderator", "student"))


def get_csrf(client: FlaskClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    return response.get_json()["csrf_token"]


def login(client: FlaskClient, user: User, password: str = "CorrectHorse!Battery9") -> None:
    token = get_csrf(client)
    response = client.post(
        "/auth/login",
        data={"email": user.email, "password": password, "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.data[:500]


def logout(client: FlaskClient) -> None:
    response = post(client, "/auth/logout")
    assert response.status_code in (302, 303)


def post(client: FlaskClient, url: str, data: dict | None = None, **kwargs):  # type: ignore[no-untyped-def]
    payload = dict(data or {})
    payload["csrf_token"] = get_csrf(client)
    return client.post(url, data=payload, **kwargs)


def post_json(
    client: FlaskClient, url: str, json: dict | list | None = None, method: str = "post", **kwargs
):  # type: ignore[no-untyped-def]
    headers = kwargs.pop("headers", {})
    headers["X-CSRFToken"] = get_csrf(client)
    return getattr(client, method)(url, json=json, headers=headers, **kwargs)


@pytest.fixture
def logged_in_student(client: FlaskClient, student: User) -> User:
    login(client, student)
    return student


@pytest.fixture
def logged_in_instructor(client: FlaskClient, instructor: User) -> User:
    login(client, instructor)
    return instructor


@pytest.fixture
def logged_in_admin(client: FlaskClient, admin: User) -> User:
    login(client, admin)
    return admin
