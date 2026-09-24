from flask import Blueprint

bp = Blueprint("cases", __name__)

from app.blueprints.cases import routes  # noqa: E402, F401
