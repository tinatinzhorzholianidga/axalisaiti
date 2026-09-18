"""Quizzes (six question types, timing, attempts, feedback modes), assignments, grading, certificates."""

from __future__ import annotations

import io
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import (
    AssignmentSubmission,
    Certificate,
    Course,
    Notification,
    QuestionType,
    QuizAttempt,
    utcnow,
)
from app.services import (
    assignment_service,
    enrollment_service,
    progress_service,
    quiz_service,
    seed_service,
)
from app.services.quiz_service import QuizError
from tests.conftest import login, post


@pytest.fixture
def demo(app):  # type: ignore[no-untyped-def]
    seed_service.seed_demo_content()
    return db.session.query(Course).filter_by(slug="phishing-awareness").one()


def _correct_form(attempt: QuizAttempt) -> dict:
    """Build a fully correct submission for any question mix."""
    form: dict = {}
    for q in quiz_service.ordered_questions(attempt):
        key = f"q{q.id}"
        if q.question_type in {QuestionType.SINGLE, QuestionType.TRUE_FALSE}:
            form[key] = str(next(o.id for o in q.options if o.is_correct))
        elif q.question_type == QuestionType.MULTIPLE:
            form[key] = [str(o.id) for o in q.options if o.is_correct]
        elif q.question_type == QuestionType.SHORT_ANSWER:
            form[key] = q.accepted_answers[0].upper() + "  "
        elif q.question_type == QuestionType.ORDERING:
            for o in q.options:
                form[f"{key}_{o.id}"] = str(o.correct_position)
        elif q.question_type == QuestionType.MATCHING:
            for o in q.options:
                form[f"{key}_{o.id}"] = str(o.id)
    return form


def test_grading_all_six_types(app, demo, student):  # type: ignore[no-untyped-def]
    course = db.session.query(Course).filter_by(slug="basic-cybersecurity").one()
    enrollment_service.enroll(student, course)
    quiz = course.final_quiz
    assert {q.question_type for q in quiz.questions} == set(QuestionType)
    attempt = quiz_service.start_attempt(student, quiz)
    assert attempt.expires_at is not None and len(attempt.question_order) == 12

    class Form(dict):
        def getlist(self, key):  # type: ignore[no-untyped-def]
            value = self.get(key, [])
            return value if isinstance(value, list) else [value]

    attempt = quiz_service.submit_attempt(attempt, Form(_correct_form(attempt)))
    assert attempt.percent == 100 and attempt.passed
    assert all(a.is_correct for a in attempt.answers)
    # wrong multiple-choice selection gets zero, partial ordering gets zero
    attempt2 = quiz_service.start_attempt(student, quiz)
    form = _correct_form(attempt2)
    multi = next(q for q in quiz.questions if q.question_type == QuestionType.MULTIPLE)
    form[f"q{multi.id}"] = [str(multi.options[0].id)]
    ordering = next(q for q in quiz.questions if q.question_type == QuestionType.ORDERING)
    form[f"q{ordering.id}_{ordering.options[0].id}"] = "5"
    attempt2 = quiz_service.submit_attempt(attempt2, Form(form))
    assert attempt2.percent < 100
    wrong = {a.question_id for a in attempt2.answers if not a.is_correct}
    assert {multi.id, ordering.id} <= wrong


def test_quiz_flow_via_http(client, demo, student):  # type: ignore[no-untyped-def]
    login(client, student)
    lesson = demo.modules[0].lessons[1]
    quiz = lesson.quiz
    # not enrolled -> redirected to the course page
    response = client.get(f"/quiz/{quiz.id}/")
    assert response.status_code == 302
    post(client, f"/courses/{demo.slug}/enroll")
    response = client.get(f"/quiz/{quiz.id}/")
    assert response.status_code == 200 and b"Start attempt" in response.data
    response = post(client, f"/quiz/{quiz.id}/start")
    attempt = db.session.query(QuizAttempt).one()
    assert response.headers["Location"].endswith(f"/quiz/attempt/{attempt.id}/")
    page = client.get(f"/quiz/attempt/{attempt.id}/").data.decode()
    assert 'name="q' in page and "onclick" not in page
    form = _correct_form(attempt)
    single = next(q for q in quiz.questions if q.question_type == QuestionType.SINGLE)
    form[f"q{single.id}"] = str(next(o.id for o in single.options if not o.is_correct))
    response = post(client, f"/quiz/attempt/{attempt.id}/", form)
    assert response.status_code == 302
    result = client.get(f"/quiz/result/{attempt.id}/").data.decode()
    db.session.refresh(attempt)
    assert attempt.status.value == "submitted" and f"{attempt.percent:.0f}%" in result
    assert "Incorrect" in result and "Correct" in result  # instant feedback shows review
    # passing marks the lesson complete and creates a notification
    if attempt.passed:
        lp = progress_service.lesson_progress_map(student, demo)[lesson.id]
        assert lp.status.value == "completed"
    assert db.session.query(Notification).filter_by(kind="quiz_result").count() == 1


def test_attempt_limits_and_expiry(app, demo, student):  # type: ignore[no-untyped-def]
    enrollment_service.enroll(student, demo)
    quiz = demo.modules[0].lessons[1].quiz
    quiz.max_attempts = 1
    quiz.time_limit_minutes = 1
    db.session.commit()
    attempt = quiz_service.start_attempt(student, quiz)
    assert quiz_service.open_attempt(student, quiz) is attempt
    attempt.expires_at = utcnow() - timedelta(minutes=5)
    db.session.commit()
    with pytest.raises(QuizError, match="Time is up"):
        quiz_service.submit_attempt(attempt, {})
    assert attempt.status.value == "expired"
    with pytest.raises(QuizError, match="all attempts"):
        quiz_service.start_attempt(student, quiz)


