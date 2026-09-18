"""Quiz attempts: start, answer parsing, grading for six question types."""

from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models import (
    AttemptStatus,
    FeedbackMode,
    Question,
    QuestionType,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    User,
    utcnow,
)
from app.services import achievement_service, audit_service, notification_service

GRACE_SECONDS = 30


class QuizError(Exception):
    pass


def user_attempts(user: User, quiz: Quiz) -> list[QuizAttempt]:
    return list(
        db.session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user.id, QuizAttempt.quiz_id == quiz.id)
            .order_by(QuizAttempt.attempt_number)
        ).scalars()
    )


def open_attempt(user: User, quiz: Quiz) -> QuizAttempt | None:
    attempt = db.session.execute(
        select(QuizAttempt).where(
            QuizAttempt.user_id == user.id,
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    ).scalar_one_or_none()
    if attempt and not attempt.is_open:
        _expire(attempt)
        return None
    return attempt


def attempts_left(user: User, quiz: Quiz) -> int | None:
    if quiz.max_attempts is None:
        return None
    used = len([a for a in user_attempts(user, quiz) if a.status != AttemptStatus.IN_PROGRESS])
    return max(0, quiz.max_attempts - used)


def best_attempt(user: User, quiz: Quiz) -> QuizAttempt | None:
    finished = [a for a in user_attempts(user, quiz) if a.status == AttemptStatus.SUBMITTED]
    return max(finished, key=lambda a: a.percent, default=None)


def start_attempt(user: User, quiz: Quiz) -> QuizAttempt:
    if not quiz.is_published or not quiz.questions:
        raise QuizError("This quiz is not available.")
    existing = open_attempt(user, quiz)
    if existing:
        return existing
    left = attempts_left(user, quiz)
    if left is not None and left <= 0:
        raise QuizError("You have used all attempts for this quiz.")
    number = len(user_attempts(user, quiz)) + 1
    question_ids = [q.id for q in quiz.questions]
    if quiz.shuffle_questions:
        random.shuffle(question_ids)
    option_order: dict[str, list[int]] = {}
    for question in quiz.questions:
        ids = [o.id for o in question.options]
        if quiz.shuffle_options and question.question_type != QuestionType.TRUE_FALSE:
            random.shuffle(ids)
        option_order[str(question.id)] = ids
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user.id,
        attempt_number=number,
        question_order=question_ids,
        option_order=option_order,
        max_points=quiz.max_points,
        expires_at=(utcnow() + timedelta(minutes=quiz.time_limit_minutes))
        if quiz.time_limit_minutes
        else None,
    )
    db.session.add(attempt)
    audit_service.record("quiz.attempt_started", target=quiz, actor=user, meta={"attempt": number})
    db.session.commit()
    return attempt


def ordered_questions(attempt: QuizAttempt) -> list[Question]:
    by_id = {q.id: q for q in attempt.quiz.questions}
    ordered = [by_id[qid] for qid in attempt.question_order if qid in by_id]
    return ordered or list(attempt.quiz.questions)


def ordered_options(attempt: QuizAttempt, question: Question):  # type: ignore[no-untyped-def]
    ids = attempt.option_order.get(str(question.id)) or [o.id for o in question.options]
    by_id = {o.id: o for o in question.options}
    return [by_id[i] for i in ids if i in by_id]


# ---- answer parsing ---------------------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def parse_answers(attempt: QuizAttempt, form: Any) -> dict[int, Any]:
    """Extract answers from the posted form: q<id> fields per question type."""
    answers: dict[int, Any] = {}
    for question in ordered_questions(attempt):
        key = f"q{question.id}"
        qtype = question.question_type
        if qtype in {QuestionType.SINGLE, QuestionType.TRUE_FALSE}:
            raw = form.get(key)
            answers[question.id] = int(raw) if raw and raw.isdigit() else None
        elif qtype == QuestionType.MULTIPLE:
            answers[question.id] = sorted({int(v) for v in form.getlist(key) if str(v).isdigit()})
        elif qtype == QuestionType.SHORT_ANSWER:
            answers[question.id] = (form.get(key) or "")[:500]
        elif qtype == QuestionType.ORDERING:
            positions: dict[int, int] = {}
            for option in question.options:
                raw = form.get(f"{key}_{option.id}")
                if raw and raw.isdigit():
                    positions[option.id] = int(raw)
            answers[question.id] = [
                oid for oid, _ in sorted(positions.items(), key=lambda kv: kv[1])
            ]
        elif qtype == QuestionType.MATCHING:
            pairs: dict[str, int | None] = {}
            for option in question.options:
                raw = form.get(f"{key}_{option.id}")
                pairs[str(option.id)] = int(raw) if raw and raw.isdigit() else None
            answers[question.id] = pairs
    return answers


