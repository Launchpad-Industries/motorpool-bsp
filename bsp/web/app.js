// Motor Pool — BSP Card Generator. GPL v3 or later.
"use strict";
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem("mp." + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("mp." + k, JSON.stringify(v)); } catch {} },
};
const api = async (url, body) => {
  const r = await fetch(url, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).error || m; } catch {} throw new Error(m); }
  return r;
};
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, 3500); }

let INFO = {}, ROWS = [], STRIKES = [], BYID = {};
let tab = store.get("tab", "assets");        // results section: "assets" or "strikes"
let force = store.get("force", []);          // [{id, grade, qty, view}]
let proposals = store.get("proposals", []);  // [{id, name, values, note}]
let cur = null;                              // detail state

const rangeTxt = r => Array.isArray(r) ? r.join("/") : (r || "-");
const srcBadge = r => `<span class="src ${r.source}${r.source === "Approved" && !r.verified ? " unv" : ""}" title="${r.source === "Approved" ? "Approved by " + esc(r.approver) + (r.verified ? " (verified)" : " (unverified)") : r.source}">${r.source === "Calculated" ? "Calc" : r.source === "Approved" ? "Appr" : "Off"}</span>`;

async function init() {
  INFO = await (await api("/api/info")).json();
  const ab = INFO.about || {};
  $("#ver").textContent = `v${ab.version}` + (ab.data_date ? ` · data ${ab.data_date}` : " · dev");
  $("#ver").title = ab.megamek_data_commit ? `MegaMek data ${ab.megamek_data_commit.slice(0, 7)}, source ${ab.megamek_source_commit.slice(0, 7)}` : "";
  $("#force-title").value = store.get("title", $("#force-title").value);
  $("#opt-summary").checked = store.get("summary", true);
  await loadRows();
  force = force.filter(f => BYID[f.id]);
  renderTable(); renderForce(); renderProposals();
  if (!INFO.official) toast(INFO.official_status + " Everything shows as approved or calculated.");
}

async function loadRows() {
  ROWS = await (await api("/api/units")).json();
  STRIKES = await (await api("/api/strikes")).json();
  BYID = Object.fromEntries([...ROWS, ...STRIKES].map(r => [r.id, r]));
}

