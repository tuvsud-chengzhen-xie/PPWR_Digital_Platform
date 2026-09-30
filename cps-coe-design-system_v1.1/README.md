# CPS CoE Design System

The shared design system for **TÜV SÜD CPS Center of Excellence** apps —
corporate identity, productivity components, **and the CPS CoE AI identity**.
Drop the files into a new project's `/ds/` (or any path), include them in your
base template, and you inherit the brand without copy-paste drift between apps.

It has two identity layers:
- **Core / app** — brand tokens, shell, productivity nudges. Used by *every* app.
- **AI identity** — the AI command bar + AI processing overlay. **Used ONLY when
  the app has a Layer-3 AI tool** (see [`AI-IDENTITY.md`](AI-IDENTITY.md)). Never
  for ordinary app actions.

## File structure

```
design-system/
├── tokens.css       ← CSS custom properties (colours, spacing, typography,
│                      shadows, motion, layout caps, sticky-top offset)
├── ai-overlay.css   ← AI IDENTITY (Layer-3 only): AI command bar / drop zone
│                      (.qi-shell/.qi-bar/.qi-glow) + full-screen processing
│                      overlay (octagon-loader swarm). See AI-IDENTITY.md.
├── ai-overlay.js    ← AI IDENTITY behaviour: window.AIOverlay.run(stages,
│                      asyncTask, originEl) — launches the swarm out of the bar,
│                      runs the task, collapses back in.
├── AI-IDENTITY.md   ← The CPS CoE AI identity spec (when to use, components,
│                      tokens, locked motion rules)
├── shell.css        ← App-shell components: topbar with blue gradient +
│                      "by …" sub-line, top nav + Setup pill + Savings chip,
│                      2-col / narrow page layouts, sticky side rail,
│                      rail-card vocabulary, page head, breadcrumb, footer
├── shell.js         ← Savings-chip celebration logic (flying octagons +
│                      counter bump). Vanilla JS, no dependencies.
├── shell.html       ← Drop-in HTML skeleton + interactive preview
├── logo.png         ← Official TÜV SÜD logo (44×44 transparent PNG).
│                      Copy into your app's /static/ — the topbar references
│                      it at /static/logo.png. Use it as-is so every CPS
│                      app shares the same corporate mark.
├── nudges.css       ← Productivity components: toast, autosave dot,
│                      shortcuts overlay, command palette, progress bar
├── nudges.js        ← Behaviour layer for the nudges
├── demo.html        ← Original component playground
├── dashboards.md    ← DATA SURFACES: dashboards, KPI strips, filter controls,
│                      the two table patterns, and the loading/patching rules.
│                      The deterministic counterpart to AI-IDENTITY.md — use it
│                      for querying/filtering/paging, never the AI overlay.
├── ai-search.md     ← AI SEARCH: asking a question of data we already hold.
│                      Command bar (drop-zone look, search purpose) + the sweep,
│                      which shows the SCALE being searched and never blocks.
└── README.md
```

### Which identity?

| the user is… | use |
| --- | --- |
| handing the AI a **document** to read | `AI-IDENTITY.md` — drop zone + swarm overlay |
| **asking a question** of data we hold | `ai-search.md` — command bar + sweep |
| filtering / paging / sorting a table | `dashboards.md` — skeleton + patch |

## Quick start (new app)

1. Copy the design-system folder into your project; mount it at `/ds/` (or
   wherever — adjust the link `href`s).
2. **Copy `logo.png` from `design-system/` into your app's `/static/`
   folder.** The shipped file is the official TÜV SÜD 44×44 transparent
   PNG. The topbar references it at `/static/logo.png` — if you serve
   static assets from a different path, adjust the `<img src>` in your
   base template, but please keep using the same image so every CPS app
   carries the same mark.
3. In your base template:
   ```html
   <link rel="icon" type="image/png" href="/static/logo.png">
   <link rel="stylesheet" href="/ds/tokens.css">
   <link rel="stylesheet" href="/ds/shell.css">
   <link rel="stylesheet" href="/static/style.css">  <!-- app-specific last -->
   ```
4. Paste the topbar / page / footer structure from `shell.html` into your
   base layout, edit the brand title and nav items.
5. Open `shell.html` directly in a browser to verify your tokens render.

---

## AI identity (Layer-3 only) — the standard for AI features

> **Use it ONLY when a Layer-3 AI tool is doing the work** (Document
> Intelligence, quotation extraction, PSUM generation, anomaly detection, …).
> Never for ordinary saves, uploads, status changes or filters. Full spec +
> locked motion rules in **[`AI-IDENTITY.md`](AI-IDENTITY.md)**.

Two components, designed to work as one flow:

