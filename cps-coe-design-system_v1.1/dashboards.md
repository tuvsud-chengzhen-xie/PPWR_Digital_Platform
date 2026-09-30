# Dashboards & Tables — CPS pattern guide

The reference implementation is the **Market Intelligence** module of Performance
Insights. Everything below is extracted from it, with the reasoning that produced
each rule. When a new data-heavy page is built, or an old one restyled, it should
end up looking and behaving like it without anyone having to re-derive these
decisions.

Read this alongside `README.md` (shell, tokens, nudges) and `AI-IDENTITY.md`
(the Layer-3 AI language). This document covers **data surfaces**: dashboards,
KPI strips, filter controls, tables and their loading behaviour.

> ## ⚠️ This is not the AI identity
>
> `AI-IDENTITY.md` governs **Layer-3 AI work** — a model is reasoning, and the
> user should feel it. It gets the command bar, the swarm overlay, the octagon
> comet loader.
>
> **Everything in this document is the opposite case**: querying, filtering,
> paging, sorting, aggregating. Deterministic work over data we already hold.
> It gets skeletons and in-place patching — never an overlay, never a swarm.
>
> | the work is… | pattern |
> | --- | --- |
> | a model reasoning about the user's input | `AIOverlay.run(...)` — AI-IDENTITY.md |
> | SQL, a filter, a page change, an aggregation | this document — skeleton + patch |
> | a page that does both | the AI part gets the overlay; the dashboard around it still follows this document |
>
> Using the AI language for a plain table filter destroys the signal, exactly as
> `AI-IDENTITY.md` warns. Using a blocking overlay for a 60 ms query is the same
> mistake in the other direction.

---

## 0. The three rules that matter most

Everything else is detail. These three are what actually separate a page that
feels good from one that doesn't:

1. **The page never goes blank.** Loading replaces *values*, never *structure*.
   There is always a dashboard on screen; it gets fuelled with data when ready.
2. **A filter change patches, it does not rebuild.** Re-rendering a whole view
   to change one number replays every entrance animation, drops focus, and
   resets scroll. That is the single biggest source of "glitchy".
3. **Entrances play once, on mount.** Anything that re-animates on every update
   reads as sluggish, no matter how fast the backend is.

---

## 1. Page anatomy

Top to bottom, always in this order:

```
main__header            page title + subtitle          (from shell.css)
  ├─ eyebrow / title    .mi-eyebrow + .mi-title
  └─ right side         .mi-spacer, .mi-livepill, .mi-btn (actions)
scope chips             .mi-chips > .mi-chip            what am I looking at
active filter chips     .mi-activechips > .mi-activechip  what am I filtering by
KPI strip               .mi-kpi-strip > .mi-kpi-tile    the 4 headline numbers
breakdown row           .mi-breakdowns > 3 columns      charts / ranked lists
geography / wide viz    .mi-geo-card                    optional
detail                  brush + table or master-detail  the rows themselves
```

**Why this order.** Scope first (what set of data), then what's filtering it,
then the summary, then progressively more detail. A user scanning downward gets
steadily more specific. Never put a table above its own KPI summary.

### Scope chips vs active-filter chips

Two different things, easy to conflate:

- **Scope chips** (`.mi-chip`) select *which data set* — a product group, a
  source. Mutually exclusive, always visible, `.is-active` on the current one.
- **Active-filter chips** (`.mi-activechip`) show *narrowing applied to that
  set* — country, risk, year. They appear only when a filter is on, each has a
  `✕` to clear it, and the row ends with a `Clear all` variant
  (`.mi-activechip--clear`).

Render the active-chip row inside a **permanent wrapper**, even when empty:

```html
<div data-role="activechips"><!-- filled by JS --></div>
```

so chips appearing and disappearing never shift the layout below them.

---

## 2. Surfaces — the glass card

Every panel on a dashboard uses one treatment. Do not invent a second card
style on the same page.

```css
background: rgba(255, 255, 255, 0.66);
backdrop-filter: blur(20px) saturate(1.25);
-webkit-backdrop-filter: blur(20px) saturate(1.25);
border: 1px solid rgba(255, 255, 255, 0.92);
border-radius: 20px;
box-shadow: 0 16px 40px rgba(0, 61, 122, 0.11), inset 0 1px 0 #fff;
```

This sits on the module's atmospheric wash (`.mi::before` — a blue radial
gradient plus a faint 52px engineering grid, masked to fade out). The glass only
reads as glass if there is something behind it; on a flat white page use the
same radius and border but drop the blur.

