"""Case studies: categories, section titles, the articles themselves, listing and home picks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask_babel import gettext as _
from sqlalchemy import func, or_, select
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    CaseCategory,
    CaseCategoryTranslation,
    CaseSectionTitle,
    CaseStudy,
    CaseStudyImage,
    CaseStudySection,
    CaseStudyTranslation,
    MediaKind,
    User,
)
from app.models.base import utcnow
from app.repositories.ordering import newest_first
from app.services import audit_service, media_service, settings_service
from app.services.course_service import _apply_translations, unique_slug
from app.services.media_service import UploadError
from app.services.sanitize import sanitize_html

LOCALES = ("ka", "en")
HTML_FIELDS = ("description", "about")

# shipped with the platform; admins add more in the panel
DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {
        "slug": "ongoing-threats",
        "ka": "მიმდინარე საფრთხეები",
        "en": "Ongoing threats",
        "icon": "alert-triangle",
        "color": "purple",
    },
]
DEFAULT_SECTION_TITLES: list[tuple[str, str]] = [
    ("ფრთხილად იყავით", "Be careful of"),
    ("როგორ ამოვიცნოთ", "How to identify"),
]


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------
def seed_defaults() -> dict[str, int]:
    created = {"case_categories": 0, "case_section_titles": 0}
    for i, data in enumerate(DEFAULT_CATEGORIES, start=1):
        if category_by_slug(data["slug"], active_only=False) is None:
            create_category(
                slug=data["slug"],
                translations={"ka": {"name": data["ka"]}, "en": {"name": data["en"]}},
                icon=data["icon"],
                color=data["color"],
                sort_order=i,
            )
            created["case_categories"] += 1
    existing = {t.name_ka for t in section_titles(active_only=False)}
    for i, (ka, en) in enumerate(DEFAULT_SECTION_TITLES, start=1):
        if ka not in existing:
            create_section_title(name_ka=ka, name_en=en, sort_order=i)
            created["case_section_titles"] += 1
    return created


# ---------------------------------------------------------------------------
# categories
# ---------------------------------------------------------------------------
def categories(*, active_only: bool = True) -> list[CaseCategory]:
    stmt = select(CaseCategory).order_by(CaseCategory.sort_order, CaseCategory.id)
    if active_only:
        stmt = stmt.where(CaseCategory.is_active.is_(True))
    return list(db.session.execute(stmt).scalars())


def category_by_slug(slug: str, *, active_only: bool = True) -> CaseCategory | None:
    stmt = select(CaseCategory).where(CaseCategory.slug == slug)
    if active_only:
        stmt = stmt.where(CaseCategory.is_active.is_(True))
    return db.session.execute(stmt).scalar_one_or_none()


def create_category(
    *, slug: str, translations: dict, actor: User | None = None, **fields: Any
) -> CaseCategory:
    category = CaseCategory(slug=unique_slug(slug, CaseCategory))
    for key, value in fields.items():
        if hasattr(category, key):
            setattr(category, key, value)
    db.session.add(category)
    db.session.flush()
    _apply_translations(category, CaseCategoryTranslation, "category_id", translations)
    audit_service.record("case_category.created", target=category, actor=actor)
    db.session.commit()
    return category


def update_category(
    category: CaseCategory, translations: dict, *, actor: User, **fields: Any
) -> CaseCategory:
    for key, value in fields.items():
        if hasattr(category, key):
            setattr(category, key, value)
    _apply_translations(category, CaseCategoryTranslation, "category_id", translations)
    audit_service.record("case_category.updated", target=category, actor=actor)
    db.session.commit()
    return category


def delete_category(category: CaseCategory, *, actor: User) -> None:
    # case studies keep existing without a category (FK SET NULL)
    audit_service.record("case_category.deleted", target=category, actor=actor)
    db.session.delete(category)
    db.session.commit()


# ---------------------------------------------------------------------------
# section titles
# ---------------------------------------------------------------------------
def section_titles(*, active_only: bool = True) -> list[CaseSectionTitle]:
    stmt = select(CaseSectionTitle).order_by(CaseSectionTitle.sort_order, CaseSectionTitle.id)
    if active_only:
        stmt = stmt.where(CaseSectionTitle.is_active.is_(True))
    return list(db.session.execute(stmt).scalars())


def create_section_title(
    *, name_ka: str, name_en: str = "", sort_order: int = 0, actor: User | None = None
) -> CaseSectionTitle:
    title = CaseSectionTitle(name_ka=name_ka, name_en=name_en or "", sort_order=sort_order)
    db.session.add(title)
    db.session.flush()
    audit_service.record("case_section_title.created", target=title, actor=actor)
    db.session.commit()
    return title


def update_section_title(title: CaseSectionTitle, *, actor: User, **fields: Any) -> None:
    for key, value in fields.items():
        if hasattr(title, key):
            setattr(title, key, value if value is not None else "")
    audit_service.record("case_section_title.updated", target=title, actor=actor)
    db.session.commit()


def delete_section_title(title: CaseSectionTitle, *, actor: User) -> None:
    audit_service.record("case_section_title.deleted", target=title, actor=actor)
    db.session.delete(title)
    db.session.commit()


# ---------------------------------------------------------------------------
# case studies
# ---------------------------------------------------------------------------
@dataclass
class CaseFilters:
    query: str | None = None
    category: str | None = None
    sort: str = "newest"
    page: int = 1
    per_page: int = 12


def published_query():  # type: ignore[no-untyped-def]
    return select(CaseStudy).where(CaseStudy.is_published.is_(True))


def get(slug: str, *, published_only: bool = True) -> CaseStudy | None:
    stmt = select(CaseStudy).where(CaseStudy.slug == slug)
    if published_only:
        stmt = stmt.where(CaseStudy.is_published.is_(True))
    return db.session.execute(stmt).scalar_one_or_none()


def listing(filters: CaseFilters, locale: str = "ka"):  # type: ignore[no-untyped-def]
    stmt = published_query()
    if filters.query:
        like = f"%{filters.query.lower()}%"
        matches = (
            select(CaseStudyTranslation.case_study_id)
            .where(
                or_(
                    func.lower(CaseStudyTranslation.title).like(like),
                    func.lower(CaseStudyTranslation.description).like(like),
                )
            )
            .scalar_subquery()
        )
        stmt = stmt.where(CaseStudy.id.in_(matches))
    if filters.category:
        stmt = stmt.join(CaseCategory).where(CaseCategory.slug == filters.category)
    if filters.sort == "title":
        title = (
            select(CaseStudyTranslation.title)
            .where(
                CaseStudyTranslation.case_study_id == CaseStudy.id,
                CaseStudyTranslation.locale == locale,
            )
            .scalar_subquery()
        )
        stmt = stmt.order_by(title, CaseStudy.id)
    elif filters.sort == "oldest":
        stmt = stmt.order_by(CaseStudy.published_at.asc(), CaseStudy.id)
    else:
        stmt = stmt.order_by(*newest_first(CaseStudy.published_at), CaseStudy.id.desc())
    return db.paginate(stmt, page=filters.page, per_page=filters.per_page, error_out=False)


def all_for_admin(query: str | None = None) -> list[CaseStudy]:
    stmt = select(CaseStudy).order_by(CaseStudy.updated_at.desc())
    if query:
        like = f"%{query.lower()}%"
        matches = (
            select(CaseStudyTranslation.case_study_id)
            .where(func.lower(CaseStudyTranslation.title).like(like))
            .scalar_subquery()
        )
        stmt = stmt.where(or_(CaseStudy.id.in_(matches), func.lower(CaseStudy.slug).like(like)))
    return list(db.session.execute(stmt).scalars())


def _set_publication(case: CaseStudy, is_published: bool) -> None:
    case.is_published = bool(is_published)
    if case.is_published and case.published_at is None:
        case.published_at = utcnow()


def create(
    *,
    actor: User,
    translations: dict[str, dict[str, Any]],
    category_id: int | None,
    is_published: bool = False,
    slug: str | None = None,
    cover: FileStorage | None = None,
    sort_order: int = 0,
) -> CaseStudy:
    title = (
        translations.get("ka", {}).get("title")
        or translations.get("en", {}).get("title")
        or "case-study"
    )
    case = CaseStudy(
        slug=unique_slug(slug or title, CaseStudy),
        category_id=category_id,
        created_by_id=actor.id,
        sort_order=sort_order,
    )
    _set_publication(case, is_published)
    db.session.add(case)
    db.session.flush()
    _apply_translations(
        case, CaseStudyTranslation, "case_study_id", translations, html_fields=HTML_FIELDS
    )
    set_cover(case, cover, actor)
    audit_service.record("case_study.created", target=case, actor=actor)
    db.session.commit()
    return case


def update(
    case: CaseStudy,
    *,
    actor: User,
    translations: dict[str, dict[str, Any]],
    category_id: int | None,
    is_published: bool,
    slug: str | None = None,
    cover: FileStorage | None = None,
    sort_order: int = 0,
) -> CaseStudy:
    if slug and slug != case.slug:
        case.slug = unique_slug(slug, CaseStudy, exclude_id=case.id)
    case.category_id = category_id
    case.sort_order = sort_order
    _set_publication(case, is_published)
    _apply_translations(
        case, CaseStudyTranslation, "case_study_id", translations, html_fields=HTML_FIELDS
    )
    set_cover(case, cover, actor)
    audit_service.record("case_study.updated", target=case, actor=actor)
    db.session.commit()
    return case


def set_cover(case: CaseStudy, file: FileStorage | None, actor: User) -> None:
    if file and file.filename:
        media = media_service.save_upload(
            file,
            kind=MediaKind.IMAGE,
            uploader=actor,
            is_public=True,
            alt_text=case.title("en") or case.slug,
        )
        case.cover_media_id = media.id


def delete(case: CaseStudy, *, actor: User) -> None:
    audit_service.record("case_study.deleted", target=case, actor=actor, meta={"slug": case.slug})
    db.session.delete(case)
    db.session.commit()


# ---- sections ---------------------------------------------------------------
def add_section(
    case: CaseStudy, *, title_id: int | None, body_ka: str, body_en: str, actor: User
) -> CaseStudySection:
    if title_id is not None and db.session.get(CaseSectionTitle, title_id) is None:
        raise UploadError(_("Choose a section title."))
    section = CaseStudySection(
        case_study_id=case.id,
        title_id=title_id,
        sort_order=len(case.sections) + 1,
        body_ka=sanitize_html(body_ka or ""),
        body_en=sanitize_html(body_en or ""),
    )
    case.sections.append(section)
    db.session.flush()
    audit_service.record("case_study.section_added", target=case, actor=actor)
    db.session.commit()
    return section


def update_section(
    section: CaseStudySection, *, title_id: int | None, body_ka: str, body_en: str, actor: User
) -> None:
    section.title_id = title_id
    section.body_ka = sanitize_html(body_ka or "")
    section.body_en = sanitize_html(body_en or "")
    audit_service.record("case_study.section_updated", target=section.case_study, actor=actor)
    db.session.commit()


def delete_section(section: CaseStudySection, *, actor: User) -> None:
    case = section.case_study
    case.sections.remove(section)
    for i, item in enumerate(case.sections, start=1):
        item.sort_order = i
    audit_service.record("case_study.section_deleted", target=case, actor=actor)
    db.session.commit()


def move_section(section: CaseStudySection, direction: str) -> None:
    case = section.case_study
    items = list(case.sections)
    index = items.index(section)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(items):
        items[index], items[other] = items[other], items[index]
        for i, item in enumerate(items, start=1):
            item.sort_order = i
        db.session.commit()


# ---- images -----------------------------------------------------------------
def add_image(
    case: CaseStudy, file: FileStorage | None, *, caption_ka: str, caption_en: str, actor: User
) -> CaseStudyImage:
    if not file or not file.filename:
        raise UploadError(_("No file selected."))
    media = media_service.save_upload(
        file, kind=MediaKind.IMAGE, uploader=actor, is_public=True, alt_text=caption_ka or ""
    )
    image = CaseStudyImage(
        case_study_id=case.id,
        media_id=media.id,
        sort_order=len(case.images) + 1,
        caption_ka=caption_ka or "",
        caption_en=caption_en or "",
    )
    case.images.append(image)
    db.session.flush()
    audit_service.record("case_study.image_added", target=case, actor=actor)
    db.session.commit()
    return image


def delete_image(image: CaseStudyImage, *, actor: User) -> None:
    case = image.case_study
    media = image.media
    case.images.remove(image)
    db.session.flush()
    media_service.delete_media(media, actor=actor)
    audit_service.record("case_study.image_deleted", target=case, actor=actor)
    db.session.commit()


# ---------------------------------------------------------------------------
# public helpers
# ---------------------------------------------------------------------------
def count_published() -> int:
    return int(
        db.session.execute(
            select(func.count()).select_from(published_query().subquery())
        ).scalar_one()
    )


def count_in_category(slug: str) -> int:
    stmt = published_query().join(CaseCategory).where(CaseCategory.slug == slug)
    return int(db.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())


def home_category_slug() -> str:
    return str(settings_service.get("site.home_threats_category", "ongoing-threats") or "").strip()


def home_picks(limit: int | None = None) -> list[CaseStudy]:
    """Newest published case studies of the home page category."""
    slug = home_category_slug()
    if limit is None:
        limit = int(settings_service.get("site.home_threats_limit", 4) or 4)
    if not slug:
        return []
    stmt = (
        published_query()
        .join(CaseCategory)
        .where(CaseCategory.slug == slug)
        .order_by(*newest_first(CaseStudy.published_at), CaseStudy.id.desc())
        .limit(max(1, limit))
    )
    return list(db.session.execute(stmt).scalars())


def search(query: str, locale: str = "ka", limit: int = 10) -> list[CaseStudy]:
    return list(listing(CaseFilters(query=query, per_page=limit), locale).items)