1. **AI Command Bar / Drop Zone** — the front door for AI input (a file, a
   prompt). A compact white pill with a flowing colourful gradient ring + TÜV
   octagon; the soft glow appears **on hover only**.
2. **AI Processing Overlay** — the working state. It **launches out of the bar**,
   takes over a **still-visible, blurred** app while the tool runs (octagon-loader
   swarm, "CPS CoE AI"), then **collapses back into the bar**.

```html
<link rel="stylesheet" href="/ds/ai-overlay.css">
<script src="/ds/ai-overlay.js"></script>
```
```js
const result = await AIOverlay.run(
  ['Reading…', 'Extracting…', 'Almost ready…'],   // staged status messages
  async () => (await fetch('/my-layer3-endpoint', {method:'POST', body: fd})).json(),
  document.getElementById('aiDrop')                // origin = the command bar
);
```

**Golden rules:** the app stays visible-but-blurred (never opaque); the octagon
never rotates; only the *formation* rotates (icons stay upright); the command
bar never gets a `transform`/`filter` (it would clip the glow). Details in
`AI-IDENTITY.md`.

---

## Corporate identity — the app shell

The visual signature of every CPS app is the same. Don't reinvent it.

### Topbar — gradient header with brand sub-line

The TÜV SÜD blue gradient with a sphere highlight at the top centre and a
faint inset shine at the bottom. The brand block uses two lines — the app
name on top, **"by CPS Center of Excellence"** on the bottom — to anchor
every app to the team that owns it.

```html
<header class="topbar">
    <div class="topbar-inner">
        <a class="brand" href="/">
            <img src="/static/logo.png" alt="TÜV SÜD" class="brand-logo">
            <div class="brand-text">
                <span class="brand-title">App name</span>
                <span class="brand-sub">by CPS Center of Excellence</span>
            </div>
        </a>
        <nav class="topnav">
            <a href="/foo" class="is-active">Foo</a>
            <a href="/bar">Bar</a>
        </nav>
        <span class="spacer"></span>
        <a href="/setup" class="topnav-setup">Setup</a>
    </div>
</header>
```

The topbar is `position: sticky; top: 0`. Anything else that sticks should
use `top: var(--sticky-top-offset)` (76px) — that variable accounts for the
topbar's actual rendered height + a small breathing gap, so sticky rails
sit *below* the topbar instead of disappearing behind it.

### Savings chip — optional gamification element

Green pill in the top nav showing a cumulative count (km saved, hours
reclaimed, $ recovered — whatever the app tracks). When the user takes a
saving action, flying green octagons spawn at the click target and fly up
to the chip — TikTok-heart style — and the chip's number pulses up. Used
in *Inspection Scheduling* for `total_saved_km` from accepted bundles.

```html
<a href="/savings" id="savings-counter" data-value="142"
   class="topnav-savings"
   title="What this counts — explain the metric here.">
    <svg class="savings-octagon" viewBox="0 0 100 100">
        <polygon points="30,5 70,5 95,30 95,70 70,95 30,95 5,70 5,30" fill="currentColor"/>
    </svg>
    <span class="savings-value">~142 km</span>
    <span class="savings-label">saved</span>
</a>
```

Load `shell.js` and annotate any saving form:

```html
<form method="post" action="/accept" data-savings-km="26">
    <button type="submit" class="btn btn-primary">Accept proposal</button>
</form>
```

shell.js intercepts the submit, fires the animation, then submits for real
after ~750ms so the celebration is visible before the page reloads. The
chip's server-rendered value lands on the next page and matches what the
user just watched count up.

### Layout system — wide / 2-col / narrow

Three page widths cover almost every use case. Set the modifier class on
`<main class="page …">`:

| Modifier | Max width | Best for |
|---|---|---|
| (none) | 1440px | Dense data grids — Planner-style inspector × day boards |
| `is-2col` | 1180px | Decision flows with a side rail — Bundling list, Smart Scheduling hub |
| `is-narrow` | 880px | Focus surfaces — single-job triage, settings, forms |

Inside `is-2col`, wrap content in the layout grid:

```html
<main class="page is-2col">
    <div class="page-head">
        <h1>Title</h1>
        <div class="page-actions">…</div>
    </div>

    <div class="layout-2col">
        <main class="layout-main">…</main>
        <aside class="layout-rail">…</aside>
    </div>
</main>
```

`.layout-rail` is `position: sticky` with `top: var(--sticky-top-offset)`
and `max-height: calc(100vh - var(--sticky-top-offset) - var(--space-4))`,
so it stays in view *below* the topbar while the user scrolls the main
column. Collapses below the main column at ≤1024px.

### Rail-card vocabulary

Every rail card uses the same shape — `.rail-card` with an optional
`.rail-card-eyebrow` small-caps label. Keeps the rail visually
consistent across apps without forcing a specific layout.

