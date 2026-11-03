# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Printable asset cards: an optional force summary page, then cards
3.5" x 2.5" (landscape), 2 across x 4 down on US Letter.

The layout echoes the Master Unit List's Alpha Strike printouts (roster page,
bordered cards with stat boxes and a unit image) without Catalyst's logos or
art: the footer carries "Battlefield Support Asset" and the provenance mark.

Usage (mock-up):
    python -m bsp.cards --mm-data PATH --out cards.html "Unit full name" ...
"""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import approvals, dist
from .art import Art, SPRITE_CREDIT
from .generate import spec_for
from .megamek import Unit, load_all

ROOT = Path(__file__).resolve().parent.parent
BV_PER_POINT = 20          # BSP rules: 1 BSP point = 20 BV
TYPE_NAMES = {"Tank": "Vehicle", "VTOL": "VTOL", "SupportTank": "Support Vehicle"}


@dataclass
class Card:
    chassis: str
    variant: str
    unit_type: str
    tons: float
    mp: int
    mode: str
    tmm: int
    range: tuple | str            # (s, m, l) or "Arrow" / "Artillery"
    skill: int
    vet_skill: int | None
    damage: str                   # "5d×4" or "-"
    check: int
    threshold: int
    cost: int
    vet_cost: int | None
    specials: list[str] = field(default_factory=list)
    source: str = "Calculated"    # Official | Approved | Calculated
    approver: str = ""
    image: str = ""               # data URI
    image_source: str = ""        # fluff | sprite | ""
    veteran: bool = False         # print as the improved-Skill (Veteran) version
    verified: bool = True         # approvals: signed by a trusted key
    drift: list[str] = field(default_factory=list)   # approvals: rules changed since

    @property
    def bv(self) -> int:
        return self.current_cost * BV_PER_POINT

    @property
    def is_vet(self) -> bool:
        return self.veteran and self.vet_cost is not None

    @property
    def current_cost(self) -> int:
        return self.vet_cost if self.is_vet else self.cost

    @property
    def current_skill(self) -> int:
        return self.vet_skill if self.is_vet else self.skill


def dmg_text(dmg) -> str:
    if not dmg:
        return "-"
    return f"{dmg[0]}d×{dmg[1]}"


EDITABLE = ("mp", "mode", "tmm", "range", "skill", "vet_skill", "damage", "check",
            "threshold", "cost", "vet_cost", "specials")


def card_values(c: Card) -> dict:
    """The editable card stats as plain data (for approvals and the app)."""
    d = {k: getattr(c, k) for k in EDITABLE}
    d["range"] = list(d["range"]) if isinstance(d["range"], tuple) else d["range"]
    return d


def apply_values(c: Card, d: dict) -> Card:
    for k in EDITABLE:
        if k in d:
            v = d[k]
            setattr(c, k, tuple(v) if k == "range" and isinstance(v, list) else v)
    return c


def _legacy_values(v: dict) -> dict:
    """Card values from an old-style approval that only stored the snapshot."""
    out = {}
    cost = str(v.get("cost", ""))
    if "(" in cost:
        r, vv = cost.replace(")", "").split("(")
        out["cost"], out["vet_cost"] = int(r), int(vv)
    elif cost.isdigit():
        out["cost"], out["vet_cost"] = int(cost), None
    rng = str(v.get("range", ""))
    if "/" in rng:
        out["range"] = [int(x) for x in rng.split("/")]
    dmg = str(v.get("damage", ""))
    if dmg and dmg[0].isdigit():
        n, _, h = dmg.partition("x")
        out["damage"] = f"{n}d×{h or 1}"
    for k in ("check", "threshold", "tmm", "skill"):
        if k in v:
            out[k] = int(v[k])
    sp = str(v.get("specials", "-"))
    out["specials"] = [] if sp == "-" else [s.strip() for s in sp.split(",")]
    return out


def card_from_unit(unit: Unit, weapons: dict, art: Art | None, approved: dict,
                   use_approval: bool = True) -> Card:
    """The calculated card for a MegaMek unit. If the unit is approved (and
    use_approval), the card carries the approved values, including tweaks."""
    sp, skill, c = spec_for(unit, weapons)
    entry = approved.get(unit.full_name) if use_approval else None
    rng = sp.range or ("Arrow" if sp.arrow else "Artillery" if sp.artillery else "-")
    path, src = art.find(unit) if art else (None, "")
    from .listing import split_variant
    card = Card(
        chassis=unit.name, variant=split_variant(unit),
        unit_type=TYPE_NAMES.get(unit.unit_type, unit.unit_type), tons=unit.tonnage,
        mp=sp.mp, mode=sp.mode, tmm=sp.tmm, range=rng, skill=skill,
        vet_skill=None if c["veteran"] is None else skill - 1,
        damage=dmg_text(sp.damage), check=sp.check, threshold=sp.threshold,
        cost=c["regular"], vet_cost=c["veteran"],
        specials=sorted(set(sp.specials)),
        image=Art.data_uri(path, trim=src == "sprite") if path else "", image_source=src)
    if entry:
        from . import approvals
        apply_values(card, entry.get("card") or _legacy_values(entry.get("values", {})))
        card.source, card.approver = "Approved", entry["by"]
        card.verified = bool(entry.get("verified"))
        card.drift = approvals.drift(entry, approvals.snapshot(sp, skill, c))
    return card


def card_from_official(row: dict, unit: Unit | None, art: Art) -> Card:
    """An official card from the owner's spreadsheet export."""
    rng = tuple(int(x) for x in row["range"].split("/")) if "/" in row["range"] else row["range"]
    dmg = row["dmg"].strip()
    if dmg and dmg[0].isdigit():
        n, _, h = dmg.partition("x")
        dmg = f"{n}d×{h or 1}"
    path, src = art.find(unit) if (unit and art) else (None, "")
    cv = row.get("costV", "").strip()
    if not cv.isdigit() or cv == row["costR"].strip():
        cv = ""          # no Veteran version (e.g. artillery: no Skill upgrades)
    return Card(
        chassis=row["name"], variant=row["variant"], unit_type=row["type"],
        tons=unit.tonnage if unit else 0, mp=int(row["mp"]), mode=row["mtype"],
        tmm=int(row["tmm"]), range=rng, skill=int(row["skill"]),
        vet_skill=int(row["skill"]) - 1 if cv else None, damage=dmg or "-",
        check=int(row["check"]), threshold=int(row["thr"]), cost=int(row["costR"]),
        vet_cost=int(cv) if cv else None,
        specials=[s.strip() for s in row["specials"].split(",") if s.strip() and s.strip() != "-"],
        source="Official", image=Art.data_uri(path, trim=src == "sprite") if path else "", image_source=src)


