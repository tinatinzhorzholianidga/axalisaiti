# CyberHero front-end

The youth/family product of the platform: a React 18 + Vite 5 single-page app
served by Flask at `/cyberhero/`. It keeps the original "Candy Clay" design
(lavender claymorphism, IO the robot mascot) and reads **all content from the
platform API** (`/api/v1/cyberhero/*`), so tracks, missions, articles, the
family agreement, mascot tips and courses are edited in the admin panel.

```
cyberhero/
├── src/
│   ├── main.jsx            entry: mounts on #cyberhero-root, BrowserRouter with data-basename
│   ├── App.jsx             routes (+ feature-flag gate for the IO tutor pages)
│   ├── lib/runtime.js      reads the data-* attributes the Flask shell renders
│   ├── lib/api.js          fetch wrapper: same-origin cookies, X-CSRFToken, ?locale=
│   ├── content/            ContentProvider: bootstrap payload + cached resource hooks
│   ├── i18n/               UI strings (en.js / ka.js) and the I18n context
│   ├── store/progress.jsx  mission/lesson progress (localStorage + server sync when signed in)
│   ├── games/              the four round engines (choice, flags, builder, branch)
│   ├── mascot/             IO: three.js model, widget, tips context, tutor brain
│   ├── pages/              welcome, tracks, guardians, parents, courses, emergency, verify, 404
│   └── styles/             global.css (original design), platform.css (tones/utilities), meter.css (generated)
├── mock/                   Vite plugin serving fixtures (npm run dev:mock)
├── test/                   vitest + testing-library suites
├── e2e/                    Playwright smoke tests against the Flask shell
└── scripts/                generate-meter-css.mjs
```

## Commands

| command | what it does |
| --- | --- |
| `npm install` | install dependencies (Node ≥ 20) |
| `npm run dev` | Vite dev server on :5173, proxying `/api` to Flask on :8000 |
| `npm run dev:mock` | same, but the API is served from `mock/fixtures/` (no backend needed) |
| `npm run build` | production bundle → `../app/static/cyberhero/` (+ `.vite/manifest.json`) |
| `npm run lint` | eslint (react, hooks, jsx-a11y) |
| `npm test` | vitest unit/component tests |
| `npm run test:e2e` | Playwright smoke tests (starts `scripts/e2e_server.py` on :5055) |
| `npm run gen:meter` | regenerate `src/styles/meter.css` |

Regenerate the mock fixtures after changing seeds or serializers:

```
python scripts/dump_cyberhero_fixtures.py     # from the repository root
```

## How the integration works

* **Shell.** `app/blueprints/cyberhero/routes.py` renders
  `templates/cyberhero/shell.html` for every `/cyberhero/*` path. The shell
  reads the Vite manifest and includes the hashed CSS/JS files. Runtime
  configuration reaches the app only through `data-*` attributes on
  `#cyberhero-root` (basename, locale, API base, user, feature flags,
  emergency contacts, tutor model URL). No inline scripts, no CDN.
* **Language.** The active locale is the platform's (Flask session →
  `<html lang>`). The header toggle navigates to `?lang=xx`, so the whole
  platform switches together.
* **Styles.** Every selector is prefixed with `.cyberhero-root` by PostCSS so
  CyberHero styles never leak into the Bootstrap host page. The strict CSP
  forbids `style=""`, so colours are tone classes (`tone-blue` … sets `--c`),
  the builder meter uses `data-value` steps and the mascot canvas uses
  `data-size`.
* **Progress.** Anonymous learners keep progress in `localStorage`. Signed-in
  learners additionally sync with `GET/PUT /api/v1/cyberhero/progress` (best
  score wins, `done` never regresses).
* **Certificates.** Finishing every Guardians mission unlocks
  `/guardians/certificate`; "Issue my certificate" calls
  `POST /api/v1/cyberhero/certificates` and the sheet shows the public ID.
  Anyone can verify it at `/cyberhero/certificate/<id>` or the platform's
  `/certificates/verify/<id>` page.
* **IO tutor (off by default).** `/io-chat` and `/mascot-demo` render only when
  the `CYBERHERO_IO_CHAT_ENABLED` flag is on. The tutor is grounded on the
  course text from `GET /knowledge`. Without a configured model it works in
  *lookup* mode (matching passages, nothing leaves the browser). With
  `CYBERHERO_TUTOR_MODEL_URL` pointing at a same-origin directory that holds
  an MLC-compiled model plus `model.wasm`, WebLLM runs the model in the
  visitor's browser via WebGPU; the shell then adds `'wasm-unsafe-eval'` to
  `script-src` for that page only. Children's conversations are never sent to
  an external LLM service.

## Content contract

The API keeps the shape of the original content modules: every text leaf is
`{ "en": "...", "ka": "..." }`, missions carry `rounds[]` of type
`choice | flags | builder | branch`, articles are `body[]` blocks of type
`h2 | p | list | callout`. See `docs/CYBERHERO_API.md` and
`docs/CYBERHERO_CONTENT_AUTHORING.md` at the repository root.
