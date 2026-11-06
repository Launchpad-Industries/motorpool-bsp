# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Rebuild data/battle_armor_squads.yaml, the battle armor cards the app lists.

    python tools/battle_armor_list.py

Run it after refreshing MegaMek data if you want new designs listed. It
overwrites the file, so hand edits to the list are lost.

A squad is listed if MegaMek's force generator gives it to any faction in any
era, at a standard size: 5 suits for Clan, 4 or 6 for Inner Sphere. A design
available only at another size is listed at that size. The force generator files
are read from mm-data's git history, so they don't need to be checked out."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bsp.megamek import load_all  # noqa: E402
from bsp.squads import LIST_FILE, design_name  # noqa: E402

MM = ROOT / "mm-data"
FOLDER = "data/forcegenerator/"
HEADER = """\
# BSP Card Generator
# The battle armor cards Motor Pool lists: squads MegaMek's force generator gives
# to at least one faction, at standard sizes (Clan 5, Inner Sphere 4 or 6; a
# design available only at another size keeps that size). Names are MegaMek unit
# names. Built by tools/battle_armor_list.py, which overwrites hand edits.

squads:
"""


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(MM), *args], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def available_squads() -> set[tuple[str, str]]:
    """(chassis, model) of every battle armor squad with a faction in any era."""
    found = set()
    for path in git("ls-tree", "--name-only", "HEAD", FOLDER).splitlines():
        if Path(path).stem.isdigit():
            for c in ET.fromstring(git("show", f"HEAD:{path}").encode("utf-8")).iter("chassis"):
                if c.get("unitType") == "BattleArmor":
                    for m in c.iter("model"):
                        if ":" in (m.findtext("availability") or ""):
                            found.add((c.get("name"), m.get("name") or ""))
    return found


def choose(units: list, available: set[tuple[str, str]]) -> list[str]:
    designs = defaultdict(list)
    for u in units:
        if (u.name, u.model) in available:
            designs[design_name(u)].append(u)
    names = []
    for versions in designs.values():
        sizes = {5} if versions[0].clan else {4, 6}
        names += [u.full_name for u in versions if u.troopers in sizes] or [u.full_name for u in versions]
    return sorted(names)


def main():
    units = [u for u in load_all(MM / "data" / "mekfiles", folders=("battlearmor",))
             if u.unit_type == "BattleArmor"]
    names = choose(units, available_squads())
    LIST_FILE.write_text(HEADER + "".join(f'  - "{n}"\n' for n in names), encoding="utf-8", newline="\n")
    print(f"{len(names)} of {len(units)} battle armor squads listed in {LIST_FILE}")


if __name__ == "__main__":
    main()
