from flask import Blueprint

bp = Blueprint("admin", __name__, template_folder="../../templates/admin")

from app.blueprints.admin import (  # noqa: E402, F401
    routes_analytics,
    routes_cases,
    routes_content,
    routes_courses,
    routes_cyberhero,
    routes_dashboard,
    routes_media,
    routes_resources,
    routes_settings,
    routes_users,
)