```html
<aside class="layout-rail">
    <div class="rail-card">
        <header class="rail-card-head">
            <span class="rail-card-eyebrow">Section title</span>
        </header>
        Side info…
        <a href="#" class="rail-link">Open module →</a>
    </div>
</aside>
```

---

## Design tokens (tokens.css)

All colours, spacing, typography, shadows, motion curves, and layout caps
live as CSS custom properties. Override at `:root` to retheme a single app
without touching shell.css.

```css
:root {
    --tuv-blue-600: #0066cc;    /* Primary accent */
    --tuv-blue-900: #003d7a;    /* Dark headers */
    --success-500: #22c55e;     /* Success states */
    --error-500:   #dc3545;     /* Error states */
    --neutral-25:  #f4f6f9;     /* Page background */

    --sticky-top-offset:     76px;    /* viewport-sticky elements stop below the topbar */
    --page-max-width:       1440px;   /* default page cap */
    --page-2col-max-width:  1180px;   /* `is-2col` cap */
    --page-narrow-max-width: 880px;   /* `is-narrow` cap */
    --rail-width:            300px;   /* side-rail column width */
}
```

---

## Nudges (productivity components)

Separate from the app shell — toasts, autosave dots, keyboard-shortcut
overlay, command palette, progress dots. See **`demo.html`** for the
interactive playground. Each documented below was extracted from the
ArrowSync annotation tool but works in any app.

### 1. Toast Notifications
Non-blocking feedback replacing `alert()`. Stacks from top-right, auto-dismisses.

```javascript
showToast('Project saved', { type: 'success' });
showToast('Upload failed', { type: 'error', duration: 5000 });
showToast('Arrow type locked', { type: 'info' });
showToast('Unsaved changes', { type: 'warn' });
```

Types: `success`, `error`, `info`, `warn`

### 2. Auto-Save Indicator
Tiny dot + text that shows save state.

```html
<span class="autosave-indicator saved" id="autosaveIndicator">
    <span class="autosave-dot"></span>
    <span class="autosave-text">Saved</span>
</span>
```

States: `unsaved` (amber), `saving` (blue pulse), `saved` (green), `error` (red)

### 3. Keyboard Shortcuts Overlay
Modal overlay listing all shortcuts, grouped by section.

```javascript
NudgeSystem.init({
    shortcuts: [
        { key: 'a', label: 'Arrow tool', keys: ['A'], section: 'Tools', action: () => {} },
        { key: 's', mod: 'cmd', label: 'Save', keys: ['⌘', 'S'], section: 'File', action: save },
    ]
});
toggleShortcutsOverlay(); // open/close
```

### 4. Command Palette (⌘K)
Spotlight-style fuzzy search across all commands.

```javascript
NudgeSystem.init({
    commands: [
        { label: 'Save Project', keys: ['⌘', 'S'], action: save, tags: 'save store' },
        { label: 'Add Photos', keys: [], action: upload, tags: 'upload import' },
    ]
});
toggleCommandPalette(); // open/close
```

### 5. Progress Bar + Nav Dots
Thin gradient bar showing annotation completeness + clickable per-image dots.

```html
<div class="progress-bar-wrap">
    <div class="progress-bar-fill" style="width: 60%"></div>
</div>

<div class="nav-dots">
    <span class="nav-dot complete"></span>
    <span class="nav-dot has-annotations current"></span>
    <span class="nav-dot"></span>
</div>
```

Dot states: default (gray), `.has-annotations` (blue), `.complete` (green), `.current` (ring)

### 6. Micro-Interactions
- `.canvas-wrapper.flash` — blue inset flash on annotation add
- `.btn-success.just-saved` — green pulse on save
- `.component-item-new` — slide-in animation for new list items

---

## Design principles

1. **One identity, many apps** — the topbar, brand sub-line, and Savings
   chip are the same across every CPS app. Override tokens for theming, not
   shell.css for restructuring.
2. **White-first** — clean medical/precision aesthetic. Dark elements only
   in headers and decision-flow heroes.
3. **Constrained reading widths** — most surfaces don't need 1440px. Pick
   `is-2col` or `is-narrow` and respect the reader's eye.
4. **Non-blocking** — toasts over alerts. Never freeze the UI.
5. **Progressive disclosure** — collapse what's optional. Shortcuts hint on
   hover; command palette for power users.
6. **Subtle motion with one exuberant moment** — most transitions are
   0.15–0.4s expo ease. The Savings celebration is the one place we let
   the UI cheer; that contrast is what makes the cheer feel earned.
7. **Information density via spatial layout** — sticky rails, eyebrow
   labels, progress dots. Convey state without taking space.
