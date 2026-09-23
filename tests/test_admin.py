"""Admin panel: access control, every page renders, and the main write paths."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.extensions import db
from app.models import (
    AuditLog,
    Category,
    CyberArticle,
    CyberMission,
    CyberTrack,
    FeatureFlag,
    MediaFile,
    User,
    UserStatus,
)
from app.services import feature_flags, seed_service, settings_service
from tests.conftest import get_csrf, login, logout, post

ADMIN_PAGES = [
    "/admin/",
    "/admin/users/",
    "/admin/courses/",
    "/admin/courses/new",
    "/admin/categories/",
    "/admin/quizzes/",
    "/admin/assignments/",
    "/admin/certificates/",
    "/admin/discussions/",
    "/admin/reviews/",
    "/admin/notifications/",
    "/admin/media/",
    "/admin/analytics/",
    "/admin/settings/",
    "/admin/flags/",
    "/admin/audit/",
    "/admin/localization/",
    "/admin/cyberhero/",
    "/admin/cyberhero/tracks/new",
    "/admin/cyberhero/missions/new",
    "/admin/cyberhero/articles/new",
    "/admin/cyberhero/resources/new",
    "/admin/cyberhero/mascot/",
    "/admin/cyberhero/knowledge/",
    "/admin/cyberhero/knowledge/new",
]


@pytest.fixture
def seeded(app):  # type: ignore[no-untyped-def]
    seed_service.seed_demo_content()
    seed_service.seed_cyberhero_content()


def test_admin_requires_permission(client, logged_in_student):  # type: ignore[no-untyped-def]
    for url in ADMIN_PAGES[:6]:
        assert client.get(url).status_code == 403, url
    assert post(client, "/admin/flags/", {"flag-CYBERHERO_ENABLED": "on"}).status_code == 403


def test_instructor_is_not_admin(client, logged_in_instructor):  # type: ignore[no-untyped-def]
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/users/").status_code == 403


def test_moderator_scope(client, moderator, seeded):  # type: ignore[no-untyped-def]
    login(client, moderator)
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/discussions/").status_code == 200
    assert client.get("/admin/reviews/").status_code == 200
    assert client.get("/admin/users/").status_code == 403
    assert client.get("/admin/settings/").status_code == 403
    assert client.get("/admin/cyberhero/").status_code == 403


@pytest.mark.parametrize("lang", ["ka", "en"])
def test_all_admin_pages_render(client, logged_in_admin, seeded, lang):  # type: ignore[no-untyped-def]
    from tests.test_pages import assert_clean

    client.get(f"/?lang={lang}")
    for url in ADMIN_PAGES:
        response = client.get(url)
        assert response.status_code == 200, (url, response.status_code)
        assert_clean(response.get_data(as_text=True))
    # detail pages for seeded content
    track = db.session.query(CyberTrack).first()
    mission = db.session.query(CyberMission).first()
    article = db.session.query(CyberArticle).first()
    user = db.session.query(User).first()
    category = db.session.query(Category).first()
    from app.models import Course

    course = db.session.query(Course).first()
    for url in (
        f"/admin/cyberhero/tracks/{track.id}",
        f"/admin/cyberhero/missions/{mission.id}",
        f"/admin/cyberhero/missions/{mission.id}/rounds/{mission.rounds[0].id}",
        f"/admin/cyberhero/missions/{mission.id}/rounds/new",
        f"/admin/cyberhero/articles/{article.id}",
        f"/admin/cyberhero/articles/{article.id}/blocks/{article.blocks[0].id}",
        f"/admin/cyberhero/articles/{article.id}/blocks/new",
        f"/admin/users/{user.id}",
        f"/admin/categories/{category.id}",
        f"/admin/courses/{course.id}",
    ):
        response = client.get(url)
        assert response.status_code == 200, url
        assert_clean(response.get_data(as_text=True))
    html = client.get("/admin/").get_data(as_text=True)
    assert f'lang="{lang}"' in html


def test_user_management(client, logged_in_admin, student):  # type: ignore[no-untyped-def]
    admin = logged_in_admin
    response = post(
        client,
        "/admin/users/new",
        {
            "email": "new.teacher@example.org",
            "first_name": "Lika",
            "last_name": "T",
            "password": "Teacher-Passw0rd-XYZ",
            "roles": ["instructor", "student"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    created = db.session.query(User).filter_by(email="new.teacher@example.org").one()
    assert created.role_names == {"instructor", "student"}
    assert created.has_permission("instructor.access")

    # Weak password rejected
    response = post(
        client,
        "/admin/users/new",
        {
            "email": "weak@example.org",
            "first_name": "A",
            "last_name": "B",
            "password": "short",
            "roles": ["student"],
        },
        follow_redirects=True,
    )
    assert db.session.query(User).filter_by(email="weak@example.org").first() is None

    # Edit roles + verify, suspend/reinstate, unlock
    version_before = student.security_version
    response = post(
        client,
        f"/admin/users/{student.id}",
        {
            "first_name": "Nino",
            "last_name": "Beridze",
            "organization": "School 1",
            "roles": ["student", "instructor"],
            "is_email_verified": "y",
            "submit": "1",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    student = db.session.get(User, student.id)
    assert "instructor" in student.role_names and student.organization == "School 1"
    assert student.security_version > version_before
    response = post(client, f"/admin/users/{student.id}/suspend", {"reason": "spam"})
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(User, student.id).status == UserStatus.SUSPENDED
    response = post(client, f"/admin/users/{student.id}/reinstate")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(User, student.id).status == UserStatus.ACTIVE
    assert post(client, f"/admin/users/{student.id}/unlock").status_code == 302
    assert post(client, f"/admin/users/{student.id}/bogus").status_code in (400, 404)

    # Admin cannot remove their own admin role or suspend themselves
    response = post(
        client,
        f"/admin/users/{admin.id}",
        {"first_name": "Ana", "last_name": "Admin", "roles": ["student"], "submit": "1"},
    )
    db.session.expire_all()
    assert "admin" in db.session.get(User, admin.id).role_names
    response = post(client, f"/admin/users/{admin.id}/suspend")
    db.session.expire_all()
    assert db.session.get(User, admin.id).status == UserStatus.ACTIVE

    actions = {a.action for a in db.session.query(AuditLog)}
    assert {"user.created", "user.suspended", "user.reinstated"} <= actions
    assert client.get("/admin/users/?q=beridze").status_code == 200
    assert client.get(f"/admin/users/{student.id}").status_code == 200


def test_settings_and_flags(client, logged_in_admin):  # type: ignore[no-untyped-def]
    assert feature_flags.is_enabled("CYBERHERO_IO_CHAT_ENABLED") is False
    page = client.get("/admin/flags/").get_data(as_text=True)
    assert "flag-CYBERHERO_IO_CHAT_ENABLED" in page
    response = post(
        client,
        "/admin/flags/",
        {"flag-CYBERHERO_ENABLED": "on", "flag-CYBERHERO_IO_CHAT_ENABLED": "on"},
    )
    assert response.status_code == 302
    assert feature_flags.is_enabled("CYBERHERO_IO_CHAT_ENABLED") is True
    flag = db.session.query(FeatureFlag).filter_by(key="CYBERHERO_IO_CHAT_ENABLED").one()
    assert flag.updated_by_id == logged_in_admin.id
    # unchecked boxes disable
    response = post(client, "/admin/flags/", {"flag-CYBERHERO_ENABLED": "on"})
    assert feature_flags.is_enabled("CYBERHERO_IO_CHAT_ENABLED") is False

    page = client.get("/admin/settings/").get_data(as_text=True)
    assert "setting-site.title" in page
    data = {
        "setting-site.title": "ციფრული აკადემია",
        "setting-cyberhero.emergency_phone": "112",
        "setting-site.support_email": "help@example.org",
    }
    response = post(client, "/admin/settings/", data)
    assert response.status_code == 302
    assert settings_service.get("site.title") == "ციფრული აკადემია"
    assert settings_service.get("cyberhero.emergency_phone") == "112"
    # CSRF is enforced on these hand-built forms
    response = client.post("/admin/settings/", data={"setting-site.title": "x"})
    assert response.status_code == 400
    assert settings_service.get("site.title") == "ციფრული აკადემია"
    # value appears in the public navbar
    html = client.get("/").get_data(as_text=True)
    assert "ციფრული აკადემია" in html


def test_categories_crud(client, logged_in_admin):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/admin/categories/",
        {
            "slug": "phishing",
            "name_ka": "ფიშინგი",
            "name_en": "Phishing",
            "icon": "mail",
            "color": "blue",
            "platform": "both",
            "sort_order": "2",
            "is_active": "y",
        },
    )
    assert response.status_code == 302, response.data[:400]
    category = db.session.query(Category).filter_by(slug="phishing").one()
    assert category.name("ka") == "ფიშინგი"
    response = post(
        client,
        f"/admin/categories/{category.id}",
        {
            "slug": "phishing",
            "name_ka": "ფიშინგი და თაღლითობა",
            "name_en": "Phishing and scams",
            "icon": "mail",
            "color": "purple",
            "platform": "elearning",
            "sort_order": "1",
            "is_active": "y",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Category, category.id).name("en") == "Phishing and scams"
    assert post(client, f"/admin/categories/{category.id}/delete").status_code == 302
    assert db.session.get(Category, category.id) is None


def test_admin_course_create_feature_and_archive(client, logged_in_admin, instructor):  # type: ignore[no-untyped-def]
    from app.models import Course, CourseStatus
    from tests.test_instructor import COURSE_FORM

    data = dict(COURSE_FORM)
    data.update({"platform": "both", "instructor_id": str(instructor.id), "is_featured": "y"})
    response = post(client, "/admin/courses/new", data)
    assert response.status_code == 302, response.data[:600]
    course = db.session.query(Course).order_by(Course.id.desc()).first()
    assert course.instructor_id == instructor.id and course.is_featured
    assert course.platform.value == "both"
    response = post(client, f"/admin/courses/{course.id}/feature")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Course, course.id).is_featured is False
    token = get_csrf(client)
    response = client.post(
        f"/admin/courses/{course.id}/status",
        data={"status": "archived", "review-csrf_token": token, "csrf_token": token},
    )
    assert response.status_code == 302, response.data[:300]
    db.session.expire_all()
    assert db.session.get(Course, course.id).status == CourseStatus.ARCHIVED
    assert client.get("/admin/courses/?status=archived").status_code == 200
    assert post(client, f"/admin/courses/{course.id}/delete").status_code == 302
    assert db.session.get(Course, course.id) is None


def test_media_library_upload_and_delete(client, logged_in_admin, upload_dir):  # type: ignore[no-untyped-def]
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (20, 30, 40)).save(buffer, format="PNG")
    response = post(
        client,
        "/admin/media/",
        {
            "file": (io.BytesIO(buffer.getvalue()), "logo.png"),
            "kind": "image",
            "alt_text": "logo",
            "is_public": "y",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302, response.data[:400]
    media = db.session.query(MediaFile).one()
    assert media.is_public and media.original_name == "logo.png"
    assert media.stored_name != "logo.png"
    assert client.get(f"/media/public/{media.id}").status_code == 200
    assert post(client, f"/admin/media/{media.id}/toggle-public").status_code == 302
    db.session.expire_all()
    assert db.session.get(MediaFile, media.id).is_public is False
    logout(client)
    assert client.get(f"/media/public/{media.id}").status_code == 404
    login(client, logged_in_admin)
    assert client.get(f"/media/files/{media.id}").status_code == 200
    # a script disguised as png is refused
    response = post(
        client,
        "/admin/media/",
        {"file": (io.BytesIO(b"<?php echo 1;"), "x.png"), "kind": "image"},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert db.session.query(MediaFile).count() == 1
    assert post(client, f"/admin/media/{media.id}/delete").status_code == 302
    assert db.session.get(MediaFile, media.id) is None


def test_broadcast_notification(client, logged_in_admin, student, instructor):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/admin/notifications/",
        {
            "title": "Maintenance",
            "body": "Tonight 22:00",
            "audience": "students",
            "link": "/about",
        },
    )
    assert response.status_code == 302
    from app.models import Notification

    def titles(user_id: int) -> set[str]:
        return {n.title for n in db.session.query(Notification).filter_by(user_id=user_id)}

    assert "Maintenance" in titles(student.id)
    assert "Maintenance" in titles(instructor.id)
    assert "Maintenance" not in titles(logged_in_admin.id)


def test_cyberhero_content_editing(client, logged_in_admin, seeded):  # type: ignore[no-untyped-def]
    track = db.session.query(CyberTrack).filter_by(slug="guardians").one()
    response = post(
        client,
        f"/admin/cyberhero/tracks/{track.id}",
        {
            "slug": "guardians",
            "sort_order": "1",
            "emoji": "🛡️",
            "color": "violet",
            "audience": track.audience,
            "route": "/guardians",
            "is_active": "y",
            "is_featured": "y",
            "certificate_enabled": "y",
            "name_ka": "მცველები",
            "name_en": "Guardians",
            "desc_ka": "აღწერა",
            "desc_en": "Description",
            "topics_ka": "ერთი\nორი",
            "topics_en": "One\nTwo",
        },
    )
    assert response.status_code == 302, response.data[:500]
    db.session.expire_all()
    track = db.session.get(CyberTrack, track.id)
    assert track.name_ka == "მცველები" and track.color == "violet"
    api = client.get("/api/v1/cyberhero/tracks?lang=ka").get_json()
    assert any(t["name"]["ka"] == "მცველები" for t in api["items"])

    mission = db.session.query(CyberMission).filter_by(track_id=track.id).first()
    response = post(
        client,
        "/admin/cyberhero/missions/new",
        {
            "slug": "new-mission",
            "track_id": str(track.id),
            "course_id": "0",
            "sort_order": "99",
            "emoji": "🧭",
            "color": "cyan",
            "topics": "phishing, passwords",
            "is_published": "y",
            "pass_ratio": "0.7",
            "name_ka": "ახალი მისია",
            "name_en": "New mission",
            "desc_ka": "აღწერა",
            "desc_en": "Description",
            "brief_ka": "ბრიფი",
            "brief_en": "Brief",
            "theory_ka": "თეორია 1\nთეორია 2",
            "theory_en": "Theory 1\nTheory 2",
            "takeaways_ka": "დასკვნა",
            "takeaways_en": "Takeaway",
        },
    )
    assert response.status_code == 302, response.data[:500]
    new_mission = db.session.query(CyberMission).filter_by(slug="new-mission").one()
    assert [n.text_en for n in new_mission.theory] == ["Theory 1", "Theory 2"]
    assert new_mission.pass_ratio == 0.7
    # add a choice round with three options, second correct
    response = post(
        client,
        f"/admin/cyberhero/missions/{new_mission.id}/rounds/new",
        {
            "round_type": "choice",
            "prompt_ka": "რა გავაკეთო?",
            "prompt_en": "What now?",
            "explain_ka": "ახსნა",
            "explain_en": "Why",
            "item_label_ka": ["ა", "ბ", "გ"],
            "item_label_en": ["A", "B", "C"],
            "item_correct": "1",
        },
    )
    assert response.status_code == 302, response.data[:500]
    db.session.expire_all()
    new_mission = db.session.get(CyberMission, new_mission.id)
    assert len(new_mission.rounds) == 1
    rnd = new_mission.rounds[0]
    assert [o.is_correct for o in rnd.items] == [False, True, False]
    detail = client.get("/api/v1/cyberhero/missions/new-mission").get_json()
    assert detail["rounds"][0]["type"] == "choice"
    assert detail["rounds"][0]["options"][1]["correct"] is True
    # branch node on a branch round
    response = post(
        client,
        f"/admin/cyberhero/missions/{new_mission.id}/rounds/new",
        {
            "round_type": "branch",
            "prompt_ka": "საუბარი",
            "prompt_en": "Chat",
            "branch_start_key": "start",
            "branch_max": "2",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    branch_round = db.session.get(CyberMission, new_mission.id).rounds[1]
    response = post(
        client,
        f"/admin/cyberhero/rounds/{branch_round.id}/nodes/new",
        {
            "key": "start",
            "sort_order": "1",
            "scene_ka": "სცენა",
            "scene_en": "Scene",
            "choice_label_ka": ["წავიდე", "დავრჩე"],
            "choice_label_en": ["Leave", "Stay"],
            "choice_next": ["end", "end"],
            "choice_points": ["1", "0"],
            "choice_feedback_ka": ["კარგი", "ცუდი"],
            "choice_feedback_en": ["Good", "Bad"],
        },
    )
    assert response.status_code == 302, response.data[:400]
    assert client.get(f"/admin/cyberhero/rounds/{branch_round.id}/nodes/new").status_code == 200
    # delete mission removes its rounds and API entry
    response = post(client, f"/admin/cyberhero/missions/{new_mission.id}/delete")
    assert response.status_code == 302
    assert client.get("/api/v1/cyberhero/missions/new-mission").status_code == 404

    # article + block
    response = post(
        client,
        "/admin/cyberhero/articles/new",
        {
            "slug": "new-article",
            "shelf": "A",
            "sort_order": "1",
            "emoji": "📘",
            "color": "blue",
            "minutes": "4",
            "is_published": "y",
            "title_ka": "სტატია",
            "title_en": "Article",
            "teaser_ka": "თიზერი",
            "teaser_en": "Teaser",
            "sources": "https://example.org/a",
        },
    )
    assert response.status_code == 302, response.data[:500]
    article = db.session.query(CyberArticle).filter_by(slug="new-article").one()
    response = post(
        client,
        f"/admin/cyberhero/articles/{article.id}/blocks/new",
        {
            "block_type": "list",
            "variant": "note",
            "ordered": "y",
            "items_ka": "ერთი\nორი",
            "items_en": "One\nTwo",
        },
    )
    assert response.status_code == 302, response.data[:500]
    api = client.get("/api/v1/cyberhero/articles/new-article").get_json()
    assert api["body"][0]["type"] == "list" and api["body"][0]["ordered"] is True
    assert api["body"][0]["items"][1]["en"] == "Two"
    assert api["sources"] == ["https://example.org/a"]
    assert mission is not None


def test_cyberhero_mascot_and_knowledge(client, logged_in_admin, seeded):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/admin/cyberhero/mascot/",
        {
            "tip-topics": "phishing",
            "tip-sort_order": "5",
            "tip-text_ka": "ყოველთვის შეამოწმე ბმული.",
            "tip-text_en": "Always check the link.",
            "tip-is_active": "y",
            "tip-submit": "1",
            "tip-csrf_token": get_csrf(client),
        },
    )
    assert response.status_code == 302, response.data[:400]
    api = client.get("/api/v1/cyberhero/mascot").get_json()
    assert any(t["en"] == "Always check the link." for t in api["tips"])
    response = post(
        client,
        "/admin/cyberhero/knowledge/new",
        {
            "title_ka": "ახალი სექცია",
            "title_en": "New section",
            "sort_order": "50",
            "chunks": "First chunk.\n\nSecond chunk.",
        },
    )
    assert response.status_code == 302, response.data[:400]
    assert client.get("/admin/cyberhero/knowledge/").status_code == 200


def test_reseed_is_idempotent(client, logged_in_admin, seeded):  # type: ignore[no-untyped-def]
    before = db.session.query(CyberMission).count()
    response = post(client, "/admin/cyberhero/reseed")
    assert response.status_code == 302
    assert db.session.query(CyberMission).count() == before


def test_audit_log_lists_actor(client, logged_in_admin):  # type: ignore[no-untyped-def]
    post(client, "/admin/flags/", {"flag-CYBERHERO_ENABLED": "on"})
    html = client.get("/admin/audit/").get_data(as_text=True)
    assert "flag" in html and logged_in_admin.email in html
    assert client.get("/admin/audit/?action=flag").status_code == 200
    assert client.get("/admin/analytics/").status_code == 200
    assert client.get("/admin/localization/").status_code == 200


def test_track_can_be_hidden_and_deleted(client, logged_in_admin, seeded):  # type: ignore[no-untyped-def]
    form = {
        "slug": "retirees",
        "sort_order": "9",
        "emoji": "🎀",
        "color": "pink",
        "audience": "adults",
        "route": "",
        "name_ka": "პენსიონერები",
        "name_en": "Retirees",
        "is_hidden": "y",
    }
    assert post(client, "/admin/cyberhero/tracks/new", form).status_code == 302
    track = db.session.query(CyberTrack).filter_by(slug="retirees").one()
    assert track.is_hidden

    # hidden: listed for admins, invisible to the CyberHero app
    assert "retirees" in client.get("/admin/cyberhero/").get_data(as_text=True)
    public = {t["id"] for t in client.get("/api/v1/cyberhero/tracks").get_json()["items"]}
    assert "retirees" not in public and "guardians" in public
    tiers = {t["id"] for t in client.get("/api/v1/cyberhero/bootstrap").get_json()["tiers"]}
    assert "retirees" not in tiers
    assert client.get("/api/v1/cyberhero/tracks/retirees").status_code == 404

    # un-hide through the form and it is back
    form.pop("is_hidden")
    assert post(client, f"/admin/cyberhero/tracks/{track.id}", form).status_code == 302
    assert client.get("/api/v1/cyberhero/tracks/retirees").status_code == 200

    # hiding a track with missions takes the missions off the API too
    guardians = db.session.query(CyberTrack).filter_by(slug="guardians").one()
    guardians.is_hidden = True
    db.session.commit()
    assert client.get("/api/v1/cyberhero/missions?track=guardians").get_json()["items"] == []
    assert client.get("/api/v1/cyberhero/missions/g1").status_code == 404
    guardians.is_hidden = False
    db.session.commit()
    assert client.get("/api/v1/cyberhero/missions/g1").status_code == 200

    # a track that is in use cannot be deleted (missions, progress and certificates survive)
    response = post(client, f"/admin/cyberhero/tracks/{guardians.id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert guardians.name("ka") in response.get_data(as_text=True)
    assert db.session.get(CyberTrack, guardians.id) is not None
    assert db.session.query(CyberMission).filter_by(track_id=guardians.id).count() > 0

    # an unused track can
    assert client.get(f"/admin/cyberhero/tracks/{track.id}/delete").status_code == 405
    response = post(client, f"/admin/cyberhero/tracks/{track.id}/delete")
    assert response.status_code == 302 and response.headers["Location"].endswith(
        "/admin/cyberhero/"
    )
    assert db.session.query(CyberTrack).filter_by(slug="retirees").count() == 0
    assert client.get("/api/v1/cyberhero/tracks/retirees").status_code == 404


def test_track_delete_requires_permission(client, logged_in_student, seeded):  # type: ignore[no-untyped-def]
    track = db.session.query(CyberTrack).filter_by(slug="guardians").one()
    assert post(client, f"/admin/cyberhero/tracks/{track.id}/delete").status_code == 403
    assert db.session.get(CyberTrack, track.id) is not None
