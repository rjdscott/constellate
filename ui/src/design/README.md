# Constellate design system — "Observatory"

The identity argument: the project is named Constellate and its platforms
are constellations (ADR 0009). The UI leans into that literally but with
restraint — a night-sky instrument, not a screensaver. Explanation graphs
*are* constellations: nodes as stars, traversal paths as asterisms. Every
other surface is a quiet, precise instrument panel that lets the data be
the decoration.

Taste rules (enforced in review):

1. **Excellence, not gimmick.** Celestial styling appears where it carries
   meaning (graphs, the overview map) and nowhere else. No twinkling, no
   parallax, no glow on buttons.
2. **Data is the decoration.** Chrome stays near-monochrome; hue is
   reserved for data semantics (platforms, planes, node types, status).
   If a color isn't encoding something, it's a neutral.
3. **Dark-first, light-equal.** Both themes ship; charts revalidate
   contrast per theme, not by inverting.
4. **Motion is causality.** Transitions explain where things came from or
   what changed. `prefers-reduced-motion` disables all non-essential
   motion. Nothing loops.
5. **No boxed atmosphere. Rules over cards.** Full-bleed composition;
   hairline rules and alignment instead of bordered boxes; a rounded
   card is a last resort, never the default container. (The vibecoded
   tell is a page of equal-weight boxes.)
6. **Show, don't tell.** A bare metric means nothing to a stranger.
   Prefer a live demonstration (the overview's proof strip: same query,
   three platforms, identical answer) with the numbers as the caption.
7. **Copy is terse.** No em-dashes in product copy; middots separate
   facts; fewest words that carry the meaning.

## Color

Tokens are CSS custom properties (Tailwind v4 `@theme`); semantic names
only in components — never raw hex.

### Neutrals (dark)

| Token | Value | Use |
|---|---|---|
| `--color-void` | `#070A12` | app background (deep ink, faint blue cast) |
| `--color-surface` | `#0C111D` | panels, cards |
| `--color-raised` | `#131A2A` | popovers, raised controls, hover fills |
| `--color-hairline` | `#1F2839` | borders, rules, chart gridlines |
| `--color-text` | `#E9EDF6` | primary text ("starlight") |
| `--color-text-dim` | `#9AA4B9` | secondary text |
| `--color-text-faint` | `#6B7488` | placeholders, disabled, axis ticks |

### Neutrals (light — "daylight observatory")

