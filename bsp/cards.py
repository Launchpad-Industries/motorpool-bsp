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

from . import approvals
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

    @property
    def bv(self) -> int:
        return self.cost * BV_PER_POINT


def dmg_text(dmg) -> str:
    if not dmg:
        return "-"
    return f"{dmg[0]}d×{dmg[1]}"


def card_from_unit(unit: Unit, weapons: dict, art: Art, approved: dict) -> Card:
    sp, skill, c = spec_for(unit, weapons)
    entry = approved.get(unit.full_name)
    rng = sp.range or ("Arrow" if sp.arrow else "Artillery" if sp.artillery else "-")
    path, src = art.find(unit)
    from .listing import split_variant
    return Card(
        chassis=unit.name, variant=split_variant(unit),
        unit_type=TYPE_NAMES.get(unit.unit_type, unit.unit_type), tons=unit.tonnage,
        mp=sp.mp, mode=sp.mode, tmm=sp.tmm, range=rng, skill=skill,
        vet_skill=None if c["veteran"] is None else skill - 1,
        damage=dmg_text(sp.damage), check=sp.check, threshold=sp.threshold,
        cost=c["regular"], vet_cost=c["veteran"],
        specials=sorted(set(sp.specials)),
        source="Approved" if entry else "Calculated",
        approver=entry["by"] if entry else "",
        image=Art.data_uri(path) if path else "", image_source=src)


