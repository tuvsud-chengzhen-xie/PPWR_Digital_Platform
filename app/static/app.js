/* PPWR Digital Platform — small behaviour layer.
   - toast after redirect (?toast=…&toast_type=…)
   - Layer-3 AI actions (AI pre-review, BOM reading, TD/DoC generation) run inside
     AIOverlay.run(), launched from their command bar / button (AI-IDENTITY.md)
   - plain uploads: drag & drop onto .upload areas (no AI styling — not AI work)
   - confirm prompts, clickable table rows */

(function () {
    const topbar = document.querySelector(".topbar");
    if (topbar) {
        const toggle = topbar.querySelector(".nav-toggle");
        const mobile = window.matchMedia("(max-width: 880px)");
        const setOpen = (open) => {
            topbar.classList.toggle("is-open", open);
            if (toggle) {
                toggle.setAttribute("aria-expanded", open ? "true" : "false");
                toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
            }
        };
        if (toggle) {
            toggle.addEventListener("click", () => setOpen(!topbar.classList.contains("is-open")));
            document.addEventListener("keydown", (e) => {
                if (e.key === "Escape" && topbar.classList.contains("is-open")) { setOpen(false); toggle.focus(); }
            });
            document.addEventListener("click", (e) => {
                if (topbar.classList.contains("is-open") && !topbar.contains(e.target)) setOpen(false);
            });
            const onChange = () => { if (!mobile.matches) setOpen(false); };
            if (mobile.addEventListener) mobile.addEventListener("change", onChange); else mobile.addListener(onChange);
        }
        // Sticky side rails stop below the top bar, whose height changes as the nav wraps.
        const syncOffset = () => {
            if (topbar.classList.contains("is-open")) return;
            document.documentElement.style.setProperty("--sticky-top-offset", (topbar.offsetHeight + 8) + "px");
        };
        syncOffset();
        if (window.ResizeObserver) new ResizeObserver(syncOffset).observe(topbar);
        else window.addEventListener("resize", syncOffset);
    }

    const params = new URLSearchParams(location.search);
    const toast = params.get("toast");
    if (toast && typeof showToast === "function") {
        showToast(toast, { type: params.get("toast_type") || "success", duration: 4200 });
        params.delete("toast"); params.delete("toast_type");
        const qs = params.toString();
        history.replaceState({}, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }

    function note(msg, type) {
        if (typeof showToast === "function") showToast(msg, { type: type || "info", duration: 4500 });
    }

    async function runAI(stages, url, body, origin) {
        const task = async () => {
            const r = await fetch(url, { method: "POST", body: body, headers: { "Accept": "application/json" } });
            let data = {};
            try { data = await r.json(); } catch (e) { data = { ok: false, message: "Unexpected response (" + r.status + ")" }; }
            if (!r.ok && data.ok !== false) data.ok = false;
            return data;
        };
        const data = (typeof AIOverlay !== "undefined" && AIOverlay.run)
            ? await AIOverlay.run(stages, task, origin) : await task();
        if (data.warnings && data.warnings.length) note(data.warnings.slice(0, 3).join(" · "), "warn");
        if (data.redirect) {
            const sep = data.redirect.includes("?") ? "&" : "?";
            location.href = data.redirect + sep + "toast=" + encodeURIComponent(data.message || "Done") +
                "&toast_type=" + (data.ok === false ? "error" : "success");
        } else {
            note(data.message || "Done", data.ok === false ? "error" : "success");
        }
    }

    // buttons / forms that trigger a Layer-3 step
    document.querySelectorAll("[data-ai-post]").forEach(el => {
        const handler = (ev) => {
            if (ev.submitter && ev.submitter.hasAttribute("formaction")) return;  // plain secondary action
            ev.preventDefault();
            const form = el.tagName === "FORM" ? el : el.closest("form");
            const body = form ? new FormData(form) : new FormData();
            const stages = (el.dataset.aiStages || "Working…").split("|");
            const origin = document.getElementById(el.dataset.aiOrigin || "") || el;
            runAI(stages, el.dataset.aiPost, body, origin);
        };
        el.addEventListener(el.tagName === "FORM" ? "submit" : "click", handler);
    });

    // AI command bar: hand the AI a workbook (BOM import)
    document.querySelectorAll(".qi-bar[data-ai-file]").forEach(bar => {
        const input = document.getElementById(bar.dataset.aiFile);
        const send = (file) => {
            if (!file) return;
            const fd = new FormData();
            fd.append("file", file);
            runAI((bar.dataset.aiStages || "Reading…").split("|"), bar.dataset.aiUrl, fd, bar);
        };
        bar.addEventListener("click", () => input.click());
        bar.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
        input.addEventListener("change", () => send(input.files[0]));
        ["dragenter", "dragover"].forEach(t => bar.addEventListener(t, (e) => { e.preventDefault(); bar.classList.add("dragover"); }));
        ["dragleave", "drop"].forEach(t => bar.addEventListener(t, (e) => { e.preventDefault(); bar.classList.remove("dragover"); }));
        bar.addEventListener("drop", (e) => send(e.dataTransfer.files[0]));
    });

    // plain upload areas
    document.querySelectorAll(".upload").forEach(zone => {
        const input = zone.querySelector("input[type=file]");
        const label = zone.querySelector("[data-file-label]");
        const title = zone.closest("form") && zone.closest("form").querySelector("[name=title]");
        const show = () => {
            if (!input.files.length) return;
            if (label) label.textContent = input.files[0].name;
            if (title && !title.value) title.value = input.files[0].name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
        };
        input.addEventListener("change", show);
        ["dragenter", "dragover"].forEach(t => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
        ["dragleave", "drop"].forEach(t => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
        zone.addEventListener("drop", (e) => { input.files = e.dataTransfer.files; show(); });
    });

    document.querySelectorAll("form[data-confirm]").forEach(f => f.addEventListener("submit", (e) => {
        if (!confirm(f.dataset.confirm)) e.preventDefault();
    }));

    document.querySelectorAll("tr[data-href]").forEach(tr => tr.addEventListener("click", (e) => {
        if (e.target.closest("a, button, form, input, select")) return;
        location.href = tr.dataset.href;
    }));

    // table editor: add a row
    document.querySelectorAll("[data-add-row]").forEach(btn => btn.addEventListener("click", () => {
        const tbody = document.getElementById(btn.dataset.addRow);
        const rows = tbody.querySelectorAll("tr").length;
        const cols = parseInt(btn.dataset.cols, 10);
        const tr = document.createElement("tr");
        for (let c = 0; c < cols; c++) {
            const td = document.createElement("td");
            const inp = document.createElement("input");
            inp.name = `t_${rows}_${c}`;
            td.appendChild(inp); tr.appendChild(td);
        }
        tbody.appendChild(tr);
        const counter = document.querySelector("input[name=t_rows]");
        if (counter) counter.value = rows + 1;
    }));

    // ticking numbers (dashboards.md §9) — on mount only, from 0
    document.querySelectorAll("[data-tick]").forEach(el => {
        const target = parseFloat(el.dataset.tick);
        if (!isFinite(target) || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        const t0 = performance.now(), dur = 600;
        const step = (t) => {
            const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
            el.textContent = Math.round(target * e).toLocaleString();
            if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    });

    /* ------------------------------------------------------------------ bilingual helpers */
    const LANG = document.documentElement.getAttribute("data-lang") || (document.querySelector("[data-lang]") || {}).dataset?.lang || "bi";
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    function bi(en, zh) {
        if (!zh || zh === en || LANG === "en") return esc(en);
        return esc(en) + ' <span class="zh">' + esc(zh) + "</span>";
    }
    const mark = (ok) => ok === true ? '<span class="ai-mark ok">✓</span>' : ok === false ? '<span class="ai-mark no">!</span>' : '<span class="ai-mark maybe">?</span>';

    /* ------------------------------------------------------------------ field format validation */
    document.querySelectorAll("input[data-pattern]").forEach(inp => {
        const err = inp.parentElement.querySelector(".field-error");
        const check = () => {
            let bad = false;
            try { bad = inp.value.trim() && !new RegExp(inp.dataset.pattern).test(inp.value.trim()); } catch (e) { bad = false; }
            inp.classList.toggle("is-invalid", !!bad);
            if (err) { err.hidden = !bad; err.textContent = bad ? inp.dataset.patternMsg : ""; }
        };
        inp.addEventListener("input", check); inp.addEventListener("blur", check); check();
    });

    /* ------------------------------------------------------------------ pre-submission check */
    const itemForm = document.querySelector("form[data-precheck]");
    if (itemForm) {
        const box = document.getElementById("precheckResult");
        let force = false;
        const run = async (forSubmit, submitter) => {
            const fd = new FormData(itemForm);
            const task = async () => {
                const r = await fetch(itemForm.dataset.precheck, { method: "POST", body: fd, headers: { "Accept": "application/json" } });
                return r.json();
            };
            const data = (typeof AIOverlay !== "undefined" && AIOverlay.run && !forSubmit)
                ? await AIOverlay.run(["Reading your entry · 读取填写…", "Checking evidence requirements · 核对证据要求…", "Applying PPWR rules · 执行 PPWR 规则…"], task, submitter)
                : await task();
            const gaps = data.gaps || [];
            let h = `<div class="precheck-head">${bi("Pre-submission check", "提交前检查")} · <b>${data.ready_pct}%</b> ${bi("of the minimum evidence", "最低证据")}` +
                ` · <span class="badge">${bi(data.obligation.label, data.obligation.label_zh)}</span></div>`;
            h += `<ul class="ai-checks">` + (data.minimum || []).map(m => `<li>${mark(m.ok)}<span>${bi(m.en, m.zh)}</span></li>`).join("") + `</ul>`;
            if (gaps.length) {
                h += `<div class="gap-box"><b>${bi("Missing or to correct", "缺失或需更正")} (${gaps.length})</b><ul>` +
                    gaps.map(g => `<li>${bi(g.en, g.zh)}</li>`).join("") + `</ul></div>`;
            } else {
                h += `<div class="banner banner-ok small">${bi("No omissions found — ready to submit.", "未发现遗漏——可以提交。")}</div>`;
            }
            const hints = (data.hints || []).filter(x => x.kind === "alert");
            if (hints.length) h += `<ul class="hint-list">` + hints.map(x => `<li class="hint-alert">${bi(x.en, x.zh)}</li>`).join("") + `</ul>`;
            if (forSubmit && gaps.length) {
                h += `<div class="form-actions"><button type="button" class="btn btn-sm" data-fix>${bi("Fix now", "立即修正")}</button>` +
                    `<button type="button" class="btn btn-sm btn-ghost" data-anyway>${bi("Submit anyway — the expert will review", "仍然提交——由专家审核")}</button></div>`;
            }
            box.innerHTML = h; box.hidden = false;
            box.scrollIntoView({ behavior: "smooth", block: "nearest" });
            const fix = box.querySelector("[data-fix]");
            if (fix) fix.addEventListener("click", () => { box.hidden = true; document.getElementById("requirements").scrollIntoView({ behavior: "smooth" }); });
            const anyway = box.querySelector("[data-anyway]");
            if (anyway) anyway.addEventListener("click", () => { force = true; (submitter || itemForm.querySelector('[name=action][value=submit]')).click(); });
            return gaps.length === 0;
        };
        const runBtn = itemForm.querySelector("[data-precheck-run]");
        if (runBtn) runBtn.addEventListener("click", () => run(false, runBtn));
        itemForm.addEventListener("submit", async (e) => {
            const btn = e.submitter;
            if (!btn || btn.value !== "submit" || force) return;
            e.preventDefault();
            const clean = await run(true, btn);
            if (clean) { force = true; btn.click(); }
        });
    }

    /* ------------------------------------------------------------------ RAG assistant */
    function renderAnswer(out, data) {
        if (data.ok === false) { out.innerHTML = `<p class="small">${esc(data.message || "Error")}</p>`; out.hidden = false; return; }
        const text = (s) => esc(s).replace(/\[S(\d+)\]/g, '<a class="cite" href="#src-$1">[S$1]</a>').replace(/\n/g, "<br>");
        let h = "";
        h += `<div class="ans-en">${text(data.en)}</div>`;
        if (LANG !== "en" && data.zh) h += `<div class="ans-zh" lang="zh">${text(data.zh)}</div>`;
        if (data.sources && data.sources.length) {
            h += `<ol class="ans-src">` + data.sources.map((s, i) =>
                `<li id="src-${i + 1}"><span class="badge ${s.binding ? "badge-high" : "badge-outline"}">${s.binding ? bi("binding", "法定") : bi("guidance", "指引")}</span> ` +
                (s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.ref || s.title)}${s.page ? " · p." + s.page : ""}</a>` : esc(s.ref || s.title)) + `</li>`).join("") + `</ol>`;
        }
        h += `<p class="xs muted">${data.mode === "llm" ? bi("Generated by the configured LLM from the sources above.", "由已配置的大模型依据上述来源生成。") : bi("Composed directly from the knowledge base (no LLM).", "直接由知识库组成（未使用大模型）。")}` +
            (data.notice ? " " + esc(data.notice) : "") + (data.corpus_state === "building" ? " " + bi("Full-text index is still building.", "全文索引仍在构建。") : "") + `</p>`;
        out.innerHTML = h; out.hidden = false;
    }
    document.querySelectorAll("form[data-ask]").forEach(f => {
        const out = f.querySelector(".ask-out");
        f.querySelectorAll("[data-q]").forEach(b => b.addEventListener("click", () => { f.q.value = b.dataset.q; f.requestSubmit(); }));
        f.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fd = new FormData(f);
            const task = async () => (await fetch(f.dataset.ask, { method: "POST", body: fd })).json();
            const data = (typeof AIOverlay !== "undefined" && AIOverlay.run)
                ? await AIOverlay.run(["Searching the PPWR knowledge base · 检索知识库…", "Ranking regulation, standards and guidance · 排序法规、标准与指南…", "Writing a cited answer · 生成带引用的回答…"], task, f)
                : await task();
            renderAnswer(out, data);
        });
    });

    /* ------------------------------------------------------------------ upload format hint */
    document.querySelectorAll(".upload[data-accept]").forEach(zone => {
        const input = zone.querySelector("input[type=file]");
        const ok = zone.dataset.accept.split(",");
        input.addEventListener("change", () => {
            const f = input.files[0]; if (!f) return;
            const ext = (f.name.split(".").pop() || "").toLowerCase();
            if (ok.indexOf(ext) < 0) note(zone.dataset.acceptMsg + ": " + ok.join(", ").toUpperCase(), "warn");
        });
    });

    /* ------------------------------------------------------------------ smart import: many files / folder / ZIP */
    document.querySelectorAll("[data-import-drop]").forEach(zone => {
        const inputs = zone.querySelectorAll("input[type=file]");
        const send = (files) => {
            if (!files || !files.length) return;
            const fd = new FormData();
            Array.from(files).forEach(f => fd.append("files", f, f.webkitRelativePath || f.relPath || f.name));
            runAI((zone.dataset.aiStages || "Reading…").split("|"), zone.dataset.importDrop, fd, zone);
        };
        inputs.forEach(i => i.addEventListener("change", () => send(i.files)));
        zone.querySelectorAll("[data-pick]").forEach(b => b.addEventListener("click", (e) => { e.preventDefault(); document.getElementById(b.dataset.pick).click(); }));
        ["dragenter", "dragover"].forEach(t => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
        ["dragleave", "drop"].forEach(t => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
        zone.addEventListener("drop", async (e) => {
            const items = e.dataTransfer.items;
            if (items && items.length && items[0].webkitGetAsEntry) {
                const files = [];
                const walk = (entry, path) => new Promise(res => {
                    if (entry.isFile) entry.file(f => { f.relPath = path + f.name; files.push(f); res(); });
                    else if (entry.isDirectory) {
                        const r = entry.createReader();
                        const all = [];
                        const read = () => r.readEntries(async (ents) => {
                            if (!ents.length) { for (const en of all) await walk(en, path + entry.name + "/"); res(); }
                            else { all.push(...ents); read(); }
                        });
                        read();
                    } else res();
                });
                const entries = Array.from(items).map(i => i.webkitGetAsEntry()).filter(Boolean);
                for (const en of entries) await walk(en, "");
                send(files);
            } else send(e.dataTransfer.files);
        });
    });
    document.querySelectorAll("[data-sample-into]").forEach(b => b.addEventListener("click", () => {
        const ta = document.getElementById(b.dataset.sampleInto);
        ta.value = b.dataset.sample;
    }));
})();
