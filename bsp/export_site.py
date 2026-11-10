# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Export Motor Pool's unit list for the public static site.

Writes ``site/data/units.json`` in the format described in
``docs/site-data-schema.md``, and copies the MegaMek unit sprites the cards
use into ``site/img/units/`` (CC BY-NC-SA 4.0, credited). The owner's own
images folder is never exported: its rights aren't known here.

Usage:
    python -m bsp.export_site                       # official values where a card exists
    python -m bsp.export_site --no-official         # calculated values everywhere
    python -m bsp.export_site --out site/data/units.json

Units are the ones Motor Pool lists (vehicles, listed battle armor squads,
support vehicles with an official card, and generic official cards), plus the
strike cards from bsp-options.tsv in their own list, with their hex diagrams
as SVG files in ``site/img/strikes/``.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from . import __version__
from .art import SPRITE_CREDIT
from .cards import Card

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DEFAULT_OUT = SITE / "data" / "units.json"
IMG_DIR = "img/units"          # relative to site/

SCHEMA_VERSION = 1
DISCLAIMER = ("Unofficial fan-made content, not affiliated with, endorsed by, or sponsored by "
              "The Topps Company, Inc., Catalyst Game Labs, or InMediaRes Productions, LLC. "
              "BattleTech is a registered trademark of The Topps Company, Inc.")
CREDITS = ["Unit data and sprites: MegaMek Data, (C) The MegaMek Team (CC BY-NC-SA 4.0)",
           "Calculated cards are derived from MegaMek Data and shared under CC BY-NC-SA 4.0"]

MOTIVES = {"t": "Tracked", "w": "Wheeled", "h": "Hover", "v": "VTOL", "g": "WiGE",
           "n": "Naval", "f": "Foot", "j": "Jump"}
