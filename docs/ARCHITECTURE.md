# Architecture

This document is the architecture plan for the eLearning platform: one Flask
backend, one database, one admin panel, and two public products with distinct
front-end identities.

```
                    elearning.gov.ge
                           │
                ┌──────────┴──────────┐
                │                     │
           eLearning             CyberHero
      Professional LMS         Youth/Family LMS
      (Jinja + Bootstrap)      (React + Vite, /cyberhero/)
                │                     │
                └──────────┬──────────┘
                           │
                    Flask application
             (blueprints → services → repositories)
                           │
              MariaDB ── Redis ── Celery ── uploads
                           │
                      Admin panel
             (manages both products' content)
```

## 1. Directory tree

```
axalisaiti/
├── app/
│   ├── __init__.py            # create_app() application factory
│   ├── config.py              # Base/Development/Testing/Production configs + production guard
│   ├── extensions.py          # db, migrate, login_manager, csrf, limiter, cache, session, babel, mail
│   ├── celery_app.py          # Celery factory bound to the Flask app context
│   ├── cli.py                 # flask create-admin / seed-roles / seed-demo / seed-cyberhero / check-production
│   ├── errors.py              # branded 403/404/429/500 handlers
│   ├── logging_config.py      # request-id aware structured logging
│   ├── security.py            # security headers + CSP
│   ├── models/                # SQLAlchemy 2.x declarative models (one file per domain)
│   ├── repositories/          # query objects; the only place raw queries live
│   ├── services/              # business logic (auth, rbac, courses, quizzes, certificates, …)
│   ├── forms/                 # Flask-WTF forms (server-side validation, CSRF)
│   ├── utils/                 # small helpers (locale, pagination, uploads, slugs)
│   ├── tasks/                 # Celery tasks (mail, exports, maintenance)
│   ├── templates/             # Jinja2 templates (layout, components, per-blueprint folders)
│   ├── static/                # css/, js/, fonts/, img/, vendor/bootstrap/, cyberhero/ (Vite output)
│   ├── translations/          # Babel catalogs (ka is the default UI language)
│   └── blueprints/
│       ├── main/              # home, about, resources, search, health
│       ├── auth/              # login, logout, register, verify, reset, change password
│       ├── courses/           # catalog, course detail, enrol, bookmark, reviews
│       ├── learning/          # lesson view, progress, dashboard, profile
│       ├── assessments/       # quizzes, assignments
│       ├── certificates/      # my certificates, public verification
│       ├── discussions/       # threads, replies, moderation
│       ├── notifications/     # inbox, mark read
│       ├── instructor/        # instructor panel + course builder
│       ├── admin/             # shared admin panel (eLearning + CyberHero)
│       ├── api/               # /api/v1 JSON API
│       └── cyberhero/         # Vite shell + CyberHero page routes
├── cyberhero/                 # React 18 + Vite 5 app (IO mascot, missions, courses)
├── migrations/                # Alembic (Flask-Migrate) revisions
├── seeds/                     # JSON content: demo courses, CyberHero tracks/missions/courses
├── tests/                     # pytest suite
├── docker/                    # nginx config, entrypoint, gunicorn config
├── docs/                      # this file + setup, deployment, admin, authoring, security
├── .github/workflows/ci.yml
├── Dockerfile · docker-compose.yml · pyproject.toml · requirements*.txt · wsgi.py · Makefile
```

Layering rule: **blueprints** handle HTTP only; **services** own business rules
and transactions; **repositories** own queries. Models never import Flask
request objects.

## 2. Database model plan

All tables use integer surrogate keys, `created_at`/`updated_at`, and are
designed for MariaDB 11.4 (`utf8mb4`). Translatable content lives in
`*_translations` tables keyed by `(parent_id, locale)`.

