"""Celery integration: tasks run inside the Flask application context."""

from __future__ import annotations

from celery import Celery, Task
from flask import Flask

celery = Celery("elearning")


def init_celery(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask  # type: ignore[misc]
    celery.config_from_object(app.config["CELERY"])
    celery.set_default()
    app.extensions["celery"] = celery

    # Import task modules so they register with the worker.
    from app import tasks  # noqa: F401

    return celery