# Official cards of these types stand for a kind of unit, not one MegaMek design.
GENERIC_TYPES = ("Infantry", "Battle Armor", "Emplacement")


def generic_official(official_tsv: Path) -> list[dict]:
    """Generic official card rows (conventional infantry, battle armor,
    emplacements, and any row listed under generic: in card_links.yaml)."""
    import csv
    import yaml
    links = yaml.safe_load((ROOT / "data" / "card_links.yaml").read_text())
    generic = set(links.get("generic", []))
    return [r for r in csv.DictReader(open(official_tsv, encoding="utf-8"), delimiter="\t")
            if f"{r['name']}|{r['variant']}" in generic or r["type"] in GENERIC_TYPES]


def card_from_generic(row: dict, art: Art | None) -> Card:
    c = card_from_official(row, None, None)
    if c.variant.strip("()").lower() in c.chassis.lower():
        c.variant = "Standard"     # "Heavy Emplacement / Heavy": don't say it twice
    if art:
        path, src = art.find_generic(row["name"], row["type"])
        if path:
            c.image, c.image_source = Art.data_uri(path, trim=src == "sprite"), src
    return c


def official_index(official_tsv: Path, mm_root: Path, vehicles: list[Unit]) -> dict:
    """MegaMek unit path -> official card row (from the owner's
    spreadsheet export), using the same links as the CSV listing."""
    import csv
    import yaml
    from .match import best_match
    from .megamek import load_unit
    links = yaml.safe_load((ROOT / "data" / "card_links.yaml").read_text())
    out = {}
    for r in csv.DictReader(open(official_tsv, encoding="utf-8"), delimiter="\t"):
        key = f"{r['name']}|{r['variant']}"
        if key in links.get("generic", []) or r["type"] != "Vehicle":
            continue
        path = links["links"].get(key) or links["review"].get(key)
        unit = load_unit(mm_root / path) if path else best_match(r, vehicles).unit
        if unit is not None:
            out[unit.path] = r
    return out