def test_delayed_feedback_hides_details(app, demo, student):  # type: ignore[no-untyped-def]
    from app.models import FeedbackMode

    enrollment_service.enroll(student, demo)
    quiz = demo.modules[0].lessons[1].quiz
    quiz.feedback_mode = FeedbackMode.DELAYED
    quiz.max_attempts = 3
    db.session.commit()
    attempt = quiz_service.start_attempt(student, quiz)

    class Form(dict):
        def getlist(self, key):  # type: ignore[no-untyped-def]
            return []

    attempt = quiz_service.submit_attempt(attempt, Form())
    assert not attempt.passed
    assert quiz_service.show_details(student, attempt) is False


def test_assignment_submission_and_grading(client, demo, student, instructor):  # type: ignore[no-untyped-def]
    demo.instructor_id = instructor.id
    db.session.commit()
    login(client, student)
    post(client, f"/courses/{demo.slug}/enroll")
    assignment = demo.modules[1].lessons[1].assignment
    page = client.get(f"/assignment/{assignment.id}/")
    assert page.status_code == 200
    response = post(
        client, f"/assignment/{assignment.id}/", {"text_content": ""}, follow_redirects=True
    )
    assert b"write your answer" in response.data
    response = post(
        client,
        f"/assignment/{assignment.id}/",
        {"text_content": "My incident report " * 20},
        follow_redirects=True,
    )
    assert b"submitted" in response.data
    submission = db.session.query(AssignmentSubmission).one()
    assert submission.attempt_number == 1 and not submission.is_late
    # file upload is rejected for text-only assignments
    response = post(
        client,
        f"/assignment/{assignment.id}/",
        {"text_content": "again", "file": (io.BytesIO(b"%PDF-1.4 test"), "report.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"text only" in response.data
    # instructor grades: late penalty not applied, lesson completed, notification sent
    grade = assignment_service.grade(
        submission, grader=instructor, points=18, feedback="<b>Good</b><script>x</script>"
    )
    assert (
        grade.points == 18 and "<script>" not in grade.feedback and "<b>Good</b>" in grade.feedback
    )
    assert submission.status.value == "graded"
    lp = progress_service.lesson_progress_map(student, demo)[assignment.lesson_id]
    assert lp.status.value == "completed"
    assert (
        db.session.query(Notification)
        .filter_by(kind="assignment_feedback", user_id=student.id)
        .count()
        == 1
    )
    # resubmission limit: max_resubmissions=2 -> three submissions total
    for _ in range(2):
        assignment_service.submit(student, assignment, text="more", file=None)
    ok, reason = assignment_service.can_submit(student, assignment)
    assert not ok and "attempts" in reason


def test_file_assignment_upload_validation(app, demo, student, upload_dir):  # type: ignore[no-untyped-def]
    from werkzeug.datastructures import FileStorage

    from app.services.assignment_service import AssignmentError

    soc = db.session.query(Course).filter_by(slug="soc-fundamentals").one()
    enrollment_service.enroll(student, soc)
    assignment = soc.modules[1].lessons[1].assignment
    fake_pdf = FileStorage(stream=io.BytesIO(b"MZ\x90\x00 not a pdf"), filename="ticket.pdf")
    with pytest.raises(AssignmentError, match=r"does not match|signature"):
        assignment_service.submit(student, assignment, text="", file=fake_pdf)
    exe = FileStorage(stream=io.BytesIO(b"MZ\x90\x00"), filename="ticket.exe")
    with pytest.raises(AssignmentError, match="not allowed"):
        assignment_service.submit(student, assignment, text="", file=exe)
    real_txt = FileStorage(
        stream=io.BytesIO(b"Priority P1: brute force with success\n"), filename="ticket.txt"
    )
    submission = assignment_service.submit(student, assignment, text="see file", file=real_txt)
    assert submission.file is not None and submission.file.stored_name.endswith(".txt")
    assert submission.file.stored_name != "ticket.txt"
    assert app.config["UPLOAD_PATH"] + "/assignments/" + submission.file.stored_name


def test_course_completion_issues_certificate(app, demo, student):  # type: ignore[no-untyped-def]
    enrollment_service.enroll(student, demo)
    demo.certificate_enabled = True
    db.session.commit()
    for module in demo.modules:
        for lesson in module.lessons:
            progress_service.complete_lesson(student, demo, lesson)
    progress = progress_service.get_course_progress(student, demo)
    # quiz not passed yet -> not complete
    assert not progress.is_complete
    quiz = demo.modules[0].lessons[1].quiz
    attempt = quiz_service.start_attempt(student, quiz)

    class Form(dict):
        def getlist(self, key):  # type: ignore[no-untyped-def]
            value = self.get(key, [])
            return value if isinstance(value, list) else [value]

    quiz_service.submit_attempt(attempt, Form(_correct_form(attempt)))
    progress = progress_service.get_course_progress(student, demo)
    assert progress.is_complete and progress.percent == 100
    certificate = (
        db.session.query(Certificate).filter_by(user_id=student.id, course_id=demo.id).one()
    )
    assert (
        certificate.public_id.startswith("EL-") and certificate.recipient_name == student.full_name
    )
    assert db.session.query(Notification).filter_by(kind="certificate").count() == 1
    # verification page works publicly and the achievement was awarded
    from app.models import UserAchievement

    codes = {
        ua.achievement.code
        for ua in db.session.query(UserAchievement).filter_by(user_id=student.id)
    }
    assert {"first_course", "first_certificate"} <= codes
    client = app.test_client()
    page = client.get(f"/certificates/verify/{certificate.public_id}")
    assert page.status_code == 200 and b"Valid certificate" in page.data
    assert student.email.encode() not in page.data
