# CPS CoE AI Search — identity for asking questions of our data

The third identity, alongside `AI-IDENTITY.md` (Layer-3 document work) and
`dashboards.md` (deterministic data surfaces).

Reference implementation: **Test Recommendation** and **Client Intelligence** in
Performance Insights. Files: `ai-search.css` + `ai-search.js`.

---

## 0. Which identity am I building?

| the user is… | identity |
| --- | --- |
| handing the AI a **document** to read and extract | `AI-IDENTITY.md` — drop zone + swarm overlay |
| **asking a question** of data we already hold | **this document** — command bar + sweep |
| filtering, paging, sorting a table | `dashboards.md` — skeleton + patch |

The distinction that matters: a Layer-3 document tool takes something *from* the
user and works on it — an overlay is fair, because the user has handed over
control and is waiting on their own file. **A search commits nothing.** The user
asked a question; they may reask, refine, cancel or wander off. So search
**never** takes the screen: no scrim, no `aria-modal`, no pointer lock.

The command bar deliberately **borrows the drop zone's look** — same aurora ring,
same octagon, same glow discipline — because both are "the front door to the AI".
It is not the same component and it does not accept files.

---

## 1. The field IS the island

One element does both jobs. `.ais-field` starts centred as the search field; on
submit it shrinks to its own text, rises, and the status morphs **inside the same
pill**. Nothing is created or destroyed — that continuity is what makes it read
as a Dynamic Island rather than two components swapping.

```
idle    [ ⬡  Client name — e.g. ALDI…            (Build brief) ]   560px, centred
live    [ ⬡  ALDI · 2 countries of origin  Cancel ]                hugs its text, risen
```

Built by `AISearch.mount(el, {placeholder, label, cta, hint, kind, onRun})`.

**Locked rules** (inherited from the drop zone in `AI-IDENTITY.md`):

- `.ais-shell` **must be `isolation: isolate`** — its own stacking context, so the
  glow paints above the page unclipped.
- `.ais-glow` is a **sibling element**, never a pseudo-element.
- **The glow is `box-shadow`, never `filter: blur`.** WebKit paints a blurred
  element softly, then promotes it to a GPU layer ~1s later and re-rasterises the
  blur clipped to the element's own box — the halo snaps to a hard rectangle in
  Safari while looking fine in Chrome. Freezing the animation does not help.
  Four same-shaped shadows offset in different directions fake the aurora. See
  `AI-IDENTITY.md` → **Pitfalls → Glow clipping**.
- **Keep `.ais-stage` and `.ais-shell` free of `overflow: hidden`** — box-shadow
  is clipped by a clipping ancestor, which reintroduces the same rectangle.
- The glow is **off at rest**, lights on **hover** and while **searching** —
  *never on focus*. The field is autofocused, so a focus-lit glow burns from page
  load, which is the "always processing" tell the identity spec forbids. Keyboard
  focus gets a `box-shadow` ring instead.
- **Never `transform` or `filter` on `.ais-field`** — either creates a stacking
  context that clips the glow into a rectangle. Movement comes from width and
  padding, not transform.
- Aurora ring at 4s, accelerating to 1.4s while searching.
- The submit button **collapses to zero width** rather than disappearing; Cancel
  expands into the space it leaves.

---

## 2. The drums

Beneath the island, one card per level, left to right. Each is an **iOS picker
wheel**: neighbouring candidates visible above and below, fading toward the
edges, settling into a highlighted centre band.

```
┌──────────────┐
│  COMPANIES   │      ← faded neighbour
│  Almi        │
│ [ALDI Stores]│      ← centre band, the match
│  Aldo        │
│              │      ← faded neighbour
│ 9 of 32,521  │
└──────────────┘
```

### What spins past matters more than the spin

The values scrolling are **real neighbouring rows** — for `Lidl` the wheel shows
`Lily`, `Lidu`, `Lilax`, `LIXIL`. Sourced from `/api/search-preview`:

