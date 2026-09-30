/* PPWR Digital Platform — small behaviour layer.
   - toast after redirect (?toast=…&toast_type=…)
   - Layer-3 AI actions (AI pre-review, BOM reading, TD/DoC generation) run inside
     AIOverlay.run(), launched from their command bar / button (AI-IDENTITY.md)
   - plain uploads: drag & drop onto .upload areas (no AI styling — not AI work)
   - confirm prompts, clickable table rows */

(function () {
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
})();
