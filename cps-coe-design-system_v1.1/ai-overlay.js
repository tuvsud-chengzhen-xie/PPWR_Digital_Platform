/* CPS CoE AI — full-screen Layer-3 processing overlay (reusable).
 *
 *   AIOverlay.run(stages, asyncTask, originEl)
 *     • launches the swarm overlay OUT of originEl (e.g. the AI command bar),
 *     • takes over the screen while asyncTask runs (staged status messages),
 *     • collapses back INTO originEl when done, then resolves asyncTask's value.
 *
 * Blue & white · octagon mark · swarm that clusters & orbits · octagon-as-loader
 * · chat-bubble status. This is the standard motion language for AI processing.
 */
window.AIOverlay = (function () {
  const NS = 'http://www.w3.org/2000/svg';
  const R = (a, b) => a + Math.random() * (b - a);
  const ICONS = {
    doc:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M8 13h8M8 17h6"/>',
    flask:'<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3"/>',
    shield:'<path d="M12 3l8 3v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/>',
    box:'<path d="M21 16V8l-9-5-9 5v8l9 5 9-5z"/><path d="M3.3 7.3 12 12l8.7-4.7M12 12v9"/>',
    lab:'<path d="M3 21h18M5 21V9l5-3v3l5-3v15M9 12h.01M14 12h.01M9 16h.01M14 16h.01"/>',
    chip:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>'
  };
  const CX = 360, CY = 320;

  function svgEl(name, attrs) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function build() {
    const ov = document.createElement('div');
    ov.className = 'aio-overlay';
    ov.innerHTML = `
      <svg width="0" height="0"><defs>
        <linearGradient id="aioTrace" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#aee0ff"/><stop offset=".5" stop-color="#2f9bff"/><stop offset="1" stop-color="#0066cc"/>
        </linearGradient></defs></svg>
      <div class="aio-scene">
        <div class="aio-aura"></div>
        <div class="aio-swarm"></div>
        <div class="aio-core">
          <div class="aio-octwrap"><svg class="aio-octsvg" viewBox="0 0 120 120"></svg>
            <div class="aio-octtext"><span class="l1">CPS</span><span class="l2">CoE</span><span class="l3">AI</span></div>
          </div>
        </div>
        <div class="aio-statuswrap"><div class="aio-statusbar"><span class="sb-spark">✦</span><span class="sb-text"></span></div></div>
      </div>`;
    return ov;
  }

  function startScene(ov, stages) {
    const ctx = { alive: true, timers: [], intervals: [] };
    const T = (fn, ms) => { const id = setTimeout(() => { if (ctx.alive) fn(); }, ms); ctx.timers.push(id); return id; };

    const swarm = ov.querySelector('.aio-swarm');
    const spin = R(26, 34).toFixed(1) + 's';
    swarm.style.setProperty('--spin', spin);

    // octagon comet loader (many thin layers → smooth fade tail)
    const octsvg = ov.querySelector('.aio-octsvg');
    const pts = "40,5 80,5 115,40 115,80 80,115 40,115 5,80 5,40", N = 9;
    for (let k = N - 1; k >= 0; k--) {
      const seg = 4 + k * 6, op = Math.max(.05, 0.95 * Math.pow(0.7, k));
      const p = svgEl('polygon', { points: pts, pathLength: '100', 'stroke-dasharray': `${seg} ${100 - seg}`, class: 'aio-trace' + (k === 0 ? ' head' : '') });
      p.style.opacity = op; p.style.strokeWidth = (3 - k * 0.13).toFixed(2);
      octsvg.appendChild(p);
    }

    const placeAt = (el, a, r) => { el.style.transform = `rotate(${a}deg) translateX(${r}px) rotate(${-a}deg)`; };
    let mode = 'spread', clusterAngle = R(0, 360);
    const items = [];
    const targetAngle = it => mode === 'cluster' ? clusterAngle + it.jitter : it.baseAngle;

    function out(it) {
      it.visible = true; it.r = it.baseR * R(.9, 1.1);
      it.el.style.transition = 'transform 1s cubic-bezier(.16,1,.3,1), opacity .6s ease';
      placeAt(it.el, targetAngle(it), it.r); it.el.style.opacity = 1;
      if (mode !== 'cluster') it.t = T(() => retract(it), R(2800, 7000));
    }
    function retract(it) {
      if (mode === 'cluster') return;
      it.visible = false;
      it.el.style.transition = 'transform .85s cubic-bezier(.5,0,.75,0), opacity .55s ease';
      placeAt(it.el, targetAngle(it), 0); it.el.style.opacity = 0;
      it.t = T(() => out(it), R(700, 3600));
    }

    const keys = Object.keys(ICONS).sort(() => Math.random() - 0.5);
    const COUNT = 6;
    for (let i = 0; i < COUNT; i++) {
      const baseAngle = (360 / COUNT) * i + R(-16, 16), baseR = R(168, 206), sz = R(86, 116);
      const n = document.createElement('div'); n.className = 'aio-node';
      n.style.width = n.style.height = sz + 'px';
      n.style.left = (CX - sz / 2) + 'px'; n.style.top = (CY - sz / 2) + 'px';
      const rr = () => Math.floor(R(40, 60));
      n.style.borderRadius = `${rr()}% ${100 - rr()}% ${rr()}% ${100 - rr()}% / ${rr()}% ${rr()}% ${100 - rr()}% ${100 - rr()}%`;
      n.style.setProperty('--np', R(3.4, 5.4).toFixed(1) + 's');
      n.style.setProperty('--nd', R(0, 2.5).toFixed(1) + 's');
      n.innerHTML = `<span class="aio-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">${ICONS[keys[i % keys.length]]}</svg></span>`;
      swarm.appendChild(n);
      const it = { el: n, baseAngle, baseR, jitter: R(-24, 24), visible: false }; placeAt(n, baseAngle, 0);
      items.push(it);
    }
    for (let i = 0; i < 7; i++) {
      const baseAngle = R(0, 360), baseR = R(150, 235), s = R(6, 11);
      const d = document.createElement('div'); d.className = 'aio-dot';
      d.style.width = d.style.height = s + 'px';
      d.style.left = (CX - s / 2) + 'px'; d.style.top = (CY - s / 2) + 'px';
      swarm.appendChild(d);
      const it = { el: d, baseAngle, baseR, jitter: R(-30, 30), visible: false }; placeAt(d, baseAngle, 0);
      items.push(it);
    }
    items.forEach(it => it.t = T(() => out(it), R(0, 2800)));

    (function modeLoop() {
      const dur = mode === 'spread' ? R(7000, 10000) : R(9000, 13000);
      T(() => {
        if (mode === 'spread') {
          mode = 'cluster'; clusterAngle = R(0, 360);
          items.forEach(it => { clearTimeout(it.t);
            if (!it.visible) { it.visible = true; it.r = it.baseR * R(.92, 1.08); }
            it.el.style.transition = 'transform 1.2s cubic-bezier(.16,1,.3,1), opacity .7s ease';
            placeAt(it.el, targetAngle(it), it.r || it.baseR); it.el.style.opacity = 1;
          });
        } else {
          mode = 'spread';
          items.forEach(it => { clearTimeout(it.t);
            it.el.style.transition = 'transform 1.2s cubic-bezier(.16,1,.3,1)';
            placeAt(it.el, targetAngle(it), it.r || it.baseR);
            it.t = T(() => retract(it), R(1400, 4200));
          });
        }
        modeLoop();
      }, dur);
    })();

    // particles emanating from the centre
    const scene = ov.querySelector('.aio-scene');
    for (let i = 0; i < 14; i++) {
      const p = document.createElement('div'); p.className = 'aio-pt'; scene.appendChild(p);
      (function cyc(el) {
        if (!ctx.alive) return;
        const ang = R(0, 2 * Math.PI), dist = R(120, 300), dur = R(2.4, 4.4), delay = R(0, 2.6);
        const anim = el.animate([
          { opacity: 0, transform: 'translate(-50%,-50%) scale(.3)' },
          { opacity: .85, offset: .15 },
          { opacity: 0, transform: `translate(calc(-50% + ${Math.cos(ang) * dist}px),calc(-50% + ${Math.sin(ang) * dist}px)) scale(1)` }
        ], { duration: dur * 1000, delay: delay * 1000, easing: 'ease-out' });
        anim.onfinish = () => cyc(el);
      })(p);
    }

    // chat-bubble status (shrink → extend, never a hard cut)
    const SET = stages && stages.length ? stages : ['Working…'];
    const bar = ov.querySelector('.aio-statusbar'), sbtext = ov.querySelector('.sb-text');
    const meas = document.createElement('span');
    meas.style.cssText = 'position:absolute;left:-9999px;top:-9999px;visibility:hidden;white-space:nowrap;font-size:16px;font-weight:600;font-family:-apple-system,Inter,system-ui,sans-serif;';
    document.body.appendChild(meas); ctx.meas = meas;
    const PAD = 72, COLLAPSED = 52;
    const widthFor = t => { meas.textContent = t; return Math.ceil(meas.offsetWidth) + PAD; };
    let si = 0;
    sbtext.textContent = SET[si]; bar.style.width = widthFor(SET[si]) + 'px'; si = (si + 1) % SET.length;
    const iv = setInterval(() => {
      sbtext.style.opacity = 0; bar.style.width = COLLAPSED + 'px';
      T(() => { sbtext.textContent = SET[si]; bar.style.width = widthFor(SET[si]) + 'px';
        requestAnimationFrame(() => { sbtext.style.opacity = 1; }); si = (si + 1) % SET.length; }, 620);
    }, 3200);
    ctx.intervals.push(iv);

    return ctx;
  }

  function stop(ctx) {
    if (!ctx) return;
    ctx.alive = false;
    ctx.timers.forEach(clearTimeout);
    ctx.intervals.forEach(clearInterval);
    if (ctx.meas) ctx.meas.remove();
  }

  let busy = false;
  async function run(stages, task, originEl) {
    if (busy) return task();        // never stack overlays
    busy = true;
    const ov = build(); document.body.appendChild(ov);
    const scene = ov.querySelector('.aio-scene');
    const ctx = startScene(ov, stages);

    // offset from screen centre to the origin element (the AI command bar)
    const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
    let ox = cx, oy = cy;
    if (originEl) { const r = originEl.getBoundingClientRect(); ox = r.left + r.width / 2; oy = r.top + r.height / 2; }
    // start small & a touch ABOVE the bar, then SLOWLY enlarge and travel to centre
    const start = `translate(${ox - cx}px, ${oy - cy - 36}px) scale(.07)`;
    const back  = `translate(${ox - cx}px, ${oy - cy}px) scale(.05)`;   // shrink down INTO the bar

    scene.style.transition = 'none';
    scene.style.opacity = '0';
    scene.style.transform = start;
    void ov.offsetWidth;                          // force reflow so the start state sticks
    requestAnimationFrame(() => {
      // opacity fades in fast (small form visible early), transform grows slowly
      scene.style.transition = 'transform 1.15s cubic-bezier(.16,1,.3,1), opacity .4s ease';
      ov.style.opacity = '1';
      scene.style.opacity = '1';
      scene.style.transform = 'translate(0,0) scale(1)';   // enlarge → centre
    });

    const started = Date.now();
    let result;
    try { result = await task(); }
    finally {
      const min = 3400, elapsed = Date.now() - started;
      if (elapsed < min) await new Promise(r => setTimeout(r, min - elapsed));
      // collapse BACK down into the bar (faster) — visible while shrinking, fades at the end
      scene.style.transition = 'transform .6s cubic-bezier(.5,0,.2,1), opacity .35s ease .3s';
      scene.style.transform = back;
      scene.style.opacity = '0';
      ov.style.transition = 'opacity .4s ease .2s';    // backdrop clears as the swarm goes in
      ov.style.opacity = '0';
      await new Promise(r => setTimeout(r, 680));
      stop(ctx); ov.remove(); busy = false;
    }
    return result;
  }

  return { run };
})();
