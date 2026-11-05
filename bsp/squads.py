# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Which battle armor squad sizes the app lists.

MegaMek has a file per squad size for nearly every design. The standard sizes
are 5 suits for Clan, 4 for Inner Sphere and 6 for ComStar, but the data has
nothing that says which designs are ComStar's: no faction field, and almost
every six-suit file's write-up mentions ComStar. So every Inner Sphere design
keeps both 4 and 6 for now. A design with none of its standard sizes (one-suit
interface armor, a named custom suit) keeps the sizes it has."""

from __future__ import annotations

import re
from collections import defaultdict

from .megamek import Unit

CLAN_SIZES = {5}
INNER_SPHERE_SIZES = {4, 6}


def design_name(unit: Unit) -> str:
    """The unit's name without its squad size tag: "Elemental Battle Armor [MG]"."""
    return re.sub(r"\s*\(Sq[dn]\s*\d\)", "", unit.full_name).strip()


def standard_squads(units: list[Unit]) -> list[Unit]:
    designs = defaultdict(list)
    for u in units:
        designs[design_name(u)].append(u)
    kept = []
    for versions in designs.values():
        wanted = CLAN_SIZES if versions[0].clan else INNER_SPHERE_SIZES
        kept += [u for u in versions if u.troopers in wanted] or versions
    return kept
