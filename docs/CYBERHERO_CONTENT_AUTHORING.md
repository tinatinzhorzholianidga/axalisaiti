# CyberHero content authoring guide

CyberHero content is data, not code. Admins edit it in the admin panel
(`/admin/cyberhero/…`). The initial content ships as JSON under
`seeds/cyberhero/` and is loaded with `flask seed-cyberhero` (idempotent:
records are matched by `slug`/`code`/`context` and updated in place, so a
plain run also resets admin edits to the seeded records). The Docker
entrypoint runs `flask seed-cyberhero --if-empty` on every start: it loads
the content once, on a database with no tracks, and never touches it again.
`flask validate-content seeds` checks the files in CI.

Tracks can be taken offline in two ways from `/admin/cyberhero/tracks/<id>`:
**Hidden** keeps the track (missions, learner progress, certificates) but
removes it from the public API and the CyberHero app; **Delete track** is
only allowed once nothing depends on the track, so learner data is never
cascaded away by accident.

Every human-readable field is bilingual: `{"ka": "...", "en": "..."}`.
Georgian is the primary language; English must be a real translation, never
a placeholder. Rich text fields (`body`, `description`, `content`, `intro`)
hold limited HTML (`p, h3, h4, ul, ol, li, strong, em, a, blockquote, table`)
and are sanitised on import.

## Sensitive topics — required framing

Sextortion, grooming, bullying, harassment and scams use **victim-first**
language: the child is never at fault, the perpetrator is. Every such item
must include (1) one practical next step, (2) "tell a trusted adult", and
(3) where relevant, the emergency number **112** and the configurable help
contacts (rendered by the app from site settings — do not hard-code other
phone numbers). Never describe techniques in a way that teaches abuse.

## Files

### `tracks.json`
```json
[{
  "slug": "cyber-guardians", "sort_order": 1, "age_min": 10, "age_max": 14, "audience": "kids",
  "color": "violet", "icon": "shield", "character": "io",
  "is_coming_soon": false, "is_featured": true, "certificate_enabled": true,
  "name": {"ka": "...", "en": "..."}, "tagline": {"ka": "...", "en": "..."},
  "description": {"ka": "...", "en": "..."}, "audience_label": {"ka": "10–14 წელი", "en": "Ages 10–14"}
}]
```
Colours: `violet | orange | green | pink | sky | yellow`. Characters: `io | hero | none`.

### `courses.json` (CyberHero courses; rendered with the CyberHero UI)
```json
[{
  "slug": "cyber-guardians-basics", "track": "cyber-guardians", "icon": "shield", "color": "violet",
  "difficulty": "beginner", "estimated_minutes": 90, "age_min": 10, "age_max": 14,
  "tags": ["passwords", "phishing"], "is_featured": true,
  "title": {"ka": "...", "en": "..."}, "short_description": {"ka": "...", "en": "..."},
  "description": {"ka": "<p>…</p>", "en": "<p>…</p>"},
  "objectives": {"ka": ["…"], "en": ["…"]}, "audience": {"ka": "…", "en": "…"},
  "modules": [{
    "title": {"ka": "…", "en": "…"}, "description": {"ka": "…", "en": "…"},
    "lessons": [{"slug": "what-is-a-password", "type": "reading", "minutes": 5,
                 "title": {"ka": "…", "en": "…"}, "summary": {"ka": "…", "en": "…"},
                 "content": {"ka": "<p>…</p>", "en": "<p>…</p>"}}]
  }]
}]
```

