# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Strike cards: the Battlefield Support options that aren't units (air
strikes, bombing, air cover, artillery, smoke, minefields).

The data comes from bsp-options.tsv (the "BSP Options" tab of the owner's
Sheet, fetched by `python -m bsp.sheet pull`). The cards share the unit cards'
frame and styles (cards.CSS); there is no Veteran grade, so a chip says what
the card is instead. Column layout: sheet.OPTIONS_COLUMNS. The stats column
holds "Label=Value" pairs separated by semicolons, plus bare flags such as
"Not an attack"."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

from .cards import BV_PER_POINT, _e

COVER_KEYS = ("Light Air Strike", "Light Bombing", "Heavy Air Strike", "Strafing", "Heavy Bombing")
DARK = "#141414"
# Fill and text colour by distance from the target hex.
RING_FILL = {0: (DARK, "#fff"), 1: ("#7a7a7a", "#fff"), 2: ("#d2d2cf", DARK)}
RADIUS_WIDTH = {0: 0.42, 1: 0.70, 2: 0.70}     # inches; radius 2 is as much as the card has height for
HATCH = ('<defs><pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" '
         'patternTransform="rotate(45)"><rect width="4" height="4" fill="#fff"/>'
         '<line x1="0" y1="0" x2="0" y2="4" stroke="#8a8a8a" stroke-width="1.6"/></pattern></defs>')
HEX_SIZE = 10
# Around the target, the direction each 1D6 result scatters: 1 straight up,
# then clockwise.
SCATTER = {(0, -1): 1, (1, -1): 2, (1, 0): 3, (0, 1): 4, (-1, 1): 5, (-1, 0): 6}


def strike_id(name: str) -> str:
    return "s" + hashlib.sha1(f"strike|{name}".encode()).hexdigest()[:9]


def parse_stats(text: str) -> dict:
    out = {}
    for part in text.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        elif part:
            out[part] = True
    return out


# --------------------------------------------------------------------------
# hex diagrams (axial coordinates). Flat-topped, like a mapsheet, so one hex
# sits directly above the target; only the strafing row stands on its points.

def _hex_path(cx: float, cy: float, s: float, flat: bool = True) -> str:
    turn = 0 if flat else -30
    pts = [(cx + s * math.cos(math.radians(60 * i + turn)), cy + s * math.sin(math.radians(60 * i + turn)))
           for i in range(6)]
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z"


def _svg(cells: list[tuple], width_in: float, defs: str = "", flat: bool = True) -> str:
    """cells: (q, r, fill, text, text colour)."""
    s, pad, root3 = HEX_SIZE, 1.5, math.sqrt(3)
    if flat:
        xy = [(s * 1.5 * c[0], s * root3 * (c[1] + c[0] / 2)) for c in cells]
        half_w, half_h = s, s * root3 / 2
    else:
        xy = [(s * root3 * (c[0] + c[1] / 2), s * 1.5 * c[1]) for c in cells]
        half_w, half_h = s * root3 / 2, s
    minx, maxx = min(x for x, _ in xy) - half_w - pad, max(x for x, _ in xy) + half_w + pad
    miny, maxy = min(y for _, y in xy) - half_h - pad, max(y for _, y in xy) + half_h + pad
    body = []
    for (x, y), (_, _, fill, text, colour) in zip(xy, cells):
        body.append(f'<path d="{_hex_path(x, y, s, flat)}" fill="{fill}" stroke="{DARK}" stroke-width="1"/>')
        if text != "":
            fs = s * (1.05 if len(str(text)) == 1 else .8)
            body.append(f'<text x="{x:.2f}" y="{y + fs * .36:.2f}" text-anchor="middle" font-family="Oswald" '
                        f'font-weight="600" font-size="{fs:.1f}" fill="{colour}">{_e(text)}</text>')
    return (f'<svg viewBox="{minx:.1f} {miny:.1f} {maxx - minx:.1f} {maxy - miny:.1f}" '
            f'style="width:{width_in}in;height:auto;display:block">{defs}{"".join(body)}</svg>')


