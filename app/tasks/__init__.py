"""Celery task modules. Importing this package registers all tasks."""

from app.tasks import mail_tasks, maintenance_tasks  # noqa: F401