### `missions.json`
```json
[{
  "slug": "phishing-hunter", "track": "cyber-guardians", "course": "cyber-guardians-basics",
  "sort_order": 1, "mission_type": "quiz", "icon": "fish", "color": "orange", "difficulty": 1,
  "estimated_minutes": 8, "xp_reward": 100, "pass_percent": 60, "is_sensitive": false,
  "help_resource": null,
  "title": {"ka": "…", "en": "…"}, "tagline": {"ka": "…", "en": "…"},
  "intro": {"ka": "…", "en": "…"}, "completion_message": {"ka": "…", "en": "…"},
  "help_note": {"ka": "…", "en": "…"},
  "rounds": [{
    "type": "questions", "title": {"ka": "…", "en": "…"}, "intro": {"ka": "…", "en": "…"},
    "time_limit_seconds": null,
    "questions": [{
      "type": "single", "points": 10,
      "prompt": {"ka": "…", "en": "…"}, "scenario": {"ka": "…", "en": "…"},
      "explanation": {"ka": "…", "en": "…"},
      "options": [{"text": {"ka": "…", "en": "…"}, "is_correct": true, "feedback": {"ka": "…", "en": "…"}}]
    }]
  }, {
    "type": "branch", "title": {"ka": "…", "en": "…"}, "intro": {"ka": "…", "en": "…"},
    "branch_start_key": "start"
  }],
  "branches": [{
    "key": "start", "speaker": "stranger", "mood": "neutral", "is_start": true, "is_ending": false,
    "text": {"ka": "…", "en": "…"},
    "choices": [{"text": {"ka": "…", "en": "…"}, "next_key": "reply-safe", "is_safe": true,
                 "feedback": {"ka": "…", "en": "…"}, "points": 10}]
  }, {"key": "reply-safe", "speaker": "io", "mood": "celebrate", "is_ending": true, "ending_kind": "safe",
      "text": {"ka": "…", "en": "…"}, "choices": []}],
  "related_articles": ["A2", "B1"]
}]
```
Question types: `single | multiple | true_false | spot` (spot = "which message is the scam?").
Mission types: `quiz` (question rounds only), `branching` (conversation only), `mixed`.
Every branching mission must have exactly one `is_start` node, every `next_key`
must exist, and every path must reach an ending.

### Parent / teacher reads (part of `courses.json`)
The sixteen parent/teacher reads are **lessons of the `teachers-parents`
course** (track `parents`), not a separate content type: three modules that
mirror the former shelves (*Understand the risks* A1–A7 · *Act* B1–B5 · *For
school* C1–C4) with one reading lesson per article, `slug` = the old code
(`a1` … `c4`). Each lesson's `content` is limited HTML: the lead paragraph,
`h3` headings, paragraphs, lists, callouts as
`<div class="callout callout-<note|script|do|dont|emergency>">…</div>` and a
closing *Sources* list. Admins edit them like any other lesson in the
course builder (`/instructor/courses/<id>/builder`); the Teachers & Parents
card on the CyberHero home opens the course (`route` of the `parents` tier),
and the old `/cyberhero/parents/<code>` links redirect to the lessons.

### `resources.json`
`kind` ∈ `emergency_contact | playbook | family_agreement | guide`.
```json
[{
  "kind": "playbook", "slug": "child-receives-threat", "sort_order": 1, "icon": "alert", "color": "orange",
  "contact_value": "", "is_verified": true,
  "title": {"ka": "…", "en": "…"}, "summary": {"ka": "…", "en": "…"},
  "body": {"ka": "<p>…</p>", "en": "<p>…</p>"}, "steps": {"ka": ["…"], "en": ["…"]}
}]
```
The family agreement is one `family_agreement` record whose `body` is the
printable agreement and whose `steps` are the individual promises.
Emergency contacts: only `112` is verified by default; other contacts are
added by admins through site settings.

### `mascot.json` (IO mascot)
```json
{
  "tips": [{"topics": ["passwords"], "en": "…", "ka": "…"}],
  "reactions": {
    "mission": [{"en": "…", "ka": "…"}], "exam": {"en": "…", "ka": "…"},
    "cert": {"…": "…"}, "guardians": {"…": "…"}, "building": {"…": "…"},
    "track.guardians": [{"en": "…", "ka": "…"}, {"en": "…", "ka": "…"}]
  }
}
```
Tips are tagged with topics (`passwords, phishing, scams, privacy, devices, strangers,
help, kindness, fake, balance, parents`) so IO can match them to the page. Reactions are
keyed by *moment*: `mission` (one is picked per finished mission), `exam`, `cert`,
`guardians`, `building` (coming-soon pages), and one `track.<track id>` list per age
track - what IO says when the visitor hovers or focuses that track's card on the
welcome page (he walks through the list on repeated hovers; without one he reads the
track's own intro / description). All of it is editable under Admin → CyberHero →
Mascot; the API serves it as `mascot.reactions` with the track hints under
`reactions.tracks.<track id>`.
