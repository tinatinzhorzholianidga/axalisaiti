# CyberHero ↔ Flask contract

The CyberHero React app is served by Flask at `/cyberhero/` and talks only to
`/api/v1/cyberhero/*`. This file is the single source of truth for the shell
and the JSON shapes. Both sides are tested against it.

## 1. Shell (Jinja) → React runtime configuration

Flask renders `app/templates/cyberhero/shell.html`, which contains:

```html
<div id="cyberhero-root" class="cyberhero-root"
     data-basename="/cyberhero"
     data-locale="ka"                       <!-- "ka" | "en" -->
     data-api-base="/api/v1/cyberhero"
     data-static-base="/static/cyberhero"   <!-- where hashed assets live -->
     data-site-base="/"                     <!-- link back to eLearning -->
     data-login-url="/auth/login?next=/cyberhero/"
     data-user-name=""                      <!-- display name when signed in, else "" -->
     data-user-id=""                        <!-- numeric id when signed in, else "" -->
     data-flags='{"CYBERHERO_IO_CHAT_ENABLED":false}'
     data-emergency-phone="112"
     data-cybercrime-contact=""             <!-- "" unless configured AND verified -->
     data-help-line=""
     data-tutor-model-url=""                <!-- optional self-hosted WebLLM model dir -->
     data-lang-switch-ka="/cyberhero/?lang=ka"
     data-lang-switch-en="/cyberhero/?lang=en"></div>
```

* No inline `<script>`; the entry is `<script type="module" src="/static/cyberhero/assets/main-<hash>.js">`
  resolved from `app/static/cyberhero/.vite/manifest.json`. CSS from the same manifest.
* The language switch inside the React header must navigate (full page load)
  to `data-lang-switch-*` so Flask persists the choice in the session.
* All API requests include `credentials: "same-origin"`. Mutating requests
  (`PUT /progress`, `POST /certificates`) send header `X-CSRFToken` obtained
  from `GET /api/v1/auth/csrf` → `{"csrf_token": "..."}`.
* Every endpoint accepts `?locale=ka|en`; responses contain text in that
  locale with Georgian fallback. The client always passes the shell locale.

## 2. Endpoints

All responses are JSON. Errors: `{"error": {"code": 404, "message": "..."}}`.

### `GET /bootstrap`
```json
{
  "locale": "ka",
  "flags": {"CYBERHERO_IO_CHAT_ENABLED": false},
  "user": null | {"id": 1, "display_name": "Nino"},
  "settings": {"emergency_phone": "112", "cybercrime_contact": "", "help_line": ""},
  "featured_tracks": ["cyber-guardians", "teachers-parents"],
  "tracks": [Track],
  "tips": {"home": [Tip], "catalog": [Tip]}
}
```

### `GET /tracks` → `{"items": [Track]}` · `GET /tracks/<slug>` → `Track` (+ `"courses": [CourseSummary]`, `"missions": [MissionSummary]`)
```json
Track = {
  "slug": "cyber-guardians", "name": "...", "tagline": "...", "description": "...",
  "audience_label": "10–14 წელი", "audience": "kids|teens|adults",
  "age_min": 10, "age_max": 14, "color": "violet|orange|green|pink|sky|yellow",
  "icon": "shield", "character": "io|hero|none", "is_coming_soon": false,
  "is_featured": true, "certificate_enabled": true,
  "mission_count": 10, "course_count": 1, "article_count": 0
}
```

### `GET /courses?track=<slug>` → `{"items": [CourseSummary]}`
```json
CourseSummary = {
  "slug": "cyber-guardians-course", "title": "...", "short_description": "...",
  "track": "cyber-guardians", "icon": "shield", "color": "violet",
  "difficulty": "beginner|intermediate|advanced", "estimated_minutes": 90,
  "age_min": 10, "age_max": 14, "lesson_count": 4, "mission_count": 10,
  "is_featured": true, "tags": ["phishing", "passwords"]
}
```

### `GET /courses/<slug>` → `Course`
```json
Course = CourseSummary + {
  "description_html": "<p>…</p>", "objectives": ["…"], "audience": "…",
  "modules": [{"id": 1, "title": "…", "description": "…",
               "lessons": [{"slug": "…", "title": "…", "summary": "…", "type": "reading|video|quiz|lab", "minutes": 5}]}],
  "missions": [MissionSummary]
}
```

### `GET /courses/<slug>/lessons/<lesson_slug>` → `Lesson`
```json
Lesson = {
  "slug": "…", "title": "…", "summary": "…", "content_html": "<p>…</p>", "type": "reading",
  "minutes": 5, "module_title": "…", "index": 2, "total": 8,
  "prev": null | {"slug": "…", "title": "…"}, "next": null | {"slug": "…", "title": "…"},
  "resources": [{"title": "…", "url": "…"}],
  "tips": [Tip]
}
```

