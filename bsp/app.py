# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Motor Pool: a local browser app for Battlefield Support asset cards.

Search MegaMek's vehicles, add assets to a force list, choose Regular or
Veteran, preview cards (official, approved or calculated), tweak and approve
calculated cards, and make a printable PDF.

Run:
    python -m bsp.app            # opens http://127.0.0.1:8640 in your browser

Settings live in ~/.motorpool/settings.json (also editable in the app).
The server only listens on this computer (127.0.0.1).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import threading
import webbrowser
import zlib
from dataclasses import asdict
from datetime import date
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from . import approvals, dist, signing
from .art import Art
from .cards import (BV_PER_POINT, Card, apply_values, card_from_generic, card_from_official,
                    card_from_unit, card_frame, card_html, card_values, document,
                    generic_official, official_index)
from .cost import cost as bsp_cost
from .megamek import Unit, load_all

APP_NAME = "Motor Pool"
ROOT = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent / "web"
SETTINGS = signing.HOME / "settings.json"
DEFAULTS = {
    "name": "",                                   # your approver name
    "approval_email": "williamtbecker@gmail.com",  # where "Send tweaks for approval" goes
    "mm_data": str(ROOT / "mm-data" / "data" / "mekfiles"),
    "official_tsv": "",                           # private export of the official cards
    "fluff_dir": "",                              # your own unit images
}
COMPARE = ("mp", "mode", "tmm", "range", "skill", "damage", "check", "threshold",
           "cost", "vet_cost", "specials")


PATH_KEYS = ("mm_data", "official_tsv", "fluff_dir")


def clean_path(p: str) -> str:
    """Accept paths pasted from Windows "Copy as path" (wrapped in quotes)."""
    return (p or "").strip().strip('"').strip("'").strip()


def load_settings() -> dict:
    s = dict(DEFAULTS)
    if SETTINGS.exists():
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    for k in PATH_KEYS:
        s[k] = clean_path(s.get(k, ""))
    if dist.DIST:
        # The packaged app reads only its bundled data.
        s["mm_data"], s["official_tsv"] = str(dist.long_path(Path(DEFAULTS["mm_data"]))), ""
    return s


def official_path(settings: dict) -> Path | None:
    """The official cards export: the Settings path, else official.tsv in the
    repository folder (git ignores it, so it never gets pushed)."""
    p = clean_path(settings.get("official_tsv", ""))
    if p:
        return Path(p)
    default = ROOT / "official.tsv"
    return default if default.exists() else None


def save_settings(s: dict):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")


def uid(unit: Unit) -> str:
    return hashlib.sha1(unit.full_name.encode()).hexdigest()[:10]


def generic_id(row: dict) -> str:
    return "g" + hashlib.sha1(f"generic|{row['name']}|{row['variant']}".encode()).hexdigest()[:9]


def diff(a: Card, b: Card) -> list[str]:
    va, vb = card_values(a), card_values(b)
    return [k for k in COMPARE if str(va.get(k)) != str(vb.get(k))]


