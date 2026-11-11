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
  // ---------- Cards ----------
  // Every card is pre-drawn by Motor Pool's own card code (python -m
  // bsp.export_site) as a small page in cards/, so it looks exactly like the
  // app's preview and PDF. The site only shows and prints those pages.
  const STRIKE_TYPE = "__strikes";
  const isStrike = (x) => x && x.kind === "strike";
  const costText = (s) => `${s.cost}${s.per ? ` ${s.per}` : ""}`;
  const cardPage = (x, skill) => (isStrike(x) ? x.card : skill === "veteran" ? x.cards.veteran : x.cards.regular);
  const cardFrame = (src, label) =>
    `<iframe class="cardframe" src="${esc(src)}" title="${esc(label)}"></iframe>`;

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
        <div class="col">${cardFrame(s.card, `${s.name} card`)}<button data-add="strike">Add to force</button></div>
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
        <div class="col">${cardFrame(u.cards.regular, `${u.name} Regular card`)}<button data-add="regular">Add Regular</button></div>
        ${hasVet ? `<div class="col">${cardFrame(u.cards.veteran, `${u.name} Veteran card`)}<button data-add="veteran">Add Veteran</button></div>` : ""}
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

  // A pre-drawn card page -> its card markup and the page's font links.
  const pageCache = new Map();
  function cardPart(src) {
    if (!pageCache.has(src)) {
      pageCache.set(src, fetch(src).then((r) => {
        if (!r.ok) throw new Error(`${src}: HTTP ${r.status}`);
        return r.text();
      }).then((text) => {
        const doc = new DOMParser().parseFromString(text, "text/html");
        const fonts = [...doc.querySelectorAll('link[href*="fonts"]')].map((l) => l.outerHTML).join("");
        return { card: doc.querySelector(".one").innerHTML, fonts };
      }));
    }
    return pageCache.get(src);
  }

  // The same print layout as Motor Pool's PDF (cards.document): US Letter,
  // 2 x 4 cards with dashed cut lines, units first, then strikes.
  async function printForce() {
    const btn = $("print-btn");
    btn.disabled = true;
    try {
      const srcs = [];
      forceInOrder().forEach(({ f }) => {
        for (let i = 0; i < f.qty; i++) srcs.push(cardPage(byId.get(f.id), f.skill));
      });
      const parts = await Promise.all(srcs.map(cardPart));
      const pages = [];
      for (let i = 0; i < parts.length; i += CARDS_PER_PAGE) {
        const cells = parts.slice(i, i + CARDS_PER_PAGE).map((p) => `<div class="cell">${p.card}</div>`).join("");
        pages.push(`<div class="page"><div class="sheet">${cells}</div></div>`);
      }
      const base = new URL("cards/", location.href).href;
      const doc = `<!doctype html><html lang="en"><head><meta charset="utf-8"><base href="${esc(base)}">
        <title>Motor Pool – Battlefield Support - Forces</title>${parts[0] ? parts[0].fonts : ""}
        <link rel="stylesheet" href="card.css"></head><body>${pages.join("")}</body></html>`;
      const old = document.getElementById("print-frame");
      if (old) old.remove();
      const frame = document.createElement("iframe");
      frame.id = "print-frame";
      frame.setAttribute("aria-hidden", "true");
      frame.style.cssText = "position:fixed;left:-10000px;top:0;width:8.5in;height:11in;border:0";
      document.body.appendChild(frame);
      await new Promise((ok) => { frame.onload = ok; frame.srcdoc = doc; });
      const w = frame.contentWindow, d = w.document;
      await Promise.all([...d.images].map((img) => img.complete ? null : new Promise((ok) => { img.onload = img.onerror = ok; })));
      if (d.fonts) await d.fonts.ready;
      w.focus();
      w.print();
    } catch (err) {
      alert(`Couldn't prepare the cards for printing (${err.message}).`);
    } finally {
      btn.disabled = force.length === 0;
    }
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
