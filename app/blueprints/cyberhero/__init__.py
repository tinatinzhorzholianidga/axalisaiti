from flask import Blueprint

bp = Blueprint("cyberhero", __name__)

from app.blueprints.cyberhero import routes  # noqa: E402, F401