def card_from_official(row: dict, unit: Unit | None, art: Art) -> Card:
    """An official card from the owner's spreadsheet export (private)."""
    rng = tuple(int(x) for x in row["range"].split("/")) if "/" in row["range"] else row["range"]
    dmg = row["dmg"].strip()
    if dmg and dmg[0].isdigit():
        n, _, h = dmg.partition("x")
        dmg = f"{n}d×{h or 1}"
    path, src = art.find(unit) if unit else (None, "")
    cv = row.get("costV", "").strip()
    return Card(
        chassis=row["name"], variant=row["variant"], unit_type=row["type"],
        tons=unit.tonnage if unit else 0, mp=int(row["mp"]), mode=row["mtype"],
        tmm=int(row["tmm"]), range=rng, skill=int(row["skill"]),
        vet_skill=int(row["skill"]) - 1 if cv else None, damage=dmg or "-",
        check=int(row["check"]), threshold=int(row["thr"]), cost=int(row["costR"]),
        vet_cost=int(cv) if cv else None,
        specials=[s.strip() for s in row["specials"].split(",") if s.strip() and s.strip() != "-"],
        source="Official", image=Art.data_uri(path) if path else "", image_source=src)


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
.cost .vet { color:#bdbdbd; font-weight:400; }

.bd { display:flex; gap:5px; padding:3px 6px 0 6px; flex:1; position:relative; z-index:1; min-height:0; }
.stats { flex:0 0 2.1in; display:flex; flex-direction:column; gap:4px; padding-bottom:4px; }
.stats.wide { flex:1; }
.box { border:1.2px solid var(--ink); border-radius:6px; padding:1px 6px; background:var(--soft); }
.row { display:flex; justify-content:space-between; align-items:baseline; gap:6px; }
.lbl { font-size:6.5pt; font-weight:600; letter-spacing:.06em; color:var(--mid); text-transform:uppercase; }
.val { font-family:'Oswald',sans-serif; font-weight:600; font-size:12pt; line-height:1.15; }
.val .g { color:#8a8a8a; font-weight:400; font-size:9pt; }
.rng { display:grid; grid-template-columns:repeat(3,1fr) 1.15fr; text-align:center; }
.rng .lbl { display:block; }
.rng .dm { border-left:1px solid var(--line); }
.chk { display:flex; align-items:center; gap:6px; white-space:nowrap; }
.track { display:flex; gap:1px; margin-left:auto; flex-wrap:nowrap; }
.track span { width:10px; height:10px; border:1px solid var(--ink); border-radius:2px; font-size:6pt;
        display:flex; align-items:center; justify-content:center; background:#fff; color:var(--mid); }
.spec { background:#fff; font-size:8pt; line-height:1.15; padding:2px 6px; flex:1; min-height:0.3in; }
.spec b { font-weight:700; letter-spacing:.04em; font-size:6.5pt; color:var(--mid); }
.art { flex:1; display:flex; align-items:center; justify-content:center; position:relative; min-width:0; }
.art img { max-width:100%; max-height:1.35in; object-fit:contain; }
.art img.sprite { width:1.05in; height:auto; image-rendering:auto; filter:grayscale(1) contrast(1.15); }
.art .credit { position:absolute; right:-2px; top:50%; transform:translateY(-50%) rotate(-90deg);
        transform-origin:center; font-size:4pt; color:#888; white-space:nowrap; width:0; }
.art .credit span{ position:absolute; left:-0.6in; width:1.2in; text-align:center; }

.ft { position:relative; z-index:1; display:flex; justify-content:space-between; align-items:center;
      height:0.24in; padding:0 0 0 6px; }
.ft .kind { font-family:'Oswald',sans-serif; font-weight:600; font-size:7.5pt; letter-spacing:.03em; white-space:nowrap;
      background:#fff; padding:1px 14px 1px 0; clip-path:polygon(0 0,calc(100% - 8px) 0,100% 100%,0 100%); }
.prov { height:100%; display:flex; align-items:center; padding:0 7px 0 12px; font-family:'Oswald',sans-serif;
      font-size:7pt; font-weight:600; letter-spacing:.04em; text-transform:uppercase; white-space:nowrap;
      clip-path:polygon(8px 0,100% 0,100% 100%,0 100%); }
.prov.official { background:var(--ink); color:#fff; }
.prov.approved { background:#5a5a5a; color:#fff; }
.prov.calculated { background:#fff; color:var(--ink); outline:1.2px dashed var(--ink); outline-offset:-3px; }
.screen-only { font-family:'Barlow',Arial,sans-serif; max-width:8in; margin:12px auto 0; font-size:10pt; color:#333; }
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&'
         'family=Barlow+Condensed:wght@400;600;700&family=Oswald:wght@400;500;600;700&display=swap" rel="stylesheet">')

MODE_NAMES = {"t": "t", "w": "w", "h": "h", "v": "v", "g": "g", "n": "n", "f": "f", "j": "j"}


def _e(x) -> str:
    return html.escape(str(x))


def card_html(c: Card) -> str:
    vet_cost = f' <span class="vet">({c.vet_cost})</span>' if c.vet_cost is not None else ""
    vet_skill = f' <span class="g">({c.vet_skill})</span>' if c.vet_skill is not None else ""
    if isinstance(c.range, tuple):
        rng = "".join(f'<div><span class="lbl">{l}</span><span class="val">{v}</span></div>'
                      for l, v in zip(("Short", "Med", "Long"), c.range))
    else:
        rng = f'<div style="grid-column:span 3"><span class="lbl">Attack</span><span class="val">{_e(c.range)}</span></div>'
    rng += f'<div class="dm"><span class="lbl">Dmg</span><span class="val">{_e(c.damage)}</span></div>'
    track = "".join(f"<span>{n}</span>" for n in range(c.check - 1, 1, -1))
    prov = {"Official": ("official", "Official"),
            "Approved": ("approved", f"Approved: {c.approver}"),
            "Calculated": ("calculated", "Calculated")}[c.source]
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
<div class="cost"><small>COST</small>{c.cost}{vet_cost}</div></div>
<div class="bd"><div class="stats{'' if img else ' wide'}">
<div class="box row"><span><span class="lbl">MP </span><span class="val">{c.mp}{_e(MODE_NAMES.get(c.mode, c.mode))}</span></span>
<span><span class="lbl">TMM </span><span class="val">+{c.tmm}</span></span>
<span><span class="lbl">Skill </span><span class="val">{c.skill}{vet_skill}</span></span></div>
<div class="box rng">{rng}</div>
<div class="box chk"><span><span class="lbl">Check </span><span class="val">{c.check}+</span></span>
<span><span class="lbl">Thr </span><span class="val">{c.threshold}</span></span>
<span class="track" title="Degradation">{track}</span></div>
<div class="box spec"><b>SPECIALS </b>{_e(specials)}</div>
</div>{img}</div>
<div class="ft"><span class="kind">BATTLEFIELD SUPPORT ASSET</span><span class="prov {prov[0]}">{_e(prov[1])}</span></div>
</div>"""


def summary_html(cards: list[Card], title: str) -> str:
    rows = "".join(
        f"<tr><td>{_e(c.chassis)}{'' if c.variant == 'Standard' else ' ' + _e(c.variant)}</td><td>{_e(c.unit_type)}</td>"
        f"<td class=n>{c.skill}</td><td class=n>{c.cost}</td><td class=n>{c.bv:,}</td>"
        f"<td class=n>{c.tons:g}</td><td>{_e(c.source + (': ' + c.approver if c.approver else ''))}</td></tr>"
        for c in cards)
    tot = (f"<tr class=total><td>{len(cards)} Assets</td><td></td><td></td>"
           f"<td class=n>{sum(c.cost for c in cards)}</td><td class=n>{sum(c.bv for c in cards):,}</td>"
           f"<td class=n>{sum(c.tons for c in cards):g}</td><td></td></tr>")
    return f"""<div class="page summary"><h1>{_e(title)}</h1>
<table><thead><tr><th>Asset</th><th>Type</th><th>Skill</th><th>BSP Cost</th><th>BV Equivalent</th><th>Tonnage</th><th>Source</th></tr></thead>
<tbody>{rows}{tot}</tbody></table>
<div class="note">BV equivalent = BSP cost × {BV_PER_POINT} (Battle Value Integration). Unofficial fan-made cards; calculated specs derived from MegaMek Data (CC BY-NC-SA 4.0).</div></div>"""


def document(cards: list[Card], title="Battlefield Support - Forces", summary=True, note="") -> str:
    pages = [summary_html(cards, title)] if summary else []
    for i in range(0, len(cards), 8):
        cells = "".join(f'<div class="cell">{card_html(c)}</div>' for c in cards[i:i + 8])
        pages.append(f'<div class="page"><div class="sheet">{cells}</div></div>')
    banner = f'<div class="screen-only">{note}</div>' if note else ""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>BSP Cards</title>{FONTS}<style>{CSS}</style></head><body>{banner}{''.join(pages)}</body></html>")


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
