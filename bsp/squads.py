# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Which battle armor squad sizes the app lists.

MegaMek has a file per squad size for nearly every design. The standard sizes
are 5 suits for Clan, 4 for Inner Sphere, and 6 for ComStar and Word of Blake.
Unit files don't say which designs those are, so the six-suit versions to list
are named in data/six_suit_squads.yaml, taken from MegaMek's force generator. A
design with none of its standard sizes (one-suit interface armor, a named custom
suit) keeps the sizes it has."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml

from .megamek import Unit

ROOT = Path(__file__).resolve().parent.parent
SIX_SUIT_LIST = ROOT / "data" / "six_suit_squads.yaml"
CLAN_SIZE = 5
INNER_SPHERE_SIZE = 4


def design_name(unit: Unit) -> str:
    """The unit's name without its squad size tag: "Elemental Battle Armor [MG]"."""
    return re.sub(r"\s*\(Sq[dn]\s*\d\)", "", unit.full_name).strip()


def six_suit_squads() -> set[str]:
    """Full names of the Inner Sphere six-suit versions to list."""
    return set(yaml.safe_load(SIX_SUIT_LIST.read_text(encoding="utf-8"))["six_suit"])


def standard_squads(units: list[Unit], six_suit: set[str] | None = None) -> list[Unit]:
    six_suit = six_suit_squads() if six_suit is None else six_suit
    designs = defaultdict(list)
    for u in units:
        designs[design_name(u)].append(u)
    kept = []
    for versions in designs.values():
        size = CLAN_SIZE if versions[0].clan else INNER_SPHERE_SIZE
        kept += [u for u in versions if u.troopers == size or (not u.clan and u.full_name in six_suit)] or versions
    return kept
