"""Portable ORDER BY helpers.

MariaDB/MySQL have no ``NULLS LAST`` syntax: SQLAlchemy emits it verbatim and
the server rejects the whole statement (the learner dashboard and profile
pages 500 on it). "Newest first, never-set last" is therefore expressed with
an ``IS NULL`` sort key that SQLite, MariaDB and PostgreSQL all understand.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.sql import ColumnElement


def newest_first(column: Any) -> tuple[ColumnElement[Any], ColumnElement[Any]]:
    """Sort key equivalent to ``column DESC NULLS LAST``.

    Use it unpacked: ``stmt.order_by(*newest_first(Model.column), ...)``.
    ``column IS NULL`` sorts as 0/1 (false/true), so rows with a value come
    first, newest on top, and rows without one trail behind.
    """
    return column.is_(None), column.desc()