```
users ──< user_roles >── roles ──< role_permissions >── permissions
users ──< enrollments >── courses
users ──< lesson_progress >── lessons
users ──< course_progress >── courses
users ──< quiz_attempts ──< quiz_answers >── questions ──< question_options
users ──< assignment_submissions ──< grades
users ──< discussion_posts >── discussions >── courses
users ──< reviews >── courses
users ──< bookmarks (course | lesson | resource)
users ──< notifications
users ──< user_achievements >── achievements
users ──< certificates >── courses
users ──< audit_logs
users ──< media_files

courses ──< course_translations (ka, en)
courses ──< course_categories >── categories ──< category_translations
courses ──< modules ──< module_translations
modules ──< lessons ──< lesson_translations
lessons ──< lesson_resources
lessons ──1 quizzes ──< questions
lessons ──1 assignments
courses ──1 final quiz (quizzes.is_final)

site_settings (key/value, typed)     feature_flags (key, enabled, description)

CyberHero:
cyber_tracks ──< cyber_track_translations
cyber_tracks ──< courses (platform = cyberhero, track_id)
courses ──< cyber_missions ──< cyber_mission_translations
cyber_missions ──< cyber_mission_rounds ──< cyber_mission_questions ──< cyber_question_options
cyber_missions ──< cyber_branches ──< cyber_branch_choices  (branching conversations)
case_categories ──< case_category_translations
case_categories ──< case_studies ──< case_study_translations, case_study_sections (heading from
                                     case_section_titles), case_study_images (media_files)
resources ── media_files          (admin-published PDFs; hidden ones are not served)
cyber_articles ──< cyber_article_blocks, cyber_article_sources   (legacy; the parent/teacher
                                                  reads are lessons of the teachers-parents course)
cyber_mascot_tips (context key, ka/en text, mood)
cyber_safety_resources (emergency info, family agreement, playbook entries; ka/en)
cyber_progress (user_id, mission_id, status, score)   # sync target for signed-in users
cyber_certificates (public_id, display_name, track, issued_at)
```

Key enums: `Platform{elearning, cyberhero, both}`, `CourseStatus{draft,
pending_review, published, archived}`, `Difficulty{beginner, intermediate,
advanced}`, `LessonType{reading, video, quiz, lab, assignment}`,
`QuestionType{single, multiple, true_false, short_answer, ordering, matching}`,
`EnrollmentMode{open, approval, invite}`.

## 3. Route map

Public (eLearning): `/`, `/about/`, `/resources/`, `/search/`, `/courses/`,
`/courses/<slug>/`, `/certificates/verify/<public_id>`, `/health`, `/readiness`.

Auth: `/auth/login`, `/auth/logout`, `/auth/register`, `/auth/verify/<token>`,
`/auth/reset`, `/auth/reset/<token>`, `/auth/password`.

Learner: `/dashboard/`, `/profile/`, `/bookmarks/`, `/learn/<course>/<lesson>/`,
`/learn/<course>/<lesson>/complete` (POST), `/quiz/<id>/start`,
`/quiz/attempt/<id>/`, `/assignment/<id>/`, `/certificates/`,
`/discussions/<course>/`, `/discussions/<course>/<thread>/`, `/notifications/`.

Instructor: `/instructor/`, `/instructor/courses/new`, `/instructor/courses/<id>/`,
`/instructor/courses/<id>/modules`, `/instructor/courses/<id>/lessons/<lid>`,
`/instructor/courses/<id>/quizzes/<qid>`, `/instructor/courses/<id>/assignments/<aid>`,
`/instructor/grading/`, `/instructor/courses/<id>/students`, `/instructor/courses/<id>/analytics`.

Admin: `/admin/` (dashboard), `/admin/users/`, `/admin/courses/`, `/admin/categories/`,
`/admin/case-studies/` (+ `categories/`, `section-titles/`), `/admin/resources/`,
`/admin/cyberhero/{tracks,missions,tips,resources,certificates}/`,
`/admin/quizzes/`, `/admin/assignments/`, `/admin/certificates/`, `/admin/discussions/`,
`/admin/reviews/`, `/admin/notifications/`, `/admin/media/`, `/admin/analytics/`,
`/admin/audit/`, `/admin/settings/`, `/admin/localization/`, `/admin/flags/`.

