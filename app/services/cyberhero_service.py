"""CyberHero content: seeding from JSON, serialisation for the React app,
progress synchronisation and certificates.

Serialisers return the *original* CyberHero data-module shapes (bilingual
leaves ``{"en": …, "ka": …}``) so the React components render unchanged.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask_babel import gettext as _
from sqlalchemy import select

from app.config import BASE_DIR
from app.extensions import db
from app.models import (
    Course,
    CourseStatus,
    CourseTranslation,
    CyberAgreementClause,
    CyberAgreementSection,
    CyberBranch,
    CyberBranchChoice,
    CyberBranchMessage,
    CyberCertificate,
    CyberKnowledgeChunk,
    CyberKnowledgeSection,
    CyberMascotReaction,
    CyberMascotTip,
    CyberMission,
    CyberMissionNote,
    CyberMissionRound,
    CyberProgress,
    CyberRoundItem,
    CyberSafetyResource,
    CyberTrack,
    Difficulty,
    Lesson,
    LessonProgress,
    LessonTranslation,
    LessonType,
    Module,
    ModuleTranslation,
    Platform,
    ProgressStatus,
    User,
    utcnow,
)
from app.services import audit_service
from app.services.sanitize import sanitize_html

SEED_DIR = BASE_DIR / "seeds" / "cyberhero"
LOCALES = ("ka", "en")
CERT_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class CyberHeroError(Exception):
    pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _ka(node: Any) -> str:
    return (node or {}).get("ka", "") if isinstance(node, dict) else ""


def _en(node: Any) -> str:
    return (node or {}).get("en", "") if isinstance(node, dict) else ""


def _lines(node: Any, locale: str) -> str:
    values = (node or {}).get(locale, []) if isinstance(node, dict) else []
    return "\n".join(str(v) for v in values)


def _pair(ka: str, en: str) -> dict[str, str]:
    return {"en": en or "", "ka": ka or ""}


def _pair_or_none(ka: str, en: str) -> dict[str, str] | None:
    return _pair(ka, en) if (ka or en) else None


def load_seed(name: str, seed_dir: Path | None = None) -> Any:
    path = (seed_dir or SEED_DIR) / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _set_bilingual(obj: Any, field: str, node: Any) -> None:
    setattr(obj, f"{field}_ka", _ka(node))
    setattr(obj, f"{field}_en", _en(node))


def _upsert(model: type, **key: Any) -> tuple[Any, bool]:
    obj = db.session.execute(select(model).filter_by(**key)).scalar_one_or_none()
    if obj is None:
        obj = model(**key)
        db.session.add(obj)
        return obj, True
    return obj, False


# ---------------------------------------------------------------------------
# seeding
# ---------------------------------------------------------------------------
def seed_tracks(data: dict) -> int:
    created = 0
    for tier in data["tiers"]:
        track, is_new = _upsert(CyberTrack, slug=tier["id"])
        created += int(is_new)
        track.sort_order = tier.get("sort_order", 0)
        track.emoji = tier.get("emoji", "🛡️")
        track.color = tier.get("color", "blue")
        track.audience = tier.get("audience", "kids")
        track.route = tier.get("route")
        track.is_active = bool(tier.get("active"))
        track.is_featured = bool(tier.get("active"))
        track.certificate_enabled = tier["id"] == "guardians"
        for field in ("tag", "name", "desc", "intro"):
            _set_bilingual(track, field, tier.get(field))
        track.topics_ka = _lines(tier.get("topics"), "ka")
        track.topics_en = _lines(tier.get("topics"), "en")
    db.session.flush()
    return created


def _build_round(mission: CyberMission, index: int, data: dict) -> CyberMissionRound:
    rtype = data["type"]
    rnd = CyberMissionRound(mission_id=mission.id, sort_order=index, round_type=rtype)
    if rtype == "choice":
        _set_bilingual(rnd, "prompt", data.get("q"))
        _set_bilingual(rnd, "explain", data.get("explain"))
        card = data.get("card") or {}
        _set_bilingual(rnd, "card_from", card.get("from"))
        _set_bilingual(rnd, "card_meta", card.get("meta"))
        _set_bilingual(rnd, "card_body", card.get("body"))
        for i, opt in enumerate(data.get("options", []), start=1):
            item = CyberRoundItem(sort_order=i, is_correct=bool(opt.get("correct")))
            _set_bilingual(item, "label", opt.get("label"))
            rnd.items.append(item)
    elif rtype == "flags":
        _set_bilingual(rnd, "prompt", data.get("prompt"))
        _set_bilingual(rnd, "explain", data.get("explain"))
        for i, it in enumerate(data.get("items", []), start=1):
            item = CyberRoundItem(sort_order=i, is_correct=bool(it.get("flag")))
            _set_bilingual(item, "label", it.get("text"))
            _set_bilingual(item, "from", it.get("from"))
            _set_bilingual(item, "explain", it.get("explain"))
            rnd.items.append(item)
    elif rtype == "builder":
        _set_bilingual(rnd, "prompt", data.get("prompt"))
        _set_bilingual(rnd, "explain", data.get("explain"))
        _set_bilingual(rnd, "explain_negative", data.get("explainNegative"))
        _set_bilingual(rnd, "meter_low", data.get("meterLow"))
        _set_bilingual(rnd, "meter_high", data.get("meterHigh"))
        rnd.target = int(data.get("target") or 0)
        for i, opt in enumerate(data.get("options", []), start=1):
            item = CyberRoundItem(sort_order=i, value=int(opt.get("value") or 0))
            _set_bilingual(item, "label", opt.get("label"))
            _set_bilingual(item, "note", opt.get("note"))
            rnd.items.append(item)
    elif rtype == "branch":
        rnd.branch_start_key = data.get("start")
        rnd.branch_max = int(data.get("max") or 0)
        for i, (key, node) in enumerate(data.get("nodes", {}).items(), start=1):
            branch = CyberBranch(key=key, sort_order=i, is_end=bool(node.get("end")))
            _set_bilingual(branch, "scene", node.get("scene"))
            for j, msg in enumerate(node.get("chat", []), start=1):
                message = CyberBranchMessage(sort_order=j)
                _set_bilingual(message, "name", msg.get("name"))
                _set_bilingual(message, "text", msg.get("text"))
                branch.messages.append(message)
            for j, ch in enumerate(node.get("choices", []), start=1):
                choice = CyberBranchChoice(
                    sort_order=j, next_key=ch.get("next"), points=int(ch.get("points") or 0)
                )
                _set_bilingual(choice, "label", ch.get("label"))
                _set_bilingual(choice, "feedback", ch.get("feedback"))
                branch.choices.append(choice)
            rnd.branches.append(branch)
    else:
        raise CyberHeroError(f"unknown round type {rtype!r} in mission {mission.slug}")
    return rnd


def seed_missions(data: list[dict]) -> int:
    created = 0
    tracks = {t.slug: t for t in db.session.execute(select(CyberTrack)).scalars()}
    for m in data:
        track = tracks.get(m.get("track", "guardians"))
        if track is None:
            raise CyberHeroError(f"mission {m['id']} references unknown track {m.get('track')}")
        mission, is_new = _upsert(CyberMission, slug=m["id"])
        created += int(is_new)
        mission.track_id = track.id
        mission.sort_order = int(m.get("order") or 0)
        mission.emoji = m.get("emoji", "⭐")
        mission.color = m.get("color", "blue")
        mission.article_code = m.get("article")
        mission.topics = ",".join(m.get("topics", []))
        mission.is_priority = bool(m.get("priority"))
        mission.is_sensitive = bool(m.get("sensitive"))
        mission.is_final = bool(m.get("final"))
        mission.timer_seconds = m.get("timer")
        mission.pass_ratio = m.get("passRatio")
        for field in ("name", "desc", "brief"):
            _set_bilingual(mission, field, m.get(field))
        _set_bilingual(mission, "help_strip", m.get("helpStrip"))
        db.session.flush()
        mission.notes.clear()
        mission.rounds.clear()
        db.session.flush()
        for i, note in enumerate(m.get("theory", []), start=1):
            mission.notes.append(
                CyberMissionNote(kind="theory", sort_order=i, text_ka=_ka(note), text_en=_en(note))
            )
        for i, note in enumerate(m.get("takeaways", []), start=1):
            mission.notes.append(
                CyberMissionNote(
                    kind="takeaway", sort_order=i, text_ka=_ka(note), text_en=_en(note)
                )
            )
        for i, rnd in enumerate(m.get("rounds", []), start=1):
            mission.rounds.append(_build_round(mission, i, rnd))
    db.session.flush()
    return created


def seed_agreement(data: dict) -> int:
    resource, is_new = _upsert(CyberSafetyResource, slug="family-media-agreement")
    resource.kind = "family_agreement"
    resource.emoji = "📝"
    resource.color = "amber"
    resource.is_verified = True
    _set_bilingual(resource, "title", data.get("title"))
    _set_bilingual(resource, "summary", data.get("sub"))
    sigs = data.get("signatures", {})
    resource.steps_ka = "\n".join(_ka(sigs.get(k)) for k in ("child", "parent", "date"))
    resource.steps_en = "\n".join(_en(sigs.get(k)) for k in ("child", "parent", "date"))
    db.session.flush()
    resource.sections.clear()
    for i, section in enumerate(data.get("sections", []), start=1):
        row = CyberAgreementSection(sort_order=i, write_lines=int(section.get("writeLines") or 0))
        _set_bilingual(row, "title", section.get("title"))
        for j, clause in enumerate(section.get("clauses", []), start=1):
            row.clauses.append(
                CyberAgreementClause(sort_order=j, text_ka=_ka(clause), text_en=_en(clause))
            )
        resource.sections.append(row)
    db.session.flush()
    return int(is_new)


def seed_resources(data: list[dict]) -> int:
    created = 0
    for r in data:
        resource, is_new = _upsert(CyberSafetyResource, slug=r["slug"])
        created += int(is_new)
        resource.kind = r["kind"]
        resource.sort_order = int(r.get("sort_order") or 0)
        resource.emoji = r.get("emoji", "🆘")
        resource.color = r.get("color", "amber")
        resource.contact_value = r.get("contact_value", "")
        resource.is_verified = bool(r.get("is_verified"))
        for field in ("title", "summary"):
            _set_bilingual(resource, field, r.get(field))
        resource.body_ka = sanitize_html(_ka(r.get("body")))
        resource.body_en = sanitize_html(_en(r.get("body")))
        resource.steps_ka = _lines(r.get("steps"), "ka")
        resource.steps_en = _lines(r.get("steps"), "en")
    db.session.flush()
    return created


def seed_mascot(data: dict) -> int:
    db.session.query(CyberMascotTip).delete()
    db.session.query(CyberMascotReaction).delete()
    count = 0
    for i, tip in enumerate(data.get("tips", []), start=1):
        db.session.add(
            CyberMascotTip(
                sort_order=i,
                topics=",".join(tip.get("topics", [])),
                text_ka=tip["ka"],
                text_en=tip["en"],
            )
        )
        count += 1
    for key, value in data.get("reactions", {}).items():
        entries = value if isinstance(value, list) else [value]
        for i, entry in enumerate(entries, start=1):
            db.session.add(
                CyberMascotReaction(key=key, sort_order=i, text_ka=_ka(entry), text_en=_en(entry))
            )
            count += 1
    db.session.flush()
    return count


def seed_knowledge(data: dict) -> int:
    db.session.query(CyberKnowledgeSection).delete()
    count = 0
    for i, section in enumerate(data.get("sections", []), start=1):
        row = CyberKnowledgeSection(
            sort_order=i, title_ka=section.get("ka", ""), title_en=section.get("en", "")
        )
        for j, chunk in enumerate(section.get("chunks", []), start=1):
            text = str(chunk).strip()
            if text:
                row.chunks.append(CyberKnowledgeChunk(sort_order=j, text=text))
                count += 1
        db.session.add(row)
    db.session.flush()
    return count


def seed_courses(data: list[dict], actor: User | None = None) -> int:
    """CyberHero courses reuse the shared Course/Module/Lesson models."""
    created = 0
    tracks = {t.slug: t for t in db.session.execute(select(CyberTrack)).scalars()}
    for c in data:
        course, is_new = _upsert(Course, slug=c["slug"])
        created += int(is_new)
        course.platform = Platform.CYBERHERO
        course.status = CourseStatus.PUBLISHED
        course.published_at = course.published_at or utcnow()
        course.cyber_track_id = tracks[c["track"]].id if c.get("track") in tracks else None
        course.icon = c.get("emoji", "🛡️")
        course.color = c.get("color", "blue")
        course.difficulty = Difficulty(c.get("difficulty", "beginner"))
        course.estimated_minutes = int(c.get("estimated_minutes") or 0)
        course.age_min = c.get("age_min")
        course.age_max = c.get("age_max")
        course.tags = ",".join(c.get("tags", []))
        course.is_featured = bool(c.get("is_featured"))
        course.certificate_enabled = False
        course.discussions_enabled = False
        course.reviews_enabled = False
        if actor:
            course.created_by_id = course.created_by_id or actor.id
        db.session.flush()
        existing = {t.locale: t for t in course.translations}
        for locale in LOCALES:
            tr = existing.get(locale) or CourseTranslation(course_id=course.id, locale=locale)
            tr.title = (c.get("title") or {}).get(locale, "")
            tr.short_description = (c.get("short_description") or {}).get(locale, "")
            tr.description = sanitize_html((c.get("description") or {}).get(locale, ""))
            tr.objectives = _lines(c.get("objectives"), locale)
            tr.audience = (c.get("audience") or {}).get(locale, "")
            if locale not in existing:
                course.translations.append(tr)
        modules_by_slug = {m.text("title", "en"): m for m in course.modules}
        for mi, mod in enumerate(c.get("modules", []), start=1):
            module = modules_by_slug.get((mod.get("title") or {}).get("en", ""))
            if module is None:
                module = Module(course_id=course.id)
                course.modules.append(module)
                db.session.flush()
            module.sort_order = mi
            mt = {t.locale: t for t in module.translations}
            for locale in LOCALES:
                tr = mt.get(locale) or ModuleTranslation(module_id=module.id, locale=locale)
                tr.title = (mod.get("title") or {}).get(locale, "")
                tr.description = (mod.get("description") or {}).get(locale, "")
                if locale not in mt:
                    module.translations.append(tr)
            lessons_by_slug = {lesson.slug: lesson for lesson in module.lessons}
            for li, les in enumerate(mod.get("lessons", []), start=1):
                lesson = lessons_by_slug.get(les["slug"])
                if lesson is None:
                    lesson = Lesson(module_id=module.id, slug=les["slug"])
                    module.lessons.append(lesson)
                    db.session.flush()
                lesson.sort_order = li
                lesson.lesson_type = LessonType(les.get("type", "reading"))
                lesson.estimated_minutes = int(les.get("minutes") or 5)
                lt = {t.locale: t for t in lesson.translations}
                for locale in LOCALES:
                    tr = lt.get(locale) or LessonTranslation(lesson_id=lesson.id, locale=locale)
                    tr.title = (les.get("title") or {}).get(locale, "")
                    tr.summary = (les.get("summary") or {}).get(locale, "")[:500]
                    tr.content = sanitize_html((les.get("content") or {}).get(locale, ""))
                    if locale not in lt:
                        lesson.translations.append(tr)
    db.session.flush()
    # link missions to their course
    for course in db.session.execute(
        select(Course).where(Course.platform == Platform.CYBERHERO)
    ).scalars():
        for mission in db.session.execute(
            select(CyberMission).where(CyberMission.track_id == course.cyber_track_id)
        ).scalars():
            mission.course_id = mission.course_id or course.id
    db.session.flush()
    return created


def seed_all(seed_dir: Path | None = None, actor: User | None = None) -> dict[str, int]:
    seed_dir = seed_dir or SEED_DIR
    summary = {
        "tracks": seed_tracks(load_seed("tiers.json", seed_dir)),
        "missions": seed_missions(load_seed("missions.json", seed_dir)),
        "agreement": seed_agreement(load_seed("agreement.json", seed_dir)),
        "resources": seed_resources(load_seed("resources.json", seed_dir)),
        "mascot_entries": seed_mascot(load_seed("mascot.json", seed_dir)),
        "knowledge_chunks": seed_knowledge(load_seed("knowledge.json", seed_dir)),
        "courses": seed_courses(load_seed("courses.json", seed_dir), actor=actor),
    }
    audit_service.record("cyberhero.seeded", meta=summary, actor=actor)
    db.session.commit()
    return summary


# ---------------------------------------------------------------------------
# serialisation (original CyberHero data shapes)
# ---------------------------------------------------------------------------
def tracks(*, include_hidden: bool = False) -> list[CyberTrack]:
    """Tracks in display order; hidden ones only for the admin panel."""
    stmt = select(CyberTrack).order_by(CyberTrack.sort_order)
    if not include_hidden:
        stmt = stmt.where(CyberTrack.is_hidden.is_(False))
    return list(db.session.execute(stmt).scalars())


def track_usage(track: CyberTrack) -> dict[str, int]:
    """What still depends on a track; a track is only deletable when all are zero."""
    from sqlalchemy import func

    certificates = int(
        db.session.execute(
            select(func.count())
            .select_from(CyberCertificate)
            .where(CyberCertificate.track_id == track.id)
        ).scalar_one()
    )
    return {
        "missions": len(track.missions),
        "courses": len(track.courses),
        "certificates": certificates,
    }


def serialize_track(track: CyberTrack) -> dict:
    return {
        "id": track.slug,
        "color": track.color,
        "emoji": track.emoji,
        "active": track.is_active,
        "route": track.route,
        "audience": track.audience,
        "featured": track.is_featured,
        "certificate": track.certificate_enabled,
        "tag": track.pair("tag"),
        "name": track.pair("name"),
        "desc": track.pair("desc"),
        "intro": track.pair("intro"),
        "topics": {"en": track.topic_list("en"), "ka": track.topic_list("ka")},
    }


def missions(track_slug: str | None = None, published_only: bool = True) -> list[CyberMission]:
    stmt = select(CyberMission).join(CyberTrack).order_by(CyberMission.sort_order)
    if published_only:
        # a hidden track takes its missions off the public API with it
        stmt = stmt.where(CyberMission.is_published.is_(True), CyberTrack.is_hidden.is_(False))
    if track_slug:
        stmt = stmt.where(CyberTrack.slug == track_slug)
    return list(db.session.execute(stmt).scalars())


def mission_by_slug(slug: str) -> CyberMission | None:
    return db.session.execute(
        select(CyberMission).where(CyberMission.slug == slug)
    ).scalar_one_or_none()


def serialize_mission_meta(m: CyberMission) -> dict:
    data = {
        "id": m.slug,
        "order": m.sort_order,
        "emoji": m.emoji,
        "color": m.color,
        "article": m.article_code,
        "track": m.track.slug,
        "course": m.course.slug if m.course else None,
        "topics": m.topic_list,
        "name": m.pair("name"),
        "desc": m.pair("desc"),
        "max": m.max_points,
    }
    if m.is_priority:
        data["priority"] = True
    if m.is_sensitive:
        data["sensitive"] = True
    if m.is_final:
        data["final"] = True
    if m.timer_seconds:
        data["timer"] = m.timer_seconds
    if m.pass_ratio:
        data["passRatio"] = m.pass_ratio
    return data


def _serialize_round(r: CyberMissionRound) -> dict:
    if r.round_type == "choice":
        data: dict[str, Any] = {
            "type": "choice",
            "q": r.pair("prompt"),
            "options": [{"label": i.pair("label"), "correct": i.is_correct} for i in r.items],
            "explain": r.pair("explain"),
        }
        if r.has_card:
            card = {"from": r.pair("card_from"), "body": r.pair("card_body")}
            meta = _pair_or_none(r.card_meta_ka, r.card_meta_en)
            if meta:
                card["meta"] = meta
            data["card"] = card
        return data
    if r.round_type == "flags":
        items = []
        for i in r.items:
            item = {"text": i.pair("label"), "flag": i.is_correct, "explain": i.pair("explain")}
            sender = _pair_or_none(i.from_ka, i.from_en)
            if sender:
                item["from"] = sender
            items.append(item)
        return {
            "type": "flags",
            "prompt": r.pair("prompt"),
            "items": items,
            "explain": r.pair("explain"),
        }
    if r.round_type == "builder":
        options = []
        for i in r.items:
            opt = {"label": i.pair("label"), "value": i.value or 0}
            note = _pair_or_none(i.note_ka, i.note_en)
            if note:
                opt["note"] = note
            options.append(opt)
        data = {
            "type": "builder",
            "prompt": r.pair("prompt"),
            "target": r.target or 0,
            "meterLow": r.pair("meter_low"),
            "meterHigh": r.pair("meter_high"),
            "options": options,
            "explain": r.pair("explain"),
        }
        negative = _pair_or_none(r.explain_negative_ka, r.explain_negative_en)
        if negative:
            data["explainNegative"] = negative
        return data
    nodes: dict[str, Any] = {}
    for b in r.branches:
        node: dict[str, Any] = {}
        if b.messages:
            node["chat"] = [
                {"name": msg.pair("name"), "text": msg.pair("text")} for msg in b.messages
            ]
        scene = _pair_or_none(b.scene_ka, b.scene_en)
        if scene:
            node["scene"] = scene
        if b.is_end:
            node["end"] = True
        else:
            choices = []
            for ch in b.choices:
                choice = {"label": ch.pair("label"), "next": ch.next_key, "points": ch.points}
                feedback = _pair_or_none(ch.feedback_ka, ch.feedback_en)
                if feedback:
                    choice["feedback"] = feedback
                choices.append(choice)
            node["choices"] = choices
        nodes[b.key] = node
    return {"type": "branch", "start": r.branch_start_key, "max": r.branch_max or 0, "nodes": nodes}


def serialize_mission(m: CyberMission) -> dict:
    data = serialize_mission_meta(m)
    data.update(
        {
            "brief": m.pair("brief"),
            "theory": [n.pair("text") for n in m.theory],
            "takeaways": [n.pair("text") for n in m.takeaways],
            "rounds": [_serialize_round(r) for r in m.rounds],
        }
    )
    help_strip = _pair_or_none(m.help_strip_ka, m.help_strip_en)
    if help_strip:
        data["helpStrip"] = help_strip
    return data


def agreement() -> dict | None:
    resource = db.session.execute(
        select(CyberSafetyResource).where(CyberSafetyResource.kind == "family_agreement")
    ).scalar_one_or_none()
    if resource is None:
        return None
    sig_ka = [*resource.step_list("ka"), "", "", ""]
    sig_en = [*resource.step_list("en"), "", "", ""]
    sections = []
    for s in resource.sections:
        section: dict[str, Any] = {"title": s.pair("title")}
        if s.clauses:
            section["clauses"] = [c.pair("text") for c in s.clauses]
        if s.write_lines:
            section["writeLines"] = s.write_lines
        sections.append(section)
    return {
        "title": resource.pair("title"),
        "sub": resource.pair("summary"),
        "sections": sections,
        "signatures": {
            "child": _pair(sig_ka[0], sig_en[0]),
            "parent": _pair(sig_ka[1], sig_en[1]),
            "date": _pair(sig_ka[2], sig_en[2]),
        },
    }


def resources(kind: str) -> list[CyberSafetyResource]:
    return list(
        db.session.execute(
            select(CyberSafetyResource)
            .where(CyberSafetyResource.kind == kind, CyberSafetyResource.is_active.is_(True))
            .order_by(CyberSafetyResource.sort_order)
        ).scalars()
    )


def serialize_resource(r: CyberSafetyResource) -> dict:
    return {
        "kind": r.kind,
        "slug": r.slug,
        "emoji": r.emoji,
        "color": r.color,
        "contact_value": r.contact_value,
        "is_verified": r.is_verified,
        "title": r.pair("title"),
        "summary": r.pair("summary"),
        "body": r.pair("body"),
        "steps": {"en": r.step_list("en"), "ka": r.step_list("ka")},
    }


def mascot() -> dict:
    tips = db.session.execute(
        select(CyberMascotTip)
        .where(CyberMascotTip.is_active.is_(True))
        .order_by(CyberMascotTip.sort_order)
    ).scalars()
    reactions: dict[str, Any] = {}
    for r in db.session.execute(
        select(CyberMascotReaction).order_by(
            CyberMascotReaction.key, CyberMascotReaction.sort_order
        )
    ).scalars():
        reactions.setdefault(r.key, []).append(r.pair("text"))
    mission_topics = {m.slug: m.topic_list for m in missions(published_only=False)}
    return {
        "tips": [{"topics": t.topic_list, "en": t.text_en, "ka": t.text_ka} for t in tips],
        "reactions": {k: (v if k == "mission" else v[0]) for k, v in reactions.items()},
        "missionTopics": mission_topics,
    }


def knowledge() -> dict:
    sections = db.session.execute(
        select(CyberKnowledgeSection).order_by(CyberKnowledgeSection.sort_order)
    ).scalars()
    return {
        "title": {"en": "Basic Cybersecurity Course", "ka": "კიბერუსაფრთხოების საბაზისო კურსი"},
        "sections": [
            {
                "id": s.sort_order - 1,
                "en": s.title_en,
                "ka": s.title_ka,
                "chunks": [c.text for c in s.chunks],
            }
            for s in sections
        ],
    }


# ---- courses (shared model, CyberHero presentation) -------------------------
def courses(track_slug: str | None = None) -> list[Course]:
    stmt = (
        select(Course)
        .where(
            Course.platform.in_([Platform.CYBERHERO, Platform.BOTH]),
            Course.status == CourseStatus.PUBLISHED,
        )
        .order_by(Course.sort_order, Course.published_at.desc())
    )
    if track_slug:
        stmt = stmt.join(CyberTrack, Course.cyber_track_id == CyberTrack.id).where(
            CyberTrack.slug == track_slug
        )
    return list(db.session.execute(stmt).scalars())


def course_by_slug(slug: str) -> Course | None:
    course = db.session.execute(select(Course).where(Course.slug == slug)).scalar_one_or_none()
    if (
        course is None
        or course.platform not in {Platform.CYBERHERO, Platform.BOTH}
        or not course.is_published
    ):
        return None
    return course


def _course_pair(course: Course, field: str) -> dict[str, str]:
    return {
        loc: (getattr(course.tr(loc), field, "") if course.tr(loc) else "") for loc in ("en", "ka")
    }


def serialize_course_meta(course: Course) -> dict:
    visible = [
        les for mod in course.modules if mod.is_published for les in mod.lessons if les.is_published
    ]
    return {
        "slug": course.slug,
        "track": course.cyber_track.slug if course.cyber_track else None,
        "emoji": course.icon,
        "color": course.color
        if course.color in {"blue", "cyan", "green", "pink", "amber", "violet", "orange", "accent"}
        else "blue",
        "difficulty": course.difficulty.value,
        "estimated_minutes": course.estimated_minutes,
        "age_min": course.age_min,
        "age_max": course.age_max,
        "tags": course.tag_list,
        "is_featured": course.is_featured,
        "lesson_count": len(visible),
        "mission_count": len([m for m in course.missions if m.is_published]),
        "title": _course_pair(course, "title"),
        "short_description": _course_pair(course, "short_description"),
        "audience": _course_pair(course, "audience"),
    }


def serialize_course(course: Course) -> dict:
    data = serialize_course_meta(course)
    data["description_html"] = _course_pair(course, "description")
    data["objectives"] = {
        loc: (course.tr(loc).objective_list if course.tr(loc) else []) for loc in ("en", "ka")
    }
    data["modules"] = [
        {
            "slug": f"m{mod.sort_order}",
            "title": {loc: mod.text("title", loc) for loc in ("en", "ka")},
            "description": {loc: mod.text("description", loc) for loc in ("en", "ka")},
            "lessons": [
                {
                    "slug": les.slug,
                    "type": les.lesson_type.value,
                    "minutes": les.estimated_minutes,
                    "title": {loc: les.text("title", loc) for loc in ("en", "ka")},
                    "summary": {loc: les.text("summary", loc) for loc in ("en", "ka")},
                }
                for les in mod.lessons
                if les.is_published
            ],
        }
        for mod in course.modules
        if mod.is_published
    ]
    data["missions"] = [serialize_mission_meta(m) for m in course.missions if m.is_published]
    return data


def serialize_lesson(course: Course, lesson: Lesson) -> dict:
    visible = [
        les for mod in course.modules if mod.is_published for les in mod.lessons if les.is_published
    ]
    ids = [les.id for les in visible]
    index = ids.index(lesson.id) if lesson.id in ids else 0
    prev_lesson = visible[index - 1] if index > 0 else None
    next_lesson = visible[index + 1] if index + 1 < len(visible) else None

    def brief(les: Lesson | None) -> dict | None:
        if les is None:
            return None
        return {"slug": les.slug, "title": {loc: les.text("title", loc) for loc in ("en", "ka")}}

    return {
        "slug": lesson.slug,
        "course": course.slug,
        "type": lesson.lesson_type.value,
        "minutes": lesson.estimated_minutes,
        "module_title": {loc: lesson.module.text("title", loc) for loc in ("en", "ka")},
        "title": {loc: lesson.text("title", loc) for loc in ("en", "ka")},
        "summary": {loc: lesson.text("summary", loc) for loc in ("en", "ka")},
        "content": {loc: lesson.text("content", loc) for loc in ("en", "ka")},
        "index": index + 1,
        "total": len(visible),
        "prev": brief(prev_lesson),
        "next": brief(next_lesson),
    }


# ---------------------------------------------------------------------------
# progress (signed-in users)
# ---------------------------------------------------------------------------
def get_progress(user: User) -> dict:
    rows = db.session.execute(
        select(CyberProgress).where(CyberProgress.user_id == user.id)
    ).scalars()
    mission_map = {
        row.mission.slug: {"done": row.done, "best": row.best, "total": row.total} for row in rows
    }
    lessons: dict[str, dict] = {}
    course_lessons = (
        select(LessonProgress, Lesson, Course)
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .join(Course, Module.course_id == Course.id)
        .where(
            LessonProgress.user_id == user.id,
            Course.platform.in_([Platform.CYBERHERO, Platform.BOTH]),
        )
    )
    for lp, lesson, course in db.session.execute(course_lessons).all():
        lessons[f"{course.slug}/{lesson.slug}"] = {"done": lp.status == ProgressStatus.COMPLETED}
    return {"guardians": {"missions": mission_map}, "lessons": lessons}


def merge_progress(user: User, payload: dict) -> dict:
    """Merge client progress into the server copy: best score wins, done never regresses."""
    incoming = ((payload or {}).get("guardians") or {}).get("missions") or {}
    if not isinstance(incoming, dict):
        raise CyberHeroError("invalid progress payload")
    by_slug = {m.slug: m for m in missions(published_only=False)}
    for slug, state in list(incoming.items())[:200]:
        mission = by_slug.get(str(slug))
        if mission is None or not isinstance(state, dict):
            continue
        row, _ = _upsert(CyberProgress, user_id=user.id, mission_id=mission.id)
        best = max(int(row.best or 0), max(0, min(int(state.get("best") or 0), 10_000)))
        row.best = best
        row.total = max(int(row.total or 0), max(0, min(int(state.get("total") or 0), 10_000)))
        if state.get("done") and not row.done:
            row.done = True
            row.completed_at = utcnow()
        row.attempts = (row.attempts or 0) + 1
    lessons = (payload or {}).get("lessons") or {}
    if isinstance(lessons, dict):
        for key, state in list(lessons.items())[:500]:
            if not (isinstance(state, dict) and state.get("done")) or "/" not in str(key):
                continue
            course_slug, lesson_slug = str(key).split("/", 1)
            lesson = db.session.execute(
                select(Lesson)
                .join(Module)
                .join(Course)
                .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
            ).scalar_one_or_none()
            if lesson is None:
                continue
            lp, _ = _upsert(LessonProgress, user_id=user.id, lesson_id=lesson.id)
            if lp.status != ProgressStatus.COMPLETED:
                lp.status = ProgressStatus.COMPLETED
                lp.completed_at = utcnow()
    db.session.commit()
    return get_progress(user)


# ---------------------------------------------------------------------------
# certificates
# ---------------------------------------------------------------------------
def _public_id() -> str:
    year = datetime.now(UTC).year
    while True:
        token = "".join(secrets.choice(CERT_ALPHABET) for _ in range(8))
        candidate = f"CH-{year}-{token}"
        if (
            db.session.execute(
                select(CyberCertificate.id).where(CyberCertificate.public_id == candidate)
            ).first()
            is None
        ):
            return candidate


def issue_certificate(
    *,
    track_slug: str,
    display_name: str,
    completed: dict[str, dict] | list,
    user: User | None = None,
) -> CyberCertificate:
    name = " ".join((display_name or "").split())[:120]
    if len(name) < 2:
        raise CyberHeroError(_("Please enter the name to print on the certificate."))
    track = db.session.execute(
        select(CyberTrack).where(CyberTrack.slug == track_slug)
    ).scalar_one_or_none()
    if track is None or not track.certificate_enabled:
        raise CyberHeroError(_("No certificate is available for this track."))
    required = missions(track_slug)
    if isinstance(completed, list):
        completed = {slug: {"done": True} for slug in completed}
    done = {
        slug
        for slug, state in (completed or {}).items()
        if isinstance(state, dict) and state.get("done")
    }
    if user is not None:
        done |= {
            row.mission.slug
            for row in db.session.execute(
                select(CyberProgress).where(
                    CyberProgress.user_id == user.id, CyberProgress.done.is_(True)
                )
            ).scalars()
        }
    missing = [m.slug for m in required if m.slug not in done]
    if missing:
        raise CyberHeroError(_("Finish every mission of the track first."))
    points = sum(int((completed or {}).get(m.slug, {}).get("best") or 0) for m in required)
    certificate = CyberCertificate(
        public_id=_public_id(),
        user_id=user.id if user else None,
        track_id=track.id,
        display_name=name,
        track_name_ka=track.name_ka,
        track_name_en=track.name_en,
        points=min(points, 10_000),
        max_points=sum(m.max_points for m in required),
    )
    db.session.add(certificate)
    audit_service.record(
        "cyberhero.certificate_issued",
        target=certificate,
        actor=user,
        meta={"track": track_slug, "anonymous": user is None},
    )
    db.session.commit()
    return certificate


def serialize_certificate(c: CyberCertificate) -> dict:
    return {
        "public_id": c.public_id,
        "valid": c.is_valid,
        "display_name": c.display_name,
        "track": c.track.slug,
        "track_name": _pair(c.track_name_ka, c.track_name_en),
        "points": c.points,
        "max_points": c.max_points,
        "issued_at": c.issued_at.isoformat(),
        "verify_url": f"/certificates/verify/{c.public_id}",
    }


def verify_certificate(public_id: str) -> CyberCertificate | None:
    public_id = (public_id or "").strip().upper()[:40]
    return db.session.execute(
        select(CyberCertificate).where(CyberCertificate.public_id == public_id)
    ).scalar_one_or_none()


def stats() -> dict[str, int]:
    """Aggregates for the admin dashboard / analytics."""
    from sqlalchemy import func

    completed = int(
        db.session.execute(
            select(func.count()).select_from(CyberProgress).where(CyberProgress.done.is_(True))
        ).scalar_one()
    )
    learners = int(
        db.session.execute(select(func.count(func.distinct(CyberProgress.user_id)))).scalar_one()
    )
    certificates = int(
        db.session.execute(select(func.count()).select_from(CyberCertificate)).scalar_one()
    )
    mission_count = int(
        db.session.execute(select(func.count()).select_from(CyberMission)).scalar_one()
    )
    return {
        "missions": mission_count,
        "mission_completions": completed,
        "signed_in_learners": learners,
        "certificates": certificates,
    }
