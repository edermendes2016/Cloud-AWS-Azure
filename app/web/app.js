/* Lab UI: plain JavaScript, no build step, no external requests. Data comes from /api. */
"use strict";

const TABS = ["pipeline", "map", "lab", "compare", "cards", "finops", "docs"];
const view = document.getElementById("view");
const state = { lang: localStorage.getItem("lang") || "en", tab: "pipeline", texts: {}, job: null, stage: null, results: {} };

// ---------- helpers ----------
const api = async (path, method = "GET", body) => {
  const res = await fetch("/api" + path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
};
const t = (key, vars = {}) => {
  const text = key.split(".").reduce((node, part) => (node || {})[part], state.texts);
  return typeof text === "string" ? text.replace(/\{(\w+)\}/g, (_, name) => vars[name]) : text ?? key;
};
const esc = (value) => String(value ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pill = (status, label) => `<span class="pill ${esc(status)}">${esc(label)}</span>`;
const scenarioText = (id) => state.texts.scenarios[id];
const scrollLogs = () => view.querySelectorAll("pre[aria-label=log]").forEach((el) => { el.scrollTop = el.scrollHeight; });

// ---------- shell ----------
async function setLang(lang) {
  state.lang = lang;
  localStorage.setItem("lang", lang);
  state.texts = await (await fetch(`i18n/${lang}.json`)).json();
  document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.lang === lang));
  document.getElementById("tabs").innerHTML = TABS.map((id) =>
    `<button type="button" role="tab" data-tab="${id}" aria-selected="${id === state.tab}">${esc(t("ui.tabs." + id))}</button>`).join("");
  render();
}

async function refreshStatus() {
  const el = document.getElementById("status");
  try {
    const s = await api("/status");
    const key = !s.ready ? "setup" : s.busy ? "busy" : "ready";
    el.className = "pill " + (key === "ready" ? "ok" : "warn");
    el.textContent = t("ui.status." + key) + (s.applied != null ? " · " + t("ui.applied", { n: s.applied }) : "");
    state.status = s;
  } catch {
    el.className = "pill bad";
    el.textContent = t("ui.status.offline");
  }
}

function render() {
  ({ pipeline: renderPipeline, map: renderMap, lab: renderLab, compare: renderCompare, cards: renderCards, finops: renderFinops, docs: renderDocs })[state.tab]()
    .catch((err) => { view.innerHTML = `<div class="panel bad">${esc(err.message)}</div>`; });
}

// ---------- jobs ----------
async function startJob(path, body, onDone) {
  try {
    state.job = await api(path, "POST", body);
    state.stage = null;
  } catch (err) {
    alertBox(err.message);
    return;
  }
  pollJob(onDone);
}

async function pollJob(onDone) {
  const job = state.job = await api("/jobs/" + state.job.id);
  if (job.scenario) state.results[job.scenario + ":" + job.kind] = job;
  if (state.tab === "pipeline" || job.scenario) render();
  if (job.status === "running" || job.status === "waiting") {
    setTimeout(() => pollJob(onDone), 1000);
  } else {
    refreshStatus();
    if (onDone) onDone(job);
  }
}

function alertBox(message) {
  view.insertAdjacentHTML("afterbegin", `<div class="panel bad" role="alert">${esc(message)}</div>`);
}

function stagesHtml(job) {
  const current = state.stage || (job.stages.find((s) => ["running", "failed", "waiting"].includes(s.status)) || job.stages.filter((s) => s.status === "passed").pop() || job.stages[0]).name;
  const chips = job.stages.map((s) =>
    `<button type="button" class="stage ${esc(s.status)}" data-stage="${esc(s.name)}" aria-pressed="${s.name === current}">
       <strong>${esc(s.name)}</strong><small>${esc(t("ui.stage_status." + s.status))}${s.seconds != null ? ` · ${s.seconds} ${t("ui.seconds")}` : ""}</small></button>`).join("");
  const log = job.stages.find((s) => s.name === current)?.log || "";
  return `<div class="stages">${chips}</div><pre tabindex="0" aria-label="log">${esc(log) || "…"}</pre>`;
}