**Contrast trap.** `backdrop-filter` lightens whatever is behind it. Any text on
these cards must be checked against the *lightest* possible backdrop, not the
average.

---

## 3. KPI strip

Four tiles, one row. The first is the headline.

```css
.mi-kpi-strip { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }
@media (max-width: 920px) { .mi-kpi-strip { grid-template-columns: repeat(2, 1fr); } }
```

Each tile: glass surface, `padding: 18px`, and a 1px highlight along the top
edge via `::before` (a transparent→white→transparent gradient) — that hairline
is what makes it read as a physical panel rather than a coloured box.

| element | spec |
| --- | --- |
| `.mi-kpi-label` | 11px, uppercase, `letter-spacing: .06em`, `--neutral-500`, semibold |
| `.mi-kpi-value` | 25px, bold, `--tuv-blue-900`, **`font-variant-numeric: tabular-nums`** |
| `.mi-kpi-value` (first tile) | 54px, `letter-spacing: -.045em`, gradient-filled via `background-clip: text` |
| `.mi-kpi-sub` | `--font-size-sm`, `--neutral-600` |

All three lines are `overflow: hidden; text-overflow: ellipsis; white-space:
nowrap`. A KPI tile must never change height because its label got longer.

**Tabular numerals are mandatory** on every number that can change. Without
them, a counting or updating figure visibly jitters as glyph widths change.

Entrance: `translateY(16px) scale(.92)` → settled, 400ms, back-out curve,
staggered `60ms` per tile via `--i`. **On mount only.**

---

## 4. Filter controls

Pill-shaped, glass, consistent across every module:

```css
border-radius: 999px;
border: 1px solid rgba(180, 215, 255, 0.8);
background: rgba(255, 255, 255, 0.7);
backdrop-filter: blur(10px);
padding: 6px 14px;
color: var(--tuv-blue-700);
font-weight: 500;
```

Focus is a 3px soft ring, never a removed outline:

```css
:focus { outline: none; border-color: var(--tuv-blue-600);
         box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.15); }
```

Buttons get `:active { transform: scale(0.97) }` at ~160ms. Chips that toggle
get `.is-active` with a filled gradient background, not just a border change —
border-only active states are easy to miss at a glance.

---

## 5. Tables

Two patterns. Pick by **what the user is doing**, not by how much data there is.

### Pattern A — scan table

For *comparing many rows across the same fields*: dates, sources, categories,
counts. A real `<table>`.

- `table-layout: fixed` with an explicit `<colgroup>`, plus a `min-width` on a
  horizontally scrollable wrapper (`overflow-x: auto`). Without both, a narrow
  viewport collapses the flexible column to nothing.
- Give every column a fixed width **except one** — the "subject" column
  (product name, description). It absorbs the remainder.
- Row height ~33px: `th { padding: 9px }`, `td { padding: 8px }`.
- Cells never wrap: `white-space: nowrap; overflow: hidden; text-overflow:
  ellipsis`. One row = one line, always. A table whose rows change height as
  content varies cannot be scanned.
- `thead` sticky at the top of the scroll container.
- **Alignment:** text left, numbers right, and numbers get `tabular-nums`. Dates
  left (they are labels, not quantities).
- Expandable detail: the trigger row gets `.has-detail`, the detail is a
  **sibling `<tr>`** with `hidden` and a full-width `colspan`. Toggle `hidden`.

  > Do **not** try to collapse a `<tr>` with `grid-template-rows: 0fr` or
  > `max-height` — table rows do not honour it. This has been implemented
  > wrongly before; use the `hidden` attribute.

### Pattern B — master–detail reading pane

For *reading one record in depth* while keeping the list in view. A two-pane
split, not a table.

- Left: compact scannable list (`.mi-mlist`), `max-height: 440px`, own scroll.
- Right: the full record (`.mi-mpane`), untruncated.
- List row = two lines: a title line (name + a source/region badge) and a single
  ellipsis-clipped meta line in a **fixed field order** (date · risk · flag +
  origin). Fixed order is what makes a list scannable; variable order is chaos.
- Selected row: background change **plus** a 3px left border in
  `--tuv-blue-600`. Colour alone is not enough.
- Selecting a row cross-fades the pane (`opacity` + `translateY(4px)`, 160ms).

### Choosing

| the user is… | pattern |
| --- | --- |
| comparing values across rows | A — scan table |
| reading one record's full text | B — master–detail |
| doing both | B, with the list carrying the comparable fields |

A wide table with a long free-text column is the failure case for A: it forces
either truncation that hides the point, or wrapping that destroys scanning.
That is exactly when to switch to B.

