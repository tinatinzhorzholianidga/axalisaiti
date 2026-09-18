"""Alembic migrations must build the same schema the models describe."""

from __future__ import annotations

import tempfile

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from app import create_app
from app.extensions import db


def test_migrations_match_models(upload_dir):  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(
            "testing",
            overrides={
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp}/mig.sqlite3",
                "UPLOAD_PATH": upload_dir,
            },
        )
        with app.app_context():
            upgrade()
            with db.engine.connect() as connection:
                context = MigrationContext.configure(
                    connection, opts={"compare_type": True, "render_as_batch": True}
                )
                diff = compare_metadata(context, db.metadata)
            assert diff == [], diff
            db.session.remove()
