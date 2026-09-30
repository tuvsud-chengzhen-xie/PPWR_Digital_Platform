# CPS CoE AI — Visual Identity (Layer-3 only)

The CPS CoE **AI identity** is the shared visual language for **AI features**. It
makes it unmistakable, across every CPS CoE app, when something *intelligent* is
happening — and it reinforces the CPS CoE brand (the TÜV SÜD octagon) every time.

> ## ⚠️ When to use it
> **Use the AI identity ONLY for a Layer-3 AI tool** — i.e. a specialised
> AI/automation service (Document Intelligence, quotation extraction, PSUM
> generation, anomaly detection, classification, etc.).
>
> **Do NOT** use it for ordinary app actions (saving a form, a normal upload,
> a status change, a plain table filter). Those use the regular Design System
> components. If there's no AI/Layer-3 model doing the work, there's no aurora,
> no octagon swarm, no glow. Over-using it destroys the signal.

Two components make up the identity. They are designed to work together:

1. **AI Command Bar / Drop Zone** — the *front door* where the user hands input
   to the AI (a file to read, a prompt, a document to analyse).
2. **AI Processing Overlay** — the *working* state: it launches **out of** the
   command bar, takes over the screen (over a still-visible, blurred app) while
   the Layer-3 tool runs, then **collapses back into** the bar when done.

Files: `ai-overlay.css` + `ai-overlay.js` (drop them in like `nudges.*`).
Requires the brand tokens (`tokens.css`) for the TÜV blue.

---

## 1. AI Command Bar / Drop Zone

A compact white pill with a **flowing colourful gradient ring** (TÜV-blue → cyan
→ violet → gold) and the **TÜV octagon** mark. It is the only "give the AI
something" surface — file drop, prompt, etc.

### Markup
```html
<input type="file" id="quoteFile" accept=".xlsx" hidden>
<div class="qi-shell">
  <div id="aiDrop" class="qi-bar gborder" tabindex="0" role="button"
       onclick="document.getElementById('quoteFile').click()"
       onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();document.getElementById('quoteFile').click();}">
    <span class="qi-oct"><svg viewBox="0 0 120 120" fill="none">
      <polygon points="40,6 80,6 114,40 114,80 80,114 40,114 6,80 6,40"
               stroke="#0066cc" stroke-width="7" stroke-linejoin="round"/></svg></span>
    <span class="qi-bar-text">Drop the file here, or <u>click to browse</u></span>
    <span class="qi-bar-hint">.xlsx</span>
  </div>
  <div class="qi-glow" aria-hidden="true"></div>   <!-- soft glow, hover-only -->
</div>
```

### Rules (locked)
- **`.qi-shell`** wraps the bar and **must be `isolation:isolate`** — its own
  stacking context. This is why the glow paints *above* the page (not behind it)
  and is never clipped into a rectangle.
- The **`.qi-glow`** is a **sibling element**, not a pseudo-element, and is the
  ONLY glow. It is **off at rest (`opacity:0`)** and **fades in on hover/drag
  only**. (Glow without hover reads as "always processing" — wrong.)
- **Build the glow from `box-shadow`, never `filter: blur`** — a blurred element
  is clipped to a hard rectangle by Safari's GPU layer promotion ~1s after hover.
  See **Pitfalls → Glow clipping** below for the full explanation + the snippet.
- The **colourful ring** (`.gborder::before`, a masked conic gradient) is always
  on — it's the frame/border, ~2px, rotating slowly (4s).
- **Never put `transform` or `filter` on `.qi-bar`.** Either creates a stacking
  context that clips the glow into a hard rectangle. Hover/drag changes the
  **glow's opacity/blur only**, never the bar's transform.
- Height **50px**, max-width **560px**, centred. The octagon mark is the left
  affordance; a small `.qi-bar-hint` (e.g. `.xlsx`) sits right.
- Drag handlers add/remove class **`dragover`** on the bar; the glow brightens.

---

## 2. AI Processing Overlay (the "swarm")

When the Layer-3 tool runs, call **one function**. The overlay launches out of
the command bar, animates while the async task runs, and collapses back in.

```js
const result = await AIOverlay.run(
  ['Reading quotation…', 'Extracting project fields…',
   'Detecting HDL / ENE split…', 'Building the test scope…'],   // staged status
  async () => {                                                  // the Layer-3 work
    const r = await fetch('/parse-quotation', { method:'POST', body: fd });
    return await r.json();
  },
  document.getElementById('aiDrop')                              // origin = the bar
);
```

`AIOverlay.run(stages, asyncTask, originEl)` → resolves the task's value.
Guards against stacking (only one overlay at a time) and enforces a minimum
on-screen time so a fast call still *feels* like the AI is thinking.

### The composition (what the user sees)
- **The app stays visible, just blurred.** Backdrop = translucent tint +
  `backdrop-filter: blur(3px)`. The user must feel the app is *living/working*,
  **not** that they navigated away. Never an opaque full-screen cover.
- **Centre piece** — a soft **white, gently *wobbling* blob** (organic, never a
  perfect circle) that breathes and drifts.
- **Octagon mark = the loader.** An **outlined octagon** with **"CPS / CoE / AI"**
  inside (TÜV-badge style). A single bright **comet of light traces around the
  octagon's edges** with a long, smooth fade-tail (many thin layers) — the
  octagon itself *is* the progress indicator. The octagon does **not** rotate
  (a spinning octagon stops looking like TÜV). "CPS CoE AI" gently pulses.
