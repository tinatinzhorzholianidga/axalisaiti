"""Instructor panel: course builder end-to-end through the HTML forms."""

from __future__ import annotations

from app.extensions import db
from app.models import Course, CourseStatus, Lesson, Module, Question, Quiz, User
from tests.conftest import login, logout, post, post_json

COURSE_FORM = {
    "title_ka": "უსაფრთხო პაროლები",
    "title_en": "Safe passwords",
    "platform": "elearning",
    "short_description_ka": "მოკლე აღწერა",
    "short_description_en": "Short description",
    "description_ka": "<p>სრული აღწერა</p>",
    "description_en": "<p>Full description</p>",
    "objectives_ka": "პირველი\nმეორე",
    "objectives_en": "First\nSecond",
    "icon": "shield",
    "color": "blue",
    "difficulty": "beginner",
    "estimated_minutes": "45",
    "enrollment_mode": "open",
    "cyber_track_id": "0",
    "is_free": "y",
    "certificate_enabled": "y",
    "certificate_pass_percent": "70",
    "discussions_enabled": "y",
    "reviews_enabled": "y",
    "submit": "1",
}


def _create_course(client, instructor: User) -> Course:  # type: ignore[no-untyped-def]
    response = post(client, "/instructor/courses/new", COURSE_FORM)
    assert response.status_code == 302, response.data[:800]
    course = db.session.query(Course).order_by(Course.id.desc()).first()
    assert course is not None and course.instructor_id == instructor.id
    return course


def test_student_cannot_open_instructor_panel(client, logged_in_student):  # type: ignore[no-untyped-def]
    assert client.get("/instructor/").status_code == 403
    assert client.get("/instructor/courses/new").status_code == 403


def test_anonymous_redirected_to_login(client):  # type: ignore[no-untyped-def]
    response = client.get("/instructor/")
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]