class Catalog:
    """Every vehicle with its official card (if any) and calculated card,
    plus generic official cards (infantry, battle armor, emplacements)."""

    def __init__(self, settings: dict):
        self.settings = settings
        self.weapons = json.loads((ROOT / "cache" / "weapons.json").read_text())
        mm = Path(settings["mm_data"])
        self.mm = mm
        every = load_all(mm, folders=("vehicles",))
        combat = [u for u in every if u.unit_type in ("Tank", "VTOL")]
        fluff = Path(settings["fluff_dir"]) if settings.get("fluff_dir") else None
        self.art = Art(mm.parent / "images" / "units", fluff)
        tsv = official_path(settings)
        self.generic = {}
        if tsv is None:
            self.official_status = "No official cards export set (Settings), and no official.tsv in the app folder."
            self.official = {}
        elif not tsv.exists():
            self.official_status = f"Official cards export not found: {tsv}"
            self.official = {}
        else:
            self.official = official_index(tsv, mm, combat)
            self.generic = {generic_id(r): r for r in generic_official(tsv)}
            self.official_status = (f"{len(self.official)} official vehicle cards and {len(self.generic)} "
                                    f"infantry, battle armor and emplacement cards from {tsv}")
        # Support vehicles are only listed when they have an official card
        # (the generator's rules are fitted to combat vehicles).
        self.units = combat + [u for u in every if u.unit_type.startswith("Support")
                               and u.path in self.official]
        self.by_id = {uid(u): u for u in self.units}
        self.reload_approvals()

    def reload_approvals(self):
        self.approved = approvals.load()
        self.rows = [self.row(u) for u in self.units] + [self.generic_row(i) for i in self.generic]
        self.rows.sort(key=lambda r: r["name"].lower())

    # --- cards ---------------------------------------------------------
    def calculated(self, unit: Unit, image=False, use_approval=True) -> Card:
        return card_from_unit(unit, self.weapons, self.art if image else None,
                              self.approved, use_approval=use_approval)

    def official_card(self, unit: Unit, image=False) -> Card | None:
        row = self.official.get(unit.path)
        return card_from_official(row, unit, self.art if image else None) if row else None

    def generic_card(self, i: str, image=True) -> Card:
        return card_from_generic(self.generic[i], self.art if image else None)

    def card_for_id(self, i: str, view: str = "official", image=True) -> Card | None:
        if i in self.generic:
            return self.generic_card(i, image)
        u = self.by_id.get(i)
        return self.card(u, view, image) if u else None

    def card(self, unit: Unit, view: str = "official", image=True) -> Card:
        off = self.official_card(unit, image) if view == "official" else None
        if view == "generated":
            return self.calculated(unit, image, use_approval=False)
        return off or self.calculated(unit, image)

    def row(self, u: Unit) -> dict:
        calc = self.calculated(u)
        off = self.official_card(u)
        c = off or calc
        year = (u.raw.get("year") or [""])[0]
        return {
            "id": uid(u), "name": u.full_name, "chassis": c.chassis, "variant": c.variant,
            "type": c.unit_type, "tons": u.tonnage, "tech": "Clan" if u.clan else "IS",
            "year": int(year) if str(year).isdigit() else None,
            "mp": c.mp, "mode": c.mode, "tmm": c.tmm,
            "range": list(c.range) if isinstance(c.range, tuple) else c.range,
            "damage": c.damage, "skill": c.skill, "check": c.check, "threshold": c.threshold,
            "cost": c.cost, "vet_cost": c.vet_cost, "specials": c.specials,
            "source": c.source, "approver": c.approver, "verified": c.verified,
            "has_official": off is not None,
            "differs": diff(off, calc) if off else [],
            "drift": calc.drift,
        }

    def generic_row(self, i: str) -> dict:
        c, name = self.generic_card(i, image=False), self.generic[i]["name"]
        return {
            "id": i, "name": name if c.variant == "Standard" else f"{name} {c.variant}",
            "chassis": c.chassis, "variant": c.variant, "type": c.unit_type, "tons": None,
            "tech": "Clan" if any(w in name for w in ("Clan", "Elemental")) else "IS", "year": None,
            "mp": c.mp, "mode": c.mode, "tmm": c.tmm,
            "range": list(c.range) if isinstance(c.range, tuple) else c.range,
            "damage": c.damage, "skill": c.skill, "check": c.check, "threshold": c.threshold,
            "cost": c.cost, "vet_cost": c.vet_cost, "specials": c.specials,
            "source": c.source, "approver": c.approver, "verified": c.verified,
            "has_official": True, "generic": True, "differs": [], "drift": [],
        }


