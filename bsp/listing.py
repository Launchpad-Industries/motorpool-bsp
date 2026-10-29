# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Spreadsheet-friendly list of asset specs.

One row per asset, laid out like the All_BSP tab (chassis and variant in
separate columns, range split into short/medium/long so spreadsheets don't
read "6/12/18" as a date). Official cards get an Official row; when the
calculated spec differs significantly, a Calculated row follows it.

Usage:
    python -m bsp.listing --mm-data PATH --out FILE.csv [--official FILE.tsv]

The official TSV is an export of the owner's spreadsheet and is never
stored in this repository."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import yaml

from .generate import spec_for
from .match import best_match
from .megamek import Unit, load_all, load_unit

ROOT = Path(__file__).resolve().parent.parent

COLUMNS = ["Chassis", "Variant", "Type", "Source", "Cost (R)", "Cost (V)",
           "Skill", "MP", "Move", "TMM", "Short", "Medium", "Long", "Dmg",
           "Check", "Threshold", "Specials", "Differs", "Tons", "MUL ID",
           "MegaMek unit", "Notes"]

# What counts as a significant difference between printed and calculated.
SIGNIFICANT = {"cost_points": 3, "damage_share": 0.15}


def dmg_text(per_hit, hits) -> str:
    """Newer-card notation: damage per group, 'd', then number of groups."""
    if not per_hit:
        return "-"
    return f"{int(per_hit)}dx{int(hits)}"


def split_variant(unit: Unit) -> str:
    v = unit.model.strip()
    if v.startswith("(") and v.endswith(")") and v.count("(") == 1:
        v = v[1:-1]
    return v or "Standard"


def _type(unit: Unit) -> str:
    return {"BattleArmor": "Battle Armor", "Infantry": "Infantry",
            "GunEmplacement": "Emplacement"}.get(unit.unit_type, "Vehicle")


def calc_row(unit: Unit, weapons: dict, chassis=None, variant=None) -> dict:
    sp, skill, c = spec_for(unit, weapons)
    rng = sp.range or (("Arrow", "-", "-") if sp.arrow else
                       ("Artillery", "-", "-") if sp.artillery else ("-", "-", "-"))
    return {
        "Chassis": chassis or unit.name, "Variant": variant or split_variant(unit),
        "Type": _type(unit), "Source": "Calculated",
        "Cost (R)": c["regular"], "Cost (V)": "-" if c["veteran"] is None else c["veteran"],
        "Skill": skill, "MP": sp.mp, "Move": sp.mode, "TMM": sp.tmm,
        "Short": rng[0], "Medium": rng[1], "Long": rng[2],
        "Dmg": dmg_text(*(sp.damage or (0, 0))), "Check": sp.check,
        "Threshold": sp.threshold,
        "Specials": ", ".join(sorted(set(sp.specials))) or "-",
        "Differs": "", "Tons": unit.tonnage, "MUL ID": unit.mul_id or "",
        "MegaMek unit": unit.full_name, "Notes": "; ".join(sp.notes),
        "_total": (sp.damage[0] * sp.damage[1]) if sp.damage else 0,
        "_if": sp.indirect,
    }


def official_row(r: dict, unit: Unit | None) -> dict:
    m = re.match(r"(\d+)(?:x(\d+))?$", r["dmg"].strip())
    rg = re.match(r"(\d+)/(\d+)/(\d+)", r["range"])
    ifm = re.search(r"IF(\d+)", r["specials"])
    variant = r["variant"].strip()
    if variant.startswith("(") and variant.endswith(")"):
        variant = variant[1:-1]
    return {
        "Chassis": r["name"], "Variant": variant or "Standard", "Type": r["type"],
        "Source": "Official", "Cost (R)": r["costR"], "Cost (V)": r["costV"] or "-",
        "Skill": r["skill"], "MP": r["mp"], "Move": r["mtype"], "TMM": r["tmm"],
        "Short": rg.group(1) if rg else r["range"], "Medium": rg.group(2) if rg else "-",
        "Long": rg.group(3) if rg else "-",
        "Dmg": dmg_text(int(m.group(1)), int(m.group(2) or 1)) if m else r["dmg"],
        "Check": r["check"], "Threshold": r["thr"], "Specials": r["specials"],
        "Differs": "", "Tons": unit.tonnage if unit else "",
        "MUL ID": (unit.mul_id or "") if unit else "",
        "MegaMek unit": unit.full_name if unit else "(generic card)", "Notes": "",
        "_total": int(m.group(1)) * int(m.group(2) or 1) if m else 0,
        "_if": int(ifm.group(1)) if ifm else 0,
    }