def card_for(unit: Unit, weapons: dict, art: Art, approved: dict,
             official: dict, view: str = "official") -> Card:
    """The card to print for a unit. view="official" uses the printed card
    when one exists (the default); view="calculated" always calculates."""
    row = official.get(unit.path)
    if row and view == "official":
        return card_from_official(row, unit, art)
    return card_from_unit(unit, weapons, art, approved)


# --------------------------------------------------------------------------
# HTML

CSS = """
@page { size: letter; margin: 0.25in; }
* { box-sizing: border-box; }
:root { --ink:#141414; --mid:#5f5f5f; --soft:#e9e9e6; --line:#c9c9c4; --paper:#fff; }
body { margin:0; background:#d9d9d4; font-family:'Barlow Condensed','Arial Narrow',sans-serif; color:var(--ink); }
.page { width:8in; min-height:10.5in; margin:0.25in auto; background:var(--paper);
        box-shadow:0 1px 6px rgba(0,0,0,.25); page-break-after:always; position:relative; }
@media print { body{background:#fff} .page{margin:0; box-shadow:none} .screen-only{display:none} }

/* summary page */
.summary { padding:0.35in 0.4in; }
.summary h1 { font-family:'Oswald',sans-serif; font-weight:500; font-size:22pt; text-align:center; margin:0 0 .25in; letter-spacing:.02em; }
.summary table { width:100%; border-collapse:collapse; font-size:9pt; font-family:'Barlow',Arial,sans-serif; }
.summary th, .summary td { border:1px solid #555; padding:2px 5px; }
.summary th { background:#cfcfcf; text-align:left; }
.summary td.n { text-align:right; font-variant-numeric:tabular-nums; }
.summary tr.total td { background:#cfcfcf; font-weight:700; }
.summary .note { margin-top:.2in; font-size:8pt; color:var(--mid); font-family:'Barlow',Arial,sans-serif; }

/* card sheet: 2 x 4 of 3.5in x 2.5in, thin cut lines between */
.sheet { display:grid; grid-template-columns:repeat(2,3.5in); grid-auto-rows:2.5in;
         justify-content:center; padding-top:0.25in; }
.cell { border:0.5px dashed #9a9a9a; margin:-0.25px; }

.card { position:relative; width:100%; height:100%; background:var(--paper);
        border:0.075in solid var(--ink); overflow:hidden; display:flex; flex-direction:column; }
.card .stripe { position:absolute; left:0; right:0; bottom:0; height:0.30in;
        background:repeating-linear-gradient(-60deg,#ececea 0 10px,#fafaf8 10px 20px); }
.hd { display:flex; align-items:flex-start; padding:3px 6px 0 6px; position:relative; z-index:1; }
.hd .names { flex:1; min-width:0; }
.hd .variant { font-size:7.5pt; line-height:1; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hd .chassis { font-family:'Oswald',sans-serif; font-weight:700; text-transform:uppercase;
        font-size:14pt; line-height:1.02; letter-spacing:-.01em; }
.hd .chassis.long { font-size:12pt; }
.hd .chassis.xlong { font-size:10.5pt; }
.cost { margin:-3px -6px 0 6px; background:var(--ink); color:#fff; padding:3px 8px 3px 14px;
        clip-path:polygon(10px 0,100% 0,100% 100%,0 100%); font-family:'Oswald',sans-serif;
        font-size:12pt; font-weight:600; white-space:nowrap; line-height:1.1; text-align:right; }
.cost small { display:block; font-size:6pt; font-weight:400; letter-spacing:.08em; opacity:.8; }
.cost .alt { color:#bdbdbd; font-weight:400; font-size:9pt; }

.bd { display:flex; gap:5px; padding:3px 6px 0 6px; flex:1; position:relative; z-index:1; min-height:0; }
.stats { flex:0 0 2.2in; display:flex; flex-direction:column; justify-content:flex-start; gap:3px; padding-bottom:3px; }
.stats.wide { flex:1; }
.box { border:1.2px solid var(--ink); border-radius:6px; padding:1px 6px; background:var(--soft); }
.row { display:flex; justify-content:space-between; align-items:baseline; gap:6px; }
.lbl { font-size:7.5pt; font-weight:600; letter-spacing:.06em; color:var(--mid); text-transform:uppercase; }
.val { font-family:'Oswald',sans-serif; font-weight:600; font-size:13pt; line-height:1.15; }
.val .g { color:#8a8a8a; font-weight:400; font-size:9.5pt; }
.rng { display:grid; grid-template-columns:repeat(3,1fr) 1.15fr; text-align:center; }
.rng .lbl { display:block; }
.rng .dm { border-left:1px solid var(--line); }
.chk { white-space:nowrap; }
.chk .top { display:flex; gap:10px; align-items:baseline; }
.track { display:flex; gap:2px; flex-wrap:nowrap; padding:1px 0 2px; }
.track span { width:15px; height:15px; border:1.2px solid var(--ink); border-radius:3px; font-size:8pt; font-weight:600;
        display:flex; align-items:center; justify-content:center; background:#fff; color:var(--mid); }
.spec { background:#fff; font-size:10pt; line-height:1.15; padding:2px 6px; }
.spec b { font-weight:700; letter-spacing:.04em; font-size:7.5pt; color:var(--mid); }
.side { flex:1; display:flex; flex-direction:column; align-items:stretch; min-width:0; gap:3px; }
.grade { align-self:flex-end; font-family:'Oswald',sans-serif; font-weight:600; font-size:8pt; letter-spacing:.08em;
        padding:1px 7px; border-radius:9px; border:1.2px solid var(--ink); }
.grade.vet { background:var(--ink); color:#fff; }
.art { flex:1; display:flex; align-items:center; justify-content:center; position:relative; min-width:0; }
.art img { max-width:100%; max-height:1.35in; object-fit:contain; }
.art img.sprite { width:0.8in; height:0.9in; object-fit:contain; image-rendering:auto; filter:grayscale(1) contrast(1.15); }
.art .credit { position:absolute; right:-2px; top:50%; transform:translateY(-50%) rotate(-90deg);
        transform-origin:center; font-size:4pt; color:#888; white-space:nowrap; width:0; }
.art .credit span{ position:absolute; left:-0.6in; width:1.2in; text-align:center; }

.ft { position:relative; z-index:1; display:flex; justify-content:space-between; align-items:center;
      height:0.24in; padding:0 0 0 6px; }
.ft .kind { font-family:'Oswald',sans-serif; font-weight:600; font-size:6.5pt; overflow:hidden; min-width:0; letter-spacing:.03em; white-space:nowrap;
      background:#fff; padding:1px 14px 1px 0; clip-path:polygon(0 0,calc(100% - 8px) 0,100% 100%,0 100%); }
.prov { height:100%; display:flex; align-items:center; padding:0 7px 0 12px; font-family:'Oswald',sans-serif;
      font-size:6.8pt; font-weight:600; letter-spacing:.02em; text-transform:uppercase; white-space:nowrap; flex:none;
      clip-path:polygon(8px 0,100% 0,100% 100%,0 100%); }
.prov.official { background:var(--ink); color:#fff; }
.prov.approved { background:#5a5a5a; color:#fff; }
.prov.approved.unverified { background:#fff; color:#5a5a5a; outline:1.2px dotted #5a5a5a; outline-offset:-3px; }
.prov.calculated { background:#fff; color:var(--ink); outline:1.2px dashed var(--ink); outline-offset:-3px; }
.screen-only { font-family:'Barlow',Arial,sans-serif; max-width:8in; margin:12px auto 0; font-size:10pt; color:#333; }
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&'
         'family=Barlow+Condensed:wght@400;600;700&family=Oswald:wght@400;500;600;700&display=swap" rel="stylesheet">')


def fonts() -> str:
    """Font links: the bundled copies in distribution mode, else Google Fonts."""
    return dist.FONTS_LINK if dist.local_fonts() else FONTS

MODE_NAMES = {"t": "t", "w": "w", "h": "h", "v": "v", "g": "g", "n": "n", "f": "f", "j": "j", "na": ""}


def _e(x) -> str:
    return html.escape(str(x))


def card_html(c: Card) -> str:
    # Regular always on the left, Veteran (in parentheses) on the right; the
    # grade in play is emphasised, the other shown small and grey.
    def pair(reg, vet, small_cls):
        if vet is None:
            return f"{reg}"
        if c.is_vet:
            return f'<span class="{small_cls}">{reg}</span> ({vet})'.replace(
                f" ({vet})", f' <span class="{small_cls}">(</span>{vet}<span class="{small_cls}">)</span>')
        return f'{reg} <span class="{small_cls}">({vet})</span>'
    cost_txt = pair(c.cost, c.vet_cost, "alt")
    skill_txt = pair(c.skill, c.vet_skill, "g")
    grade = ('<span class="grade vet">VETERAN</span>' if c.is_vet
             else '<span class="grade">REGULAR</span>')
    if isinstance(c.range, tuple):
        rng = "".join(f'<div><span class="lbl">{l}</span><span class="val">{v}</span></div>'
                      for l, v in zip(("Short", "Med", "Long"), c.range))
    else:
        rng = f'<div style="grid-column:span 3"><span class="lbl">Attack</span><span class="val">{_e(c.range)}</span></div>'
    rng += f'<div class="dm"><span class="lbl">Dmg</span><span class="val">{_e(c.damage)}</span></div>'
    # Degradation pips from full strength down: mark one off each time the
    # Asset survives a Destroy Check.
    track = "".join(f"<span>{n}</span>" for n in range(c.check, 1, -1))
    prov = {"Official": ("official", "Source: Official Catalyst BSP"),
            "Approved": ("approved" if c.verified else "approved unverified",
                         f"Source: Approved-{c.approver}" if c.verified
                         else f"Source: Unverified-{c.approver}"),
            "Calculated": ("calculated", "Source: Calculated")}[c.source]
    long_name = " xlong" if len(c.chassis) > 24 else " long" if len(c.chassis) > 17 else ""
    img = ""
    if c.image:
        cls = "sprite" if c.image_source == "sprite" else ""
        credit = (f'<div class="credit"><span>{_e(SPRITE_CREDIT)}</span></div>'
                  if c.image_source == "sprite" else "")
        img = f'<div class="art"><img class="{cls}" src="{c.image}" alt="">{credit}</div>'
    specials = ", ".join(c.specials) if c.specials else "—"
    return f"""<div class="card"><div class="stripe"></div>