API v1 (`/api/v1/`): `auth/session`, `courses`, `courses/<slug>`, `search`,
`progress/lessons/<id>` (POST), `notifications`, `notifications/<id>/read`,
`bookmarks`, `cyberhero/bootstrap`, `cyberhero/tracks`, `cyberhero/courses`,
`cyberhero/courses/<slug>`, `cyberhero/courses/<slug>/lessons/<slug>`,
`cyberhero/missions/<slug>`, `cyberhero/resources/<kind>`, `cyberhero/tips`,
`cyberhero/progress` (GET/PUT, signed-in sync), `cyberhero/certificates` (POST).
Admin-only API endpoints require the same permission checks as the admin UI.

CyberHero (React, served by Flask shell): `/cyberhero/`, `/cyberhero/courses/`,
`/cyberhero/course/<slug>/`, `/cyberhero/learn/<course>/<lesson>/`,
`/cyberhero/mission/<slug>/`, `/cyberhero/tracks/`, `/cyberhero/course/teachers-parents/`
(the parent/teacher reads; `/cyberhero/parents/…` redirects there), `/cyberhero/teachers/`,
`/cyberhero/emergency/`, `/cyberhero/family-agreement/`, `/cyberhero/certificate/`,
`/cyberhero/tutor/` (only when `CYBERHERO_IO_CHAT_ENABLED`).

## 4. Permission model

Roles are rows; permissions are rows; both are seeded and editable by admins.
Route protection uses `@require_permission("code")`; object-level ownership is
checked in services (an instructor may only edit their own course unless they
hold `courses.manage_all`).

| Permission                 | student | instructor | moderator | admin |
|----------------------------|:-------:|:----------:|:---------:|:-----:|
| courses.enroll             | ✓ | ✓ | ✓ | ✓ |
| learning.access            | ✓ | ✓ | ✓ | ✓ |
| quizzes.attempt            | ✓ | ✓ | ✓ | ✓ |
| assignments.submit         | ✓ | ✓ | ✓ | ✓ |
| discussions.participate    | ✓ | ✓ | ✓ | ✓ |
| reviews.write              | ✓ | ✓ | ✓ | ✓ |
| courses.create             |   | ✓ |   | ✓ |
| courses.manage_own         |   | ✓ |   | ✓ |
| courses.manage_all         |   |   |   | ✓ |
| courses.publish            |   |   |   | ✓ |
| assignments.grade          |   | ✓ |   | ✓ |
| analytics.view_own         |   | ✓ |   | ✓ |
| analytics.view_all         |   |   |   | ✓ |
| discussions.moderate_own   |   | ✓ | ✓ | ✓ |
| discussions.moderate_all   |   |   | ✓ | ✓ |
| reviews.moderate           |   |   | ✓ | ✓ |
| users.manage               |   |   |   | ✓ |
| roles.manage               |   |   |   | ✓ |
| categories.manage          |   |   |   | ✓ |
| cyberhero.manage           |   |   |   | ✓ |
| certificates.manage        |   |   |   | ✓ |
| media.manage               |   | ✓ |   | ✓ |
| notifications.broadcast    |   |   |   | ✓ |
| settings.manage            |   |   |   | ✓ |
| flags.manage               |   |   |   | ✓ |
| audit.view                 |   |   |   | ✓ |
| admin.access               |   |   | ✓ | ✓ |
| instructor.access          |   | ✓ |   | ✓ |

## 5. Authentication and sessions

* Flask-Login with Argon2id password hashes (argon2-cffi), minimum 12 chars.
* `users.security_version` is the security stamp. The Flask-Login session id is
  `"<user_id>:<security_version>"`; any password change, role change, or
  suspension bumps the version and invalidates every other session.
