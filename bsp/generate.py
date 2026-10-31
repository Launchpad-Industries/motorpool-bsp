# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Turn MegaMek units into asset specs.

Usage:
    python -m bsp.generate --mm-data PATH --out DIR [--name TEXT]

PATH is the mm-data checkout's data/mekfiles folder. Writes one .bfs file
per combat vehicle (or those whose name contains TEXT) plus index.csv."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from . import approvals, bfs
from .cost import cost
from .derive import derive_vehicle
from .megamek import Unit, load_all

CACHE = Path(__file__).resolve().parent.parent / "cache"


def default_skill(unit: Unit) -> int:
    """Skill 6 for Inner Sphere units; 5 for Clan front-line designs.
    Clan-built versions of Inner Sphere designs ("(Clan)", " C") stay at 6,
    matching the official cards. A targeting computer improves Skill by 1."""
    skill = 6
    model = f" {unit.model} "
    if unit.clan and "Clan" not in model and " C " not in model and not unit.model.endswith("C"):
        skill = 5
    if any("targeting computer" in it.lower() or "targetingcomputer" in it.lower()
           for _, it in unit.weapons()):
        skill -= 1
    return skill


def spec_for(unit: Unit, weapons: dict):
    sp = derive_vehicle(unit, weapons)
    skill = 8 if sp.artillery else default_skill(unit)   # official artillery cards
    if skill < 6 and "TC" not in sp.specials and any(
            "targeting" in it.lower() for _, it in unit.weapons()):
        sp.specials.append("TC")
    c = cost(sp.mp, sp.tmm, sp.damage, sp.range, skill, sp.check,
             sp.indirect, sp.specials)
    return sp, skill, c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mm-data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--name", default="")
    a = ap.parse_args(argv)
    weapons = json.loads((CACHE / "weapons.json").read_text())
    units = [u for u in load_all(a.mm_data, folders=("vehicles",))
             if u.unit_type in ("Tank", "VTOL") and a.name.lower() in u.full_name.lower()]
    a.out.mkdir(parents=True, exist_ok=True)
    approved = approvals.load()
    rows = []
    for u in units:
        sp, skill, c = spec_for(u, weapons)
        entry = approved.get(u.full_name)
        rec = bfs.to_bfs(u, sp, c, skill, provenance="approved" if entry else "auto")
        if entry:
            rec["approvedBy"], rec["approvedOn"] = entry["by"], entry["on"]
            moved = approvals.drift(entry, approvals.snapshot(sp, skill, c))
            if moved:
                rec["notes"].append("drift since approval: " + ", ".join(moved))
        fn = "".join(ch if ch.isalnum() or ch in " ()-_." else "_" for ch in u.full_name) + ".bfs"
        (a.out / fn).write_text(bfs.dumps(rec), encoding="utf-8")
        rows.append({"name": u.full_name, "mul_id": u.mul_id or "", "tons": u.tonnage,
                     "mp": f"{sp.mp}{sp.mode}", "tmm": sp.tmm,
                     "range": "/".join(map(str, sp.range)) if sp.range else "-",
                     "damage": f"{sp.damage[0]}x{sp.damage[1]}" if sp.damage else "-",
                     "skill": f"{skill}" if c["veteran"] is None else f"{skill} ({skill - 1})", "check": sp.check,
                     "threshold": sp.threshold,
                     "cost": f"{c['regular']}" if c["veteran"] is None else f"{c['regular']} ({c['veteran']})",
                     "specials": ", ".join(sorted(set(sp.specials))) or "-",
                     "file": fn})
    with open(a.out / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["name"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} specs written to {a.out}")


if __name__ == "__main__":
    main()