def differences(off: dict, calc: dict, sig=SIGNIFICANT) -> list[str]:
    out = []
    for k in ("MP", "TMM", "Skill", "Check", "Threshold"):
        if str(off[k]) != str(calc[k]):
            out.append(k)
    if (str(off["Short"]), str(off["Long"])) != (str(calc["Short"]), str(calc["Long"])) \
            and str(off["Short"]).isdigit():
        out.append("Range")
    t0, t1 = off["_total"], calc["_total"]
    if t0 and abs(t1 - t0) > max(1, sig["damage_share"] * t0):
        out.append("Dmg")
    if off["_if"] != calc["_if"]:
        out.append("IF")
    if str(off["Cost (R)"]).isdigit() and abs(int(off["Cost (R)"]) - calc["Cost (R)"]) >= sig["cost_points"]:
        out.append("Cost")
    return out


def build(mm_root: Path, official_tsv: Path | None) -> list[dict]:
    weapons = json.loads((ROOT / "cache" / "weapons.json").read_text())
    links = yaml.safe_load((ROOT / "data" / "card_links.yaml").read_text())
    vehicles = [u for u in load_all(mm_root, folders=("vehicles",))
                if u.unit_type in ("Tank", "VTOL")]
    rows, carded = [], set()
    chassis_name: dict[str, str] = {}     # MegaMek chassis -> card chassis
    if official_tsv:
        for r in csv.DictReader(open(official_tsv, encoding="utf-8"), delimiter="\t"):
            key = f"{r['name']}|{r['variant']}"
            unit = None
            if key in links.get("generic", []):
                unit = None
            elif key in links["links"] or key in links["review"]:
                unit = load_unit(mm_root / (links["links"].get(key) or links["review"][key]))
            elif r["type"] == "Vehicle":
                unit = best_match(r, vehicles).unit
            off = official_row(r, unit)
            if key in links["review"]:
                off["Notes"] = "MegaMek link needs review"
            rows.append(off)
            if unit is None or unit.unit_type not in ("Tank", "VTOL"):
                continue
            carded.add(unit.path)
            chassis_name.setdefault(unit.name, set()).add(off["Chassis"])
            calc = calc_row(unit, weapons, off["Chassis"], off["Variant"])
            diff = differences(off, calc)
            if diff:
                off["Differs"] = calc["Differs"] = ", ".join(diff)
                rows.append(calc)
    # File uncarded MegaMek variants under the card's chassis name, but only
    # when the names correspond one-to-one and no card row would be shadowed.
    sources: dict[str, set] = {}
    for mm, cards in chassis_name.items():
        for c in cards:
            sources.setdefault(c, set()).add(mm)
    rename = {mm: next(iter(c)) for mm, c in chassis_name.items()
              if len(c) == 1 and len(sources[next(iter(c))]) == 1}
    taken = {(r["Chassis"].lower(), r["Variant"].lower()) for r in rows}
    for u in vehicles:
        if u.path in carded:
            continue
        row = calc_row(u, weapons, rename.get(u.name))
        if (row["Chassis"].lower(), row["Variant"].lower()) in taken:
            row = calc_row(u, weapons)
        rows.append(row)
    order = {"Official": 0, "Approved": 1, "Calculated": 2}
    rows.sort(key=lambda x: (x["Chassis"].lower(), x["Variant"].lower(), order[x["Source"]]))
    return rows


def write(rows: list[dict], out: Path):
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the asset spec list as CSV")
    ap.add_argument("--mm-data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--official", type=Path, help="TSV export of the official cards")
    a = ap.parse_args(argv)
    rows = build(a.mm_data, a.official)
    write(rows, a.out)
    n = {s: sum(1 for r in rows if r["Source"] == s) for s in ("Official", "Calculated")}
    print(f"{len(rows)} rows ({n['Official']} official, {n['Calculated']} calculated) -> {a.out}")


if __name__ == "__main__":
    main()
