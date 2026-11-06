# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Which battle armor squads the app lists.

MegaMek has a file per squad size for nearly every design, with no faction in
the unit file. data/battle_armor_squads.yaml names the ones to list: squads a
faction actually fields, at standard sizes (tools/battle_armor_list.py)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .megamek import Unit

ROOT = Path(__file__).resolve().parent.parent
LIST_FILE = ROOT / "data" / "battle_armor_squads.yaml"


def design_name(unit: Unit) -> str:
    """The unit's name without its squad size tag: "Elemental Battle Armor [MG]"."""
    return re.sub(r"\s*\(Sq[dn]\s*\d\)", "", unit.full_name).strip()


def squad_names() -> set[str]:
    """Full names of the battle armor squads to list."""
    return set(yaml.safe_load(LIST_FILE.read_text(encoding="utf-8"))["squads"])


def listed_squads(units: list[Unit]) -> list[Unit]:
    names = squad_names()
    return [u for u in units if u.full_name in names]
