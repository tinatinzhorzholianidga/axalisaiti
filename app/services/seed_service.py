"""Seed data: roles, demo eLearning content and CyberHero content (idempotent)."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.config import BASE_DIR
from app.extensions import db
from app.models import (
    Assignment,
    Category,
    Course,
    CourseStatus,
    CourseTranslation,
    Difficulty,
    Lesson,
    LessonTranslation,
    LessonType,
    Module,
    ModuleTranslation,
    Platform,
    Question,
    QuestionOption,
    QuestionType,
    Quiz,
    SubmissionType,
    User,
    utcnow,
)
from app.services import course_service, cyberhero_service
from app.services.rbac import seed_roles_and_permissions
from app.services.sanitize import sanitize_html
from app.services.user_service import create_user

ELEARNING_SEED_DIR = BASE_DIR / "seeds" / "elearning"
LOCALES = ("ka", "en")

DEMO_CATEGORIES: list[dict[str, Any]] = [
    {
        "slug": "cybersecurity",
        "icon": "shield",
        "color": "blue",
        "ka": "კიბერუსაფრთხოება",
        "en": "Cybersecurity",
    },
    {"slug": "soc", "icon": "activity", "color": "purple", "ka": "SOC", "en": "SOC"},
    {"slug": "networks", "icon": "network", "color": "cyan", "ka": "ქსელები", "en": "Networks"},
    {
        "slug": "web-security",
        "icon": "globe",
        "color": "green",
        "ka": "Web Security",
        "en": "Web Security",
    },
    {"slug": "cloud", "icon": "cloud", "color": "blue", "ka": "Cloud", "en": "Cloud"},
    {
        "slug": "programming",
        "icon": "code",
        "color": "purple",
        "ka": "პროგრამირება",
        "en": "Programming",
    },
    {
        "slug": "governance",
        "icon": "book",
        "color": "cyan",
        "ka": "მართვა და შესაბამისობა",
        "en": "Governance",
    },
    {
        "slug": "digital-forensics",
        "icon": "search",
        "color": "green",
        "ka": "ციფრული ფორენზიკა",
        "en": "Digital Forensics",
    },
]


def _load(name: str) -> Any:
    path = ELEARNING_SEED_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def seed_categories() -> int:
    created = 0
    for i, data in enumerate(DEMO_CATEGORIES, start=1):
        existing = db.session.execute(
            select(Category).where(Category.slug == data["slug"])
        ).scalar_one_or_none()
        if existing:
            continue
        course_service.create_category(
            slug=data["slug"],
            translations={"ka": {"name": data["ka"]}, "en": {"name": data["en"]}},
            icon=data["icon"],
            color=data["color"],
            sort_order=i,
        )
        created += 1
    return created


def demo_instructor() -> User:
    email = "instructor@elearning.gov.ge"
    user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        return user
    seed_roles_and_permissions()
    password = secrets.token_urlsafe(18)
    user = create_user(
        email=email,
        password=password,
        first_name="გიორგი",
        last_name="კაპანაძე",
        roles=["instructor", "student"],
    )
    user.display_name = "Giorgi Kapanadze"
    user.organization = "Digital Governance Agency"
    db.session.commit()
    print(f"Created demo instructor {email} with password: {password}")
    return user


def _translations(course: Course, data: dict) -> None:
    existing = {t.locale: t for t in course.translations}
    for locale in LOCALES:
        tr = existing.get(locale) or CourseTranslation(course_id=course.id, locale=locale)
        tr.title = data["title"][locale]
        tr.short_description = data.get("short_description", {}).get(locale, "")[:400]
        tr.description = sanitize_html(data.get("description", {}).get(locale, ""))
        tr.objectives = "\n".join(data.get("objectives", {}).get(locale, []))
        tr.prerequisites = "\n".join(data.get("prerequisites", {}).get(locale, []))
        tr.audience = data.get("audience", {}).get(locale, "")
        tr.certificate_requirements = data.get("certificate_requirements", {}).get(locale, "")
        if locale not in existing:
            course.translations.append(tr)


def _upsert_module(course: Course, index: int, data: dict) -> Module:
    module = next((m for m in course.modules if m.text("title", "en") == data["title"]["en"]), None)
    if module is None:
        module = Module(course_id=course.id)
        course.modules.append(module)
        db.session.flush()
    module.sort_order = index
    existing = {t.locale: t for t in module.translations}
    for locale in LOCALES:
        tr = existing.get(locale) or ModuleTranslation(module_id=module.id, locale=locale)
        tr.title = data["title"][locale]
        tr.description = data.get("description", {}).get(locale, "")
        if locale not in existing:
            module.translations.append(tr)
    return module


def _upsert_lesson(module: Module, index: int, data: dict) -> Lesson:
    lesson = next((les for les in module.lessons if les.slug == data["slug"]), None)
    if lesson is None:
        lesson = Lesson(module_id=module.id, slug=data["slug"])
        module.lessons.append(lesson)
        db.session.flush()
    lesson.sort_order = index
    lesson.lesson_type = LessonType(data.get("type", "reading"))
    lesson.estimated_minutes = int(data.get("minutes") or 10)
    lesson.is_free_preview = bool(data.get("free_preview"))
    lesson.video_url = data.get("video_url")
    existing = {t.locale: t for t in lesson.translations}
    for locale in LOCALES:
        tr = existing.get(locale) or LessonTranslation(lesson_id=lesson.id, locale=locale)
        tr.title = data["title"][locale]
        tr.summary = data.get("summary", {}).get(locale, "")[:500]
        tr.content = sanitize_html(data.get("content", {}).get(locale, ""))
        if locale not in existing:
            lesson.translations.append(tr)
    return lesson


def _upsert_quiz(course: Course, lesson: Lesson | None, data: dict) -> Quiz:
    quiz = None
    if lesson is not None:
        quiz = lesson.quiz
    elif data.get("final"):
        quiz = next((q for q in course.quizzes if q.is_final), None)
    if quiz is None:
        quiz = Quiz(
            course_id=course.id, lesson_id=lesson.id if lesson else None, title_ka="", title_en=""
        )
        db.session.add(quiz)
        db.session.flush()
    quiz.is_final = bool(data.get("final"))
    quiz.title_ka = data["title"]["ka"]
    quiz.title_en = data["title"]["en"]
    quiz.description_ka = data.get("description", {}).get("ka", "")
    quiz.description_en = data.get("description", {}).get("en", "")
    quiz.time_limit_minutes = data.get("time_limit_minutes")
    quiz.max_attempts = data.get("max_attempts")
    quiz.pass_percent = int(data.get("pass_percent") or 70)
    quiz.shuffle_questions = bool(data.get("shuffle_questions"))
    quiz.shuffle_options = bool(data.get("shuffle_options"))
    quiz.questions.clear()
    db.session.flush()
    for qi, q in enumerate(data.get("questions", []), start=1):
        question = Question(
            sort_order=qi,
            question_type=QuestionType(q["type"]),
            prompt_ka=q["prompt"]["ka"],
            prompt_en=q["prompt"]["en"],
            explanation_ka=q.get("explanation", {}).get("ka", ""),
            explanation_en=q.get("explanation", {}).get("en", ""),
            points=float(q.get("points") or 1),
            accepted_answers=q.get("accepted_answers", []),
        )
        for oi, opt in enumerate(q.get("options", []), start=1):
            question.options.append(
                QuestionOption(
                    sort_order=oi,
                    text_ka=opt["text"]["ka"],
                    text_en=opt["text"]["en"],
                    is_correct=bool(opt.get("correct")),
                    match_ka=opt.get("match", {}).get("ka", ""),
                    match_en=opt.get("match", {}).get("en", ""),
                    correct_position=opt.get("position"),
                )
            )
        quiz.questions.append(question)
    return quiz


def _upsert_assignment(course: Course, lesson: Lesson | None, data: dict) -> Assignment:
    assignment = lesson.assignment if lesson is not None else None
    if assignment is None:
        assignment = Assignment(
            course_id=course.id, lesson_id=lesson.id if lesson else None, title_ka="", title_en=""
        )
        db.session.add(assignment)
    assignment.title_ka = data["title"]["ka"]
    assignment.title_en = data["title"]["en"]
    assignment.instructions_ka = sanitize_html(data.get("instructions", {}).get("ka", ""))
    assignment.instructions_en = sanitize_html(data.get("instructions", {}).get("en", ""))
    assignment.submission_type = SubmissionType(data.get("submission_type", "text"))
    assignment.max_points = float(data.get("max_points") or 100)
    assignment.max_resubmissions = int(data.get("max_resubmissions", 2))
    assignment.allow_late = bool(data.get("allow_late", True))
    assignment.late_penalty_percent = int(data.get("late_penalty_percent") or 0)
    return assignment


def upsert_course(data: dict, instructor: User) -> tuple[Course, bool]:
    course = db.session.execute(
        select(Course).where(Course.slug == data["slug"])
    ).scalar_one_or_none()
    is_new = course is None
    if course is None:
        course = Course(slug=data["slug"], created_by_id=instructor.id)
        db.session.add(course)
        db.session.flush()
    course.platform = Platform(data.get("platform", "elearning"))
    course.instructor_id = instructor.id
    course.status = CourseStatus(data.get("status", "published"))
    course.published_at = course.published_at or (
        utcnow() if course.status == CourseStatus.PUBLISHED else None
    )
    course.difficulty = Difficulty(data.get("difficulty", "beginner"))
    course.icon = data.get("icon", "shield")
    course.color = data.get("color", "blue")
    course.estimated_minutes = int(data.get("estimated_minutes") or 0)
    course.tags = ",".join(data.get("tags", []))
    course.is_featured = bool(data.get("is_featured"))
    course.certificate_enabled = bool(data.get("certificate_enabled", True))
    course.certificate_pass_percent = int(data.get("certificate_pass_percent") or 70)
    course.sort_order = int(data.get("sort_order") or 0)
    if data.get("categories"):
        course.categories = list(
            db.session.execute(
                select(Category).where(Category.slug.in_(data["categories"]))
            ).scalars()
        )
    _translations(course, data)
    for mi, mod in enumerate(data.get("modules", []), start=1):
        module = _upsert_module(course, mi, mod)
        for li, les in enumerate(mod.get("lessons", []), start=1):
            lesson = _upsert_lesson(module, li, les)
            if les.get("quiz"):
                _upsert_quiz(course, lesson, les["quiz"])
            if les.get("assignment"):
                _upsert_assignment(course, lesson, les["assignment"])
    if data.get("final_quiz"):
        _upsert_quiz(course, None, {**data["final_quiz"], "final": True})
    db.session.flush()
    return course, is_new


def _flagship_course_from_knowledge() -> dict | None:
    """Build the 'Basic Cybersecurity Course' from the elearning.gov.ge text
    shipped with CyberHero's knowledge base (seeds/cyberhero/knowledge.json)."""
    path = BASE_DIR / "seeds" / "cyberhero" / "knowledge.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        knowledge = json.load(fh)

    def html(chunks: list[str]) -> str:
        return "\n".join(f"<p>{c.strip()}</p>" for c in chunks if c.strip())

    modules = []
    for section in knowledge["sections"]:
        chunks = [c for c in section["chunks"] if c.strip()]
        groups = [chunks[i : i + 4] for i in range(0, len(chunks), 4)] or [[]]
        lessons = []
        for gi, group in enumerate(groups, start=1):
            slug = f"{course_service.slugify(section['en'])}-{gi}"
            title_ka = (
                section["ka"] if len(groups) == 1 else f"{section['ka']} ({gi}/{len(groups)})"
            )
            title_en = (
                section["en"] if len(groups) == 1 else f"{section['en']} ({gi}/{len(groups)})"
            )
            lessons.append(
                {
                    "slug": slug,
                    "type": "reading",
                    "minutes": max(4, 2 * len(group)),
                    "free_preview": section["id"] == 0,
                    "title": {"ka": title_ka, "en": title_en},
                    "summary": {"ka": group[0][:200] if group else "", "en": ""},
                    "content": {"ka": html(group), "en": html(group)},
                }
            )
        modules.append({"title": {"ka": section["ka"], "en": section["en"]}, "lessons": lessons})
    meta = _load("basic_cybersecurity.json")
    if not meta:
        return None
    return {
        **meta,
        "modules": modules,
        "final_quiz": _load("basic_cybersecurity_final_quiz.json") or None,
    }


