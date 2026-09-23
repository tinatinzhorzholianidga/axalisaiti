"""Management commands: ``flask create-admin``, ``flask seed-roles`` …"""

from __future__ import annotations

import getpass
import sys

import click
from flask import Flask
from flask.cli import with_appcontext


@click.command("create-admin")
@click.option("--email", prompt=True)
@click.option("--first-name", default="Platform")
@click.option("--last-name", default="Administrator")
@click.option("--password", default=None, help="Omit to be prompted securely.")
@with_appcontext
def create_admin(email: str, first_name: str, last_name: str, password: str | None) -> None:
    """Create (or promote) an administrator account. Safe to rerun."""
    from app.extensions import db
    from app.services.auth_service import find_by_email, validate_password_strength
    from app.services.rbac import assign_role, seed_roles_and_permissions
    from app.services.user_service import create_user

    seed_roles_and_permissions()
    user = find_by_email(email)
    if user:
        if assign_role(user, "admin"):
            db.session.commit()
            click.echo(f"Promoted existing user {email} to admin.")
        else:
            click.echo(f"{email} is already an admin.")
        return
    if password is None:
        password = getpass.getpass("Password (min 12 chars): ")
    problem = validate_password_strength(password)
    if problem:
        click.echo(problem, err=True)
        sys.exit(1)
    create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        roles=["admin", "instructor", "student"],
    )
    click.echo(f"Created admin {email}.")


@click.command("seed-roles")
@with_appcontext
def seed_roles() -> None:
    """Create roles, permissions, default settings, feature flags and achievements."""
    from app.services import achievement_service, feature_flags, settings_service
    from app.services.rbac import seed_roles_and_permissions

    result = seed_roles_and_permissions()
    settings = settings_service.seed_defaults()
    flags = feature_flags.seed_defaults()
    achievements = achievement_service.seed_defaults()
    from app.services.seed_service import seed_categories

    categories = seed_categories()
    click.echo(
        f"Roles: +{result['roles']}, permissions: +{result['permissions']}, "
        f"settings: +{settings}, flags: +{flags}, achievements: +{achievements}, "
        f"categories: +{categories}"
    )


@click.command("seed-demo")
@with_appcontext
def seed_demo() -> None:
    """Load demo categories, instructors and eLearning courses (idempotent)."""
    from app.services.seed_service import seed_demo_content

    summary = seed_demo_content()
    for key, value in summary.items():
        click.echo(f"{key}: {value}")


@click.command("seed-cyberhero")
@click.option(
    "--if-empty",
    is_flag=True,
    help="Only seed when no CyberHero track exists yet, so admin edits are never overwritten.",
)
@with_appcontext
def seed_cyberhero(if_empty: bool) -> None:
    """Load CyberHero tracks, missions, articles and safety resources (idempotent)."""
    from app.services import cyberhero_service
    from app.services.seed_service import seed_cyberhero_content

    if if_empty and cyberhero_service.tracks():
        click.echo(
            "CyberHero content already present; skipping (run without --if-empty to refresh)."
        )
        return
    summary = seed_cyberhero_content()
    for key, value in summary.items():
        click.echo(f"{key}: {value}")


@click.command("check-production")
def check_production() -> None:
    """Validate that the environment is safe for production."""
    from app.config import ProductionConfig

    problems = ProductionConfig.validate()
    if problems:
        click.echo("Production configuration problems:")
        for problem in problems:
            click.echo(f" - {problem}")
        sys.exit(1)
    click.echo("Production configuration OK.")


@click.command("validate-content")
@click.argument("path", default="seeds")
def validate_content(path: str) -> None:
    """Validate seed JSON files (structure, bilingual fields, references)."""
    from app.services.seed_service import validate_seed_files

    errors = validate_seed_files(path)
    if errors:
        for err in errors:
            click.echo(f"ERROR: {err}")
        sys.exit(1)
    click.echo("Seed content OK.")


def register_cli(app: Flask) -> None:
    for command in (
        create_admin,
        seed_roles,
        seed_demo,
        seed_cyberhero,
        check_production,
        validate_content,
    ):
        app.cli.add_command(command)
