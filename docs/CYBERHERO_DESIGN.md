# CyberHero design system ("Candy Clay")

CyberHero keeps the playful, colourful identity of the existing CyberHero site.
It is intentionally different from the professional eLearning UI and must never
inherit eLearning's dark navy styling. All selectors are prefixed with
`.cyberhero-root` at build time (PostCSS) so styles cannot leak either way.

## Tokens (`cyberhero/src/styles/tokens.css`)

```css
.cyberhero-root {
  /* canvas */
  --ch-bg: #F1EDFF;            /* lavender page background */
  --ch-bg-2: #E9E2FF;
  --ch-surface: #FFFFFF;
  --ch-surface-soft: #FAF8FF;
  --ch-ink: #2A2352;           /* deep violet-navy text */
  --ch-ink-soft: #5F5A85;
  --ch-line: #E4DDFB;

  /* accents */
  --ch-violet: #7C5CFF;  --ch-violet-dark: #5B3FE0;  --ch-violet-soft: #E8E1FF;
  --ch-orange: #FF8A3D;  --ch-orange-dark: #E56F22;  --ch-orange-soft: #FFE8D6;
  --ch-green:  #3DD598;  --ch-green-dark:  #22B57C;  --ch-green-soft:  #D9F7EA;
  --ch-pink:   #FF6FB5;  --ch-pink-dark:   #E24F97;  --ch-pink-soft:   #FFE0EF;
  --ch-sky:    #5AC8FA;  --ch-sky-dark:    #2FA9E0;  --ch-sky-soft:    #DDF3FF;
  --ch-yellow: #FFD447;  --ch-yellow-dark: #E8B914;  --ch-yellow-soft: #FFF5CC;
  --ch-red:    #FF5C5C;

  /* gradients (used on hero, track cards, mission headers) */
  --ch-grad-violet: linear-gradient(135deg, #8F74FF 0%, #6C4DFF 100%);
  --ch-grad-sunset: linear-gradient(135deg, #FFB36B 0%, #FF7A59 100%);
  --ch-grad-mint:   linear-gradient(135deg, #7BEBC1 0%, #34C48F 100%);
  --ch-grad-candy:  linear-gradient(135deg, #FF9BD2 0%, #B48CFF 100%);
  --ch-grad-sky:    linear-gradient(135deg, #8ADBFF 0%, #4FB8F0 100%);

  /* shape */
  --ch-radius-sm: 14px; --ch-radius: 22px; --ch-radius-lg: 28px; --ch-radius-pill: 999px;

  /* clay shadows: soft drop + inner highlight + darker bottom edge */
  --ch-shadow-card: 0 14px 34px rgba(124, 92, 255, 0.14), inset 0 -4px 0 rgba(42, 35, 82, 0.05);
  --ch-shadow-card-hover: 0 22px 44px rgba(124, 92, 255, 0.22), inset 0 -4px 0 rgba(42, 35, 82, 0.05);
  --ch-shadow-button: 0 6px 0 var(--ch-violet-dark), 0 12px 24px rgba(124, 92, 255, 0.3);
  --ch-shadow-soft: 0 8px 20px rgba(42, 35, 82, 0.08);

  /* type */
  --ch-font: "Noto Sans Georgian", "Segoe UI", system-ui, -apple-system, sans-serif;
  --ch-text-xs: 0.8rem; --ch-text-sm: 0.925rem; --ch-text: 1.05rem; --ch-text-lg: 1.25rem;
  --ch-h3: 1.5rem; --ch-h2: 2rem; --ch-h1: clamp(2.2rem, 5vw, 3.4rem);

  /* spacing */
  --ch-space-1: 6px; --ch-space-2: 12px; --ch-space-3: 18px; --ch-space-4: 24px;
  --ch-space-5: 36px; --ch-space-6: 56px;

  /* motion */
  --ch-ease: cubic-bezier(.34, 1.56, .64, 1);   /* bouncy */
  --ch-fast: 160ms; --ch-normal: 260ms; --ch-slow: 480ms;
}
```

## Components and their look

* **Header**: white pill-shaped bar floating on the lavender canvas, CyberHero
  wordmark with a small shield/robot glyph, nav chips, language switch
  (ქარ / EN) as a two-segment pill, "eLearning →" link.
* **Buttons** (`.ch-btn`): chunky, `border-radius: var(--ch-radius-pill)`, bold
  label, 3D bottom edge shadow, press = translateY(4px) and shadow shrink.
  Variants: violet (primary), orange, green, ghost (white with violet text).
* **Cards** (`.ch-card`): white, radius 22–28px, clay shadow, lift on hover
  (translateY(-6px) with the bouncy ease). Track cards get a gradient header
  band and a big rounded icon tile; mission cards show a difficulty dot row,
  minutes chip, XP chip and a progress meter; article cards show the code
  badge (A1…), section colour stripe and reading time.
* **Badges/chips** (`.ch-chip`): pill, soft pastel background, ink text.
* **Progress meter** (`.ch-meter`): thick rounded track with gradient fill and
  a small star at the end when complete; width set via `--ch-value` custom
  property (CSP-safe, set from JS with `style.setProperty` is NOT allowed —
  use inline-free approach: a `<div class="ch-meter"><div class="ch-meter__fill" data-value="35">` and a
  stylesheet with `[data-value="35"]{width:35%}` generated in 5% steps).
* **Mascot IO**: react-three-fiber robot (rounded capsule body, dome head,
  antenna with glowing tip, screen face with two eye ovals, stubby arms);
  bobbing idle animation, blinks, "celebrate" spin on mission complete,
  "think" tilt on wrong answer. Static SVG fallback (same silhouette) when
  WebGL is unavailable or `prefers-reduced-motion` / `cyberhero.motion=reduced`.
* **Mascot tip bubble** (`.ch-tip`): white speech bubble with a small tail,
  violet border, mood icon.
* **Hero character**: SVG illustration (child in cape + mask, violet/orange)
  used only on the home hero and the certificate.
* **Decorative background**: three or four large blurred pastel blobs
  (`.ch-blob`) fixed behind content, gently drifting (disabled under reduced motion).
* **Callouts**: `.ch-callout--safe` (green), `--warning` (orange), `--help` (sky, with 112 badge).
* **Certificate preview**: landscape card with candy gradient border, hero
  character, big name, track name, date, public id, printable (`@media print`).

## Accessibility

Focus rings: 3px `var(--ch-violet)` outline with 2px offset. Minimum touch
target 44px. Colour never the sole state carrier (icons + text). Live region
for answer feedback. Skip link inside the root. Reduced motion disables blob
drift, bouncy hover and mascot animation.