def seed_demo_content() -> dict[str, int]:
    seed_roles_and_permissions()
    summary = {"categories": seed_categories(), "courses": 0, "updated": 0}
    instructor = demo_instructor()
    courses: list[dict] = []
    flagship = _flagship_course_from_knowledge()
    if flagship:
        courses.append(flagship)
    courses += _load("courses.json")
    for data in courses:
        _, is_new = upsert_course(data, instructor)
        summary["courses" if is_new else "updated"] += 1
    db.session.commit()
    summary["case_studies"] = seed_case_studies(instructor)
    return summary


DEMO_CASE_STUDIES: list[dict[str, Any]] = [
    {
        "slug": "fake-bank-sms-2026",
        "category": "ongoing-threats",
        "ka": {
            "title": "ყალბი SMS „ბანკიდან“: ბარათის დაბლოკვის სქემა",
            "description": "<p>2026 წლის სექტემბრიდან საქართველოში მასობრივად იგზავნება SMS-ები, "
            "რომლებიც თითქოს ბანკიდანაა და ბარათის „დაბლოკვის“ შესახებ აფრთხილებს. ბმული "
            "ბანკის ვებგვერდის ასლზე გადაჰყავს მომხმარებელი, სადაც ბარათის მონაცემებს ითხოვენ.</p>",
            "about": "<p>შეტყობინება ბანკის ნამდვილ ნომერს ბაძავს და სასწრაფო მოქმედებას მოითხოვს. "
            "ყალბი გვერდი ვიზუალურად ბანკის საიტის იდენტურია, თუმცა მისამართი განსხვავდება.</p>",
            "sections": [
                (
                    "როგორ ამოვიცნოთ",
                    "<ul><li>ბმულის მისამართი ბანკის დომენს არ ემთხვევა.</li>"
                    "<li>შეტყობინება დაუყოვნებლივ მოქმედებას ითხოვს.</li></ul>",
                ),
                (
                    "ფრთხილად იყავით",
                    "<p>ბანკი არასდროს ითხოვს ბარათის PIN-კოდს ან CVV-ს SMS-ით.</p>",
                ),
            ],
        },
        "en": {
            "title": "Fake bank SMS: the card-blocking scheme",
            "description": "<p>Since September 2026, SMS messages posing as a bank warn about a "
            "card being “blocked”. The link leads to a copy of the bank's website that asks "
            "for card details.</p>",
            "about": "<p>The message imitates the bank's real number and demands urgent action. "
            "The fake page looks identical to the bank's site, but the address differs.</p>",
            "sections": [
                (
                    "How to identify",
                    "<ul><li>The link does not match the bank's domain.</li>"
                    "<li>The message demands immediate action.</li></ul>",
                ),
                ("Be careful of", "<p>A bank never asks for your PIN or CVV by SMS.</p>"),
            ],
        },
    },
    {
        "slug": "deepfake-voice-call",
        "category": "ongoing-threats",
        "ka": {
            "title": "ხმის დიპფეიკი: „ხელმძღვანელი“ სასწრაფო გადარიცხვას ითხოვს",
            "description": "<p>თანამშრომლებს ურეკავს „დირექტორი“, რომლის ხმაც ხელოვნური "
            "ინტელექტით არის შექმნილი, და სასწრაფო გადარიცხვას ითხოვს.</p>",
            "about": "<p>ხმა საჯარო ვიდეოებიდან არის დაკლონილი. ზარი ხშირად სამუშაო დღის "
            "ბოლოს მოდის, როცა შემოწმება რთულია.</p>",
            "sections": [
                (
                    "ფრთხილად იყავით",
                    "<p>ნებისმიერი გადარიცხვა დაადასტურეთ სხვა არხით - დარეკეთ ცნობილ ნომერზე.</p>",
                ),
            ],
        },
        "en": {
            "title": "Voice deepfake: the “director” asks for an urgent transfer",
            "description": "<p>Employees receive a call from the “director”, whose voice is "
            "generated by AI, asking for an urgent transfer.</p>",
            "about": "<p>The voice is cloned from public videos. The call usually comes at the "
            "end of the working day, when checking is hard.</p>",
            "sections": [
                (
                    "Be careful of",
                    "<p>Confirm any transfer through another channel - call a "
                    "number you already know.</p>",
                ),
            ],
        },
    },
    {
        "slug": "qr-parking-scam",
        "category": "ongoing-threats",
        "ka": {
            "title": "ყალბი QR-კოდები პარკირების ავტომატებზე",
            "description": "<p>პარკირების ავტომატებზე დაკრულია ყალბი QR-კოდები, რომლებიც "
            "ყალბ გადახდის გვერდზე გადაჰყავს მძღოლებს.</p>",
            "about": "<p>სტიკერი ორიგინალ კოდს ფარავს. გადახდის გვერდი ბარათის სრულ "
            "მონაცემებს ითხოვს.</p>",
            "sections": [],
        },
        "en": {
            "title": "Fake QR codes on parking meters",
            "description": "<p>Fake QR codes stuck on parking meters send drivers to a bogus "
            "payment page.</p>",
            "about": "<p>The sticker covers the original code. The payment page asks for full "
            "card details.</p>",
            "sections": [],
        },
    },
]