// ---------- tab: pipeline ----------
async function renderPipeline() {
  const busy = state.job && ["running", "waiting"].includes(state.job.status);
  const job = state.job && !state.job.scenario ? state.job : null;
  view.innerHTML = `
    <div class="panel"><p>${esc(t("ui.pipeline_intro"))}</p>
      <div class="row">
        <button class="btn" data-run="pipeline" ${busy ? "disabled" : ""}>${esc(t("ui.run_pipeline"))}</button>
        <button class="btn secondary" data-run="gates" ${busy ? "disabled" : ""}>${esc(t("ui.run_gates"))}</button>
        <button class="btn danger" data-run="destroy" ${busy ? "disabled" : ""}>${esc(t("ui.run_destroy"))}</button>
      </div></div>
    <div class="panel">${job ? `
      <div class="row"><h2>${esc(t("ui.job"))} ${esc(job.id)}</h2>${pill(job.status, t("ui.job_status." + job.status))}
        ${job.seconds != null ? `<span class="muted">${t("ui.total")}: ${job.seconds} ${t("ui.seconds")}</span>` : ""}</div>
      ${stagesHtml(job)}
      ${job.status === "waiting" ? `<div class="note" role="alert"><strong>${esc(t("ui.approval_title"))}</strong><p>${esc(t("ui.approval_text"))}</p>
        <div class="row"><button class="btn" data-approve="true">${esc(t("ui.approve"))}</button><button class="btn danger" data-approve="false">${esc(t("ui.reject"))}</button></div></div>` : ""}`
      : `<p class="muted">${esc(t("ui.no_job"))}</p>`}</div>`;
  scrollLogs();
}

// ---------- tab: network map ----------
async function renderMap() {
  const [net, fin] = await Promise.all([api("/network"), api("/finops")]);
  const hot = (key) => (net.highlights.includes(key) ? " alert" : "");
  const badge = (key) => (net.highlights.includes(key) ? " " + pill("bad", t("ui.fault_active")) : "");
  const extras = `
    <div class="grid" style="margin-top:16px">
      <div class="node${hot("state")}"><h3>${esc(t("ui.state_backend"))}${badge("state")}</h3>${esc(t("ui.state_backend_text"))}</div>
      <div class="node${hot("repo")}"><h3>${esc(t("ui.repository"))}${badge("repo")}</h3>${esc(t("ui.repository_text"))}</div>
      <div class="node${hot("orphan") || (fin.orphans.length ? " alert" : "")}"><h3>${esc(t("ui.outside_tf"))}${badge("orphan")}</h3>
        ${esc(t("ui.orphans_n", { n: fin.orphans.length }))}${fin.orphans.map((o) => `<br><code>${esc(o.type)} ${esc(o.id)}</code>`).join("")}</div>
    </div>`;
  if (!net.applied) {
    view.innerHTML = `<div class="panel"><p class="muted">${esc(t("ui.not_applied"))}</p>${extras}</div>`;
    return;
  }
  const azs = [...new Set(net.subnets.map((s) => s.az))];
  const rows = ["public", "app", "data"].map((tier) => {
    const tables = net.route_tables.filter((r) => r.tier === tier);
    const route = [...new Set(tables.map((r) => r.default_route || t("ui.none")))].join(", ");
    const rt = tier === "app" ? hot("rt-app") : "";
    return `<div class="cell tier-${tier}${rt}"><strong>${tier}</strong><br><small>${esc(t("ui.default_route"))}: ${esc(route)}</small></div>` +
      azs.map((az) => {
        const s = net.subnets.find((x) => x.az === az && x.tier === tier);
        return `<div class="cell tier-${tier}"><strong>${esc(s.name)}</strong><br><code>${esc(s.cidr)}</code></div>`;
      }).join("");
  }).join("");
  const inCode = new Set(net.db_rules.code.map((r) => r.cidr + ":" + r.port));
  const rule = (r, live) => `<li><code>${esc(r.cidr)} → ${esc(r.port)}</code>${live && !inCode.has(r.cidr + ":" + r.port) ? " " + pill("bad", t("ui.not_in_code")) : ""}</li>`;
  const drift = net.db_rules.live.some((r) => !inCode.has(r.cidr + ":" + r.port));
  view.innerHTML = `
    <div class="panel"><p class="muted">${esc(t("ui.map_intro"))}</p>
      <h2>VPC ${esc(net.vpc.name)} <code>${esc(net.vpc.cidr)}</code></h2>
      <div class="map" style="--azs:${azs.length}">
        <div class="cell head">${esc(t("ui.tier"))}</div>${azs.map((az) => `<div class="cell head">${esc(az)}</div>`).join("")}
        ${rows}
      </div>
      <div class="grid" style="margin-top:16px">
        <div class="node"><h3>${esc(t("ui.edge"))}</h3>${esc(t("ui.igw"))}: 1<br>${esc(t("ui.nat"))}: ${net.nat_gateways}</div>
        <div class="node${hot("rds")}"><h3>${esc(t("ui.database"))}${badge("rds")}</h3>
          <code>${esc(net.db.id)}</code> ${esc(net.db.class)} · ${net.db.multi_az ? "Multi-AZ" : "Single-AZ"} ·
          ${esc(t(net.db.public ? "ui.public" : "ui.private"))}${net.db.encrypted ? " · " + esc(t("ui.encrypted")) : ""}
          <br>${esc(t("ui.alarms"))}: ${net.alarms.length}</div>
        <div class="node${hot("sg-db") || (drift ? " alert" : "")}"><h3>Security group${badge("sg-db")}</h3>
          ${esc(t("ui.db_rules_code"))}<ul>${net.db_rules.code.map((r) => rule(r, false)).join("")}</ul>
          ${esc(t("ui.db_rules_live"))}<ul>${net.db_rules.live.map((r) => rule(r, true)).join("")}</ul></div>
      </div>${extras}</div>`;
}

