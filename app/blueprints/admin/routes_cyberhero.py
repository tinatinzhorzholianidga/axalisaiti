"""Admin: CyberHero content management (tracks, missions, rounds, branches,
articles, safety resources, agreement, mascot, knowledge base)."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import select

from app.blueprints.admin import bp
from app.blueprints.admin.helpers import get_or_404, lines, locale
from app.extensions import db
from app.forms.admin import (
    AgreementSectionForm,
    ArticleForm,
    BlockForm,
    BranchNodeForm,
    KnowledgeSectionForm,
    MissionForm,
    ReactionForm,
    RoundForm,
    SafetyResourceForm,
    TipForm,
    TrackForm,
)
from app.models import (
    Course,
    CyberAgreementClause,
    CyberAgreementSection,
    CyberArticle,
    CyberArticleBlock,
    CyberArticleSource,
    CyberBranch,
    CyberBranchChoice,
    CyberBranchMessage,
    CyberKnowledgeChunk,
    CyberKnowledgeSection,
    CyberMascotReaction,
    CyberMascotTip,
    CyberMission,
    CyberMissionNote,
    CyberMissionRound,
    CyberRoundItem,
    CyberSafetyResource,
    CyberTrack,
    Platform,
)
from app.services import audit_service, course_service, cyberhero_service
from app.services.rbac import require_permission
from app.services.sanitize import sanitize_html

BILINGUAL = ("ka", "en")


def _fill(form, obj, fields: tuple[str, ...]) -> None:  # type: ignore[no-untyped-def]
    for name in fields:
        if hasattr(form, name) and hasattr(obj, name):
            form[name].data = getattr(obj, name)


def _apply(form, obj, fields: tuple[str, ...]) -> None:  # type: ignore[no-untyped-def]
    for name in fields:
        if hasattr(form, name) and hasattr(obj, name):
            value = form[name].data
            setattr(obj, name, value if value is not None else "")


def _log(action: str, target, meta: dict | None = None) -> None:  # type: ignore[no-untyped-def]
    audit_service.record(f"cyberhero.{action}", target=target, actor=current_user, meta=meta or {})
    db.session.commit()


# ---- overview ---------------------------------------------------------------
@bp.route("/cyberhero/")
@require_permission("cyberhero.manage")
def cyberhero():  # type: ignore[no-untyped-def]
    return render_template(
        "admin/cyberhero/index.html",
        tracks=cyberhero_service.tracks(include_hidden=True),
        missions=cyberhero_service.missions(published_only=False),
        articles=list(
            db.session.execute(
                select(CyberArticle).order_by(CyberArticle.shelf, CyberArticle.sort_order)
            ).scalars()
        ),
        resources=list(
            db.session.execute(
                select(CyberSafetyResource).order_by(
                    CyberSafetyResource.kind, CyberSafetyResource.sort_order
                )
            ).scalars()
        ),
        courses=list(
            db.session.execute(
                select(Course).where(Course.platform.in_([Platform.CYBERHERO, Platform.BOTH]))
            ).scalars()
        ),
        stats=cyberhero_service.stats(),
        locale=locale(),
    )


@bp.route("/cyberhero/reseed", methods=["POST"])
@require_permission("cyberhero.manage")
def cyberhero_reseed():  # type: ignore[no-untyped-def]
    summary = cyberhero_service.seed_all(actor=current_user)
    flash(_("Seed content reloaded: %(summary)s", summary=summary), "success")
    return redirect(url_for("admin.cyberhero"))


# ---- tracks -----------------------------------------------------------------
TRACK_FIELDS = (
    "slug",
    "sort_order",
    "emoji",
    "color",
    "audience",
    "route",
    "is_active",
    "is_featured",
    "is_hidden",
    "certificate_enabled",
    "tag_ka",
    "tag_en",
    "name_ka",
    "name_en",
    "desc_ka",
    "desc_en",
    "intro_ka",
    "intro_en",
    "topics_ka",
    "topics_en",
)


@bp.route("/cyberhero/tracks/new", methods=["GET", "POST"])
@bp.route("/cyberhero/tracks/<int:track_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_track(track_id: int | None = None):  # type: ignore[no-untyped-def]
    track = get_or_404(CyberTrack, track_id) if track_id else None
    form = TrackForm()
    if request.method == "GET" and track:
        _fill(form, track, TRACK_FIELDS)
    if form.validate_on_submit():
        if track is None:
            track = CyberTrack(slug=form.slug.data, name_ka="", name_en="")
            db.session.add(track)
        _apply(form, track, TRACK_FIELDS)
        track.route = (form.route.data or "").strip() or None
        db.session.flush()
        _log("track_saved", track)
        flash(_("Track saved."), "success")
        return redirect(url_for("admin.cyberhero"))
    return render_template(
        "admin/cyberhero/track_form.html",
        form=form,
        track=track,
        usage=cyberhero_service.track_usage(track) if track else None,
        locale=locale(),
    )


@bp.route("/cyberhero/tracks/<int:track_id>/delete", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_track_delete(track_id: int):  # type: ignore[no-untyped-def]
    track = get_or_404(CyberTrack, track_id)
    usage = cyberhero_service.track_usage(track)
    if any(usage.values()):
        # never cascade away missions, learner progress or issued certificates
        flash(
            _(
                "“%(name)s” still has %(missions)d missions, %(courses)d courses and "
                "%(certificates)d certificates. Delete or move them first, or hide the "
                "track instead.",
                name=track.name(locale()),
                **usage,
            ),
            "error",
        )
        return redirect(url_for("admin.cyber_track", track_id=track.id))
    audit_service.record(
        "cyberhero.track_deleted", target=track, actor=current_user, meta={"slug": track.slug}
    )
    db.session.delete(track)
    db.session.commit()
    flash(_("Track deleted."), "info")
    return redirect(url_for("admin.cyberhero"))


# ---- missions ---------------------------------------------------------------
MISSION_FIELDS = (
    "slug",
    "sort_order",
    "emoji",
    "color",
    "article_code",
    "topics",
    "is_priority",
    "is_sensitive",
    "is_final",
    "is_published",
    "timer_seconds",
    "name_ka",
    "name_en",
    "desc_ka",
    "desc_en",
    "brief_ka",
    "brief_en",
    "help_strip_ka",
    "help_strip_en",
)


def _mission_choices(form: MissionForm) -> None:
    form.track_id.choices = [
        (t.id, t.name("en") or t.slug) for t in cyberhero_service.tracks(include_hidden=True)
    ]
    form.course_id.choices = [(0, "—")] + [
        (c.id, c.title("en") or c.slug)
        for c in db.session.execute(
            select(Course).where(Course.platform.in_([Platform.CYBERHERO, Platform.BOTH]))
        ).scalars()
    ]


@bp.route("/cyberhero/missions/new", methods=["GET", "POST"])
@bp.route("/cyberhero/missions/<int:mission_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_mission(mission_id: int | None = None):  # type: ignore[no-untyped-def]
    mission = get_or_404(CyberMission, mission_id) if mission_id else None
    form = MissionForm()
    _mission_choices(form)
    if request.method == "GET" and mission:
        _fill(form, mission, MISSION_FIELDS)
        form.track_id.data = mission.track_id
        form.course_id.data = mission.course_id or 0
        form.pass_ratio.data = str(mission.pass_ratio) if mission.pass_ratio else ""
        form.theory_ka.data = "\n".join(n.text_ka for n in mission.theory)
        form.theory_en.data = "\n".join(n.text_en for n in mission.theory)
        form.takeaways_ka.data = "\n".join(n.text_ka for n in mission.takeaways)
        form.takeaways_en.data = "\n".join(n.text_en for n in mission.takeaways)
    if form.validate_on_submit():
        if mission is None:
            mission = CyberMission(
                slug=form.slug.data, track_id=form.track_id.data, name_ka="", name_en=""
            )
            db.session.add(mission)
            db.session.flush()
        _apply(form, mission, MISSION_FIELDS)
        mission.track_id = form.track_id.data
        mission.course_id = form.course_id.data or None
        try:
            mission.pass_ratio = float(form.pass_ratio.data) if form.pass_ratio.data else None
        except ValueError:
            mission.pass_ratio = None
        mission.notes.clear()
        db.session.flush()
        for kind, ka_field, en_field in (
            ("theory", form.theory_ka, form.theory_en),
            ("takeaway", form.takeaways_ka, form.takeaways_en),
        ):
            ka_lines, en_lines = lines(ka_field.data), lines(en_field.data)
            for i, text_ka in enumerate(ka_lines, start=1):
                text_en = en_lines[i - 1] if i - 1 < len(en_lines) else text_ka
                mission.notes.append(
                    CyberMissionNote(kind=kind, sort_order=i, text_ka=text_ka, text_en=text_en)
                )
        _log("mission_saved", mission)
        flash(_("Mission saved."), "success")
        return redirect(url_for("admin.cyber_mission", mission_id=mission.id))
    return render_template(
        "admin/cyberhero/mission_form.html", form=form, mission=mission, locale=locale()
    )


@bp.route("/cyberhero/missions/<int:mission_id>/delete", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_mission_delete(mission_id: int):  # type: ignore[no-untyped-def]
    mission = get_or_404(CyberMission, mission_id)
    audit_service.record("cyberhero.mission_deleted", target=mission, actor=current_user)
    db.session.delete(mission)
    db.session.commit()
    flash(_("Mission deleted."), "info")
    return redirect(url_for("admin.cyberhero"))


# ---- rounds -----------------------------------------------------------------
ROUND_FIELDS = (
    "round_type",
    "prompt_ka",
    "prompt_en",
    "explain_ka",
    "explain_en",
    "explain_negative_ka",
    "explain_negative_en",
    "card_from_ka",
    "card_from_en",
    "card_meta_ka",
    "card_meta_en",
    "card_body_ka",
    "card_body_en",
    "target",
    "meter_low_ka",
    "meter_low_en",
    "meter_high_ka",
    "meter_high_en",
    "branch_start_key",
    "branch_max",
)


@bp.route("/cyberhero/missions/<int:mission_id>/rounds/new", methods=["GET", "POST"])
@bp.route("/cyberhero/missions/<int:mission_id>/rounds/<int:round_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_round(mission_id: int, round_id: int | None = None):  # type: ignore[no-untyped-def]
    mission = get_or_404(CyberMission, mission_id)
    rnd = get_or_404(CyberMissionRound, round_id) if round_id else None
    if rnd is not None and rnd.mission_id != mission.id:
        abort(404)
    form = RoundForm()
    if request.method == "GET" and rnd:
        _fill(form, rnd, ROUND_FIELDS)
    if form.validate_on_submit():
        if rnd is None:
            rnd = CyberMissionRound(
                mission_id=mission.id,
                sort_order=len(mission.rounds) + 1,
                round_type=form.round_type.data,
            )
            db.session.add(rnd)
            mission.rounds.append(rnd)
            db.session.flush()
        _apply(form, rnd, ROUND_FIELDS)
        rnd.target = form.target.data
        rnd.branch_max = form.branch_max.data
        rnd.branch_start_key = (form.branch_start_key.data or "").strip() or None
        # items (choice options / flags / builder toggles) come as parallel arrays
        if rnd.round_type in {"choice", "flags", "builder"}:
            rnd.items.clear()
            db.session.flush()
            labels_ka = request.form.getlist("item_label_ka")
            labels_en = request.form.getlist("item_label_en")
            froms_ka = request.form.getlist("item_from_ka")
            froms_en = request.form.getlist("item_from_en")
            notes_ka = request.form.getlist("item_note_ka")
            notes_en = request.form.getlist("item_note_en")
            explains_ka = request.form.getlist("item_explain_ka")
            explains_en = request.form.getlist("item_explain_en")
            values = request.form.getlist("item_value")
            correct = set(request.form.getlist("item_correct"))
            order = 0
            for index, label in enumerate(labels_ka):
                if not label.strip():
                    continue
                order += 1

                def pick(values_list: list[str], i: int = index) -> str:
                    return values_list[i].strip() if i < len(values_list) else ""

                value = pick(values)
                rnd.items.append(
                    CyberRoundItem(
                        sort_order=order,
                        label_ka=label.strip(),
                        label_en=pick(labels_en) or label.strip(),
                        from_ka=pick(froms_ka),
                        from_en=pick(froms_en),
                        note_ka=pick(notes_ka),
                        note_en=pick(notes_en),
                        explain_ka=pick(explains_ka),
                        explain_en=pick(explains_en),
                        is_correct=str(index) in correct,
                        value=int(value) if value.lstrip("-").isdigit() else None,
                    )
                )
        _log("round_saved", mission, {"round_id": rnd.id})
        flash(_("Round saved."), "success")
        return redirect(url_for("admin.cyber_round", mission_id=mission.id, round_id=rnd.id))
    return render_template(
        "admin/cyberhero/round_form.html", form=form, mission=mission, rnd=rnd, locale=locale()
    )


@bp.route("/cyberhero/missions/<int:mission_id>/rounds/<int:round_id>/delete", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_round_delete(mission_id: int, round_id: int):  # type: ignore[no-untyped-def]
    mission = get_or_404(CyberMission, mission_id)
    rnd = get_or_404(CyberMissionRound, round_id)
    if rnd.mission_id != mission.id:
        abort(404)
    mission.rounds.remove(rnd)
    db.session.delete(rnd)
    db.session.flush()
    course_service.renumber(mission.rounds)
    _log("round_deleted", mission)
    return redirect(url_for("admin.cyber_mission", mission_id=mission.id))


@bp.route(
    "/cyberhero/missions/<int:mission_id>/rounds/<int:round_id>/move/<direction>", methods=["POST"]
)
@require_permission("cyberhero.manage")
def cyber_round_move(mission_id: int, round_id: int, direction: str):  # type: ignore[no-untyped-def]
    mission = get_or_404(CyberMission, mission_id)
    course_service.move(mission.rounds, round_id, -1 if direction == "up" else 1)
    return redirect(url_for("admin.cyber_mission", mission_id=mission.id))


# ---- branch nodes -----------------------------------------------------------
@bp.route("/cyberhero/rounds/<int:round_id>/nodes/new", methods=["GET", "POST"])
@bp.route("/cyberhero/rounds/<int:round_id>/nodes/<int:node_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_branch(round_id: int, node_id: int | None = None):  # type: ignore[no-untyped-def]
    rnd = get_or_404(CyberMissionRound, round_id)
    node = get_or_404(CyberBranch, node_id) if node_id else None
    if node is not None and node.round_id != rnd.id:
        abort(404)
    form = BranchNodeForm()
    if request.method == "GET" and node:
        _fill(form, node, ("key", "sort_order", "is_end", "scene_ka", "scene_en"))
    if form.validate_on_submit():
        if node is None:
            node = CyberBranch(round_id=rnd.id, key=form.key.data)
            db.session.add(node)
            rnd.branches.append(node)
            db.session.flush()
        _apply(form, node, ("key", "sort_order", "is_end", "scene_ka", "scene_en"))
        node.messages.clear()
        node.choices.clear()
        db.session.flush()
        names_ka, names_en = (
            request.form.getlist("msg_name_ka"),
            request.form.getlist("msg_name_en"),
        )
        texts_ka, texts_en = (
            request.form.getlist("msg_text_ka"),
            request.form.getlist("msg_text_en"),
        )
        for i, text in enumerate(texts_ka):
            if text.strip():
                node.messages.append(
                    CyberBranchMessage(
                        sort_order=len(node.messages) + 1,
                        text_ka=text.strip(),
                        text_en=(texts_en[i] if i < len(texts_en) else "").strip() or text.strip(),
                        name_ka=(names_ka[i] if i < len(names_ka) else "").strip(),
                        name_en=(names_en[i] if i < len(names_en) else "").strip(),
                    )
                )
        labels_ka, labels_en = (
            request.form.getlist("choice_label_ka"),
            request.form.getlist("choice_label_en"),
        )
        nexts, points = request.form.getlist("choice_next"), request.form.getlist("choice_points")
        fb_ka, fb_en = (
            request.form.getlist("choice_feedback_ka"),
            request.form.getlist("choice_feedback_en"),
        )
        for i, label in enumerate(labels_ka):
            if label.strip():
                pts = points[i] if i < len(points) else "0"
                node.choices.append(
                    CyberBranchChoice(
                        sort_order=len(node.choices) + 1,
                        label_ka=label.strip(),
                        label_en=(labels_en[i] if i < len(labels_en) else "").strip()
                        or label.strip(),
                        next_key=(nexts[i] if i < len(nexts) else "").strip() or None,
                        points=int(pts) if pts.strip().isdigit() else 0,
                        feedback_ka=(fb_ka[i] if i < len(fb_ka) else "").strip(),
                        feedback_en=(fb_en[i] if i < len(fb_en) else "").strip(),
                    )
                )
        _log("branch_saved", rnd.mission, {"node": node.key})
        flash(_("Node saved."), "success")
        return redirect(url_for("admin.cyber_round", mission_id=rnd.mission_id, round_id=rnd.id))
    return render_template(
        "admin/cyberhero/branch_form.html", form=form, rnd=rnd, node=node, locale=locale()
    )


@bp.route("/cyberhero/rounds/<int:round_id>/nodes/<int:node_id>/delete", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_branch_delete(round_id: int, node_id: int):  # type: ignore[no-untyped-def]
    rnd = get_or_404(CyberMissionRound, round_id)
    node = get_or_404(CyberBranch, node_id)
    if node.round_id != rnd.id:
        abort(404)
    db.session.delete(node)
    _log("branch_deleted", rnd.mission)
    return redirect(url_for("admin.cyber_round", mission_id=rnd.mission_id, round_id=rnd.id))


# ---- articles ---------------------------------------------------------------
ARTICLE_FIELDS = (
    "slug",
    "shelf",
    "sort_order",
    "emoji",
    "color",
    "minutes",
    "mission_slug",
    "is_priority",
    "is_published",
    "title_ka",
    "title_en",
    "teaser_ka",
    "teaser_en",
    "lead_ka",
    "lead_en",
)


@bp.route("/cyberhero/articles/new", methods=["GET", "POST"])
@bp.route("/cyberhero/articles/<int:article_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_article(article_id: int | None = None):  # type: ignore[no-untyped-def]
    article = get_or_404(CyberArticle, article_id) if article_id else None
    form = ArticleForm()
    if request.method == "GET" and article:
        _fill(form, article, ARTICLE_FIELDS)
        form.sources.data = "\n".join(s.citation for s in article.sources)
    if form.validate_on_submit():
        if article is None:
            article = CyberArticle(
                slug=form.slug.data, shelf=form.shelf.data, title_ka="", title_en=""
            )
            db.session.add(article)
            db.session.flush()
        _apply(form, article, ARTICLE_FIELDS)
        article.mission_slug = (form.mission_slug.data or "").strip() or None
        article.sources.clear()
        for i, citation in enumerate(lines(form.sources.data), start=1):
            article.sources.append(CyberArticleSource(sort_order=i, citation=citation[:500]))
        _log("article_saved", article)
        flash(_("Article saved."), "success")
        return redirect(url_for("admin.cyber_article", article_id=article.id))
    return render_template(
        "admin/cyberhero/article_form.html", form=form, article=article, locale=locale()
    )


@bp.route("/cyberhero/articles/<int:article_id>/blocks/new", methods=["GET", "POST"])
@bp.route("/cyberhero/articles/<int:article_id>/blocks/<int:block_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_block(article_id: int, block_id: int | None = None):  # type: ignore[no-untyped-def]
    article = get_or_404(CyberArticle, article_id)
    block = get_or_404(CyberArticleBlock, block_id) if block_id else None
    if block is not None and block.article_id != article.id:
        abort(404)
    form = BlockForm()
    if request.method == "GET" and block:
        _fill(
            form,
            block,
            ("block_type", "variant", "ordered", "title_ka", "title_en", "text_ka", "text_en"),
        )
        form.items_ka.data = "\n".join(i.get("ka", "") for i in block.items)
        form.items_en.data = "\n".join(i.get("en", "") for i in block.items)
        form.paragraphs_ka.data = "\n".join(p.get("ka", "") for p in block.paragraphs)
        form.paragraphs_en.data = "\n".join(p.get("en", "") for p in block.paragraphs)
    if form.validate_on_submit():
        if block is None:
            block = CyberArticleBlock(
                article_id=article.id,
                sort_order=len(article.blocks) + 1,
                block_type=form.block_type.data,
            )
            db.session.add(block)
            article.blocks.append(block)
        _apply(
            form,
            block,
            ("block_type", "variant", "ordered", "title_ka", "title_en", "text_ka", "text_en"),
        )
        ka_items, en_items = lines(form.items_ka.data), lines(form.items_en.data)
        block.items = [
            {"ka": ka, "en": en_items[i] if i < len(en_items) else ka}
            for i, ka in enumerate(ka_items)
        ]
        ka_ps, en_ps = lines(form.paragraphs_ka.data), lines(form.paragraphs_en.data)
        block.paragraphs = [
            {"ka": ka, "en": en_ps[i] if i < len(en_ps) else ka} for i, ka in enumerate(ka_ps)
        ]
        _log("block_saved", article, {"block_id": block.id})
        flash(_("Block saved."), "success")
        return redirect(url_for("admin.cyber_article", article_id=article.id))
    return render_template(
        "admin/cyberhero/block_form.html", form=form, article=article, block=block, locale=locale()
    )


@bp.route("/cyberhero/articles/<int:article_id>/blocks/<int:block_id>/<action>", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_block_action(article_id: int, block_id: int, action: str):  # type: ignore[no-untyped-def]
    article = get_or_404(CyberArticle, article_id)
    block = get_or_404(CyberArticleBlock, block_id)
    if block.article_id != article.id:
        abort(404)
    if action == "delete":
        article.blocks.remove(block)
        db.session.delete(block)
        db.session.flush()
        course_service.renumber(article.blocks)
    elif action in {"up", "down"}:
        course_service.move(article.blocks, block.id, -1 if action == "up" else 1)
    else:
        abort(400)
    _log("block_changed", article)
    return redirect(url_for("admin.cyber_article", article_id=article.id))


# ---- safety resources + agreement ------------------------------------------
RESOURCE_FIELDS = (
    "kind",
    "slug",
    "sort_order",
    "emoji",
    "color",
    "contact_value",
    "is_verified",
    "is_active",
    "title_ka",
    "title_en",
    "summary_ka",
    "summary_en",
    "steps_ka",
    "steps_en",
)


@bp.route("/cyberhero/resources/new", methods=["GET", "POST"])
@bp.route("/cyberhero/resources/<int:resource_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_resource(resource_id: int | None = None):  # type: ignore[no-untyped-def]
    resource = get_or_404(CyberSafetyResource, resource_id) if resource_id else None
    form = SafetyResourceForm()
    if request.method == "GET" and resource:
        _fill(form, resource, RESOURCE_FIELDS)
        form.body_ka.data = resource.body_ka
        form.body_en.data = resource.body_en
    if form.validate_on_submit():
        if resource is None:
            resource = CyberSafetyResource(
                kind=form.kind.data, slug=form.slug.data, title_ka="", title_en=""
            )
            db.session.add(resource)
            db.session.flush()
        _apply(form, resource, RESOURCE_FIELDS)
        resource.body_ka = sanitize_html(form.body_ka.data or "")
        resource.body_en = sanitize_html(form.body_en.data or "")
        _log("resource_saved", resource)
        flash(_("Saved."), "success")
        return redirect(url_for("admin.cyber_resource", resource_id=resource.id))
    return render_template(
        "admin/cyberhero/resource_form.html",
        form=form,
        resource=resource,
        section_form=AgreementSectionForm(prefix="sec"),
        locale=locale(),
    )


@bp.route("/cyberhero/resources/<int:resource_id>/sections/new", methods=["POST"])
@bp.route(
    "/cyberhero/resources/<int:resource_id>/sections/<int:section_id>", methods=["GET", "POST"]
)
@require_permission("cyberhero.manage")
def cyber_agreement_section(resource_id: int, section_id: int | None = None):  # type: ignore[no-untyped-def]
    resource = get_or_404(CyberSafetyResource, resource_id)
    section = get_or_404(CyberAgreementSection, section_id) if section_id else None
    if section is not None and section.resource_id != resource.id:
        abort(404)
    form = AgreementSectionForm(prefix="sec")
    if request.method == "GET" and section:
        _fill(form, section, ("title_ka", "title_en", "write_lines"))
        form.clauses_ka.data = "\n".join(c.text_ka for c in section.clauses)
        form.clauses_en.data = "\n".join(c.text_en for c in section.clauses)
    if form.validate_on_submit():
        if section is None:
            section = CyberAgreementSection(
                resource_id=resource.id,
                sort_order=len(resource.sections) + 1,
                title_ka="",
                title_en="",
            )
            db.session.add(section)
            resource.sections.append(section)
            db.session.flush()
        _apply(form, section, ("title_ka", "title_en", "write_lines"))
        section.clauses.clear()
        ka, en = lines(form.clauses_ka.data), lines(form.clauses_en.data)
        for i, text in enumerate(ka, start=1):
            section.clauses.append(
                CyberAgreementClause(
                    sort_order=i, text_ka=text, text_en=en[i - 1] if i - 1 < len(en) else text
                )
            )
        _log("agreement_section_saved", resource)
        flash(_("Section saved."), "success")
        return redirect(url_for("admin.cyber_resource", resource_id=resource.id))
    return render_template(
        "admin/cyberhero/section_form.html",
        form=form,
        resource=resource,
        section=section,
        locale=locale(),
    )


@bp.route(
    "/cyberhero/resources/<int:resource_id>/sections/<int:section_id>/delete", methods=["POST"]
)
@require_permission("cyberhero.manage")
def cyber_agreement_section_delete(resource_id: int, section_id: int):  # type: ignore[no-untyped-def]
    resource = get_or_404(CyberSafetyResource, resource_id)
    section = get_or_404(CyberAgreementSection, section_id)
    if section.resource_id != resource.id:
        abort(404)
    db.session.delete(section)
    _log("agreement_section_deleted", resource)
    return redirect(url_for("admin.cyber_resource", resource_id=resource.id))


# ---- mascot -----------------------------------------------------------------
@bp.route("/cyberhero/mascot/", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_mascot():  # type: ignore[no-untyped-def]
    tip_form = TipForm(prefix="tip")
    reaction_form = ReactionForm(prefix="re")
    if tip_form.submit.data and tip_form.validate_on_submit():
        tip = CyberMascotTip(
            topics=tip_form.topics.data or "",
            sort_order=tip_form.sort_order.data or 0,
            text_ka=tip_form.text_ka.data,
            text_en=tip_form.text_en.data,
            is_active=bool(tip_form.is_active.data),
        )
        db.session.add(tip)
        _log("tip_saved", tip)
        flash(_("Tip added."), "success")
        return redirect(url_for("admin.cyber_mascot"))
    if reaction_form.submit.data and reaction_form.validate_on_submit():
        reaction = CyberMascotReaction(
            key=reaction_form.key.data,
            sort_order=reaction_form.sort_order.data or 1,
            text_ka=reaction_form.text_ka.data,
            text_en=reaction_form.text_en.data,
        )
        db.session.add(reaction)
        _log("reaction_saved", reaction)
        flash(_("Reaction added."), "success")
        return redirect(url_for("admin.cyber_mascot"))
    tips = list(
        db.session.execute(select(CyberMascotTip).order_by(CyberMascotTip.sort_order)).scalars()
    )
    reactions = list(
        db.session.execute(
            select(CyberMascotReaction).order_by(
                CyberMascotReaction.key, CyberMascotReaction.sort_order
            )
        ).scalars()
    )
    return render_template(
        "admin/cyberhero/mascot.html",
        tips=tips,
        reactions=reactions,
        tip_form=tip_form,
        reaction_form=reaction_form,
        locale=locale(),
    )


@bp.route("/cyberhero/mascot/tips/<int:tip_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_tip(tip_id: int):  # type: ignore[no-untyped-def]
    tip = get_or_404(CyberMascotTip, tip_id)
    form = TipForm(prefix="tip")
    if request.method == "GET":
        _fill(form, tip, ("topics", "sort_order", "text_ka", "text_en", "is_active"))
    if form.validate_on_submit():
        _apply(form, tip, ("topics", "sort_order", "text_ka", "text_en", "is_active"))
        _log("tip_saved", tip)
        flash(_("Tip saved."), "success")
        return redirect(url_for("admin.cyber_mascot"))
    return render_template("admin/cyberhero/tip_form.html", form=form, tip=tip, locale=locale())


@bp.route("/cyberhero/mascot/tips/<int:tip_id>/delete", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_tip_delete(tip_id: int):  # type: ignore[no-untyped-def]
    tip = get_or_404(CyberMascotTip, tip_id)
    db.session.delete(tip)
    _log("tip_deleted", None, {"tip_id": tip_id})
    return redirect(url_for("admin.cyber_mascot"))


@bp.route("/cyberhero/mascot/reactions/<int:reaction_id>/delete", methods=["POST"])
@require_permission("cyberhero.manage")
def cyber_reaction_delete(reaction_id: int):  # type: ignore[no-untyped-def]
    reaction = get_or_404(CyberMascotReaction, reaction_id)
    db.session.delete(reaction)
    _log("reaction_deleted", None, {"reaction_id": reaction_id})
    return redirect(url_for("admin.cyber_mascot"))


# ---- knowledge base ---------------------------------------------------------
@bp.route("/cyberhero/knowledge/")
@require_permission("cyberhero.manage")
def cyber_knowledge():  # type: ignore[no-untyped-def]
    sections = list(
        db.session.execute(
            select(CyberKnowledgeSection).order_by(CyberKnowledgeSection.sort_order)
        ).scalars()
    )
    return render_template("admin/cyberhero/knowledge.html", sections=sections, locale=locale())


@bp.route("/cyberhero/knowledge/new", methods=["GET", "POST"])
@bp.route("/cyberhero/knowledge/<int:section_id>", methods=["GET", "POST"])
@require_permission("cyberhero.manage")
def cyber_knowledge_section(section_id: int | None = None):  # type: ignore[no-untyped-def]
    section = get_or_404(CyberKnowledgeSection, section_id) if section_id else None
    form = KnowledgeSectionForm()
    if request.method == "GET" and section:
        _fill(form, section, ("title_ka", "title_en", "sort_order"))
        form.chunks.data = "\n\n".join(c.text for c in section.chunks)
    if form.validate_on_submit():
        if section is None:
            section = CyberKnowledgeSection(title_ka="", title_en="")
            db.session.add(section)
            db.session.flush()
        _apply(form, section, ("title_ka", "title_en", "sort_order"))
        section.chunks.clear()
        for i, chunk in enumerate(
            [c.strip() for c in (form.chunks.data or "").split("\n\n") if c.strip()], start=1
        ):
            section.chunks.append(CyberKnowledgeChunk(sort_order=i, text=chunk))
        _log("knowledge_saved", section)
        flash(_("Section saved."), "success")
        return redirect(url_for("admin.cyber_knowledge"))
    return render_template(
        "admin/cyberhero/knowledge_form.html", form=form, section=section, locale=locale()
    )
