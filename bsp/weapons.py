# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
#
# Weapon statistics are read from MegaMek's source code
# (https://github.com/MegaMek/megamek, GPL v3) at run time and cached
# locally; no MegaMek code is copied into this repository.
"""Build a weapon stats table (damage, ranges, BV, rack size, average
damage) from MegaMek's weapon class definitions."""

from __future__ import annotations

import json
import re
from pathlib import Path

_CLASS = re.compile(r"public\s+(?:abstract\s+)?class\s+(\w+)\s+extends\s+(\w+)")
_ASSIGN = re.compile(r"^\s*(?:this\.)?(\w+)\s*=\s*([^;]+);", re.M)
_CALL = re.compile(r'(?:this\.)?(setInternalName|addLookupName)\(\s*("[^"]*"|(?:this\.)?name)\s*\)')
_FLAG = re.compile(r"\b(F_[A-Z_]+)\b")

FIELDS = ("name", "damage", "shortRange", "mediumRange", "longRange",
          "extremeRange", "minimumRange", "bv", "heat", "rackSize",
          "shortAV", "medAV", "longAV", "extAV", "tonnage", "ammoType")


def _literal(v: str):
    v = v.strip()
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v   # a constant like DAMAGE_BY_CLUSTERTABLE or WEAPON_NA


def _parse_file(p: Path) -> dict | None:
    src = p.read_text(encoding="utf-8", errors="replace")
    m = _CLASS.search(src)
    if not m:
        return None
    cls, parent = m.groups()
    # Only look inside the no-arg constructor.
    ctor = re.search(rf"public\s+{cls}\s*\(\s*\)\s*\{{(.*?)\n    \}}", src, re.S)
    body = ctor.group(1) if ctor else ""
    vals = {k: _literal(v) for k, v in _ASSIGN.findall(body) if k in FIELDS}
    names = []
    for fn, arg in _CALL.findall(body):
        names.append(vals.get("name") if arg.endswith("name") else arg.strip('"'))
    flags = sorted(set(_FLAG.findall(body)))
    return {"class": cls, "parent": parent, "vals": vals, "names": names,
            "flags": flags, "abstract": "abstract class" in src[: m.end()]}


def build_table(weapons_src: Path) -> dict[str, dict]:
    """Return {lookup name: stats} for every concrete weapon class."""
    classes = {}
    for p in weapons_src.rglob("*.java"):
        info = _parse_file(p)
        if info:
            classes[info["class"]] = info

    def resolved(cls: str, seen=()) -> dict:
        info = classes.get(cls)
        if not info or cls in seen:
            return {}
        merged = resolved(info["parent"], seen + (cls,))
        merged.update(info["vals"])
        merged["_flags"] = sorted(set(merged.get("_flags", [])) | set(info["flags"]))
        return merged

    table: dict[str, dict] = {}
    display = []
    for cls, info in classes.items():
        if info["abstract"] or not info["names"] and "name" not in info["vals"]:
            continue
        stats = resolved(cls)
        stats["class"] = cls
        stats["clan"] = cls.startswith("CL")
        for k in info["names"]:              # internal and lookup names
            if k:
                table[k] = stats
        display.append((stats.get("name"), stats))
    # Display names ("LRM 20") are shared by IS and Clan versions; vehicle
    # files use the display name for the Inner Sphere version, so IS wins.
    for nm, stats in sorted(display, key=lambda x: not x[1]["clan"]):
        if isinstance(nm, str) and nm not in table or (isinstance(nm, str) and table[nm]["clan"] and not stats["clan"]):
            table[nm] = stats
    return table


def load_table(cache: Path, weapons_src: Path | None = None) -> dict[str, dict]:
    if cache.exists():
        return json.loads(cache.read_text())
    if weapons_src is None:
        raise FileNotFoundError(cache)
    table = build_table(weapons_src)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(table, indent=1, sort_keys=True))
    return table