### Shared table rules

- **Country origin uses CSS flags**, never emoji. `window.countryFlagHtml(name)`
  from `js/flags.js` — gradient-drawn, offline, no external requests, and
  consistent across platforms (emoji flags render differently per OS and are
  absent on some Windows builds).
- **Source/region badges** are `.rc-badge` / `.mi-srcbadge` with a per-region
  modifier class. Same colour for the same authority everywhere in the app.
- Risk / severity text uses `--error-600`, weight 600 — never a red row
  background, which reads as "error" rather than "hazard class".

---

## 6. Charts

- **Ranked bars** (`.mi-bar__fill`, `.mi-origin__fill`) are full-row
  *backgrounds behind the label*, not thin bars. They must stay a light tint:
  a saturated fill puts dark text on deep blue and fails 4.5:1. Only bars that
  carry no text (`.mi-yc2-bar`) may take the saturated gradient.
- **Bubble maps**: bubble area encodes count, one hue. Do not label bubbles —
  labels overlap and clutter at any real density. Reveal country + value on
  hover via a `.mi-tip` tooltip (opacity 0 → 1). Size alone carries the ranking;
  the ranked list next to the map carries the exact numbers.
- **Map background** is `world-equirectangular.svg`, a flat vector silhouette in
  `--neutral-100`. Its projection is pinned to the bubble overlay's
  (`x = (lon+180)/360`, `y = (85-lat)/145`). If either changes, both change —
  see `tools/make_world_svg.py`.
- **Range brush** (`.mi-ds`): capped at `max-width: 460px` and centred. A
  handful of points stretched across a full card is mostly empty space. Grey
  underneath = the whole set, blue = the selection, clipped from the *same* path
  so narrowing reads as draining colour out of one shape.

---

## 7. Loading and updating

This section is the difference between "fast" and "feels fast". Follow it
exactly.

### 7.1 Never blank the view

Forbidden: replacing a dashboard with a spinner, a "Loading…" line, or generic
grey blocks. All three destroy the layout and make every load feel like a page
navigation.

Two legitimate states:

**a) Something is already on screen** → keep it, mark it pending:

```css
[data-role="result"].is-swapping { opacity: 0.5; }   /* NO transform */
[data-role="result"] { transition: opacity var(--duration-normal) var(--ease-out); }
```

No `transform`, no `scale`. Nudging a whole dashboard is the "everything
jumped" glitch, and it defeats the point of keeping it visible.

**b) Nothing is on screen yet** (first open) → a skeleton **in the real
layout's shape**: same cards, same KPI strip, same column count.

```js
function dashboardSkeleton() {
  const tiles = `<div class="mi-skel mi-skel--tile"></div>`.repeat(4);
  const cols  = `<div class="mi-skel mi-skel--col"></div>`.repeat(3);
  return `<div class="card">
      <div class="mi-skel mi-skel--head"></div>
      <div class="mi-kpi-strip">${tiles}</div>
      <div class="mi-breakdowns">${cols}</div>
      …`;
}
```