def _ring(q: int, r: int) -> int:
    return (abs(q) + abs(r) + abs(q + r)) // 2


def radius_svg(groups: list[str], radius: int, smoke: bool = False) -> str:
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            d = _ring(q, r)
            if d > radius:
                continue
            if smoke:
                cells.append((q, r, "url(#hatch)", "T" if d == 0 else "", DARK))
            else:
                fill, colour = RING_FILL[d]
                cells.append((q, r, fill, groups[d] if d < len(groups) else "", colour))
    return _svg(cells, RADIUS_WIDTH[radius], HATCH if smoke else "")


def scatter_svg() -> str:
    cells = [(0, 0, DARK, "T", "#fff")] + [(q, r, "#fff", n, DARK) for (q, r), n in SCATTER.items()]
    return _svg(cells, 0.40)


def line_svg(groups: str, n: int = 5) -> str:
    return _svg([(q, 0, DARK, groups, "#fff") for q in range(n)], 0.96, flat=False)


def single_svg(groups: str) -> str:
    return _svg([(0, 0, DARK, groups, "#fff")], 0.42)


# --------------------------------------------------------------------------

@dataclass
class StrikeCard:
    name: str
    category: str                 # Air | Artillery | Minefield
    cost: int
    per: str = ""                 # "per hex", or blank for one use
    stats: dict = field(default_factory=dict)
    effect: str = ""
    book: str = ""                # "BT Core Rulebook p. 154"
    notes: str = ""               # for the app's detail panel; never printed
    # What the app and the force summary read from any card:
    source: str = "Official"
    approver: str = ""
    variant: str = "Standard"
    tons: float = 0
    vet_cost: None = None
    veteran: bool = False
    is_vet: bool = False
    grade_name: str = "—"
    current_skill: str = "—"

    @property
    def id(self) -> str:
        return strike_id(self.name)

    @property
    def title(self) -> str:
        """The name to show: "Light Density" alone doesn't say it's a minefield."""
        if self.category == "Minefield" and "minefield" not in self.name.lower():
            return f"{self.name} Minefield"
        return self.name

    @property
    def chassis(self) -> str:
        return self.title

    @property
    def support(self) -> str:
        return f'{self.stats["Support"]} Support' if self.stats.get("Support") else ""

    @property
    def unit_type(self) -> str:
        return self.support or self.category

    @property
    def current_cost(self) -> int:
        return self.cost

    @property
    def bv(self) -> int:
        return self.cost * BV_PER_POINT

    @property
    def groups(self) -> str:
        return self.stats.get("Groups", "")

    @property
    def not_attack(self) -> bool:
        return bool(self.stats.get("Not an attack"))

    @property
    def guided(self) -> bool:
        return "Needs" in self.stats

    def chip(self) -> str:
        if self.not_attack:
            return '<span class="grade">NOT AN ATTACK</span>'
        return f'<span class="grade vet">{"MINEFIELD" if self.category == "Minefield" else "STRIKE"}</span>'

    def diagrams(self) -> str:
        s, groups, out = self.stats, self.groups, []
        if s.get("Needs") == "TAG":
            out += [single_svg(groups), '<div class="cap">TAG-painted target</div>']
        elif "Radius" in s:
            radius, smoke = int(s["Radius"]), s.get("Type") == "Smoke"
            out.append(radius_svg([] if smoke else groups.split("/"), radius, smoke))
            out.append(f'<div class="cap">{"Smoke" if smoke else "Damage"} radius {radius}</div>')
        elif "line" in s.get("Area", ""):
            out += [line_svg(groups), '<div class="cap">Up to 5 hexes in a line</div>']
        elif groups not in ("", "none"):
            cap = "One hex" if self.category == "Minefield" else "Target hex"
            out += [single_svg(groups), f'<div class="cap">{cap}</div>']
        if "Scatter" in s:
            out += [scatter_svg(), f'<div class="cap">Scatter ({_e(s["Scatter"])})</div>']
        return "".join(out)

    def write_box(self) -> str:
        """The box for the player to write on, under the rules."""
        if self.category == "Artillery" and not self.guided:
            return ('<div class="box write"><span class="lbl">Target hex<i></i></span>'
                    '<span class="lbl" style="flex:.6">Turn<i></i></span>'
                    '<span class="used inl"><span class="lbl">Used</span><span class="bx"></span></span></div>')
        if self.category == "Minefield":
            track = "".join(f"<span>{n}</span>" for n in range(int(self.groups), 0, -1))
            return ('<div class="box write col"><span class="lbl">Hex<i></i></span>'
                    f'<div class="track" title="Groups left">{track}</div></div>')
        return ""

    def html(self) -> str:
        s = self.stats
        title = self.title
        long_name = " xlong" if len(title) > 24 else " long" if len(title) > 17 else ""
        per = f'<small class="per">/{_e(self.per.replace("per ", ""))}</small>' if self.per else ""
        blocks = []
        if "TN" in s:
            groups = self.groups if self.groups not in ("", "none") else "—"
            blocks.append('<div class="box big3">'
                          f'<div><span class="lbl">Target No.</span><span class="val">{_e(s["TN"])}+</span></div>'
                          f'<div><span class="lbl">Groups ×5</span><span class="val">{_e(groups)}</span></div>'
                          f'<div><span class="lbl">Type</span><span class="val">{_e(s.get("Type", "—"))}</span></div></div>')
        cover = [(k, s[k]) for k in COVER_KEYS if k in s]
        if cover:
            cells = "".join(f'<span class="lbl">{_e(k)}</span><span class="val">{_e(v)}+</span>' for k, v in cover)
            blocks.append(f'<div class="box"><div class="lbl">Cancels on</div><div class="tn">{cells}</div></div>')
        page = self.book.replace("BT Core Rulebook", "Core Rulebook")
        ref = f' <i class="ref">({_e(page)})</i>' if page else ""
        blocks.append(f'<div class="box rules"><b>RULES </b>{_e(self.effect)}{ref}</div>')
        write = self.write_box()
        blocks.append(write)
        used = "" if write else '<div class="used"><span class="lbl">Used</span><span class="bx"></span></div>'
        return (f'<div class="card strike"><div class="stripe"></div>'
                f'<div class="hd"><div class="names"><div class="variant">{_e(self.support) or "&nbsp;"}</div>'
                f'<div class="chassis{long_name}">{_e(title)}</div></div>'
                f'<div class="cost"><small>COST</small>{self.cost}{per}</div></div>'
                f'<div class="bd"><div class="stats">{"".join(blocks)}</div>'
                f'<div class="side">{self.chip()}<div class="diag">{self.diagrams()}</div>{used}</div></div>'
                '<div class="ft"><span class="kind">BATTLEFIELD SUPPORT</span>'
                '<span class="prov official">Source: BattleTech Core Rulebook</span></div></div>')


def card_from_row(row: dict) -> StrikeCard:
    """Raises ValueError, KeyError or TypeError if a number the card needs isn't one."""
    card = StrikeCard(
        name=row["name"].strip(), category=row["category"].strip(), cost=int(row["costR"]),
        per=(row.get("per") or "").strip(), stats=parse_stats(row.get("stats") or ""),
        effect=(row.get("effect") or "").strip(), book=(row.get("source") or "").strip(),
        notes=(row.get("notes") or "").strip())
    card.html()        # a bad radius or group count fails here, not while printing
    return card


def load(path: Path) -> tuple[dict, list[str]]:
    """{id: StrikeCard}, in file order, and the names of rows that were skipped."""
    cards, skipped = {}, []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if not (row.get("name") or "").strip():
                continue
            try:
                card = card_from_row(row)
            except (ValueError, KeyError, TypeError):
                skipped.append(row["name"].strip())
                continue
            cards[card.id] = card
    return cards, skipped