// ---------- tab: failure lab ----------
async function renderLab() {
  const [scenarios, status] = await Promise.all([api("/scenarios"), api("/status")]);
  const busy = status.busy;
  const applied = status.applied > 0;
  view.innerHTML = `<div class="panel"><p>${esc(t("ui.lab_intro"))}</p></div><div class="grid">` + scenarios.map((s) => {
    const text = scenarioText(s.id);
    const live = state.job?.scenario === s.id ? state.job : null;
    const inject = state.results[s.id + ":inject"], fix = state.results[s.id + ":fix"];
    const blocked = s.kind !== "repo" && !applied;
    const summary = [
      inject && inject.status !== "running" ? pill(inject.status, inject.status === "detected" ? t("ui.detected_by", { control: inject.control, s: inject.seconds }) : t("ui.job_status." + inject.status)) : "",
      fix && fix.status === "passed" && !s.injected ? pill("passed", t("ui.fixed_in", { s: fix.seconds })) : "",
    ].join(" ");
    return `<section class="panel${s.injected ? " alert" : ""}">
      <div class="row"><h2>${esc(text.title)}</h2>${pill("", t("ui.kind." + s.kind))}</div>
      <p>${esc(text.story)}</p>
      <p class="muted">${esc(t("ui.control"))}: <code>make ${esc(s.control)}</code>${blocked ? " · " + esc(t("ui.needs_apply")) : ""}</p>
      <div class="row">
        <button class="btn danger" data-inject="${s.id}" ${busy || blocked || s.injected ? "disabled" : ""}>${esc(t("ui.inject"))}</button>
        <button class="btn" data-fix="${s.id}" ${busy || !s.injected ? "disabled" : ""}>${esc(t("ui.fix"))}</button>
      </div>
      <p>${summary}</p>
      ${live ? `<details open><summary>${esc(t("ui.show_log"))}</summary>${stagesHtml(live)}</details>` : ""}
    </section>`;
  }).join("") + "</div>";
  scrollLogs();
}