<div class="hd"><div class="names"><div class="variant">{_e('' if c.variant == 'Standard' else c.variant) or '&nbsp;'}</div>
<div class="chassis{long_name}">{_e(c.chassis)}</div></div>
<div class="cost"><small>COST</small>{cost_txt}</div></div>
<div class="bd"><div class="stats">
<div class="box row"><span><span class="lbl">MP </span><span class="val">{c.mp}{_e(MODE_NAMES.get(c.mode, c.mode))}</span></span>
<span><span class="lbl">TMM </span><span class="val">+{c.tmm}</span></span>
<span><span class="lbl">Skill </span><span class="val">{skill_txt}</span></span></div>
<div class="box rng">{rng}</div>
<div class="box chk"><div class="top"><span><span class="lbl">Check </span><span class="val">{c.check}+</span></span>
<span><span class="lbl">Threshold </span><span class="val">{c.threshold}</span></span></div>
<div class="track" title="Degradation">{track}</div></div>
<div class="box spec"><b>SPECIALS </b>{_e(specials)}</div>
</div><div class="side">{grade}{img}</div></div>
<div class="ft"><span class="kind">BATTLEFIELD SUPPORT</span><span class="prov {prov[0]}">{_e(prov[1])}</span></div>
</div>"""


def card_frame(inner: str, scale: float | None = None) -> str:
    """A tiny standalone page showing one card (for the app's preview). By
    default the card scales itself to fit the frame's width, so the whole
    card shows whatever the screen size, zoom or display scaling."""
    fit = ("" if scale else
           "<script>function fit(){var o=document.querySelector('.one');"
           "var s=Math.min(innerWidth/o.offsetWidth,innerHeight/o.offsetHeight);"
           "o.style.transform='scale('+s+')';}"
           "addEventListener('resize',fit);addEventListener('load',fit);fit();</script>")
    return (f"<!doctype html><html><head><meta charset=utf-8>{fonts()}<style>{CSS}"
            f"html,body{{background:transparent;margin:0;overflow:hidden;width:100%;height:100%}}.one{{width:3.5in;height:2.5in;"
            f"transform:scale({scale or 1});transform-origin:0 0}}</style></head>"
            f"<body><div class=one>{inner}</div>{fit}</body></html>")


def summary_html(cards: list[Card], title: str) -> str:
    rows = "".join(
        f"<tr><td>{_e(c.chassis)}{'' if c.variant == 'Standard' else ' ' + _e(c.variant)}</td><td>{_e(c.unit_type)}</td>"
        f"<td>{'Veteran' if c.is_vet else 'Regular'}</td><td class=n>{c.current_skill}</td><td class=n>{c.current_cost}</td><td class=n>{c.bv:,}</td>"
        f"<td class=n>{format(c.tons, 'g') if c.tons else '—'}</td><td>{_e(c.source + (': ' + c.approver if c.approver else ''))}</td></tr>"
        for c in cards)
    tot = (f"<tr class=total><td>{len(cards)} Assets</td><td></td><td></td><td></td>"
           f"<td class=n>{sum(c.current_cost for c in cards)}</td><td class=n>{sum(c.bv for c in cards):,}</td>"
           f"<td class=n>{sum(c.tons for c in cards):g}</td><td></td></tr>")
    return f"""<div class="page summary"><h1>{_e(title)}</h1>
<table><thead><tr><th>Asset</th><th>Type</th><th>Grade</th><th>Skill</th><th>BSP Cost</th><th>BV Equivalent</th><th>Tonnage</th><th>Source</th></tr></thead>
<tbody>{rows}{tot}</tbody></table>
<div class="note">BV equivalent = BSP cost × {BV_PER_POINT} (Battle Value Integration). Unofficial fan-made cards; calculated specs derived from MegaMek Data (CC BY-NC-SA 4.0).</div></div>"""


def document(cards: list[Card], title="Battlefield Support - Forces", summary=True, note="",
             app_name="Motor Pool") -> str:
    pages = [summary_html(cards, title)] if summary else []
    for i in range(0, len(cards), 8):
        cells = "".join(f'<div class="cell">{card_html(c)}</div>' for c in cards[i:i + 8])
        pages.append(f'<div class="page"><div class="sheet">{cells}</div></div>')
    banner = f'<div class="screen-only">{note}</div>' if note else ""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{_e(app_name)} – {_e(title)}</title>{fonts()}<style>{CSS}</style></head><body>{banner}{''.join(pages)}</body></html>")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render asset cards to HTML")
    ap.add_argument("--mm-data", required=True, type=Path, help="mm-data/data/mekfiles")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fluff", type=Path, help="folder of your own unit images")
    ap.add_argument("--no-summary", action="store_true")
    ap.add_argument("units", nargs="+", help="MegaMek unit full names")
    a = ap.parse_args(argv)
    weapons = json.loads((ROOT / "cache" / "weapons.json").read_text())
    art = Art(a.mm_data.parent / "images" / "units", a.fluff)
    pool = {u.full_name: u for u in load_all(a.mm_data, folders=("vehicles",))}
    approved = approvals.load()
    cards = [card_from_unit(pool[n], weapons, art, approved) for n in a.units]
    a.out.write_text(document(cards, summary=not a.no_summary), encoding="utf-8")
    print(f"{len(cards)} cards -> {a.out}")


if __name__ == "__main__":
    main()
