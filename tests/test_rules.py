# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Checks for the rules. Tests that need MegaMek data are skipped when the
data hasn't been downloaded (set MM_DATA to mm-data/data/mekfiles)."""

import json
import os
from pathlib import Path

import pytest

from bsp.cost import cost, check_value
from bsp.derive import tmm_for_mp

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))
CACHE = ROOT / "cache"


def test_tmm_table():
    assert [tmm_for_mp(m) for m in (0, 2, 3, 5, 7, 10, 18, 25)] == [0, 0, 1, 2, 3, 4, 5, 6]


def test_check_value_rule():
    assert check_value(7) == 75
    assert check_value(9) == 225
    assert round(check_value(6), 1) == 50.0


def test_veteran_uses_unrounded_cost():
    c = cost(8, 3, (5, 4), (3, 6, 9), 6, 7, 2, ["APC1", "IF2"])
    assert c["veteran"] == int(c["unrounded"] * 1.15 + 0.5)


@pytest.mark.skipif(not (MM.exists() and (CACHE / "weapons.json").exists()
                         and (CACHE / "ammo.json").exists()),
                    reason="MegaMek data not downloaded")
def test_hephaestus_bv_matches_techmanual_example():
    from bsp.bv import vehicle_bv
    from bsp.megamek import load_all
    weapons = json.loads((CACHE / "weapons.json").read_text())
    ammo = json.loads((CACHE / "ammo.json").read_text())
    unit = next(u for u in load_all(MM, folders=("vehicles",))
                if u.full_name == "Hephaestus Scout Tank Prime")
    assert vehicle_bv(unit, weapons, ammo) == 777   # TechManual p. 308