def grade_question(question: Question, answer: Any) -> tuple[bool, float]:
    qtype = question.question_type
    correct_ids = {o.id for o in question.options if o.is_correct}
    if qtype in {QuestionType.SINGLE, QuestionType.TRUE_FALSE}:
        ok = answer is not None and answer in correct_ids
    elif qtype == QuestionType.MULTIPLE:
        ok = bool(correct_ids) and set(answer or []) == correct_ids
    elif qtype == QuestionType.SHORT_ANSWER:
        accepted = {_normalize(a) for a in (question.accepted_answers or []) if str(a).strip()}
        ok = bool(accepted) and _normalize(str(answer)) in accepted
    elif qtype == QuestionType.ORDERING:
        expected = [
            o.id
            for o in sorted(question.options, key=lambda o: (o.correct_position or 0, o.sort_order))
        ]
        ok = list(answer or []) == expected
    elif qtype == QuestionType.MATCHING:
        ok = bool(question.options) and all(
            (answer or {}).get(str(o.id)) == o.id for o in question.options
        )
    else:
        ok = False
    return ok, float(question.points) if ok else 0.0


def submit_attempt(attempt: QuizAttempt, form: Any) -> QuizAttempt:
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise QuizError("This attempt was already submitted.")
    if attempt.expires_at and utcnow() > attempt.expires_at + timedelta(seconds=GRACE_SECONDS):
        _expire(attempt)
        raise QuizError("Time is up for this attempt.")
    answers = parse_answers(attempt, form)
    score = 0.0
    for question in ordered_questions(attempt):
        answer = answers.get(question.id)
        ok, points = grade_question(question, answer)
        score += points
        attempt.answers.append(
            QuizAnswer(question_id=question.id, answer=answer, is_correct=ok, points_awarded=points)
        )
    attempt.score_points = score
    attempt.max_points = attempt.quiz.max_points
    attempt.percent = round(100.0 * score / attempt.max_points, 1) if attempt.max_points else 0.0
    attempt.passed = attempt.percent >= attempt.quiz.pass_percent
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = utcnow()
    audit_service.record(
        "quiz.attempt_submitted",
        target=attempt.quiz,
        actor=attempt.user,
        meta={
            "attempt": attempt.attempt_number,
            "percent": attempt.percent,
            "passed": attempt.passed,
        },
    )
    db.session.commit()

    from app.services import progress_service

    course = attempt.quiz.course
    if attempt.passed and attempt.quiz.lesson:
        progress_service.complete_lesson(attempt.user, course, attempt.quiz.lesson)
    else:
        progress_service.recalculate(attempt.user, course)
    achievement_service.check_quiz(attempt.user, attempt)
    verdict = "passed" if attempt.passed else "not passed"
    quiz_title = attempt.quiz.title("en") or attempt.quiz.title_ka
    notification_service.notify(
        attempt.user_id,
        kind="quiz_result",
        title=f"Quiz result: {attempt.percent:.0f}% - {verdict}",
        body=f"{quiz_title} ({course.title('en') or course.slug})",
        link=f"/quiz/attempt/{attempt.id}/",
    )
    return attempt


def _expire(attempt: QuizAttempt) -> None:
    attempt.status = AttemptStatus.EXPIRED
    attempt.submitted_at = utcnow()
    db.session.commit()


def expire_stale_attempts() -> int:
    stale = list(
        db.session.execute(
            select(QuizAttempt).where(
                QuizAttempt.status == AttemptStatus.IN_PROGRESS,
                QuizAttempt.expires_at.is_not(None),
                QuizAttempt.expires_at < utcnow() - timedelta(seconds=GRACE_SECONDS),
            )
        ).scalars()
    )
    for attempt in stale:
        attempt.status = AttemptStatus.EXPIRED
        attempt.submitted_at = utcnow()
    db.session.commit()
    return len(stale)


def show_details(user: User, attempt: QuizAttempt) -> bool:
    """Instant feedback shows everything; delayed shows details once the learner
    has passed or has no attempts left."""
    quiz = attempt.quiz
    if quiz.feedback_mode == FeedbackMode.INSTANT:
        return True
    if attempt.passed:
        return True
    left = attempts_left(user, quiz)
    return left is not None and left <= 0


def quiz_stats(quiz: Quiz) -> dict:
    attempts = [a for a in quiz.attempts if a.status == AttemptStatus.SUBMITTED]
    if not attempts:
        return {"attempts": 0, "pass_rate": 0, "average": 0, "questions": []}
    per_question = []
    for question in quiz.questions:
        answered = [ans for a in attempts for ans in a.answers if ans.question_id == question.id]
        correct = sum(1 for ans in answered if ans.is_correct)
        per_question.append(
            {
                "question": question,
                "answered": len(answered),
                "correct_rate": round(100 * correct / len(answered)) if answered else 0,
            }
        )
    return {
        "attempts": len(attempts),
        "pass_rate": round(100 * sum(1 for a in attempts if a.passed) / len(attempts)),
        "average": round(sum(a.percent for a in attempts) / len(attempts), 1),
        "questions": per_question,
    }
