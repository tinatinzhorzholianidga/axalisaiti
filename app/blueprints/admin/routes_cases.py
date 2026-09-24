"""Admin: case studies, their categories and the optional section titles."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, locale
from app.forms.cases import (
    CaseCategoryForm,
    CaseImageForm,
    CaseSectionForm,
    CaseStudyForm,
    SectionTitleForm,
)
from app.models import CaseCategory, CaseSectionTitle, CaseStudy, CaseStudyImage, CaseStudySection
from app.services import case_study_service
from app.services.media_service import UploadError
from app.services.rbac import require_permission


def _translations(form: CaseStudyForm) -> dict[str, dict[str, str]]:
    return {
        "ka": {
            "title": form.title_ka.data or "",
            "description": form.description_ka.data or "",
            "about": form.about_ka.data or "",
        },
        "en": {
            "title": form.title_en.data or "",
            "description": form.description_en.data or "",
            "about": form.about_en.data or "",
        },
    }


def _prepare(form: CaseStudyForm) -> None:
    form.category_id.choices = [(0, "—")] + [
        (c.id, c.name(locale())) for c in case_study_service.categories(active_only=False)
    ]


def _fill(form: CaseStudyForm, case: CaseStudy) -> None:
    for loc in ("ka", "en"):
        has = any(t.locale == loc for t in case.translations)
        tr = case.tr(loc) if has else None
        getattr(form, f"title_{loc}").data = tr.title if tr else ""
        getattr(form, f"description_{loc}").data = tr.description if tr else ""
        getattr(form, f"about_{loc}").data = tr.about if tr else ""
    form.slug.data = case.slug
    form.category_id.data = case.category_id or 0
    form.sort_order.data = case.sort_order
    form.is_published.data = case.is_published


# ---- list / create / edit ---------------------------------------------------
@bp.route("/case-studies/")
@require_permission("case_studies.manage")
def case_studies():  # type: ignore[no-untyped-def]
    q = (request.args.get("q") or "").strip()[:100]
    return render_template(
        "admin/cases/index.html",
        items=case_study_service.all_for_admin(q or None),
        q=q,
        locale=locale(),
    )


@bp.route("/case-studies/new", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_study_new():  # type: ignore[no-untyped-def]
    form = CaseStudyForm()
    _prepare(form)
    if form.validate_on_submit():
        try:
            case = case_study_service.create(
                actor=current_user,
                translations=_translations(form),
                category_id=form.category_id.data or None,
                is_published=bool(form.is_published.data),
                slug=form.slug.data or None,
                cover=form.cover.data,
                sort_order=form.sort_order.data or 0,
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Case study created. Add sections and pictures below."), "success")
            return redirect(url_for("admin.case_study_edit", case_id=case.id))
    return render_template(
        "admin/cases/form.html",
        form=form,
        case=None,
        section_form=None,
        image_form=None,
        locale=locale(),
    )


@bp.route("/case-studies/<int:case_id>", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_study_edit(case_id: int):  # type: ignore[no-untyped-def]
    case = get_or_404(CaseStudy, case_id)
    form = CaseStudyForm()
    _prepare(form)
    section_form = CaseSectionForm(prefix="sec")
    section_form.title_id.choices = [
        (t.id, t.name(locale())) for t in case_study_service.section_titles()
    ]
    image_form = CaseImageForm(prefix="img")
    if request.method == "GET":
        _fill(form, case)
    if form.submit.data and form.validate_on_submit():
        try:
            case_study_service.update(
                case,
                actor=current_user,
                translations=_translations(form),
                category_id=form.category_id.data or None,
                is_published=bool(form.is_published.data),
                slug=form.slug.data or None,
                cover=form.cover.data,
                sort_order=form.sort_order.data or 0,
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Case study saved."), "success")
            return redirect(url_for("admin.case_study_edit", case_id=case.id))
    return render_template(
        "admin/cases/form.html",
        form=form,
        case=case,
        section_form=section_form,
        image_form=image_form,
        locale=locale(),
    )


@bp.route("/case-studies/<int:case_id>/delete", methods=["POST"])
@require_permission("case_studies.manage")
def case_study_delete(case_id: int):  # type: ignore[no-untyped-def]
    case = get_or_404(CaseStudy, case_id)
    case_study_service.delete(case, actor=current_user)
    flash(_("Case study deleted."), "info")
    return redirect(url_for("admin.case_studies"))


# ---- sections ---------------------------------------------------------------
@bp.route("/case-studies/<int:case_id>/sections", methods=["POST"])
@require_permission("case_studies.manage")
def case_section_add(case_id: int):  # type: ignore[no-untyped-def]
    case = get_or_404(CaseStudy, case_id)
    form = CaseSectionForm(prefix="sec")
    form.title_id.choices = [(t.id, t.name(locale())) for t in case_study_service.section_titles()]
    if form.validate_on_submit():
        try:
            case_study_service.add_section(
                case,
                title_id=form.title_id.data,
                body_ka=form.body_ka.data or "",
                body_en=form.body_en.data or "",
                actor=current_user,
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Section added."), "success")
    else:
        flash(_("Choose a section title."), "error")
    return redirect(url_for("admin.case_study_edit", case_id=case.id) + "#sections")


def _section(case_id: int, section_id: int) -> CaseStudySection:
    section = get_or_404(CaseStudySection, section_id)
    if section.case_study_id != case_id:
        abort(404)
    return section


@bp.route("/case-studies/<int:case_id>/sections/<int:section_id>", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_section_edit(case_id: int, section_id: int):  # type: ignore[no-untyped-def]
    section = _section(case_id, section_id)
    form = CaseSectionForm()
    form.title_id.choices = [(t.id, t.name(locale())) for t in case_study_service.section_titles()]
    if request.method == "GET":
        form.title_id.data = section.title_id
        form.body_ka.data = section.body_ka
        form.body_en.data = section.body_en
    if form.validate_on_submit():
        case_study_service.update_section(
            section,
            title_id=form.title_id.data,
            body_ka=form.body_ka.data or "",
            body_en=form.body_en.data or "",
            actor=current_user,
        )
        flash(_("Section saved."), "success")
        return redirect(url_for("admin.case_study_edit", case_id=case_id) + "#sections")
    return render_template(
        "admin/cases/section_form.html", form=form, section=section, locale=locale()
    )


@bp.route("/case-studies/<int:case_id>/sections/<int:section_id>/<action>", methods=["POST"])
@require_permission("case_studies.manage")
def case_section_action(case_id: int, section_id: int, action: str):  # type: ignore[no-untyped-def]
    section = _section(case_id, section_id)
    if action == "delete":
        case_study_service.delete_section(section, actor=current_user)
        flash(_("Section deleted."), "info")
    elif action in {"up", "down"}:
        case_study_service.move_section(section, action)
    else:
        abort(404)
    return redirect(url_for("admin.case_study_edit", case_id=case_id) + "#sections")


# ---- images -----------------------------------------------------------------
@bp.route("/case-studies/<int:case_id>/images", methods=["POST"])
@require_permission("case_studies.manage")
def case_image_add(case_id: int):  # type: ignore[no-untyped-def]
    case = get_or_404(CaseStudy, case_id)
    form = CaseImageForm(prefix="img")
    if form.validate_on_submit():
        try:
            case_study_service.add_image(
                case,
                form.file.data,
                caption_ka=form.caption_ka.data or "",
                caption_en=form.caption_en.data or "",
                actor=current_user,
            )
        except UploadError as exc:
            flash(str(exc), "error")
        else:
            flash(_("Image added."), "success")
    return redirect(url_for("admin.case_study_edit", case_id=case.id) + "#images")


@bp.route("/case-studies/<int:case_id>/images/<int:image_id>/delete", methods=["POST"])
@require_permission("case_studies.manage")
def case_image_delete(case_id: int, image_id: int):  # type: ignore[no-untyped-def]
    image = get_or_404(CaseStudyImage, image_id)
    if image.case_study_id != case_id:
        abort(404)
    case_study_service.delete_image(image, actor=current_user)
    flash(_("Image removed."), "info")
    return redirect(url_for("admin.case_study_edit", case_id=case_id) + "#images")


# ---- categories -------------------------------------------------------------
def _category_translations(form: CaseCategoryForm) -> dict[str, dict[str, str]]:
    return {
        "ka": {"name": form.name_ka.data or "", "description": form.description_ka.data or ""},
        "en": {"name": form.name_en.data or "", "description": form.description_en.data or ""},
    }


@bp.route("/case-studies/categories/", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_categories():  # type: ignore[no-untyped-def]
    form = CaseCategoryForm()
    if form.validate_on_submit():
        case_study_service.create_category(
            slug=form.slug.data,
            translations=_category_translations(form),
            actor=current_user,
            icon=form.icon.data or "alert-triangle",
            color=form.color.data,
            sort_order=form.sort_order.data or 0,
            is_active=bool(form.is_active.data),
        )
        flash(_("Category created."), "success")
        return redirect(url_for("admin.case_categories"))
    return render_template(
        "admin/cases/categories.html",
        items=case_study_service.categories(active_only=False),
        form=form,
        locale=locale(),
    )


@bp.route("/case-studies/categories/<int:category_id>", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_category_edit(category_id: int):  # type: ignore[no-untyped-def]
    category = get_or_404(CaseCategory, category_id)
    form = CaseCategoryForm()
    if request.method == "GET":
        has_en = any(t.locale == "en" for t in category.translations)
        form.slug.data = category.slug
        form.name_ka.data = category.name("ka")
        form.name_en.data = category.text("name", "en") if has_en else ""
        form.description_ka.data = category.text("description", "ka")
        form.description_en.data = category.text("description", "en") if has_en else ""
        form.icon.data = category.icon
        form.color.data = category.color
        form.sort_order.data = category.sort_order
        form.is_active.data = category.is_active
    if form.validate_on_submit():
        case_study_service.update_category(
            category,
            _category_translations(form),
            actor=current_user,
            icon=form.icon.data or "alert-triangle",
            color=form.color.data,
            sort_order=form.sort_order.data or 0,
            is_active=bool(form.is_active.data),
        )
        flash(_("Category saved."), "success")
        return redirect(url_for("admin.case_categories"))
    return render_template(
        "admin/cases/category_form.html", form=form, category=category, locale=locale()
    )


@bp.route("/case-studies/categories/<int:category_id>/delete", methods=["POST"])
@require_permission("case_studies.manage")
def case_category_delete(category_id: int):  # type: ignore[no-untyped-def]
    category = get_or_404(CaseCategory, category_id)
    case_study_service.delete_category(category, actor=current_user)
    flash(_("Category deleted."), "info")
    return redirect(url_for("admin.case_categories"))


# ---- section titles ---------------------------------------------------------
@bp.route("/case-studies/section-titles/", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_section_titles():  # type: ignore[no-untyped-def]
    form = SectionTitleForm()
    if form.validate_on_submit():
        case_study_service.create_section_title(
            name_ka=form.name_ka.data,
            name_en=form.name_en.data or "",
            sort_order=form.sort_order.data or 0,
            actor=current_user,
        )
        flash(_("Section title created."), "success")
        return redirect(url_for("admin.case_section_titles"))
    return render_template(
        "admin/cases/section_titles.html",
        items=case_study_service.section_titles(active_only=False),
        form=form,
        locale=locale(),
    )


@bp.route("/case-studies/section-titles/<int:title_id>", methods=["GET", "POST"])
@require_permission("case_studies.manage")
def case_section_title_edit(title_id: int):  # type: ignore[no-untyped-def]
    title = get_or_404(CaseSectionTitle, title_id)
    form = SectionTitleForm(obj=title)
    if form.validate_on_submit():
        case_study_service.update_section_title(
            title,
            actor=current_user,
            name_ka=form.name_ka.data,
            name_en=form.name_en.data or "",
            sort_order=form.sort_order.data or 0,
            is_active=bool(form.is_active.data),
        )
        flash(_("Section title saved."), "success")
        return redirect(url_for("admin.case_section_titles"))
    return render_template(
        "admin/cases/section_title_form.html", form=form, title=title, locale=locale()
    )


@bp.route("/case-studies/section-titles/<int:title_id>/delete", methods=["POST"])
@require_permission("case_studies.manage")
def case_section_title_delete(title_id: int):  # type: ignore[no-untyped-def]
    title = get_or_404(CaseSectionTitle, title_id)
    case_study_service.delete_section_title(title, actor=current_user)
    flash(_("Section title deleted."), "info")
    return redirect(url_for("admin.case_section_titles"))
