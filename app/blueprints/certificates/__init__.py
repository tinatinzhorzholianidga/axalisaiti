from flask import Blueprint

bp = Blueprint("certificates", __name__)

from app.blueprints.certificates import routes  # noqa: E402, F401
