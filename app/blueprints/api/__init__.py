from flask import Blueprint

bp = Blueprint("api", __name__)

from app.blueprints.api import routes, routes_cyberhero  # noqa: E402, F401