PROVENANCE = {"Official": "official", "Approved": "approved", "Calculated": "calculated"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def move_text(c: Card) -> str:
    mode = "" if c.mode in ("na", "-", None) else c.mode
    return f"{c.mp}{mode}"


def damage_text(c: Card) -> str:
    return (c.damage or "-").replace("×", "x")


def tech_base(raw: dict) -> str | None:
    t = ((raw or {}).get("type") or [""])[0].lower()
    if "mixed" in t:
        return "Mixed"
    if "clan" in t:
        return "Clan"
    return "IS" if t else None


def spec_of(c: Card) -> dict:
    specials = list(c.specials)
    if isinstance(c.range, (tuple, list)) and len(c.range) == 3:
        rng = [int(x) for x in c.range]
    else:
        # "Arrow" / "Artillery": no range bands; keep the word as a special.
        rng = [0, 0, 0]
        if c.range and c.range != "-" and c.range not in specials:
            specials.append(c.range)
    indirect = 0
    for s in specials:
        m = re.fullmatch(r"IF(\d+)", s.strip())
        if m:
            indirect = int(m.group(1))
    return {"move": move_text(c), "tmm": c.tmm,
            "skill": {"regular": c.skill, "veteran": c.vet_skill if c.vet_cost is not None else None},
            "range": rng, "damage": damage_text(c), "indirect": indirect,
            "check": c.check, "threshold": c.threshold, "specials": specials}


def unit_entry(c: Card, name: str, *, motive: str | None = None, tonnage=None, tech=None,
               year=None, mul_id=None, has_official: bool = False, approval: dict | None = None,
               art: dict | None = None) -> dict:
    """One schema Unit (without its id) from a card."""
    prov = PROVENANCE.get(c.source, "calculated")
    u = {"name": name, "type": c.unit_type}
    if isinstance(tonnage, float) and tonnage.is_integer():
        tonnage = int(tonnage)
    for k, v in (("motive", motive), ("tonnage", tonnage or None), ("techBase", tech),
                 ("introYear", year), ("mulId", mul_id)):
        if v is not None:
            u[k] = v
    u["provenance"] = prov
    if prov == "approved":
        u["approvedBy"] = c.approver
        if approval and approval.get("on"):
            u["approvedOn"] = str(approval["on"])
        u["verified"] = bool(c.verified)
    if has_official and prov != "official":
        u["hasOfficialCard"] = True
    u["spec"] = spec_of(c)
    u["cost"] = {"regular": c.cost, "veteran": c.vet_cost}
    if art:
        u["art"] = art
    if prov == "approved" and c.drift:
        u["notes"] = "The calculation rules have changed since this card was approved: " + ", ".join(c.drift) + "."
    return u


def assign_ids(entries: list[tuple[str, dict]]) -> list[dict]:
    """entries: (tie-break key, unit). Ids are name slugs; a clash gets -2, -3, ...
    in tie-break key order so the same data always gives the same ids."""
    seen: dict[str, int] = {}
    out = []
    for _, u in sorted(entries, key=lambda e: (slug(e[1]["name"]), e[0])):
        base = slug(u["name"]) or "unit"
        seen[base] = seen.get(base, 0) + 1
        out.append({"id": base if seen[base] == 1 else f"{base}-{seen[base]}", **u})
    out.sort(key=lambda u: (u["name"].lower(), u["id"]))
    return out


class SpriteCopier:
    """Copies (trimmed) MegaMek sprites into site/img/units/, once each."""

    def __init__(self, units_dir: Path | None, site: Path):
        self.units_dir, self.dest = units_dir, site / IMG_DIR
        self.written: dict[Path, str] = {}

    def __call__(self, path: Path | None, source: str) -> dict | None:
        if not path or source != "sprite" or not self.units_dir:
            return None       # only MegaMek sprites; never the owner's own images
        if path not in self.written:
            rel = path.resolve().relative_to(self.units_dir.resolve())
            name = slug(str(rel.with_suffix(""))) + ".png"
            self.dest.mkdir(parents=True, exist_ok=True)
            (self.dest / name).write_bytes(trimmed_png(path))
            self.written[path] = f"{IMG_DIR}/{name}"
        return {"src": self.written[path], "credit": SPRITE_CREDIT}

    def remove_unused(self):
        if not self.dest.exists():
            return
        keep = {Path(p).name for p in self.written.values()}
        for f in self.dest.iterdir():
            if f.is_file() and f.name not in keep:
                f.unlink()


def trimmed_png(path: Path) -> bytes:
    """The sprite cropped to its visible pixels (sprites sit in an 84x72 hex)."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    box = im.getchannel("A").getbbox()
    if box:
        im = im.crop(box)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


STRIKE_IMG_DIR = "img/strikes"     # relative to site/
SVG_FONT = 'font-family="Oswald, \'Arial Narrow\', sans-serif"'


def standalone_svg(svg: str) -> str:
    """A card diagram as its own file: an SVG namespace, and the printed width
    as an attribute (the card's inline style doesn't apply inside an <img>)."""
    m = re.search(r'style="width:([\d.]+)in;height:auto;display:block"', svg)
    if m:
        svg = svg.replace(m.group(0), f'xmlns="http://www.w3.org/2000/svg" width="{m.group(1)}in"', 1)
    elif "xmlns=" not in svg:
        svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    return svg.replace('font-family="Oswald"', SVG_FONT)


def strike_entry(c, write_svg=None) -> dict:
    """One schema Strike from a strikes.StrikeCard. write_svg(name, svg) -> src
    saves a diagram file; without it, diagrams get their would-be path."""
    s = c.stats
    sid = "strike-" + slug(c.title)
    out = {"id": sid, "name": c.title, "category": c.category}
    if c.support:
        out["support"] = c.support
    out["chip"] = "NOT AN ATTACK" if c.not_attack else "MINEFIELD" if c.category == "Minefield" else "STRIKE"
    out["cost"] = c.cost
    if c.per:
        out["per"] = c.per
    if str(s.get("TN", "")).isdigit():
        out["tn"] = int(s["TN"])
    for key, field in (("Groups", "groups"), ("Type", "attackType"), ("Scatter", "scatter"), ("Needs", "needs")):
        if isinstance(s.get(key), str) and s[key]:
            out[field] = s[key]
    if str(s.get("Radius", "")).isdigit():
        out["radius"] = int(s["Radius"])
    if c.cancels:
        out["cancels"] = [{"strike": k, "tn": int(v)} for k, v in c.cancels]
    out["effect"] = c.effect
    if c.rules_ref:
        out["rulesRef"] = c.rules_ref
    if c.write_on:
        out["writeOn"] = c.write_on
    diagrams = []
    for n, (svg, caption) in enumerate(c.diagram_parts(), 1):
        name = f"{sid.removeprefix('strike-')}-{n}.svg"
        src = write_svg(name, standalone_svg(svg)) if write_svg else f"{STRIKE_IMG_DIR}/{name}"
        diagrams.append({"src": src, "caption": caption})
    out["diagrams"] = diagrams
    if c.notes:
        out["notes"] = c.notes
    out["source"] = "BattleTech Core Rulebook"
    return out


def export_strikes(cards, site: Path) -> list[dict]:
    dest = site / STRIKE_IMG_DIR
    dest.mkdir(parents=True, exist_ok=True)
    written = set()

    def write_svg(name: str, svg: str) -> str:
        (dest / name).write_text(svg, encoding="utf-8")
        written.add(name)
        return f"{STRIKE_IMG_DIR}/{name}"

    out = [strike_entry(c, write_svg) for c in cards]
    for f in dest.iterdir():
        if f.is_file() and f.name not in written:
            f.unlink()
    ids = [s["id"] for s in out]
    if len(ids) != len(set(ids)):
        raise SystemExit("Two strike cards have the same name; ids would clash.")
    return out          # file order, as in Motor Pool: air, artillery, minefields


def git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def build(cat, official: bool = True, site: Path = SITE) -> dict:
    """The site data for a Motor Pool catalog (bsp.app.Catalog)."""
    copy_art = SpriteCopier(cat.art.units_dir, site)
    entries = []
    for u in cat.units:
        off = cat.official_card(u)
        card = off if (off and official) else cat.calculated(u)
        year = (u.raw.get("year") or [""])[0]
        entry = unit_entry(
            card, u.full_name, motive=MOTIVES.get(card.mode), tonnage=u.tonnage,
            tech=tech_base(u.raw), year=int(year) if str(year).isdigit() else None,
            mul_id=u.mul_id, has_official=off is not None,
            approval=cat.approved.get(u.full_name) if card.source == "Approved" else None,
            art=copy_art(*cat.art.find(u)))
        entries.append((u.path, entry))
    if official:
        # Generic official cards (infantry, emplacements...) have no calculated
        # version, so they're only exported with official values.
        for i, row in cat.generic.items():
            c = cat.generic_card(i, image=False)
            name = cat.generic_row(i)["name"]
            entries.append((i, unit_entry(c, name, motive=MOTIVES.get(c.mode),
                                          tech=cat.generic_row(i)["tech"],
                                          art=copy_art(*cat.art.find_generic(row["name"], row["type"])))))
    copy_art.remove_unused()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedOn": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": f"bsp-card-generator {__version__} (git {git_rev()})",
        "disclaimer": DISCLAIMER,
        "credits": CREDITS + (["Official card values: the official Battlefield Support asset cards "
                               "(game statistics only; no official art, logos or rules text)"]
                              if official else []),
        "units": assign_ids(entries),
        "strikes": export_strikes(cat.strikes.values(), site),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export Motor Pool's units for the public site.")
    ap.add_argument("--no-official", action="store_true",
                    help="use calculated values even where an official card exists")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output file (default {DEFAULT_OUT})")
    a = ap.parse_args(argv)
    from .app import Catalog, load_settings
    cat = Catalog(load_settings())
    site = a.out.resolve().parent.parent       # .../site/data/units.json -> .../site
    data = build(cat, official=not a.no_official, site=site)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for u in data["units"]:
        counts[u["provenance"]] = counts.get(u["provenance"], 0) + 1
    print(f"Wrote {len(data['units'])} units "
          f"({', '.join(f'{n} {k}' for k, n in sorted(counts.items()))}) and "
          f"{len(data['strikes'])} strike cards to {a.out}; art in {site / IMG_DIR}, "
          f"diagrams in {site / STRIKE_IMG_DIR}")
    if cat.strikes_skipped:
        print(f"Skipped strike cards (numbers not readable): {', '.join(cat.strikes_skipped)}")


if __name__ == "__main__":
    main()