- **The swarm.** Small white blob-cards (with thin line icons) + dots that
  **emerge out of the centre individually** — the visible count keeps changing
  (sometimes one, sometimes three, sometimes all). The whole formation **rotates
  together and breathes in/out** around the centre; **icons stay upright** (they
  counter-rotate the formation — only the *formation* rotates, never the icons).
  Periodically the swarm **gathers into a group and orbits** the centre as one —
  during that go-around, individual emerging/retracting **pauses** (it resumes
  once the group spreads out again). Particles drift out of the centre.
- **Status = a white/blue chat bubble** that **shrinks then extends** for every
  message (auto-sizing to the text, ✦ spark stays) — smooth, never a hard cut.
  Its border is the flowing gradient (same language as the command bar).
- **Everything is randomised each run** (angles, sizes, blob shapes, icons,
  speeds, particle directions) so it never looks like a fixed loop.

### Launch / collapse (locked motion)
- **Out:** starts **small and slightly above the bar**, then **enlarges and
  travels to centre** over ~1.15s (`cubic-bezier(.16,1,.3,1)`); opacity fades in
  fast so the small form is visible before it grows.
- **Back:** **shrinks down into the bar** (~0.6s), staying visible while it
  shrinks, fading only at the very end (the blurred backdrop clears as it goes
  in). Minimum total on-screen ~3.4s.

---

## Tokens (the AI palette + motion)

| Token | Value | Use |
|---|---|---|
| AI aurora colours | `#4d9edf` blue · `#22d3ee` cyan · `#7c5cff` violet · `#FAB434` gold | gradient ring + status border (conic) **and** the glow (box-shadow) |
| Overlay blue (loader/centre) | `#0066cc / #4d9edf` (+ white) | octagon, swarm, aura — **blue & white** |
| Octagon mark | TÜV SÜD octagon, **outlined**, "CPS CoE AI" inside | the brand anchor in every AI moment |
| Easing (enter/organic) | `cubic-bezier(.16, 1, .3, 1)` | launch, crossfades, repositions |
| Ring rotation | 4s linear | command-bar border + status border |
| Swarm spin | 26–34s (randomised) | whole formation; icons counter-rotate |
| Backdrop | `blur(3px)` + light tint | app stays visible behind |
| Glow | **`box-shadow`** (never `filter:blur` — see Pitfalls), hover-only, fade `.35s` | command bar |

Note the deliberate split: **the command bar's ring/glow is colourful**
(blue→cyan→violet→gold); **the processing overlay is blue & white** (it carries
the CPS brand, not a Google-style rainbow). Keep that distinction.

---

## Pitfalls (learned the hard way)

### Glow clipping → "snaps to a hard rectangle" (Safari)
**Symptom:** a soft glow halo behind an element looks perfect right after hover,
then ~1 second later snaps to a hard rectangular edge — the glow gets clipped to
a box. Usually Safari/WebKit; often fine in Chrome.

**Real cause:** the glow was built with **`filter: blur()`** on an element.
WebKit paints it softly at first, then promotes the blurred element to a GPU
compositing layer a moment later and **re-rasterises the blur clipped to the
element's own box** — the part that should bleed outside the box is cut off →
hard rectangle. It happens **whether or not** the gradient animates, so
"make it static / stop the animation" does **not** fix it.

**Not the culprit** (don't waste time here): `isolation: isolate` on the wrapper;
animating a registered `@property`.

**The fix (cross-browser):** never use `filter: blur` for a glow that must bleed
outside its box — build the glow from **`box-shadow`**. Box-shadows paint
*outside* the border box, are never clipped to it, and are unaffected by layer
compositing, so they render identically in Safari and Chrome and never degrade.
Fake a multicolour aurora with a few offset coloured shadows (this is exactly
what `.qi-glow` now uses):

```css
/* glow sits BEHIND an opaque element: bar z-index:1, glow z-index:0 */
.qi-glow{
  position:absolute; inset:0; border-radius:999px; z-index:0;
  pointer-events:none; opacity:0;
  transition:opacity .35s ease, box-shadow .35s ease;
  box-shadow:
    -14px -10px 28px -4px rgba(77,158,223,.55),   /* blue   top-left  */
     14px -10px 28px -4px rgba(34,211,238,.50),   /* cyan   top-right */
     14px  10px 28px -4px rgba(124,92,255,.55),   /* violet bot-right */
    -14px  10px 28px -4px rgba(250,180,52,.50);   /* gold   bot-left  */
}
.qi-bar:hover ~ .qi-glow{ opacity:.95 }   /* glow is a SIBLING behind the bar */
```
**Key points:** each shadow is the same rounded shape, offset + blurred in a
different direction so each edge shows a different colour; the centre is hidden
behind the opaque element; **negative spread (`-4px`)** stops colours bleeding
inward. **Gotcha:** `box-shadow` *is* clipped by an ancestor with
`overflow:hidden` — keep ancestors un-clipped.

> Rule of thumb: **persistent decorative glows = `box-shadow`.** Reserve
> `filter: blur` for large, transient, full-bleed elements (e.g. the overlay's
> background aura) where box-clipping isn't visible.

---

## Production note

In the MVP the Layer-3 work behind the overlay is local (openpyxl parsing, a
rule engine). In production the **same `AIOverlay.run(stages, task, origin)`
interface** wraps the real service — e.g. **Azure Document Intelligence**,
a model endpoint, or a queued job. The identity does not change; only the
`asyncTask` does.

---

## Summary — the standard

- **AI input?** → use the **AI Command Bar / Drop Zone** (`.qi-shell` + `.qi-bar`).
- **Layer-3 tool running?** → wrap it in **`AIOverlay.run(...)`** so the swarm
  launches from that bar, processes over the blurred-but-living app, and returns.
- **Not AI?** → don't use any of this.