`--color-void #F6F7FB · surface #FFFFFF · raised #EEF1F7 · hairline
#D9DEE9 · text #161D2E · text-dim #4C566B · text-faint #78829A`. Light
theme gets one true shadow (`--elevation-*`); dark theme elevation is
surface-step + hairline (shadows don't read on ink).

### Accent

One accent: **starlight gold** `--color-accent #E3B858` (dark) /
`#8A6A1F` (light). Used for: primary actions, focus rings, active nav,
the animated path highlight. Deliberately *not* a platform color — the
accent means "you/attention", platforms mean data.

### Data hues

Platform triad (colorblind-safe: separated on the blue–yellow axis and in
the red channel; validated with a CVD simulator before any chart ships):

| Series | Dark | Light |
|---|---|---|
| `--data-lyra` (embedded) | `#5DD3F0` cyan | `#0E7FA3` |
| `--data-orion` (unified) | `#F0B24E` amber | `#9A6B12` |
| `--data-hydra` (composed) | `#B18CF5` violet | `#6D4FC4` |

Plane set (timings breakdowns; never on the same chart as the platform
triad): `--data-relational #72CBA8 · --data-vector #6FA5F5 ·
--data-graph #C79BF2 · --data-fusion` = neutral `text-dim`.

Graph node types (constellation view): movie = starlight `#E9EDF6` (the
stars), user = cyan `#5DD3F0`, tag = violet `#B18CF5`, genre = amber
`#F0B24E`, seed/highlight ring = accent gold. Node radius encodes
magnitude (score or degree); edges are hairline at 60% opacity, path
edges draw on in accent.

Status: ok `#5BD08C` / warn `#F0B24E` / error `#F07A6A` (dark values;
light variants darkened to ≥4.5:1 on white).

### Validation (computed 2026-08-05, script in PR description)

- WCAG contrast: `text`/`text-dim` ≥ 4.5:1 and every data hue ≥ 3:1
  against all three background steps, both themes; `text-faint` tuned to
  clear 3:1 on `raised` (dark 4.2–3.7:1, light 3.9–3.4:1).
- CVD: Viénot protanopia/deuteranopia simulation, pairwise ΔE*ab of the
  platform triad ≥ 24 in every condition (weakest: lyra–hydra under
  deuteranopia, which also carries a 0.55 vs 0.35 relative-luminance
  gap). Rule regardless: hue is never the sole channel — series get
  direct labels, distinct markers or dash patterns where they overlap.

## Typography

Two faces, bundled locally via `@fontsource` (a conference demo never
depends on CDN wifi). A serif display face (Fraunces) was tried and
retired 2026-08-05: clean over bookish.

- **Inter** (variable) — everything, display included. Display = medium
  weight, tracking −0.015em, large sizes; wordmark and overlines =
  uppercase, tracking 0.22–0.28em. Tabular-nums on any number that can
  change width.
- **JetBrains Mono** — data: metric values, ids, fingerprints, code,
  axis ticks, timing readouts.

Scale (base 14 — this is a dense instrument, not a marketing page):
`12 / 13 / 14 / 16 / 20 / 25 / 32 / 40 / 56`. Tokens `--text-xs …
--text-3xl`, display sizes `--text-d1 56 / --text-d2 40 / --text-d3 32`
(Fraunces). Line heights: 1.5 body, 1.2 headings, 1.0 display numerals.

## Spacing, radius, layout

- 4px grid: `--space-1..10` = 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- Radius: `--radius-sm 4` (controls), `--radius-md 8` (cards),
  `--radius-lg 12` (panels/dialogs), `--radius-full` (pills). Nothing
  bubblier — instruments have machined corners.
- App shell: fixed left rail (icons + labels, 220px, collapses to 64px),
  content max-width none (dashboards want the room), 12-col grid,
  `--space-6` gutters.

## Elevation

Dark: `elevation-0` = surface, `1` = raised + hairline, `2` = raised +
hairline + `0 8px 32px rgb(0 0 0 / 0.4)`. Light: standard two-step soft
shadow. No glows except the graph path highlight.

## Motion

Durations `--motion-fast 120ms` (hover, toggles), `--motion-base 200ms`
(panel/popover enter), `--motion-view 400ms` (route/view transitions),
`--motion-trace 900ms` (constellation path draw-on). Easing: standard
`cubic-bezier(.2, 0, 0, 1)`; exits accelerate (`.4, 0, 1, 1`). Library:
Motion (`motion/react`). Choreography rules: enter = fade + 4px rise;
lists stagger ≤ 40ms/item, cap 8; path highlight = stroke draw-on then
node rings, sequential along the path (the one place motion is allowed
to be theatrical — it is literally the explanation). All of it behind
`prefers-reduced-motion`.

## Charts (Observable Plot)

Transparent background; gridlines = hairline; axis text = text-faint,
mono 12; series = data hues, 2px lines, area fills at 10% opacity;
direct end-of-line labels over legends when ≤4 series; percentile bands
(p50/p95/p99) as line + band, not grouped bars; significance shown as
CI whiskers + printed p-value, never asterisk stars alone. Every chart
readable in both themes and screenshot-ready at 2× (talk slides are a
first-class render target).

## Starfield

The overview page only, and full-bleed (never inside a box): a static
seeded canvas starfield behind the platform chart. Magnitude-weighted:
mostly dust, per-star alpha 4–24% on a squared curve, ~260 stars. Under
it, the `.aurora` wash: three radial gradients of the platform hues at
≤5% alpha. Never animated, never on data surfaces, never in light theme
(daylight observatory is clean paper). This is all the pure atmosphere
the system permits.