// ---------- tab: before × after ----------
async function renderCompare() {
  const runs = (await api("/jobs")).filter((j) => j.kind === "pipeline" && j.seconds != null);
  const table = runs.length ? `<div class="scroll"><table><thead><tr><th>${esc(t("ui.run"))}</th><th>${esc(t("ui.result"))}</th>
      ${runs[0].stages.map((s) => `<th class="num">${esc(s.name)}</th>`).join("")}<th class="num">${esc(t("ui.total"))}</th></tr></thead><tbody>
      ${runs.map((j) => `<tr><td><code>${esc(j.id)}</code></td><td>${pill(j.status, t("ui.job_status." + j.status))}</td>
        ${j.stages.map((s) => `<td class="num">${s.seconds ?? "–"}</td>`).join("")}<td class="num"><strong>${j.seconds}</strong></td></tr>`).join("")}
      </tbody></table></div>` : `<p class="muted">${esc(t("ui.compare_empty"))}</p>`;
  view.innerHTML = `
    <div class="panel"><h2>${esc(t("ui.compare_field"))}</h2>
      <table><tbody>
        <tr><th scope="row">${esc(t("ui.compare_manual"))}</th><td>${esc(t("ui.compare_manual_value"))}</td><td style="width:55%"><div class="bartrack"><div class="bar slow" style="width:100%"></div></div></td></tr>
        <tr><th scope="row">${esc(t("ui.compare_pipeline"))}</th><td>${esc(t("ui.compare_pipeline_value"))}</td><td><div class="bartrack"><div class="bar" style="width:5%"></div></div></td></tr>
      </tbody></table>
      <div class="note"><strong>${esc(t("ui.how_measured"))}:</strong> ${esc(t("ui.compare_field_how"))}</div></div>
    <div class="panel"><h2>${esc(t("ui.compare_lab"))} (${esc(t("ui.seconds"))})</h2>${table}
      <div class="note"><strong>${esc(t("ui.how_measured"))}:</strong> ${esc(t("ui.compare_lab_how"))}</div></div>`;
}

// ---------- tab: scenario cards ----------
async function renderCards() {
  const scenarios = await api("/scenarios");
  view.innerHTML = `<div class="panel"><p>${esc(t("ui.cards_intro"))}</p></div><div class="grid">` + scenarios.map((s) => {
    const text = scenarioText(s.id), card = text.card, run = state.results[s.id + ":inject"];
    const after = run?.status === "detected" ? t("ui.card_metric_live", { control: "make " + run.control, s: run.seconds }) : t("ui.card_metric_none");
    return `<section class="panel"><h2>${esc(text.title)}</h2><dl>
      <dt>${esc(t("ui.card.context"))}</dt><dd>${esc(card.context)}</dd>
      <dt>${esc(t("ui.card.automated"))}</dt><dd>${esc(card.automated)}</dd>
      <dt>${esc(t("ui.card.pipeline"))}</dt><dd>${esc(card.pipeline)}</dd>
      <dt>${esc(t("ui.card.metrics"))}</dt><dd>${esc(card.before)}<br>${esc(after)}<br><span class="muted">${esc(t("ui.how_measured"))}: ${esc(t("ui.card_metric_how"))}</span></dd>
      <dt>${esc(t("ui.card.risks"))}</dt><dd>${esc(card.risks)}</dd>
      <dt>${esc(t("ui.card.validated"))}</dt><dd>${esc(card.validated)}</dd></dl></section>`;
  }).join("") + "</div>";
}