def seed_case_studies(actor: User | None = None) -> int:
    """Demo case studies for the home page and the case study catalogue (idempotent)."""
    from app.models import CaseStudy
    from app.services import case_study_service

    case_study_service.seed_defaults()
    actor = actor or demo_instructor()
    titles = {t.name_ka: t for t in case_study_service.section_titles(active_only=False)}
    created = 0
    for data in DEMO_CASE_STUDIES:
        if db.session.execute(
            select(CaseStudy).where(CaseStudy.slug == data["slug"])
        ).scalar_one_or_none():
            continue
        category = case_study_service.category_by_slug(data["category"], active_only=False)
        case = case_study_service.create(
            actor=actor,
            translations={
                loc: {k: v for k, v in data[loc].items() if k != "sections"} for loc in LOCALES
            },
            category_id=category.id if category else None,
            is_published=True,
            slug=data["slug"],
        )
        for (heading_ka, body_ka), (_heading_en, body_en) in zip(
            data["ka"]["sections"], data["en"]["sections"], strict=True
        ):
            title = titles.get(heading_ka)
            case_study_service.add_section(
                case,
                title_id=title.id if title else None,
                body_ka=body_ka,
                body_en=body_en,
                actor=actor,
            )
        created += 1
    return created


def seed_cyberhero_content() -> dict[str, int]:
    seed_roles_and_permissions()
    return cyberhero_service.seed_all()