// ---------------------------------------------------------------- search
const searchWords = () => $("#q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
function filteredStrikes() {
  const q = searchWords();
  return STRIKES.filter(r => {
    const hay = `${r.name} ${r.category} ${r.support} ${r.type || ""} ${r.effect}`.toLowerCase();
    return q.every(w => hay.includes(w));
  });
}
function filtered() {
  const q = searchWords();
  const mode = $("#f-mode").value, typ = $("#f-type").value, src = $("#f-source").value, tech = $("#f-tech").value, sort = $("#f-sort").value;
  let rs = ROWS.filter(r => {
    if (mode && r.mode !== mode) return false;
    if (typ && (typ === "veh" ? r.generic : r.type !== typ)) return false;
    if (src && r.source !== src) return false;
    if (tech && r.tech !== tech) return false;
    if (!q.length) return true;
    const hay = (r.name + " " + r.specials.join(" ") + " " + r.type + " " + r.tech).toLowerCase();
    return q.every(w => hay.includes(w));
  });
  const key = {name: r => r.name.toLowerCase(), cost: r => r.cost, tons: r => r.tons ?? 0, year: r => r.year || 9999}[sort];
  rs.sort((a, b) => key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0);
  return rs;
}
const perTxt = r => r.per ? `<small>/${esc(r.per.replace("per ", ""))}</small>` : "";
function renderStrikes(rs) {
  let group = null;
  $("#tbl-strikes tbody").innerHTML = rs.map(r => {
    const head = r.category !== group ? `<tr class="grp"><td colspan="7">${esc(r.category)}</td></tr>` : "";
    group = r.category;
    return `${head}<tr data-id="${r.id}" class="${cur && cur.id === r.id ? "sel" : ""}">
    <td><button class="add" data-add="${r.id}" title="Add to force">+</button></td>
    <td class="nm">${esc(r.name)}</td><td class="n">${r.cost}${perTxt(r)}</td>
    <td class="n">${r.tn ? esc(r.tn) + "+" : "—"}</td><td>${r.groups && r.groups !== "none" ? esc(r.groups) : "—"}</td>
    <td>${esc(r.type || "—")}</td><td class="fx">${esc(r.effect)}</td></tr>`;
  }).join("");
}
function renderTable() {
  const rs = filtered(), shown = rs.slice(0, 400), ss = filteredStrikes(), strikes = tab === "strikes";
  $("#n-assets").textContent = rs.length; $("#n-strikes").textContent = ss.length;
  [...$("#r-tabs").children].forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  $("#tbl").hidden = strikes; $("#tbl-strikes").hidden = !strikes;
  $(".filters").hidden = strikes;           // movement, source, tech, sort: units only
  if (strikes) {
    $("#count").textContent = `${ss.length} strikes`;
    return renderStrikes(ss);
  }
  $("#count").textContent = `${rs.length} assets` + (rs.length > shown.length ? ` (showing first ${shown.length}; refine the search)` : "");
  $("#tbl tbody").innerHTML = shown.map(r => `<tr data-id="${r.id}" class="${cur && cur.id === r.id ? "sel" : ""}">
    <td><button class="add" data-add="${r.id}" title="Add to force">+</button></td>
    <td class="nm">${esc(r.chassis)}<small>${esc(r.variant === "Standard" ? "" : r.variant)}</small>${r.differs.length ? `<span class="flag" title="Calculated differs: ${esc(r.differs.join(", "))}">≠</span>` : ""}${r.drift.length ? `<span class="flag" title="Rules changed since approval: ${esc(r.drift.join(", "))}">drift</span>` : ""}</td>
    <td>${srcBadge(r)}</td><td class="n">${r.cost}${r.vet_cost != null ? ` <small>(${r.vet_cost})</small>` : ""}</td><td class="n">${r.tons ?? "—"}</td>
    <td>${r.mp}${r.mode === "na" ? "" : r.mode}</td><td class="n">+${r.tmm}</td><td>${esc(rangeTxt(r.range))}</td><td>${esc(r.damage)}</td><td class="n">${r.check}</td>
    <td class="sp">${esc(r.specials.join(", "))}</td></tr>`).join("");
}
["#q", "#f-mode", "#f-type", "#f-source", "#f-tech", "#f-sort"].forEach(s => $(s).addEventListener("input", renderTable));
$("#r-tabs").addEventListener("click", e => {
  const b = e.target.closest("[data-tab]"); if (!b) return;
  tab = b.dataset.tab; store.set("tab", tab); renderTable();
});
for (const body of ["#tbl tbody", "#tbl-strikes tbody"]) $(body).addEventListener("click", e => {
  const add = e.target.closest("[data-add]");
  if (add) { addToForce(add.dataset.add); e.stopPropagation(); return; }
  const tr = e.target.closest("tr"); if (tr && tr.dataset.id) openDetail(tr.dataset.id);
});

// ---------------------------------------------------------------- force
function addToForce(id, grade = "reg", view = "official") {
  const ex = force.find(f => f.id === id && f.grade === grade && f.view === view);
  if (ex) ex.qty++; else force.push({id, grade, qty: 1, view});
  saveForce(); toast(`Added ${BYID[id].name}`);
}
function cardCost(f) {
  const r = BYID[f.id]; if (!r) return 0;
  // Use the costs of the card that will print.
  const c = (f.view === "calculated" && r.calc) ? r.calc : r;
  return (f.grade === "vet" && c.vet_cost != null) ? c.vet_cost : c.cost;
}
function renderForce() {
  $("#force-empty").hidden = force.length > 0;
  const entry = (f, i) => {
    const r = BYID[f.id];
    const vetOk = r.vet_cost != null;
    if (r.strike) return `<div class="fitem${cur && cur.id === f.id ? " sel" : ""}" data-i="${i}">
      <div class="nm" data-open="${f.id}">${esc(r.name)}</div><button class="rm" data-rm="${i}" title="Remove">×</button>
      <div class="meta">${esc(r.category)}${r.per ? " · " + esc(r.per) : ""}
        <span class="qty"><button data-q="-1">−</button>${f.qty}<button data-q="1">+</button></span>
        <span class="cost">${cardCost(f) * f.qty} BSP</span></div></div>`;
    return `<div class="fitem${cur && cur.id === f.id ? " sel" : ""}" data-i="${i}">
      <div class="nm" data-open="${f.id}">${esc(r.name)}</div><button class="rm" data-rm="${i}" title="Remove">×</button>
      <div class="meta">${srcBadge(r)}
        <span class="pill"><button data-g="reg" class="${f.grade !== "vet" ? "on" : ""}">Reg</button><button data-g="vet" class="${f.grade === "vet" ? "on" : ""}" ${vetOk ? "" : "disabled title='No Veteran version'"}>Vet</button></span>
        ${r.has_official && !r.generic ? `<span class="pill"><button data-v="official" class="${f.view !== "calculated" ? "on" : ""}">Official</button><button data-v="calculated" class="${f.view === "calculated" ? "on" : ""}">Calc</button></span>` : ""}
        <span class="qty"><button data-q="-1">−</button>${f.qty}<button data-q="1">+</button></span>
        <span class="cost">${cardCost(f) * f.qty} BSP</span></div></div>`;
  };
  // Units first, then strikes in their own section (i stays the place in force).
  const items = force.map((f, i) => [f, i]);
  const strikes = items.filter(([f]) => BYID[f.id].strike);
  const strikeBsp = strikes.reduce((s, [f]) => s + cardCost(f) * f.qty, 0);
  $("#force-list").innerHTML = items.filter(([f]) => !BYID[f.id].strike).map(([f, i]) => entry(f, i)).join("")
    + (strikes.length ? `<div class="fsec"><span>Strikes</span><span>${strikeBsp} BSP</span></div>` : "")
    + strikes.map(([f, i]) => entry(f, i)).join("");
  const bsp = force.reduce((s, f) => s + cardCost(f) * f.qty, 0);
  $("#tot-bsp").textContent = bsp; $("#tot-bv").textContent = (bsp * (INFO.bv_per_point || 20)).toLocaleString();
  $("#tot-n").textContent = force.reduce((s, f) => s + f.qty, 0);
}
async function saveForce() {
  // Calculated-view costs for official units need the calculated card's numbers.
  for (const f of force) {
    const r = BYID[f.id];
    if (f.view === "calculated" && r.has_official && !r.calc) {
      const u = await (await api("/api/unit/" + f.id)).json();
      r.calc = u.calculated;
    }
  }
  store.set("force", force); renderForce();
}
$("#force-list").addEventListener("click", e => {
  const it = e.target.closest(".fitem"); if (!it) return;
  const f = force[+it.dataset.i];
  const t = e.target;
  if (t.dataset.rm !== undefined) force.splice(+t.dataset.rm, 1);
  else if (t.dataset.g) { if (!t.disabled) f.grade = t.dataset.g; }
  else if (t.dataset.v) f.view = t.dataset.v;
  else if (t.dataset.q) { f.qty = Math.max(1, f.qty + +t.dataset.q); }
  else if (!t.closest("button")) {
    // Anywhere else on the entry: preview this card as it will print.
    openDetail(f.id, {grade: f.grade, view: f.view}); return;
  }
  saveForce();
  // Keep an open preview in step with the entry's grade / view.
  if (cur && cur.id === f.id && force.includes(f)) openDetail(f.id, {grade: f.grade, view: f.view});
});
$("#force-title").addEventListener("input", e => store.set("title", e.target.value));
$("#opt-summary").addEventListener("change", e => store.set("summary", e.target.checked));
$("#btn-clear").addEventListener("click", () => { if (confirmLight("Clear the force list?")) { force = []; saveForce(); } });
function confirmLight(msg) { return window.confirm(msg); }
const forceBody = () => ({items: force, summary: $("#opt-summary").checked, title: $("#force-title").value});
$("#btn-pdf").addEventListener("click", async () => {
  if (!force.length) return toast("Add some assets first.");
  const b = $("#btn-pdf"); b.disabled = true; b.textContent = "Making PDF…";
  try {
    const r = await api("/api/pdf", forceBody());
    const blob = await r.blob(), a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = ($("#force-title").value || "motor-pool").replace(/\s+/g, "-").toLowerCase() + ".pdf";
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  } catch (err) { toast(err.message); }
  b.disabled = false; b.textContent = "Make PDF";
});
$("#btn-print").addEventListener("click", async () => {
  if (!force.length) return toast("Add some assets first.");
  const html = await (await api("/api/print-html", forceBody())).text();
  const w = window.open("", "_blank"); w.document.write(html); w.document.close();
});

// ---------------------------------------------------------------- detail
async function openDetail(id, opts = {}) {
  const u = await (await api("/api/unit/" + id)).json();
  const r = BYID[id];
  // opts.view is a force-list view ("official" / "calculated"): map it to a
  // preview tab showing the card that will print.
  let view = r.has_official ? "official" : (r.source === "Approved" ? "approved" : "generated");
  if (opts.view === "calculated") view = u.approval ? "approved" : "generated";
  cur = {id, u, r, view, grade: opts.grade || "reg"};
  $("#detail").hidden = false; $("#editor").hidden = true;
  $("#d-name").textContent = u.name;
  $("#d-views").hidden = $("#d-grade").hidden = !!u.strike;   // strikes: one version, no Veteran
  $("#d-sub").textContent = u.strike ? `${r.support} · ${r.cost} BSP${r.per ? " " + r.per : ""}`
    : u.generic ? `${r.type} · generic official card`
    : `${r.type} · ${u.tons} t · ${r.tech}${r.year ? " · " + r.year : ""}`;
  const views = [];
  if (u.official) views.push(["official", "Official"]);
  if (u.approval) views.push(["approved", "Approved"]);
  // Generic cards (infantry, battle armor, emplacements) are official only.
  if (!u.generic) views.push(["generated", "Calculated"]);
  if (u.official && !u.generic) views.push(["diff", "Differences"]);
  $("#d-views").innerHTML = views.map(([k, l]) => `<button data-view="${k}" class="${k === cur.view ? "on" : ""}">${l}</button>`).join("");
  renderTable(); renderForce(); showView();
}
function showView() {
  const {u, view} = cur;
  [...$("#d-views").children].forEach(b => b.classList.toggle("on", b.dataset.view === cur.view));
  [...$("#d-grade").children].forEach(b => b.classList.toggle("on", b.dataset.g === cur.grade));
  const frame = $("#d-card");
  frame.hidden = view === "diff";
  if (view !== "diff") {
    const apiView = view === "official" ? "official" : view === "approved" ? "calculated" : "generated";
    frame.src = `/api/card/${cur.id}?view=${apiView}&grade=${cur.grade}`;
  }
  $("#d-diff").innerHTML = u.strike ? (u.notes ? `<p class="muted">${esc(u.notes)}</p>` : "") : view === "diff" ? diffTable(u.official, u.calculated) : (u.drift.length && view === "approved" ? `<p class="flag">The rules have changed since this was approved (${esc(u.drift.join(", "))}). The approved values still print; re-approve to update.</p>` : "");
  const a = u.approval;
  $("#d-approval").innerHTML = a ? `Approved by <b>${esc(a.by)}</b> on ${esc(a.on)} — ${a.verified ? "verified signature" : "<span class=flag>unverified</span>"}${a.changes ? " · tweaked: " + esc(Object.keys(a.changes).join(", ")) : ""}${a.cost_override ? " · cost overridden" : ""}${a.note ? " · " + esc(a.note) : ""}` : "";
  const canApprove = view === "generated" || view === "approved";
  $("#d-approve").hidden = !canApprove; $("#d-tweak").hidden = !canApprove;
  $("#d-approve").textContent = a && view === "approved" ? "Re-approve" : "Approve as shown";
}
function diffTable(off, calc) {
  const keys = ["mp", "mode", "tmm", "range", "skill", "damage", "check", "threshold", "cost", "vet_cost", "specials"];
  const f = v => Array.isArray(v) ? (v.every(x => typeof x === "number") ? v.join("/") : v.join(", ")) : (v ?? "-");
  return `<table><thead><tr><th></th><th>Official</th><th>Calculated</th></tr></thead><tbody>${keys.map(k => {
    const a = f(off[k]), b = f(calc[k]);
    return `<tr><th>${k.replace("_", " ")}</th><td>${esc(a)}</td><td class="${a == b ? "" : "chg"}">${esc(b)}</td></tr>`;
  }).join("")}</tbody></table><p class="muted">Official values always print unless you choose “Calc” in the force list.</p>`;
}
$("#d-views").addEventListener("click", e => { if (e.target.dataset.view) { cur.view = e.target.dataset.view; showView(); } });
$("#d-grade").addEventListener("click", e => { if (e.target.dataset.g) { cur.grade = e.target.dataset.g; if ($("#editor").hidden) showView(); else livePreview(); } });
$("#d-close").addEventListener("click", () => { $("#detail").hidden = true; cur = null; renderTable(); renderForce(); });
$("#d-add").addEventListener("click", () => addToForce(cur.id, cur.grade, cur.view === "generated" && cur.r.has_official ? "calculated" : "official"));
$("#d-approve").addEventListener("click", () => approve(cur.view === "approved" ? cur.u.calculated : cur.u.generated, false, ""));
$("#d-tweak").addEventListener("click", () => openEditor(cur.view === "approved" ? cur.u.calculated : cur.u.generated));

// ---------------------------------------------------------------- tweak editor
const E = id => $("#e-" + id);
function openEditor(v) {
  $("#editor").hidden = false;
  E("mp").value = v.mp; E("mode").value = v.mode; E("tmm").value = v.tmm; E("skill").value = v.skill;
  const rg = Array.isArray(v.range) ? v.range : ["", "", ""];
  E("s").value = rg[0]; E("m").value = rg[1]; E("l").value = rg[2];
  E("dmg").value = v.damage; E("check").value = v.check; E("thr").value = v.threshold;
  E("spec").value = (v.specials || []).join(", "); E("note").value = "";
  E("override").checked = false; E("cost").value = v.cost; E("vcost").value = v.vet_cost ?? "";
  cur.base = v; cur.editRange = Array.isArray(v.range) ? null : v.range;
  livePreview(); $("#editor").scrollIntoView({behavior: "smooth", block: "nearest"});
}
function editedValues() {
  const n = id => parseInt(E(id).value, 10);
  const range = cur.editRange && !E("s").value ? cur.editRange : [n("s"), n("m"), n("l")];
  const skill = n("skill");
  return {mp: n("mp"), mode: E("mode").value, tmm: n("tmm"), range, skill,
          vet_skill: cur.base.vet_skill == null ? null : skill - 1,
          damage: E("dmg").value.trim().replace(/x/i, "d×").replace("dd×", "d×"),
          check: n("check"), threshold: n("thr"),
          specials: E("spec").value.split(",").map(s => s.trim()).filter(Boolean),
          cost: n("cost"), vet_cost: E("vcost").value === "" ? null : n("vcost")};
}
let lpTimer;
function livePreview() {
  clearTimeout(lpTimer);
  lpTimer = setTimeout(async () => {
    const v = editedValues();
    try {
      const c = await (await api("/api/recost", {values: v})).json();
      $("#e-formula").textContent = `${c.cost}${c.vet_cost != null ? " (" + c.vet_cost + ")" : ""}  ·  ${c.unrounded}`;
      if (!E("override").checked) { E("cost").value = c.cost; E("vcost").value = c.vet_cost ?? ""; v.cost = c.cost; v.vet_cost = c.vet_cost; }
    } catch (err) { $("#e-formula").textContent = "–"; }
    $("#d-card").hidden = false;
    $("#d-card").srcdoc = await (await api("/api/preview", {id: cur.id, values: v, grade: cur.grade})).text();
  }, 200);
}
$("#editor").addEventListener("input", e => { if (e.target.id === "e-override") { E("cost").disabled = E("vcost").disabled = !E("override").checked; } livePreview(); });
$("#e-reset").addEventListener("click", () => openEditor(cur.u.generated));
$("#e-approve").addEventListener("click", () => approve(editedValues(), E("override").checked, E("note").value));
$("#e-propose").addEventListener("click", () => {
  proposals = proposals.filter(p => p.id !== cur.id);
  proposals.push({id: cur.id, name: cur.u.name, values: editedValues(), note: E("note").value});
  store.set("proposals", proposals); renderProposals(); toast("Added to tweaks to send.");
});

async function approve(values, override, note) {
  if (!INFO.name) { toast("Set your name in Settings first."); return openSettings(); }
  const signed = INFO.owner && INFO.owner === INFO.name;
  if (!confirmLight(`Approve ${cur.u.name} as ${INFO.name}${signed ? " (signed, verified)" : " (unverified: this computer has no trusted signing key)"}?`)) return;
  try {
    const {entry} = await (await api("/api/approve", {id: cur.id, values, cost_override: override, note})).json();
    toast(`Approved by ${entry.by}${entry.verified ? " (verified)" : " (unverified)"}.`);
    await refreshRows(); openDetail(cur.id);
  } catch (err) { toast(err.message); }
}
async function refreshRows() {
  await loadRows(); renderTable(); renderForce();
}

// ---------------------------------------------------------------- proposals
function renderProposals() {
  $("#proposals").hidden = !proposals.length;
  $("#prop-n").textContent = `(${proposals.length})`;
  $("#prop-list").innerHTML = proposals.map((p, i) => `<div class="pi"><span>${esc(p.name)}</span><button class="rm ghost" data-prm="${i}">×</button></div>`).join("");
}
$("#prop-list").addEventListener("click", e => { if (e.target.dataset.prm) { proposals.splice(+e.target.dataset.prm, 1); store.set("proposals", proposals); renderProposals(); } });
$("#btn-send").addEventListener("click", async () => {
  if (!INFO.name) { toast("Set your name in Settings first."); return openSettings(); }
  const out = await (await api("/api/proposals/export", {items: proposals, from: INFO.name})).json();
  $("#send-body").value = out.body;
  $("#send-msg").textContent = out.mailto
    ? `Opens your email program with this message to ${INFO.settings.approval_email}. Just press Send.`
    : `This batch is too long for an email link. Copy the text (or save it as a file) and email it to ${INFO.settings.approval_email}.`;
  const a = $("#send-mail"); a.hidden = !out.mailto; a.href = out.mailto || "#";
  $("#send-file").onclick = () => { const b = new Blob([out.body], {type: "text/plain"}), l = document.createElement("a"); l.href = URL.createObjectURL(b); l.download = "motor-pool-tweaks.txt"; l.click(); };
  $("#dlg-send").showModal();
});
$("#send-copy").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("#send-body").value); toast("Copied."); } catch { $("#send-body").select(); } });
$("#send-close").addEventListener("click", () => $("#dlg-send").close());
$("#send-mail").addEventListener("click", () => setTimeout(() => {
  if (confirmLight("Did the email go out? Clear the tweaks list?")) { proposals = []; store.set("proposals", proposals); renderProposals(); $("#dlg-send").close(); }
}, 800));