def create_app(settings: dict | None = None) -> Flask:
    settings = settings or load_settings()
    app = Flask(__name__, static_folder=None)
    state = {"cat": Catalog(settings), "settings": settings}

    def cat() -> Catalog:
        return state["cat"]

    def unit_or_404(i: str) -> Unit:
        u = cat().by_id.get(i)
        if u is None:
            abort(404)
        return u

    @app.get("/")
    def index():
        if dist.local_fonts():
            page = (WEB / "index.html").read_text(encoding="utf-8")
            start, end = page.index('<link rel="preconnect"'), page.index('<link rel="stylesheet" href="/web/app.css">')
            return Response(page[:start] + dist.FONTS_LINK + "\n" + page[end:], mimetype="text/html")
        return send_from_directory(WEB, "index.html")

    @app.get("/fonts/<path:p>")
    def fonts(p):
        return send_from_directory(dist.ROOT / "fonts", p)

    @app.get("/web/<path:p>")
    def web(p):
        return send_from_directory(WEB, p)

    @app.get("/api/info")
    def info():
        s = state["settings"]
        return jsonify(app=APP_NAME, units=len(cat().units), official=len(cat().official),
                       official_status=cat().official_status,
                       approved=len(cat().approved), owner=signing.owner_name(),
                       name=s.get("name") or "", settings=s, bv_per_point=BV_PER_POINT,
                       about=dist.about())

    @app.get("/api/units")
    def units():
        return jsonify(cat().rows)

    @app.get("/api/unit/<i>")
    def unit(i):
        if i in cat().generic:
            # Official-only card for a type of unit: nothing to calculate or tweak.
            return jsonify(id=i, name=cat().generic_row(i)["name"], tons=None, generic=True,
                           official=card_values(cat().generic_card(i, image=False)),
                           calculated=None, generated=None, approval=None,
                           differs=[], drift=[], weapons=[])
        u = unit_or_404(i)
        off = cat().official_card(u)
        calc = cat().calculated(u)
        gen = cat().calculated(u, use_approval=False)
        entry = cat().approved.get(u.full_name)
        return jsonify(
            id=i, name=u.full_name, tons=u.tonnage,
            official=card_values(off) if off else None,
            calculated=card_values(calc), generated=card_values(gen),
            approval={k: v for k, v in entry.items() if k != "sig"} if entry else None,
            differs=diff(off, calc) if off else [], drift=calc.drift,
            weapons=[n for _, n in u.weapons()])

    @app.get("/api/card/<i>")
    def card(i):
        c = cat().card_for_id(i, request.args.get("view", "official"))
        if c is None:
            abort(404)
        c.veteran = request.args.get("grade") == "vet"
        scale = request.args.get("scale")
        return Response(card_frame(card_html(c), float(scale) if scale else None), mimetype="text/html")

    @app.post("/api/preview")
    def preview():
        """Card HTML for edited values (tweak editor)."""
        d = request.get_json()
        u = unit_or_404(d["id"])
        c = cat().calculated(u, image=True)
        apply_values(c, d["values"])
        c.source, c.approver, c.verified = "Calculated", "", True
        c.veteran = d.get("grade") == "vet"
        return Response(card_frame(card_html(c), d.get("scale")), mimetype="text/html")

    @app.post("/api/recost")
    def recost():
        v = request.get_json()["values"]
        return jsonify(recost_values(v))

    @app.post("/api/approve")
    def approve():
        d = request.get_json()
        u = unit_or_404(d["id"])
        name = (d.get("by") or state["settings"].get("name") or "").strip()
        if not name:
            return jsonify(error="Set your name in Settings first."), 400
        from .generate import spec_for
        sp, skill, c = spec_for(u, cat().weapons)
        gen = card_values(cat().calculated(u, use_approval=False))
        values = d["values"]
        changes = {k: {"from": gen.get(k), "to": values.get(k)} for k in COMPARE
                   if str(gen.get(k)) != str(values.get(k))}
        e = approvals.record(u.full_name, approvals.snapshot(sp, skill, c), values, name,
                             changes=changes, cost_override=bool(d.get("cost_override")),
                             note=d.get("note", ""))
        cat().reload_approvals()
        return jsonify(entry={k: v for k, v in e.items() if k != "sig"})

    @app.post("/api/withdraw")
    def withdraw():
        u = unit_or_404(request.get_json()["id"])
        ok = approvals.withdraw(u.full_name)
        cat().reload_approvals()
        return jsonify(ok=ok)

    @app.post("/api/pdf")
    def pdf():
        d = request.get_json()
        html_doc = force_document(cat(), d)
        try:
            data = html_to_pdf(html_doc)
        except Exception as e:     # Playwright/Chromium (or Edge, packaged) missing
            hint = "" if dist.DIST else ". Run: python -m playwright install chromium"
            return jsonify(error=f"PDF engine unavailable: {e}{hint}"), 500
        name = (d.get("title") or "motor-pool").strip().replace(" ", "-").lower()
        return Response(data, mimetype="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})

    @app.post("/api/print-html")
    def print_html():
        return Response(force_document(cat(), request.get_json()), mimetype="text/html")

    @app.post("/api/proposals/export")
    def proposals_export():
        d = request.get_json()
        s = state["settings"]
        out = export_proposals(cat(), d["items"], d.get("from") or s.get("name") or "someone")
        out["mailto"] = mailto(s.get("approval_email", ""), out["subject"], out["body"])
        return jsonify(out)

    @app.post("/api/proposals/import")
    def proposals_import():
        try:
            return jsonify(import_proposals(cat(), request.get_json()["code"]))
        except Exception as e:
            return jsonify(error=f"Could not read that code: {e}"), 400

    @app.get("/api/settings")
    def get_settings():
        return jsonify(state["settings"])

    @app.post("/api/settings")
    def set_settings():
        s = dict(state["settings"])
        s.update({k: (clean_path(v) if k in PATH_KEYS else v)
                  for k, v in request.get_json().items() if k in DEFAULTS})
        if dist.DIST:
            s["mm_data"], s["official_tsv"] = str(dist.long_path(Path(DEFAULTS["mm_data"]))), ""
        save_settings(s)
        reload = any(s[k] != state["settings"].get(k) for k in ("mm_data", "official_tsv", "fluff_dir"))
        state["settings"] = s
        if reload:
            state["cat"] = Catalog(s)
        return jsonify(s)

    return app


# --------------------------------------------------------------------------
# helpers

def parse_damage(text: str):
    t = (text or "").replace("×", "x").replace("d", "").strip()
    if not t or t == "-":
        return None
    n, _, h = t.partition("x")
    return (int(n), int(h or 1))


def recost_values(v: dict) -> dict:
    """BSP cost for edited card stats (Regular skill drives the formula)."""
    import re
    rng = v.get("range")
    rng = tuple(rng) if isinstance(rng, list) and len(rng) == 3 else None
    specials = [s for s in v.get("specials", []) if s]
    ind = 0
    for s in specials:
        m = re.fullmatch(r"IF(\d+)", s.strip())
        if m:
            ind = int(m.group(1))
    c = bsp_cost(int(v["mp"]), int(v["tmm"]), parse_damage(v.get("damage")), rng,
                 int(v["skill"]), int(v["check"]), ind, specials)
    return {"cost": c["regular"], "vet_cost": c["veteran"], "unrounded": round(c["unrounded"], 2)}


def force_document(cat: Catalog, d: dict) -> str:
    cards = []
    for it in d.get("items", []):
        if cat.card_for_id(it["id"], image=False) is None:
            continue
        for _ in range(max(1, int(it.get("qty", 1)))):
            c = cat.card_for_id(it["id"], it.get("view", "official"))
            c.veteran = it.get("grade") == "vet"
            cards.append(c)
    return document(cards, title=d.get("title") or "Battlefield Support - Forces",
                    summary=bool(d.get("summary", True)), app_name=APP_NAME)


_PDF_LOCK = threading.Lock()


def html_to_pdf(html_doc: str) -> bytes:
    if dist.DIST:
        return dist.html_to_pdf_edge(html_doc)
    from playwright.sync_api import sync_playwright
    with _PDF_LOCK, sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(html_doc, wait_until="networkidle")
        data = page.pdf(format="Letter", print_background=True,
                        margin={"top": "0.25in", "bottom": "0.25in",
                                "left": "0.25in", "right": "0.25in"})
        b.close()
    return data


# --- proposals ("Send tweaks for approval") ---------------------------------

def export_proposals(cat: Catalog, items: list[dict], sender: str) -> dict:
    """items: [{id, values, note}] -> readable summary + import code."""
    lines, payload = [], []
    for it in items:
        u = cat.by_id.get(it["id"])
        if u is None:
            continue
        gen = card_values(cat.calculated(u, use_approval=False))
        v = it["values"]
        changes = [f"{k} {fmt(gen.get(k))} → {fmt(v.get(k))}" for k in COMPARE
                   if str(gen.get(k)) != str(v.get(k))]
        lines.append(f"- {u.full_name}: " + ("; ".join(changes) if changes else "approve as generated")
                     + (f"  [{it['note']}]" if it.get("note") else ""))
        payload.append({"unit": u.full_name, "values": v, "note": it.get("note", "")})
    code = base64.urlsafe_b64encode(zlib.compress(json.dumps(
        {"v": 1, "from": sender, "on": date.today().isoformat(), "items": payload}).encode())).decode()
    subject = f"{APP_NAME}: {len(payload)} card tweak(s) for approval from {sender}"
    body = (f"{sender} proposes these card changes:\n\n" + "\n".join(lines) +
            f"\n\nTo review them, open {APP_NAME} > Import proposals and paste this code:\n\n"
            f"MOTORPOOL:{code}\n")
    return {"subject": subject, "body": body, "code": f"MOTORPOOL:{code}", "count": len(payload)}


def fmt(v) -> str:
    if isinstance(v, list):
        return "/".join(map(str, v)) if all(isinstance(x, int) for x in v) else ", ".join(v) or "-"
    return "-" if v is None else str(v)


def mailto(to: str, subject: str, body: str) -> str:
    url = f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}"
    return url if len(url) <= 1900 else ""      # too long for some mail programs


def import_proposals(cat: Catalog, code: str) -> dict:
    code = code.strip()
    if "MOTORPOOL:" in code:
        code = code.split("MOTORPOOL:", 1)[1].split()[0]
    data = json.loads(zlib.decompress(base64.urlsafe_b64decode(code.encode())))
    by_name = {u.full_name: u for u in cat.units}
    out = []
    for it in data["items"]:
        u = by_name.get(it["unit"])
        if u is None:
            out.append({"unit": it["unit"], "error": "not in this app's MegaMek data"})
            continue
        gen = card_values(cat.calculated(u, use_approval=False))
        out.append({"id": uid(u), "unit": it["unit"], "values": it["values"], "note": it.get("note", ""),
                    "generated": gen, "changed": [k for k in COMPARE
                                                  if str(gen.get(k)) != str(it["values"].get(k))]})
    return {"from": data.get("from"), "on": data.get("on"), "items": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description=f"{APP_NAME}: Battlefield Support cards")
    ap.add_argument("--port", type=int, default=8640)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    app = create_app()
    url = f"http://127.0.0.1:{a.port}/"
    print(f"{APP_NAME} running at {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=a.port, debug=False)


if __name__ == "__main__":
    main()
