from flask import Blueprint

bp = Blueprint("learning", __name__)

from app.blueprints.learning import routes  # noqa: E402, F401