1. **exact** — `col ILIKE %q%`, the real matches
2. **similar** — a cheap SQL net (shared opening letters) ranked by
   `difflib.SequenceMatcher` in Python
3. **fallback** — if there is no match at all, the most-recalled values overall,
   so the drum still shows something true rather than filler

`kind=brand` searches `brand` (a client question); `kind=product` searches
`product_raw` (a product question). One SQL pass, ~250–650ms, no LLM — it lands
long before the Azure work does.

### The levels narrow

This is what stops every search looking identical. Each card carries
`N of <corpus total>`, so the sequence reads as the corpus narrowing to *this*
query:

| level | ALDI | Philips |
| --- | --- | --- |
| Companies | 9 of 32,521 | 9 of 32,521 |
| Recall records | 29 of 157,363 | 36 of 157,363 |
| First seen | 1985 → 2026 | 1980 → 2025 |
| Top origin | China · 2 of 349 | Netherlands · 8 of 349 |
| Authorities | AU·US·EU·KR · 4 of 9 | AU·EU·US·NZ · 4 of 9 |

**No findings in the drums.** "29 records exist" is scope; *what those recalls
say* is the result and belongs underneath, when it is complete.

Earlier levels **frost** (`blur(1.6px)`, 42% opacity, narrowed) rather than
vanishing — a salesperson wants to glance back while reading the answer.

---

## 3. Elastic timing — Azure is 2s or 20s

The sequence is **not a fixed timeline**. It races the real work:

**Fast abort.** If the work resolves while drums are still playing, every pending
drum lands immediately (`.is-snap`, 0.28s instead of 1.5s) and the sequence
finishes. A fast answer must never wait for choreography — `apple-design` is
blunt that manufactured latency on the input path is a regression.

```js
await Promise.race([work, sleep(BEAT)]);
if (settled) break;
```

**Long wait.** If the drums are exhausted and the work is still running, stop
inventing levels. Switch to an honest waiting state: the **real server stage**,
elapsed time, an indeterminate bar. Looping the drums would be exactly the
generic filler this identity exists to replace.

**Cancel** is always present while live, and must abort the request and reset
the field.

---

## 4. Motion rules

- **All of it is CSS.** A search pins the main thread (retrieval, reranking) and
  JS-driven animation drops frames precisely when the user is watching hardest.
  The drums are `transform` transitions; the island is `width`/`max-width`.
- **Never leave a value unresolved.** Anything time-based can be starved — a
  background tab throttles timers, a busy main thread starves rAF. Every drum
  exposes `land(fast)` so the sequencer can force it to its true value, and the
  sequence always calls it before finishing.
- Drum spin 1.5s on `cubic-bezier(.12,.72,.16,1)` — a long, decelerating settle
  like a flicked picker. Fast-abort variant 0.28s.
- Beat between levels 1150ms. Card entry 0.55s spring from `translateX(44px)`.
- Frosting transitions over 0.55s so a card softens rather than snapping out.
- Reduced motion: every value still resolves and every label still reads; drums
  land instantly, frosting drops the blur and keeps a lighter opacity.

---

## 5. Checklist

- [ ] No scrim, no `aria-modal`, no pointer lock — the page stays usable
- [ ] The field morphs into the island; nothing is created or destroyed
- [ ] Glow off at rest; hover and searching only, never focus
- [ ] No `transform`/`filter` on `.ais-field`
- [ ] Every drum value is a real row; junk placeholders filtered out
- [ ] Each level shows `N of <corpus total>` so the narrowing is visible
- [ ] No findings in the drums — findings are the result underneath
- [ ] Fast abort: a quick answer never waits for the choreography
- [ ] Long wait: real server stage + elapsed, and the drums never loop
- [ ] Cancel aborts the request and resets the field
- [ ] Stage text free of mechanism jargon ("comparing against every product we
      hold", not "cross-encoder rerank")
- [ ] `prefers-reduced-motion` keeps every value, drops the movement
