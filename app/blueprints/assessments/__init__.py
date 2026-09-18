from flask import Blueprint

bp = Blueprint("assessments", __name__)

from app.blueprints.assessments import routes  # noqa: E402, F401