### `GET /missions?track=<slug>` → `{"items": [MissionSummary]}` · `GET /missions/<slug>` → `Mission`
```json
MissionSummary = {
  "slug": "phishing-hunter", "title": "…", "tagline": "…", "track": "cyber-guardians",
  "course": "cyber-guardians-course" | null, "icon": "fish", "color": "orange",
  "difficulty": 1, "estimated_minutes": 8, "xp_reward": 100, "mission_type": "quiz|branching|mixed",
  "is_sensitive": false, "sort_order": 1
}
Mission = MissionSummary + {
  "intro": "…", "completion_message": "…", "help_note": "…", "pass_percent": 60,
  "max_points": 120,
  "help_resource": null | {"slug": "…", "title": "…", "contact_value": "112"},
  "rounds": [{
     "id": 1, "type": "questions|branch|info", "title": "…", "intro": "…",
     "time_limit_seconds": null | 45, "branch_start_key": null | "start",
     "questions": [{
        "id": 1, "type": "single|multiple|true_false|spot", "prompt": "…", "scenario": "…",
        "explanation": "…", "points": 10, "image_url": null,
        "options": [{"id": 1, "text": "…", "is_correct": true, "feedback": "…"}]
     }]
  }],
  "branches": {"start": {"key": "start", "speaker": "stranger|io|hero|friend|narrator", "mood": "neutral",
                          "text": "…", "is_ending": false, "ending_kind": null,
                          "choices": [{"id": 1, "text": "…", "next_key": "n2", "is_safe": true, "feedback": "…", "points": 10}]}},
  "related_articles": [{"slug": "…", "code": "A3", "title": "…"}]
}
```

### `GET /articles?section=understand|act|school&audience=parents|teachers` → 
```json
{"sections": [{"key": "understand", "title": "…", "articles": [ArticleSummary]}, …], "items": [ArticleSummary]}
ArticleSummary = {"slug": "…", "code": "A1", "title": "…", "summary": "…", "section": "understand",
                  "audience": "parents|teachers|both", "reading_minutes": 6, "icon": "eye", "color": "sky",
                  "is_sensitive": false}
```
### `GET /articles/<slug>` → `ArticleSummary + {"body_html", "key_takeaways": [...], "sources": [{"title","publisher","url","year"}], "related_missions": [{"slug","title"}], "prev": …, "next": …}`

### `GET /resources/<kind>` with kind ∈ `emergency_contact | playbook | family_agreement | guide`
```json
{"items": [{"slug": "…", "title": "…", "summary": "…", "body_html": "…", "steps": ["…"],
            "icon": "…", "color": "…", "contact_value": "112", "is_verified": true}]}
```

### `GET /tips?context=<key>` → `{"items": [Tip]}` · `Tip = {"context": "home", "mood": "happy|think|celebrate|alert|neutral", "text": "…"}`
Contexts used by the client: `home`, `catalog`, `course`, `lesson`, `mission_intro`,
`mission_correct`, `mission_wrong`, `mission_complete`, `articles`, `emergency`, `certificate`.

### Progress (signed-in users only; anonymous users keep progress in `localStorage` key `cyberhero.progress.v1`)
* `GET /progress` → `{"missions": {"<slug>": {"status": "in_progress|completed", "best_score": 80, "max_score": 120, "attempts": 2, "completed_at": "…"}}, "lessons": {"<course>/<lesson>": {"status": "completed"}}}`
* `PUT /progress` body same shape → merged result (best score wins, completed never regresses). Requires `X-CSRFToken`. 401 when anonymous.

### Certificates
* `POST /certificates` body `{"track": "cyber-guardians", "display_name": "Nino", "completed_missions": ["…"]}`
  → `201 {"public_id": "CH-2026-ABCD1234", "display_name": "Nino", "track_name": "…", "issued_at": "…", "verify_url": "/certificates/verify/CH-2026-ABCD1234"}`.
  Rules: display name 2–60 chars; every published mission of the track must be listed; anonymous allowed; nothing else stored.
* `GET /certificates/<public_id>` → `{"valid": true, "display_name", "track_name", "issued_at"}`.

## 3. localStorage keys (client)
* `cyberhero.progress.v1` — `{missions:{}, lessons:{}, xp: 0, updated_at}`; written after every answer/round so navigation never loses progress.
* `cyberhero.name` — last display name used for a certificate (optional convenience).
* `cyberhero.motion` — `"reduced"` override.