// import
$("#btn-import").addEventListener("click", () => { $("#imp-list").innerHTML = ""; $("#dlg-import").showModal(); });
$("#imp-close").addEventListener("click", () => $("#dlg-import").close());
$("#imp-read").addEventListener("click", async () => {
  try {
    const d = await (await api("/api/proposals/import", {code: $("#imp-code").value})).json();
    $("#imp-list").innerHTML = `<p class="muted">From <b>${esc(d.from)}</b> on ${esc(d.on)}: ${d.items.length} proposal(s).</p>` + d.items.map((it, i) => it.error
      ? `<div class="imp">${esc(it.unit)}: ${esc(it.error)}</div>`
      : `<div class="imp"><b>${esc(it.unit)}</b>${it.note ? " — " + esc(it.note) : ""}<br>${it.changed.length ? it.changed.map(k => `${k}: ${esc(fmtV(it.generated[k]))} → <b>${esc(fmtV(it.values[k]))}</b>`).join("; ") : "approve as generated"}
         <div class="dactions"><button class="primary" data-iapp="${i}">Review &amp; approve…</button></div></div>`).join("");
    $("#imp-list").onclick = e => {
      const i = e.target.dataset.iapp; if (i === undefined) return;
      const it = d.items[+i]; $("#dlg-import").close();
      openDetail(it.id).then(() => { openEditor(it.values); E("note").value = `Proposed by ${d.from}` + (it.note ? `: ${it.note}` : ""); E("override").checked = true; E("cost").disabled = E("vcost").disabled = false; E("cost").value = it.values.cost; E("vcost").value = it.values.vet_cost ?? ""; livePreview(); });
    };
  } catch (err) { toast(err.message); }
});
const fmtV = v => Array.isArray(v) ? (v.every(x => typeof x === "number") ? v.join("/") : v.join(", ")) : (v ?? "-");