// ---------- tab: finops ----------
async function renderFinops() {
  const f = await api("/finops");
  const pct = Math.min(100, (f.cost.total / f.budget) * 100);
  view.innerHTML = `
    <div class="panel"><p>${esc(t("ui.finops_intro"))}</p>
      <h2>${esc(t("ui.budget"))}: ${esc(t("ui.of_budget", { total: f.cost.total.toFixed(2), budget: f.budget.toFixed(2) }))}</h2>
      <div class="bartrack" role="img" aria-label="${pct.toFixed(0)}%"><div class="bar" style="width:${pct}%;${f.cost.total > f.budget ? "background:var(--bad)" : ""}"></div></div>
      ${f.cost.items.length ? `<div class="scroll"><table><thead><tr><th>${esc(t("ui.resource"))}</th><th>${esc(t("ui.detail"))}</th><th class="num">${esc(t("ui.monthly"))}</th></tr></thead><tbody>
        ${f.cost.items.map((i) => `<tr><td><code>${esc(i.address)}</code></td><td>${esc(i.detail)}</td><td class="num">${i.monthly == null ? esc(t("ui.unknown")) : i.monthly.toFixed(2)}</td></tr>`).join("")}
        </tbody></table></div>` : `<p class="muted">${esc(t("ui.not_applied"))}</p>`}
      <p class="muted">${esc(f.cost.note)}</p></div>
    <div class="grid">
      <div class="panel"><h2>${esc(t("ui.tags_title"))}</h2>${f.untagged.length
        ? `<ul>${f.untagged.map((u) => `<li><code>${esc(u.address)}</code>: ${esc(u.message)}</li>`).join("")}</ul>`
        : `<p>${pill("ok", "OK")} ${esc(t("ui.tags_ok", { tags: f.required_tags.join(", ") }))}</p>`}</div>
      <div class="panel"><h2>${esc(t("ui.orphans_title"))}</h2>${f.orphans.length
        ? `<ul>${f.orphans.map((o) => `<li>${pill("bad", o.type)} <code>${esc(o.id)}</code></li>`).join("")}</ul>`
        : `<p>${pill("ok", "OK")} ${esc(t("ui.orphans_ok"))}</p>`}</div>
    </div>`;
}

// ---------- tab: docs ----------
async function renderDocs() {
  const d = state.texts.docs;
  const level = { emulator: "ok", local: "ok", plan: "warn", not_run: "", real: "ok" };
  view.innerHTML = `
    <div class="panel"><h2>${esc(t("ui.docs_quickstart"))}</h2><pre>${d.quickstart.map(esc).join("\n")}</pre></div>
    <div class="panel"><h2>${esc(t("ui.docs_validation"))}</h2><div class="scroll"><table>
      <thead><tr><th>${esc(t("ui.docs_item"))}</th><th>${esc(t("ui.docs_level"))}</th><th>${esc(t("ui.docs_note"))}</th></tr></thead>
      <tbody>${d.validation.map(([item, lvl, note]) => `<tr><td>${esc(item)}</td><td>${pill(level[lvl], t("ui.levels." + lvl))}</td><td>${esc(note)}</td></tr>`).join("")}</tbody></table></div></div>
    <div class="panel"><h2>${esc(t("ui.docs_adrs"))}</h2><div class="scroll"><table>
      <thead><tr><th>${esc(t("ui.decision"))}</th><th>${esc(t("ui.why"))}</th></tr></thead>
      <tbody>${d.adrs.map(([title, why]) => `<tr><th scope="row">${esc(title)}</th><td>${esc(why)}</td></tr>`).join("")}</tbody></table></div></div>
    <div class="panel"><h2>${esc(t("ui.docs_lessons"))}</h2><ul>${d.lessons.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>`;
}

// ---------- events ----------
document.addEventListener("click", (event) => {
  const el = event.target.closest("button");
  if (!el) return;
  const d = el.dataset;
  if (d.lang) setLang(d.lang);
  else if (d.tab) { state.tab = d.tab; document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", b === el)); render(); }
  else if (d.run === "pipeline") startJob("/pipeline", { apply: true });
  else if (d.run === "gates") startJob("/pipeline", { apply: false });
  else if (d.run === "destroy") startJob("/destroy");
  else if (d.approve) api(`/jobs/${state.job.id}/approval`, "POST", { approve: d.approve === "true" });
  else if (d.stage) { state.stage = d.stage; render(); }
  else if (d.inject) startJob(`/scenarios/${d.inject}/inject`, null, render);
  else if (d.fix) startJob(`/scenarios/${d.fix}/fix`, null, render);
});

setLang(state.lang).then(refreshStatus);
setInterval(refreshStatus, 5000);