* Lockout: after `LOGIN_MAX_FAILED` failures the account is locked for
  `LOGIN_LOCKOUT_MINUTES`; the response never reveals whether the email exists.
* Sessions are server-side in Redis (Flask-Session), cookies `Secure`,
  `HttpOnly`, `SameSite=Lax`. Nothing sensitive is stored client-side.
* CSRF via Flask-WTF on every form and on JSON API mutations (`X-CSRFToken`).
* Rate limits via Flask-Limiter (Redis storage) with tighter limits on auth.

## 6. Design systems

**A – eLearning** (`app/static/css/tokens.css`, `elearning.css`): dark first,
navy `#07111F`, blue `#5681FF`, purple `#7767FF`, cyan `#24C4DB`, radii 6–12px,
thin borders, 150–300ms transitions, `data-theme="dark|light"` on `<html>`,
applied before first paint by `static/js/theme-init.js` (external, blocking).

**B – CyberHero** (`cyberhero/src/styles/*.css`, all selectors prefixed with
`.cyberhero-root` by PostCSS): lavender canvas `#F1EDFF`, violet `#7C5CFF`,
orange `#FF8A3D`, green `#3DD598`, radii 20–32px, "Candy Clay" soft shadows,
IO mascot (react-three-fiber) with static SVG fallback.

Bootstrap 5.3 is vendored locally and loaded only by the eLearning layout.
The CyberHero shell extends the site layout but wraps the React root in
`.cyberhero-root`, where Bootstrap inheritance is reset.

## 7. CyberHero integration

* `npm run build` in `cyberhero/` emits into `app/static/cyberhero/` with a
  Vite manifest. `app/blueprints/cyberhero` reads the manifest and renders
  `<script type="module" src="…hashed.js">` plus hashed CSS.
* Runtime config (basename, locale, feature flags, API base, user display name)
  is passed through `data-*` attributes on `#cyberhero-root`; no inline script.
* The same bundle has a second entry, `cyberhero/src/io-host.jsx`: IO as the
  welcome host of the eLearning home page (`/`), a fixed corner widget like
  the CyberHero one. `main.home` reads that entry's
  files from the manifest and passes locale, skin and his "doors" (the page's
  *Browse courses* / *Open CyberHero* buttons, tagged `data-io-path`; the
  CyberHero one while enabled) as `data-*` on `#io-host-root`; without a build
  the widget is simply left out. Its stylesheet (`src/styles/io-host.css`) is scoped by hand
  under `.io-host-root` and skips the `.cyberhero-root` prefixer.
* Content is fetched from `/api/v1/cyberhero/*`; anonymous progress is kept in
  `localStorage`; signed-in users sync to `cyber_progress`.

## 8. Deployment

Multi-stage Docker image (Node 22 → Python builder → slim non-root runtime),
docker-compose with nginx, web (gunicorn), worker (celery), mariadb, redis,
all with health checks. Alembic migrations run by the entrypoint. Uploads live
in a volume outside the static tree and are served through authorised routes.

## 9. Implementation milestones

1. Foundation: factory, config, extensions, logging, headers, health, Docker, CI.
2. Users, RBAC, auth, sessions, reset, lockout, audit.
3. Courses, categories, modules, lessons, translations, enrolment, progress.
4. eLearning design system, navbar, home, catalog, detail, lesson, dashboard, profile, themes.
5. Quizzes, assignments, grading, certificates, notifications, discussions, reviews, bookmarks, achievements.
6. Instructor panel and course builder.
7. Admin panel (both products), media library, settings, flags, audit, analytics.
8. CyberHero React app: home, tracks, catalog, course (incl. the Teachers & Parents reads), missions, certificate, mascot.
9. CyberHero ↔ Flask integration: manifest, locale, flags, namespace, CSP.
10. Security review and tests.
11. Static analysis, builds, smoke tests.
12. Responsive and accessibility review.
