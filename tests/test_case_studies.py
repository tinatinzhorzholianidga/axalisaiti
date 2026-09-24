"""Case studies (public + admin), the home page threats section and the resources page."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.extensions import db
from app.models import CaseStudy, EnrollmentStatus, Resource
from app.services import case_study_service, enrollment_service, resource_service, seed_service
from tests.conftest import get_csrf, login, logout, post


@pytest.fixture
def demo(app):  # type: ignore[no-untyped-def]
    seed_service.seed_demo_content()


def _png() -> tuple[io.BytesIO, str]:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (120, 80, 200)).save(buf, format="PNG")
    buf.seek(0)
    return buf, "cover.png"


def _pdf(name: str = "guide.pdf") -> tuple[io.BytesIO, str]:
    return io.BytesIO(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"), name


# ---- public --------------------------------------------------------------
def test_seed_defaults_create_category_and_section_titles(app):  # type: ignore[no-untyped-def]
    created = case_study_service.seed_defaults()
    assert created == {"case_categories": 1, "case_section_titles": 2}
    assert (
        case_study_service.category_by_slug("ongoing-threats").name("ka") == "მიმდინარე საფრთხეები"
    )
    assert [t.name_en for t in case_study_service.section_titles()] == [
        "Be careful of",
        "How to identify",
    ]
    assert case_study_service.seed_defaults() == {"case_categories": 0, "case_section_titles": 0}


def test_case_study_pages_render(client, demo):  # type: ignore[no-untyped-def]
    html = client.get("/case-studies/").get_data(as_text=True)
    assert html.count('class="course-card case-card"') == 3
    assert "მიმდინარე საფრთხეები" in html and '="None"' not in html
    en = client.get("/case-studies/?lang=en").get_data(as_text=True)
    assert "Case studies" in en and "Ongoing threats" in en
    # filters: search + category + sort
    filtered = client.get("/case-studies/?q=sms&category=ongoing-threats&sort=title").get_data(
        as_text=True
    )
    assert filtered.count('class="course-card case-card"') == 1 and "fake-bank-sms-2026" in filtered
    assert client.get("/case-studies/?category=nope").get_data(as_text=True).count("case-card") == 0
    # the article: description, about and the optional sections in order
    page = client.get("/case-studies/fake-bank-sms-2026/?lang=en").get_data(as_text=True)
    assert page.index("<h2>Description</h2>") < page.index("<h2>About</h2>")
    assert (
        page.index("<h2>About</h2>")
        < page.index("<h2>How to identify</h2>")
        < page.index("<h2>Be careful of</h2>")
    )
    assert "Related case studies" in page and "deepfake-voice-call" in page
    ka = client.get("/case-studies/fake-bank-sms-2026/?lang=ka").get_data(as_text=True)
    assert "<h2>აღწერა</h2>" in ka and "<h2>როგორ ამოვიცნოთ</h2>" in ka
    assert client.get("/case-studies/does-not-exist/").status_code == 404


def test_home_shows_ongoing_threats_and_new_statistics(client, demo):  # type: ignore[no-untyped-def]
    html = client.get("/?lang=en").get_data(as_text=True)
    assert "Featured courses" not in html and "learners" not in html and "completion" not in html
    assert "Ongoing threats" in html and html.count('class="course-card case-card"') == 3
    assert "case studies</span>" in html and "ongoing threats</span>" in html
    ka = client.get("/?lang=ka").get_data(as_text=True)
    assert "მიმდინარე საფრთხეები" in ka and "რჩეული კურსები" not in ka
    # newest first, capped by the setting
    from app.services import settings_service

    settings_service.set_value("site.home_threats_limit", 2)
    html = client.get("/?lang=en").get_data(as_text=True)
    assert html.count('class="course-card case-card"') == 2
    first = html.index("qr-parking-scam")
    assert first < html.index("deepfake-voice-call")


def test_drafts_are_hidden_from_visitors_but_shown_to_admins(client, demo, admin):  # type: ignore[no-untyped-def]
    case = db.session.query(CaseStudy).filter_by(slug="qr-parking-scam").one()
    case.is_published = False
    db.session.commit()
    assert client.get("/case-studies/qr-parking-scam/").status_code == 404
    assert client.get("/case-studies/").get_data(as_text=True).count("case-card") == 2
    login(client, admin)
    assert client.get("/case-studies/qr-parking-scam/").status_code == 200


def test_search_finds_case_studies(client, demo):  # type: ignore[no-untyped-def]
    html = client.get("/search/?q=deepfake&lang=en").get_data(as_text=True)
    assert "Case studies (1)" in html and "deepfake-voice-call" in html


# ---- admin ---------------------------------------------------------------
def test_admin_case_study_crud(client, logged_in_admin, demo):  # type: ignore[no-untyped-def]
    category = case_study_service.category_by_slug("ongoing-threats")
    cover, name = _png()
    response = post(
        client,
        "/admin/case-studies/new",
        {
            "title_ka": "ახალი ქეისი",
            "title_en": "New case",
            "slug": "new-case",
            "description_ka": "<p>აღწერა</p><script>alert(1)</script>",
            "description_en": "<p>Description</p>",
            "about_ka": "<p>დეტალები</p>",
            "about_en": "<p>Details</p>",
            "category_id": str(category.id),
            "sort_order": "0",
            "is_published": "y",
            "cover": (cover, name),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302, response.data[:600]
    case = db.session.query(CaseStudy).filter_by(slug="new-case").one()
    assert case.is_published and case.published_at and case.cover is not None
    assert "<script" not in case.text("description", "ka")
    edit_url = f"/admin/case-studies/{case.id}"
    assert client.get(edit_url).status_code == 200

    # extra section from the admin list, then a picture
    title = case_study_service.section_titles()[0]
    response = post(
        client,
        f"{edit_url}/sections",
        {
            "sec-csrf_token": get_csrf(client),
            "sec-title_id": str(title.id),
            "sec-body_ka": "<p>ფრთხილად</p>",
            "sec-body_en": "<p>Careful</p>",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    case = db.session.get(CaseStudy, case.id)
    assert [s.heading("en") for s in case.sections] == ["Be careful of"]
    img, img_name = _png()
    response = post(
        client,
        f"{edit_url}/images",
        {
            "img-csrf_token": get_csrf(client),
            "img-file": (img, img_name),
            "img-caption_ka": "სქრინშოტი",
            "img-caption_en": "Screenshot",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    db.session.expire_all()
    case = db.session.get(CaseStudy, case.id)
    assert len(case.images) == 1 and case.images[0].media.is_public

    public = client.get("/case-studies/new-case/?lang=en").get_data(as_text=True)
    assert "<h2>Be careful of</h2>" in public and 'alt="Screenshot"' in public
    assert "<h2>Description</h2>" in public and "<h2>About</h2>" in public

    # unpublish through the form, remove the section, delete the case study
    response = post(
        client,
        edit_url,
        {
            "title_ka": "ახალი ქეისი",
            "description_ka": "<p>აღწერა</p>",
            "about_ka": "<p>დეტალები</p>",
            "category_id": "0",
            "sort_order": "1",
            "submit": "1",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    case = db.session.get(CaseStudy, case.id)
    assert case.is_published is False and case.category_id is None
    section = case.sections[0]
    assert post(client, f"{edit_url}/sections/{section.id}/delete").status_code == 302
    assert post(client, f"{edit_url}/delete").status_code == 302
    assert db.session.get(CaseStudy, case.id) is None


def test_admin_case_categories_and_section_titles(client, logged_in_admin, demo):  # type: ignore[no-untyped-def]
    response = post(
        client,
        "/admin/case-studies/categories/",
        {
            "slug": "resolved",
            "name_ka": "მოგვარებული",
            "name_en": "Resolved",
            "icon": "shield",
            "color": "green",
            "sort_order": "2",
            "is_active": "y",
        },
    )
    assert response.status_code == 302
    category = case_study_service.category_by_slug("resolved")
    assert category.name("en") == "Resolved"
    assert "resolved" in client.get("/case-studies/").get_data(as_text=True)
    response = post(
        client,
        f"/admin/case-studies/categories/{category.id}",
        {
            "slug": "resolved",
            "name_ka": "მოგვარებული",
            "name_en": "Resolved cases",
            "icon": "shield",
            "color": "green",
            "sort_order": "2",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    assert case_study_service.category_by_slug("resolved", active_only=False).is_active is False
    assert post(client, f"/admin/case-studies/categories/{category.id}/delete").status_code == 302
    assert case_study_service.category_by_slug("resolved", active_only=False) is None

    response = post(
        client,
        "/admin/case-studies/section-titles/",
        {
            "name_ka": "რა უნდა გავაკეთოთ",
            "name_en": "What to do",
            "sort_order": "3",
            "is_active": "y",
        },
    )
    assert response.status_code == 302
    titles = case_study_service.section_titles()
    assert [t.name_en for t in titles][-1] == "What to do"
    assert (
        post(client, f"/admin/case-studies/section-titles/{titles[-1].id}/delete").status_code
        == 302
    )
    assert len(case_study_service.section_titles()) == 2


def test_case_study_admin_requires_permission(client, logged_in_student, demo):  # type: ignore[no-untyped-def]
    for url in (
        "/admin/case-studies/",
        "/admin/case-studies/new",
        "/admin/case-studies/categories/",
        "/admin/resources/",
    ):
        assert client.get(url).status_code == 403, url


# ---- resources -----------------------------------------------------------
def test_platform_resources_visibility(client, logged_in_admin, demo):  # type: ignore[no-untyped-def]
    pdf, name = _pdf()
    response = post(
        client,
        "/admin/resources/",
        {
            "file": (pdf, name),
            "title_ka": "სახელმძღვანელო",
            "title_en": "Guide",
            "description_ka": "PDF",
            "is_visible": "y",
            "sort_order": "0",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302, response.data[:600]
    resource = db.session.query(Resource).one()
    assert resource.is_visible and resource.media.is_public
    # a non-PDF is refused
    bad = post(
        client,
        "/admin/resources/",
        {"file": (io.BytesIO(b"hello"), "notes.txt"), "title_ka": "x", "is_visible": "y"},
        content_type="multipart/form-data",
    )
    assert bad.status_code == 200 and db.session.query(Resource).count() == 1

    logout(client)
    html = client.get("/resources/").get_data(as_text=True)
    assert "სახელმძღვანელო" in html and f"/media/public/{resource.media_id}" in html
    assert client.get(f"/media/public/{resource.media_id}").status_code == 200

    login(client, logged_in_admin)
    assert post(client, f"/admin/resources/{resource.id}/toggle").status_code == 302
    db.session.expire_all()
    resource = db.session.get(Resource, resource.id)
    assert resource.is_visible is False and resource.media.is_public is False
    logout(client)
    html = client.get("/resources/").get_data(as_text=True)
    assert "სახელმძღვანელო" not in html
    assert client.get(f"/media/public/{resource.media_id}").status_code == 404

    login(client, logged_in_admin)
    assert post(client, f"/admin/resources/{resource.id}/delete").status_code == 302
    assert db.session.query(Resource).count() == 0


def test_course_files_appear_for_enrolled_learners_only(client, demo, student, instructor):  # type: ignore[no-untyped-def]
    from app.models import Course
    from app.services import course_service

    course = db.session.query(Course).filter_by(platform="elearning").first()
    lesson = course_service.visible_lessons(course)[0]
    course_service.add_resource(
        lesson,
        title_ka="ჩეკლისტი",
        title_en="Checklist",
        url="https://example.org/c",
        media_id=None,
        actor=instructor,
    )
    anonymous = client.get("/resources/").get_data(as_text=True)
    assert "ჩეკლისტი" not in anonymous and "from-courses" in anonymous
    login(client, student)
    before = client.get("/resources/").get_data(as_text=True)
    assert "ჩეკლისტი" not in before
    enrollment_service.enroll(student, course)
    after = client.get("/resources/").get_data(as_text=True)
    assert "ჩეკლისტი" in after and course.title("ka") in after
    enrollment = enrollment_service.get_enrollment(student, course)
    enrollment.status = EnrollmentStatus.DROPPED
    db.session.commit()
    assert "ჩეკლისტი" not in client.get("/resources/").get_data(as_text=True)
    assert resource_service.course_resources_for(student) == []