// ---------------------------------------------------------------- settings
async function openSettings() {
  const s = await (await api("/api/settings")).json(), f = $("#dlg-settings form");
  for (const [k, v] of Object.entries(s)) if (f.elements[k]) f.elements[k].value = v;
  for (const el of f.querySelectorAll(".dev-only")) el.hidden = !!(INFO.about && INFO.about.dist);
  $("#owner-note").textContent = INFO.official_status + " — " + (INFO.owner
    ? `This computer holds the signing key for “${INFO.owner}”: approvals made here as ${INFO.owner} are signed and verified.`
    : "This computer has no trusted signing key, so approvals made here are saved under your name as unverified.");
  $("#dlg-settings").showModal();
}
$("#btn-settings").addEventListener("click", openSettings);
// Theme is a per-browser choice, applied at once (index.html sets it before first paint).
$("#theme").value = document.documentElement.dataset.theme;
$("#theme").addEventListener("change", e => { document.documentElement.dataset.theme = e.target.value; store.set("theme", e.target.value); });
$("#dlg-settings").addEventListener("close", async () => {
  if ($("#dlg-settings").returnValue !== "save") return;
  const f = $("#dlg-settings form"), body = {};
  for (const k of ["name", "approval_email", "mm_data", "official_tsv", "fluff_dir"]) body[k] = f.elements[k].value.trim();
  try { await api("/api/settings", body); INFO = await (await api("/api/info")).json(); await refreshRows(); toast("Settings saved. " + INFO.official_status); }
  catch (err) { toast(err.message); }
});

init().catch(err => toast("Could not start: " + err.message));
