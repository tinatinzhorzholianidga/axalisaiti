"""Temporary minimal course service (replaced in Phase 3)."""

from __future__ import annotations


def featured_courses(limit: int = 6) -> list:
    return []


def active_categories() -> list:
    return []


def public_stats() -> dict:
    return {"courses": 0, "students": 0, "completion": 0}


def public_resources(limit: int = 60) -> list:
    return []