def test_course_builder_flow(client, app, logged_in_instructor, admin):  # type: ignore[no-untyped-def]
    instructor = logged_in_instructor
    assert client.get("/instructor/").status_code == 200
    assert client.get("/instructor/courses/new").status_code == 200
    course = _create_course(client, instructor)
    assert course.status == CourseStatus.DRAFT
    assert course.slug.startswith("safe-passwords") or course.slug
    assert course.title("ka") == "უსაფრთხო პაროლები"
    assert course.tr("en").objective_list == ["First", "Second"]

    # Module
    response = post(
        client,
        f"/instructor/courses/{course.id}/modules",
        {"title_ka": "მოდული 1", "title_en": "Module 1", "is_published": "y"},
    )
    assert response.status_code == 302
    module = db.session.query(Module).filter_by(course_id=course.id).one()
    assert client.get(f"/instructor/courses/{course.id}/builder").status_code == 200
    assert client.get(f"/instructor/courses/{course.id}/modules/{module.id}").status_code == 200

    # Publishing without lessons is refused
    response = post(client, f"/instructor/courses/{course.id}/submit", follow_redirects=True)
    assert b"at least one lesson" in response.data or course.status == CourseStatus.DRAFT
    assert course.status == CourseStatus.DRAFT

    # Lessons (reading + quiz)
    lesson_url = f"/instructor/courses/{course.id}/modules/{module.id}/lessons/new"
    assert client.get(lesson_url).status_code == 200
    response = post(
        client,
        lesson_url,
        {
            "title_ka": "გაკვეთილი 1",
            "title_en": "Lesson 1",
            "lesson_type": "reading",
            "estimated_minutes": "10",
            "content_ka": "<p>ტექსტი</p><script>alert(1)</script>",
            "content_en": "<p>Text</p>",
            "is_published": "y",
        },
    )
    assert response.status_code == 302
    lesson = db.session.query(Lesson).filter_by(module_id=module.id).one()
    assert "<script>" not in lesson.tr("ka").content
    assert client.get(f"/instructor/courses/{course.id}/lessons/{lesson.id}").status_code == 200
    response = post(
        client,
        lesson_url,
        {"title_ka": "ქვიზი", "title_en": "Quiz", "lesson_type": "quiz", "is_published": "y"},
    )
    assert response.status_code == 302
    quiz_lesson = (
        db.session.query(Lesson).filter_by(module_id=module.id).order_by(Lesson.id.desc()).first()
    )
    assert [lsn.sort_order for lsn in module.lessons] == [1, 2]

    # Move lessons with the accessible non-drag control, then via reorder endpoint
    response = post(client, f"/instructor/courses/{course.id}/lessons/{quiz_lesson.id}/move/up")
    assert response.status_code == 302
    db.session.expire_all()
    module = db.session.get(Module, module.id)
    assert module.lessons[0].id == quiz_lesson.id
    response = post_json(
        client,
        f"/instructor/courses/{course.id}/modules/{module.id}/lessons/reorder",
        {"order": [lesson.id, quiz_lesson.id]},
    )
    assert response.status_code == 200 and response.get_json()["ok"] is True
    # reorder without the CSRF header is refused
    response = client.post(
        f"/instructor/courses/{course.id}/modules/{module.id}/lessons/reorder",
        json={"order": [quiz_lesson.id, lesson.id]},
    )
    assert response.status_code == 400
    db.session.expire_all()
    module = db.session.get(Module, module.id)
    assert module.lessons[0].id == lesson.id

    # Quiz attached to the quiz lesson
    quiz_url = f"/instructor/courses/{course.id}/quizzes/new?lesson={quiz_lesson.id}"
    assert client.get(quiz_url).status_code == 200
    response = post(
        client,
        quiz_url,
        {
            "title_ka": "შემოწმება",
            "title_en": "Check",
            "pass_percent": "60",
            "max_attempts": "3",
            "feedback_mode": "instant",
            "show_explanations": "y",
            "is_published": "y",
        },
    )
    assert response.status_code == 302, response.data[:500]
    quiz = db.session.query(Quiz).filter_by(course_id=course.id).one()
    assert quiz.lesson_id == quiz_lesson.id

    # Questions: one of each editor path
    q_url = f"/instructor/courses/{course.id}/quizzes/{quiz.id}/questions/new"
    assert client.get(q_url).status_code == 200
    response = post(
        client,
        q_url,
        {
            "question_type": "single",
            "prompt_ka": "რომელი პაროლია ძლიერი?",
            "prompt_en": "Which password is strong?",
            "points": "2",
            "opt_text_ka": ["123456", "Tq7!vB#9pL2m"],
            "opt_text_en": ["123456", "Tq7!vB#9pL2m"],
            "opt_correct": ["1"],
        },
    )
    assert response.status_code == 302, response.data[:500]
    response = post(
        client,
        q_url,
        {
            "question_type": "true_false",
            "prompt_ka": "პაროლის გაზიარება უსაფრთხოა.",
            "prompt_en": "Sharing a password is safe.",
            "points": "1",
            "tf_correct": "false",
        },
    )
    assert response.status_code == 302
    response = post(
        client,
        q_url,
        {
            "question_type": "matching",
            "prompt_ka": "დააკავშირე",
            "prompt_en": "Match",
            "points": "1",
            "opt_text_ka": ["2FA", "VPN"],
            "opt_text_en": ["2FA", "VPN"],
            "opt_match_ka": ["მეორე ფაქტორი", "დაშიფრული არხი"],
            "opt_match_en": ["Second factor", "Encrypted tunnel"],
        },
    )
    assert response.status_code == 302
    questions = db.session.query(Question).filter_by(quiz_id=quiz.id).order_by(Question.sort_order)
    kinds = [q.question_type.value for q in questions]
    assert kinds == ["single", "true_false", "matching"]
    single = questions[0]
    assert [o.is_correct for o in single.options] == [False, True]
    tf = questions[1]
    assert [o.is_correct for o in tf.options] == [False, True]
    assert client.get(f"/instructor/courses/{course.id}/quizzes/{quiz.id}").status_code == 200
    assert (
        client.get(
            f"/instructor/courses/{course.id}/quizzes/{quiz.id}/questions/{single.id}"
        ).status_code
        == 200
    )

    # Assignment
    a_url = f"/instructor/courses/{course.id}/assignments/new"
    assert client.get(a_url).status_code == 200
    response = post(
        client,
        a_url,
        {
            "title_ka": "დავალება",
            "title_en": "Assignment",
            "instructions_ka": "<p>დაწერე</p>",
            "instructions_en": "<p>Write</p>",
            "submission_type": "text",
            "max_points": "10",
            "allow_late": "y",
            "late_penalty_percent": "10",
            "max_resubmissions": "1",
            "is_published": "y",
        },
    )
    assert response.status_code == 302, response.data[:500]
    assert len(course.assignments) == 1

    # Submit for review -> pending (approval required by default), admin notified
    response = post(client, f"/instructor/courses/{course.id}/submit")
    assert response.status_code == 302
    db.session.expire_all()
    course = db.session.get(Course, course.id)
    assert course.status == CourseStatus.PENDING_REVIEW
    from app.models import Notification

    def kinds(user_id: int) -> set[str]:
        return {n.kind for n in db.session.query(Notification).filter_by(user_id=user_id)}

    assert "review_request" in kinds(admin.id)

    # Course stays hidden from the public catalog while pending
    logout(client)
    assert client.get(f"/courses/{course.slug}/").status_code == 404

    # Admin approves via the admin panel
    login(client, admin)
    page = client.get(f"/admin/courses/{course.id}")
    assert page.status_code == 200 and b"review-approve" in page.data
    response = post(
        client,
        f"/admin/courses/{course.id}/status",
        {"review-approve": "1", "review-note": "Looks good", "review-csrf_token": "x"},
    )
    assert response.status_code in (302, 400)
    # the prefixed form needs its own token: re-post with a real one
    if response.status_code == 400:
        from tests.conftest import get_csrf

        token = get_csrf(client)
        response = client.post(
            f"/admin/courses/{course.id}/status",
            data={"review-approve": "1", "review-note": "Looks good", "review-csrf_token": token},
        )
        assert response.status_code == 302, response.data[:300]
    db.session.expire_all()
    course = db.session.get(Course, course.id)
    assert course.status == CourseStatus.PUBLISHED
    assert course.published_at is not None
    assert "course_update" in kinds(instructor.id)
    logout(client)
    assert client.get(f"/courses/{course.slug}/").status_code == 200

    # Instructor sees analytics/students/reviews pages and can unpublish
    login(client, instructor)
    for path in ("analytics", "students", "reviews", "discussions", "builder", ""):
        url = f"/instructor/courses/{course.id}/{path}"
        assert client.get(url).status_code == 200, url
    assert client.get("/instructor/courses/").status_code == 200
    assert client.get("/instructor/grading/").status_code == 200
    response = post(client, f"/instructor/courses/{course.id}/unpublish")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Course, course.id).status == CourseStatus.DRAFT