Skeleton block heights must match the real blocks they stand in for (measure
them — `.mi-skel--head: 120px` matches `.mi-rec-head`, `--tile: 131px`,
`--browser: 440px` matches `.mi-mlist`'s max-height). A skeleton whose
proportions are guessed produces a jump when data lands, which is worse than no
skeleton. Aim for **<15px drift** on everything above the fold.

Set `aria-busy="true"` on the container while loading and remove it after.

### 7.2 Mount vs patch

The rule: **rebuild only when the subject changes; otherwise patch in place.**

```js
if (mountedNode === currentNode.id && container.querySelector('[data-role="browser"]')) {
    patch(container, data);      // filter change — update values only
    return;
}
mount(container, data);          // different subject — full build
mountedNode = currentNode.id;
```

Know which parts of a response actually change. In MI the API computes all
breakdowns over the **full** node set so they stay usable as filter controls —
so on a filter change `by_risk` / `by_country` / `by_year` / `by_source` are
byte-identical, and only the filtered count and the visible rows move. Rebuilding
the map and charts for that is pure waste and pure glitch.

A patch updates, in order:

1. the count (ticking from the **on-screen** value, not from 0)
2. any summary text
3. the rows / detail pane
4. the active-filter chips
5. `.is-active` classes on the controls that drive the filters

and touches nothing else.

Verify a patch by **DOM node identity**, not by eye:

```js
const before = container.querySelector('.mi-map');
// …trigger a filter change…
console.assert(container.querySelector('.mi-map') === before, 'map was rebuilt');
```

If a control owns internal state (a brush's lo/hi), expose a sync hook on the
element (`el.__syncRange = () => {…}`) so a patch can pull it back into line
when a filter is cleared from elsewhere, without rebuilding it.

### 7.3 Dim only what changes

Scope the pending state to the region a filter actually affects — the list, not
the whole page:

```css
.mi-browser { transition: opacity var(--duration-fast) var(--ease-out); }
.mi-browser.is-busy { opacity: 0.55; pointer-events: none; }
```

Greying an entire dashboard for a 60ms fetch reads as a flicker.

### 7.4 Guard against stale responses

Dragging a control fires several requests. Without a sequence guard a slow early
one can land last and paint a stale value over a newer one:

```js
let reqSeq = 0;
async function reload() {
  const seq = ++reqSeq;
  const data = await (await fetch(url)).json();
  if (seq !== reqSeq) return;      // superseded mid-flight
  render(data);
}
```

### 7.5 Debounce, don't throttle

Continuous controls (sliders, brushes, type-ahead) commit on a **trailing**
debounce of ~140ms. Long enough to coalesce a drag, short enough that a
deliberate single change feels immediate.

---

## 8. Motion

Full rationale in `README.md`; the data-surface specifics:

- **Use the tokens.** `--ease-out-expo`, `--ease-out`, `--ease-spring`,
  `--duration-fast/normal/slow`. Never paste a raw `cubic-bezier(...)` that
  duplicates a token — a token change then only applies to half the file.
- **Budget:** UI transitions under 300ms. Press feedback 100–160ms. Only rare,
  high-emotion moments (empty states, completion) earn longer.
- **Entrances play once**, on mount. A patched list gets a marker class that
  kills the per-row animation:
  ```css
  .mi-browser.is-patched .mi-mrow { animation: none; }
  ```
- **Never `scale(0)`.** Enter from `0.9`–`0.97` plus opacity. Springing out of
  nothing reads as a popup, not as data appearing.
- **Never animate a chart's geometry for decoration.** Fade it in; do not
  `scaleY` it. Data being read should not move for style. (`backwards` fill also
  holds the FROM state until the animation's clock runs — frozen in a background
  tab — so a geometry transform can leave a chart visibly squashed.)
- **Drag is 1:1.** While dragging, kill the transition (`.is-drag { transition:
  none }`) so the handle tracks the pointer exactly and stays interruptible.
  Only the release may spring.
- **Stagger** 20–30ms for list rows, 60ms for KPI tiles, 22ms for map bubbles.
  Order it meaningfully — bubbles stagger biggest-first, so the map fills in
  from the countries that matter.
- **Reduced motion is not optional.** Every keyframe needs an opt-out. Keep the
  colour/state cue, drop the movement:
  ```css
  @media (prefers-reduced-motion: reduce) {
      .mi-kpi-tile, .mi-mrow, .mi-skel { animation: none; }
      .mi-kpi-tile:hover { transform: none; }
  }
  ```
  Audit it with exact selector matching — substring checks give false passes.

---

## 9. Numbers

- `font-variant-numeric: tabular-nums` on every figure that can change.
- Always `toLocaleString()` — `48006` is not a number a human reads.
- A changing headline figure **ticks** to its new value over ~320ms (600ms on
  first mount), easing `1 - (1-p)³`, **from the value currently displayed**, not
  from zero. Cancel any tick already running on that element so rapid updates
  retarget smoothly instead of racing.
- Show the denominator when filtered: `9,851 of 48,006 matched`, not `9,851`.

---

## 10. Checklist

Before calling a dashboard or table done:

- [ ] Page never blanks — pending keeps the view, first load shows a
      shape-matched skeleton
- [ ] Above-the-fold drift between skeleton and loaded state <15px
- [ ] Filter change patches; verified by DOM node identity that charts/map/
      controls were not rebuilt
- [ ] Focus survives a filter change (drag a control with the keyboard)
- [ ] Stale-response guard present on any control that fires repeatedly
- [ ] Every changing number: `tabular-nums`, `toLocaleString`, ticks from
      current value
- [ ] Table rows are one line, fixed height, never wrap
- [ ] Numbers right-aligned, text left-aligned
- [ ] Flags are CSS flags, not emoji
- [ ] Entrance animations play on mount only
- [ ] Every keyframe has a `prefers-reduced-motion` opt-out
- [ ] No raw `cubic-bezier`/duration literals that duplicate a token
- [ ] Contrast checked against the *lightest* backdrop, not the average
