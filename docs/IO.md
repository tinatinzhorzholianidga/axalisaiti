# IO (იო) — the platform's robot guide 🤖

IO is the 3D helper robot of the CyberHero product and, since this release, the
welcome host of the eLearning home page. This document describes the **current**
IO: where he appears, what he does on each page, where his words come from, and
how to run, edit and test him.

| | |
|---|---|
| **Character** | metal-droid IO v4 — the *Original* (white, green sprout) and *Metal* skins, DGA face plate, coloured chest LEDs, EVE-style arm blades |
| **Engine** | three.js + react-three-fiber, rendered on the visitor's GPU (WebGL); a 🤖 sticker stands in when WebGL is missing or crashes |
| **Languages** | Georgian (default) and English — every line he says is bilingual |
| **Where** | every CyberHero page (`/cyberhero/…`), the eLearning home page (`/`), the IO tutor page (`/cyberhero/io-chat`, feature-flagged) |
| **Content** | tips, reactions and track hints are edited in *Admin → CyberHero → Mascot*; the home-page lines live in code |
| **Privacy** | nothing the visitor does with IO leaves the browser; no analytics, no third-party requests |

---

## 1. The character

`cyberhero/src/mascot/`

| File | Role |
|---|---|
| `RobotModel.jsx` | IO's body: dome head with the sprout, screen face, stubby arms, chest LEDs; two skins (`skin="classic" \| "metal"`), the *builder* variant (DGA hard hat + hold-up palm) for coming-soon pages |
| `faceTexture.js` | the face, drawn on a canvas texture: eyes, mouth, the DGA plate; moods `happy, wink, thinking, excited, celebrate, sleepy, funny` |
| `RobotCanvas.jsx` | the stage: lights, camera, WebGL detection and fallback, `prefers-reduced-motion` (still face, render on demand), the window-wide cursor tracking, keyboard operation (Enter / Space = tap) |
| `HeroModel.jsx` | the hooded *Hero* character kept from the mascot demo |
| `Fireworks.jsx` | the celebration overlay for finished missions |

What he can do, from props: `emotion` (a mood), `gesture` (`wave`, `bounce`, `spin`), `talking` (the mouth moves while text types out), `follow` (eyes follow the cursor across the whole page), `idle` (bobbing, blinks, small antics), `onTap`.

Sizes are CSP-safe `data-size` steps (150 / 185 / 190 / 210 / 220 / 230 / 320 / 430 px); the widget uses **230 px on monitors, 185 px on tablets, 150 px on phones**.

---

## 2. IO on CyberHero — the floating helper

`cyberhero/src/mascot/MascotWidget.jsx`, `MascotProvider.jsx`, `mascotContext.js`

He lives fixed in the bottom-right corner of every CyberHero page (he follows the visitor down the page), flies in on arrival and waves. The ✕ hides him; the 🤖 chip brings him back.

