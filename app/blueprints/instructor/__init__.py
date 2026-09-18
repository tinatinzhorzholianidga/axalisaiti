from flask import Blueprint

bp = Blueprint("instructor", __name__)

from app.blueprints.instructor import routes  # noqa: E402, F401