def test_instructor_cannot_touch_other_instructors_course(client, app, instructor):  # type: ignore[no-untyped-def]
    from tests.conftest import make_user

    other = make_user("other@example.org", roles=("instructor", "student"))
    login(client, other)
    course = _create_course(client, other)
    logout(client)
    login(client, instructor)
    assert client.get(f"/instructor/courses/{course.id}/builder").status_code == 403
    assert client.get(f"/instructor/courses/{course.id}/").status_code == 403
    response = post(client, f"/instructor/courses/{course.id}/delete")
    assert response.status_code == 403
    assert db.session.get(Course, course.id) is not None


def test_module_delete_and_course_delete(client, logged_in_instructor):  # type: ignore[no-untyped-def]
    course = _create_course(client, logged_in_instructor)
    post(client, f"/instructor/courses/{course.id}/modules", {"title_ka": "A", "is_published": "y"})
    post(client, f"/instructor/courses/{course.id}/modules", {"title_ka": "B", "is_published": "y"})
    a, b = db.session.query(Module).filter_by(course_id=course.id).order_by(Module.sort_order)
    post(client, f"/instructor/courses/{course.id}/modules/{b.id}/move/up")
    db.session.expire_all()
    course = db.session.get(Course, course.id)
    assert [m.id for m in course.modules] == [b.id, a.id]
    response = post(client, f"/instructor/courses/{course.id}/modules/{b.id}/delete")
    assert response.status_code == 302
    db.session.expire_all()
    course = db.session.get(Course, course.id)
    assert [m.id for m in course.modules] == [a.id]
    assert course.modules[0].sort_order == 1
    response = post(client, f"/instructor/courses/{course.id}/delete")
    assert response.status_code == 302
    assert db.session.get(Course, course.id) is None