* **Tips that match the page.** Tips are tagged with topics (`passwords, phishing, scams, privacy, devices, strangers, help, kindness, fake, balance, parents`). On a mission he picks tips for that mission's topics, in the Teachers & Parents area he speaks to adults, on the Emergency page he keeps to *help*. Clicking him (or 💡 *next tip*) gives the next one.
* **Track hints on the welcome page.** Hover or keyboard-focus any age-track card in *Choose your age* and IO says a hint about that track — a real mission, lesson or topic from its content (Phishing Hunter, Fort Knox, the Guardian Exam; the teen's online-world map, *Home setup in 30 minutes*, Classroom mode; what the coming-soon tracks will teach). Excited face for live tracks, thinking face for coming-soon ones, three lines per track in turn; leave the card and he goes back to his tips. A track without hints gets its own intro / description read out.
* **Mission companion.** During a mission he is the coach: a wrong answer moves the round's explanation into his bubble (thinking face), a right answer gets a move and praise, a finished mission gets a celebration with fireworks, the passed Guardian Exam and the certificate get their own lines.
* **Context openers.** Entering the Guardians map, the certificate page or a coming-soon track page gets a fitting opener (`guardians`, `cert`, `building` — the latter with the hard hat).

---

## 3. IO on the eLearning home page — the welcome host

`cyberhero/src/io-host.jsx` (second Vite entry), `cyberhero/src/host/`

The same character, as the bilingual **host** of `/` (ported from the *IO-for-main-page* project). He floats in the same corner as on CyberHero and:

* greets by the time of day (morning / afternoon / evening), then introduces himself;
* walks his orientation lines on click or Enter / Space — the two paths (the basic course for adults, CyberHero for kids and teens), the sign-in button, the certificate, the language switch, who runs the platform, a nudge to start;
* reacts when the page's two "doors" — *Browse courses* and *Open CyberHero* (`data-io-path`) — are hovered or focused, and waves goodbye when one is chosen (a new-tab click leaves him where he is);
* gives no cyber-security tips there (those live inside the courses);
* knows when CyberHero is disabled (every line that names it is dropped) and when the visitor is signed in (no "the Sign in button is top-right").

| File | Role |
|---|---|
| `host/hints.js` | everything he says on the home page, KA + EN, checked by `npm test` (length, one emoji, typography, no cyber tips, no leaked Latin) |
| `host/hostBrain.js` | which line when: greeting → intro → click cycle, hover / farewell pools, the doors and sign-in filters |
| `host/IoHost.jsx` | IO + his bubble: entrance, typewriter, click cycle, hover / farewell API, hide button |
| `host/HomeHost.jsx` | the corner widget on the Flask page: door wiring, responsive size, hide / show with focus management |
| `styles/io-host.css` | the widget's styles, scoped under `.io-host-root`, using the eLearning design tokens (dark and light themes) |

The Flask side (`app/blueprints/main/routes.py`, `templates/main/home.html`) reads the entry from the Vite manifest and passes locale, doors, labels and sign-in state as `data-*` on `#io-host-root` — no inline script, strict CSP unchanged. Without a built bundle the page simply renders without IO.

---

## 4. IO the tutor (feature-flagged)

`cyberhero/src/pages/IoChatPage.jsx`, `mascot/ioBrain.js`

Behind `CYBERHERO_IO_CHAT_ENABLED`, `/cyberhero/io-chat` turns IO into a course tutor grounded **only** on the Basic Cybersecurity Course text served by `GET /api/v1/cyberhero/knowledge` (editable in the admin panel). Retrieval is lexical and Georgian-aware; with `CYBERHERO_TUTOR_MODEL_URL` pointing at a same-origin MLC model directory the answer is generated in the visitor's browser by WebLLM (WebGPU), otherwise IO works in *lookup* mode and shows the matching passages. Nothing a child types is sent to any external service.

---

## 5. Where his words come from

| Words | Source | Editable |
|---|---|---|
| CyberHero tips | `seeds/cyberhero/mascot.json → tips` | Admin → CyberHero → Mascot |
| Reactions (`mission`, `exam`, `cert`, `guardians`, `building`) | `mascot.json → reactions` | same |
| Track hover hints (`track.<slug>`, three per track) | `mascot.json → reactions` | same — the *Moment* list offers one key per track, including tracks created later |
| Home-page host lines | `cyberhero/src/host/hints.js` | in code (`npm test` checks them) |
| Tutor knowledge | `seeds/cyberhero/knowledge.json` | Admin → CyberHero → Knowledge base |

The API serves the mascot content as `mascot` in `/api/v1/cyberhero/bootstrap` (and `/api/v1/cyberhero/mascot`): `tips[]`, `reactions.{mission[], exam, cert, guardians, building}`, `reactions.tracks.<slug>[]`, `missionTopics`.

Writing rules used for all of IO's copy: one register per audience (informal შენ for kids and teens, polite თქვენ for parents), ≤ 110 characters per language, at most one emoji, Georgian typography (spaced em dash, „…“ quotes), native Georgian without calques.

---

## 6. Configuration

| Setting | Effect |
|---|---|
| `CYBERHERO_ENABLED` (config / feature flag) | serves CyberHero; also decides whether the home-page host has the CyberHero door and mentions it |
| `CYBERHERO_IO_CHAT_ENABLED` (feature flag) | the tutor page and the knowledge API |
| `CYBERHERO_TUTOR_MODEL_URL` | same-origin directory with an MLC-compiled model + `model.wasm`; empty = lookup mode |

---

## 7. Running and testing

```bash
cd cyberhero
npm install
npm run build        # both entries → app/static/cyberhero/ (+ manifest)
npm run dev:mock     # CyberHero on :5173 from fixtures, no backend
npm run lint         # eslint (react, hooks, jsx-a11y)
npm test             # vitest: host lines & brain, track hints, the welcome-page hover, widget hide/show
npm run test:e2e     # Playwright against Flask: CyberHero pages, the home-page host, the hover hints
```

Python side: `pytest tests/test_home_io.py tests/test_cyberhero_api.py tests/test_admin.py` (home-page runtime attributes, mascot payload, admin reactions). After changing seeds run `python scripts/dump_cyberhero_fixtures.py` to refresh the mock fixtures.

---

## 8. Accessibility and privacy

* IO's stage is a keyboard-operable button whenever he can be tapped; hide / show never drops focus.
* Every line is announced once through a polite live region; the visible typewriter is hidden from screen readers.
* `prefers-reduced-motion` gives a still face, no fly-in and instant text.
* No inline styles or scripts anywhere (strict CSP); the 3D scene sizes itself through `data-size` steps.
* No recordings, no analytics, no third-party requests; the tutor's model and course text are served from the platform itself.

---

## 9. History

* **v1–v2** — Byte / Cipher / Hero characters, the mascot demo page.
* **IO summer edition** — the chosen robot: oval face, sprout, mission companion, fireworks, builder hard hat.
* **IO v4 (metal droid)** — Original and Metal skins, EVE-style arm blades, real armour plate, chest LEDs, helmet kits (demo), keyboard-operable stage.
* **IO Chat** — the in-browser course tutor (WebLLM), later grounded on the platform's knowledge base.
* **IO for main page** — the welcome host (greetings, click cycle, doors), now on the eLearning home page.
* **Track hints** — IO tells you about the age track under your cursor on the CyberHero welcome page.
