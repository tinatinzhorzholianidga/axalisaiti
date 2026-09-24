"""Public case studies: a filterable list and the article page."""

from __future__ import annotations

from flask import abort, current_app, render_template, request
from flask_babel import get_locale
from flask_babel import gettext as _
from flask_login import current_user

from app.blueprints.cases import bp
from app.forms.cases import CaseFilterForm
from app.services import case_study_service
from app.services.case_study_service import CaseFilters


@bp.route("/")
def index():  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    form = CaseFilterForm(request.args, meta={"csrf": False})
    categories = case_study_service.categories()
    form.category.choices = [("", _("All categories"))] + [
        (c.slug, c.name(locale)) for c in categories
    ]
    filters = CaseFilters(
        query=(form.q.data or "").strip()[:100] or None,
        category=form.category.data or None,
        sort=form.sort.data or "newest",
        page=max(1, request.args.get("page", 1, type=int)),
        per_page=current_app.config["ITEMS_PER_PAGE"],
    )
    pagination = case_study_service.listing(filters, locale)
    return render_template(
        "cases/index.html",
        form=form,
        pagination=pagination,
        categories=categories,
        filters=filters,
        locale=locale,
    )


@bp.route("/<slug>/")
def detail(slug: str):  # type: ignore[no-untyped-def]
    locale = str(get_locale())
    case = case_study_service.get(slug, published_only=False)
    if case is None:
        abort(404)
    if not case.is_published and not (
        current_user.is_authenticated and current_user.has_permission("case_studies.manage")
    ):
        abort(404)
    related = [
        c
        for c in case_study_service.listing(
            CaseFilters(category=case.category.slug if case.category else None, per_page=4), locale
        ).items
        if c.id != case.id
    ][:3]
    return render_template("cases/detail.html", case=case, related=related, locale=locale)