# ---------------------------------------------------------------------------
# validation (CI)
# ---------------------------------------------------------------------------
def _leaves(node: Any, path: str, out: list[tuple[str, Any]]) -> None:
    if isinstance(node, dict):
        if "en" in node or "ka" in node:
            out.append((path, node))
            return
        for key, value in node.items():
            _leaves(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _leaves(value, f"{path}[{i}]", out)


def validate_seed_files(path: str) -> list[str]:
    errors: list[str] = []
    root = Path(path)
    cyber = root / "cyberhero"
    if not cyber.exists():
        return [f"{cyber} does not exist"]
    data: dict[str, Any] = {}
    for name in (
        "tiers",
        "missions",
        "agreement",
        "mascot",
        "knowledge",
        "courses",
        "resources",
    ):
        file = cyber / f"{name}.json"
        if not file.exists():
            errors.append(f"missing {file.name}")
            continue
        try:
            with file.open(encoding="utf-8") as fh:
                data[name] = json.load(fh)
        except ValueError as exc:
            errors.append(f"{file.name}: invalid JSON ({exc})")
    if errors:
        return errors

    # bilingual completeness
    for name in ("tiers", "missions", "agreement", "courses", "resources"):
        leaves: list[tuple[str, Any]] = []
        _leaves(data[name], name, leaves)
        for leaf_path, leaf in leaves:
            values = {loc: leaf.get(loc) for loc in LOCALES}
            if all(isinstance(v, list) for v in values.values()):
                continue
            filled = {loc for loc, v in values.items() if isinstance(v, str) and v.strip()}
            if filled and filled != set(LOCALES):
                for locale in set(LOCALES) - filled:
                    errors.append(f"{leaf_path}: missing {locale}")

    # missions: rounds and branch graphs
    for mission in data["missions"]:
        for ri, rnd in enumerate(mission.get("rounds", [])):
            label = f"{mission['id']}.rounds[{ri}]"
            if rnd.get("type") not in {"choice", "flags", "builder", "branch"}:
                errors.append(f"{label}: unknown type {rnd.get('type')}")
            if (
                rnd.get("type") == "choice"
                and sum(1 for o in rnd.get("options", []) if o.get("correct")) != 1
            ):
                errors.append(f"{label}: choice rounds need exactly one correct option")
            if rnd.get("type") == "flags" and not any(i.get("flag") for i in rnd.get("items", [])):
                errors.append(f"{label}: flags round has no flags")
            if rnd.get("type") == "branch":
                nodes = rnd.get("nodes", {})
                if rnd.get("start") not in nodes:
                    errors.append(f"{label}: start node missing")
                for key, node in nodes.items():
                    if node.get("end"):
                        continue
                    if not node.get("choices"):
                        errors.append(f"{label}.{key}: no choices and not an end node")
                    for choice in node.get("choices", []):
                        if choice.get("next") not in nodes:
                            errors.append(
                                f"{label}.{key}: next {choice.get('next')!r} does not exist"
                            )
                # every path reaches an end
                reachable, stack = set(), [rnd.get("start")]
                while stack:
                    key = stack.pop()
                    if key in reachable or key not in nodes:
                        continue
                    reachable.add(key)
                    stack += [c.get("next") for c in nodes[key].get("choices", [])]
                if not any(nodes[k].get("end") for k in reachable if k in nodes):
                    errors.append(f"{label}: no ending reachable from start")

    # the 16 parent/teacher reads are lessons of the Teachers & Parents course
    parents = next((c for c in data["courses"] if c.get("track") == "parents"), None)
    lessons = (
        [les for mod in parents.get("modules", []) for les in mod.get("lessons", [])]
        if parents
        else []
    )
    codes = {les["slug"] for les in lessons}
    expected = (
        {f"a{i}" for i in range(1, 8)}
        | {f"b{i}" for i in range(1, 6)}
        | {f"c{i}" for i in range(1, 5)}
    )
    if parents is None:
        errors.append("courses: no course on the parents track")
    elif codes != expected:
        errors.append(f"parents course: expected lessons {sorted(expected)} got {sorted(codes)}")
    mission_ids = {m["id"] for m in data["missions"]}
    for les in lessons:
        if les.get("mission") and les["mission"] not in mission_ids:
            errors.append(f"lesson {les['slug']}: unknown mission {les['mission']}")
    for mission in data["missions"]:
        if mission.get("article") and mission["article"] not in codes:
            errors.append(f"mission {mission['id']}: unknown parent lesson {mission['article']}")
    return errors
