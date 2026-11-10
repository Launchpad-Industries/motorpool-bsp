// Motor Pool static viewer. Reads data/units.json (schema: docs/site-data-schema.md).
// No server, no build step. Force list is kept in localStorage when available.
(function () {
  "use strict";

  const STORE_KEY = "motorpool.force.v1";
  const CARDS_PER_PAGE = 8;
  const $ = (id) => document.getElementById(id);

  let data = null;
  let byId = new Map();
  let selectedId = null;
  let force = loadForce(); // [{ id, skill: "regular"|"veteran", qty }]

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function loadForce() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch (e) { return []; }
  }
  function saveForce() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(force)); } catch (e) { /* storage unavailable */ }
  }

  function sourceLabel(u) {
    if (u.provenance === "official") return "Official";
    if (u.provenance === "approved") {
      return u.verified === false ? `Unverified-${u.approvedBy || "?"}` : `Approved-${u.approvedBy || "?"}`;
    }
    return "Calculated";
  }
  function provClass(u) {
    if (u.provenance === "approved" && u.verified === false) return "prov-unverified";
    return `prov-${u.provenance}`;
  }

  function cardHTML(u, skill) {
    const s = u.spec;
    const vet = skill === "veteran";
    const cost = vet ? u.cost.veteran : u.cost.regular;
    const sk = vet ? s.skill.veteran : s.skill.regular;
    const specials = (s.specials || []).slice();
    if (s.indirect && !specials.some((x) => /^IF\d/.test(x))) specials.push(`IF${s.indirect}`);
    const pips = "<i></i>".repeat(Math.max(0, Math.min(12, s.check || 0)));
    const sub = [u.type, u.motive, u.tonnage ? `${u.tonnage}t` : ""].filter(Boolean).join(" · ");
    const art = u.art && u.art.src
      ? `<img class="c-art" src="${esc(u.art.src)}" alt="" loading="lazy">` : "";
    return `
      <div class="card ${vet ? "veteran" : "regular"} ${provClass(u)}">
        <div class="c-head">
          <div>
            <div class="c-name">${esc(u.name)}</div>
            <div class="c-sub">${esc(sub)}</div>
          </div>
          <div class="c-cost">${esc(cost)}<br><span class="c-chip">${vet ? "VETERAN" : "REGULAR"}</span></div>
        </div>
        <div class="c-stats">
          <div><b>Move</b><span>${esc(s.move)}</span></div>
          <div><b>TMM</b><span>${esc(s.tmm)}</span></div>
          <div><b>Skill</b><span>${esc(sk)}</span></div>
          <div><b>Range</b><span>${esc((s.range || []).join("/"))}</span></div>
          <div><b>Damage</b><span>${esc(s.damage)}</span></div>
          <div><b>IF</b><span>${s.indirect ? esc(s.indirect) : "—"}</span></div>
          <div><b>Check</b><span>${esc(s.check)}</span></div>
          <div><b>Thresh.</b><span>${esc(s.threshold)}</span></div>
        </div>
        <div class="c-body">
          <div class="c-specials">
            <b>Specials:</b> ${specials.length ? esc(specials.join(", ")) : "—"}
            <div class="c-pips" title="Destroy Check pips">${pips}</div>
          </div>
          ${art}
        </div>
        <div class="c-foot"><span>Source: ${esc(sourceLabel(u))}</span><span>Unofficial</span></div>
      </div>`;
  }

  // ---------- Strike cards (no Veteran grade; schema "Strike") ----------
  const STRIKE_TYPE = "__strikes";
  const isStrike = (x) => x && x.kind === "strike";
  const costText = (s) => `${s.cost}${s.per ? ` ${s.per}` : ""}`;

  function writeOnHTML(s) {
    if (s.writeOn === "target") {
      return `<div class="s-write"><span>Target hex<i></i></span><span class="short">Turn<i></i></span><span class="used">Used <b class="bx"></b></span></div>`;
    }
    if (s.writeOn === "hex") {
      const n = Math.max(0, Math.min(12, parseInt(s.groups, 10) || 0));
      const track = Array.from({ length: n }, (_, i) => `<span>${n - i}</span>`).join("");
      return `<div class="s-write"><span>Hex<i></i></span><span class="track" title="Groups left">${track}</span></div>`;
    }
    return "";
  }

  function strikeCardHTML(s) {
    const stats = s.tn != null ? `
      <div class="s-stats">
        <div><b>Target No.</b><span>${esc(s.tn)}+</span></div>
        <div><b>Groups ×5</b><span>${esc(s.groups && s.groups !== "none" ? s.groups : "—")}</span></div>
        <div><b>Type</b><span>${esc(s.attackType || "—")}</span></div>
      </div>` : "";
    const cancels = (s.cancels || []).length ? `
      <div class="s-cancels"><b>Cancels on</b>${s.cancels.map((c) =>
        `<span>${esc(c.strike)}</span><span class="tn">${esc(c.tn)}+</span>`).join("")}</div>` : "";
    const diagrams = (s.diagrams || []).map((d) =>
      `<figure><img src="${esc(d.src)}" alt="${esc(d.caption)}"><figcaption>${esc(d.caption)}</figcaption></figure>`).join("");
    const chipClass = s.chip === "NOT AN ATTACK" ? "plain" : s.chip === "MINEFIELD" ? "mine" : "strike";
    return `
      <div class="card strike">
        <div class="c-head">
          <div>
            <div class="c-sub">${esc(s.support || s.category)}</div>
            <div class="c-name">${esc(s.name)}</div>
          </div>
          <div class="c-cost">${esc(s.cost)}${s.per ? `<small> ${esc(s.per)}</small>` : ""}<br><span class="c-chip ${chipClass}">${esc(s.chip)}</span></div>
        </div>
        <div class="s-body">
          <div class="s-main">
            ${stats}${cancels}
            <div class="s-rules"><b>Rules</b> ${esc(s.effect)}${s.rulesRef ? ` <i>(${esc(s.rulesRef)})</i>` : ""}</div>
            ${writeOnHTML(s)}
          </div>
          <div class="s-side">${diagrams}${s.writeOn ? "" : `<div class="used">Used <b class="bx"></b></div>`}</div>
        </div>
        <div class="c-foot"><span>Source: ${esc(s.source || "BattleTech Core Rulebook")}</span><span>Unofficial</span></div>
      </div>`;
  }

  const anyCardHTML = (x, skill) => (isStrike(x) ? strikeCardHTML(x) : cardHTML(x, skill));

  // ---------- Browse ----------
  function filtered() {
    const q = $("search").value.trim().toLowerCase();
    const t = $("type-filter").value;
    const p = $("prov-filter").value;
    const match = (x) => !q || x.name.toLowerCase().includes(q);
    const units = t === STRIKE_TYPE ? [] : data.units.filter((u) =>
      match(u) && (!t || u.type === t) && (!p || u.provenance === p));
    // Strike cards are the rulebook's options: they count as official.
    const strikes = (t && t !== STRIKE_TYPE) || (p && p !== "official") ? [] : data.strikes.filter(match);
    return { units, strikes };
  }

  function resultLI(x, meta) {
    return `
      <li data-id="${esc(x.id)}" class="${x.id === selectedId ? "active" : ""}">
        <span>${esc(x.name)}</span>
        <span class="meta">${meta}</span>
      </li>`;
  }

  function renderResults() {
    const { units, strikes } = filtered();
    const html = units.map((u) => resultLI(u,
      `${esc(u.cost.regular)}${u.cost.veteran != null ? ` (${esc(u.cost.veteran)})` : ""} · ${esc(sourceLabel(u))}`));
    if (strikes.length) {
      html.push(`<li class="group">Strikes</li>`);
      strikes.forEach((s) => html.push(resultLI(s, `${esc(costText(s))} · ${esc(s.category)}`)));
    }
    $("results").innerHTML = html.join("") || `<li class="muted">No matches.</li>`;
  }

  function renderStrikeDetail(s) {
    $("detail").innerHTML = `
      <h2>${esc(s.name)}</h2>
      <div class="muted">${esc([s.category, s.support].filter(Boolean).join(" · "))} · ${esc(costText(s))} BSP</div>
      ${s.notes ? `<p>${esc(s.notes)}</p>` : ""}
      <div class="card-pair">
        <div class="col">${strikeCardHTML(s)}<button data-add="strike">Add to force</button></div>
      </div>
      <p class="muted">Hex diagrams drawn by Motor Pool.</p>`;
  }

  function renderDetail() {
    const u = byId.get(selectedId);
    if (!u) return;
    if (isStrike(u)) { renderStrikeDetail(u); return; }
    const hasVet = u.cost.veteran != null && u.spec.skill.veteran != null;
    const official = u.hasOfficialCard && u.provenance !== "official"
      ? `<p class="muted">An official card exists for this unit; these are calculated values.</p>` : "";
    const mul = u.mulId
      ? ` · <a href="https://masterunitlist.info/Unit/Details/${encodeURIComponent(u.mulId)}" target="_blank" rel="noopener">MUL</a>` : "";
    $("detail").innerHTML = `
      <h2>${esc(u.name)}</h2>
      <div class="muted">${esc([u.type, u.techBase, u.introYear].filter(Boolean).join(" · "))}${mul}</div>
      ${official}
      ${u.notes ? `<p>${esc(u.notes)}</p>` : ""}
      <div class="card-pair">
        <div class="col">${cardHTML(u, "regular")}<button data-add="regular">Add Regular</button></div>
        ${hasVet ? `<div class="col">${cardHTML(u, "veteran")}<button data-add="veteran">Add Veteran</button></div>` : ""}
      </div>
      ${u.art && u.art.credit ? `<p class="muted">Art: ${esc(u.art.credit)}</p>` : ""}`;
  }

  // ---------- Force ----------
  function addToForce(id, skill) {
    const hit = force.find((f) => f.id === id && f.skill === skill);
    if (hit) hit.qty += 1; else force.push({ id, skill, qty: 1 });
    saveForce(); renderForce();
  }

  function entryCost(f) {
    const x = byId.get(f.id);
    if (isStrike(x)) return x.cost;
    return (f.skill === "veteran" ? x.cost.veteran : x.cost.regular) || 0;
  }

  // Units first, then strikes (as Motor Pool prints them), keeping each
  // entry's index in the force array for the edit controls.
  function forceInOrder() {
    const all = force.map((f, i) => ({ f, i }));
    return [...all.filter((e) => !isStrike(byId.get(e.f.id))), ...all.filter((e) => isStrike(byId.get(e.f.id)))];
  }

  function renderForce() {
    force = force.filter((f) => byId.has(f.id) && f.qty > 0);
    let total = 0, strikeHeader = false;
    $("force-list").innerHTML = forceInOrder().map(({ f, i }) => {
      const x = byId.get(f.id);
      const c = entryCost(f);
      total += c * f.qty;
      const head = isStrike(x) && !strikeHeader ? (strikeHeader = true, `<li class="group">Strikes</li>`) : "";
      const chip = isStrike(x) ? "" :
        ` <span class="skill-chip ${f.skill}">${f.skill === "veteran" ? "V" : "R"}</span>`;
      const qtyLabel = isStrike(x) && x.per ? `Quantity (${x.per})` : "Quantity";
      return `${head}<li>
        <span>${esc(x.name)}${chip} <span class="muted">${esc(isStrike(x) ? costText(x) : c)}</span></span>
        <input type="number" min="0" max="99" value="${f.qty}" data-qty="${i}" aria-label="${esc(qtyLabel)}">
        <button data-del="${i}" aria-label="Remove">✕</button>
      </li>`;
    }).join("") || `<li class="muted">Add cards from a unit's or strike's detail panel.</li>`;
    const count = force.reduce((n, f) => n + f.qty, 0);
    $("force-totals").textContent = count ? `${count} card${count === 1 ? "" : "s"} · ${total} BSP` : "";
    $("print-btn").disabled = count === 0;
  }

  function printForce() {
    const cards = [];
    forceInOrder().forEach(({ f }) => {
      for (let i = 0; i < f.qty; i++) cards.push(anyCardHTML(byId.get(f.id), f.skill));
    });
    const pages = [];
    for (let i = 0; i < cards.length; i += CARDS_PER_PAGE) {
      pages.push(`<div class="print-page">${cards.slice(i, i + CARDS_PER_PAGE).join("")}</div>`);
    }
    $("print-sheet").innerHTML = pages.join("");
    window.print();
  }

  // ---------- Wiring ----------
  function wire() {
    ["search", "type-filter", "prov-filter"].forEach((id) => $(id).addEventListener("input", renderResults));
    $("results").addEventListener("click", (e) => {
      const li = e.target.closest("li[data-id]");
      if (!li) return;
      selectedId = li.dataset.id;
      history.replaceState(null, "", `#${encodeURIComponent(selectedId)}`);
      renderResults(); renderDetail();
    });
    $("detail").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-add]");
      if (b && selectedId) addToForce(selectedId, b.dataset.add);   // strikes add as "strike"
    });
    $("force-list").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-del]");
      if (b) { force.splice(Number(b.dataset.del), 1); saveForce(); renderForce(); }
    });
    $("force-list").addEventListener("change", (e) => {
      const inp = e.target.closest("input[data-qty]");
      if (inp) { force[Number(inp.dataset.qty)].qty = Math.max(0, parseInt(inp.value, 10) || 0); saveForce(); renderForce(); }
    });
    $("print-btn").addEventListener("click", printForce);
    $("clear-btn").addEventListener("click", () => { force = []; saveForce(); renderForce(); });
  }

  async function init() {
    try {
      const res = await fetch("data/units.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (err) {
      $("detail").innerHTML = `<p>Couldn't load unit data (${esc(err.message)}). If you opened this file directly, run a local server instead: <code>python -m http.server -d site</code></p>`;
      return;
    }
    data.units.sort((a, b) => a.name.localeCompare(b.name));
    data.strikes = (data.strikes || []).map((s) => ({ ...s, kind: "strike" }));
    byId = new Map([...data.units, ...data.strikes].map((x) => [x.id, x]));
    const types = [...new Set(data.units.map((u) => u.type))].sort();
    $("type-filter").insertAdjacentHTML("beforeend", types.map((t) => `<option>${esc(t)}</option>`).join("") +
      (data.strikes.length ? `<option value="${STRIKE_TYPE}">Strikes</option>` : ""));
    $("footer").innerHTML = [
      esc(data.disclaimer || ""),
      ...(data.credits || []).map(esc),
      data.generatedOn ? `Data generated ${esc(data.generatedOn)}` : "",
    ].filter(Boolean).join(" · ");
    wire();
    const fromHash = decodeURIComponent(location.hash.slice(1));
    if (byId.has(fromHash)) selectedId = fromHash;
    renderResults(); renderForce();
    if (selectedId) renderDetail();
  }

  init();
})();
