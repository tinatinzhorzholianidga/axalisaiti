from flask import Blueprint

bp = Blueprint("discussions", __name__)

from app.blueprints.discussions import routes  # noqa: E402, F401
