# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Battle armor rules (agreed with Will 4 Nov 2026), checked against the
official Elemental cards. Skipped when MegaMek data isn't downloaded."""

import json
import os
from pathlib import Path

import pytest

from bsp.derive import squad_hits

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))
CACHE = ROOT / "cache"
need_data = pytest.mark.skipif(not (MM.exists() and (CACHE / "weapons.json").exists()),
                               reason="MegaMek data not downloaded")


def test_squad_hits():
    assert squad_hits(1) == 1.0
    assert round(squad_hits(4), 2) == 2.64
    assert round(squad_hits(5), 2) == 3.17


def _card(file_name):
    from bsp.generate import spec_for
    from bsp.megamek import load_unit
    path = next((MM / "battlearmor").rglob(file_name.replace("[", "?").replace("]", "?")))
    sp, skill, c = spec_for(load_unit(path), json.loads((CACHE / "weapons.json").read_text()))
    return sp, skill, c


@need_data
def test_elemental_mg_matches_official_card_stats():
    # Official generic Elemental (MegaMek links it to [MG] Sqd5): 3j, TMM 2,
    # 1/2/3, 6x2, Skill 5, Check 9, Threshold 5. Cost 19 by the formula (card 17).
    sp, skill, c = _card("Elemental BA [MG] (Sqd5).blk")
    assert (sp.mp, sp.mode, sp.tmm, sp.range, sp.damage) == (3, "j", 2, (1, 2, 3), (6, 2))
    assert (skill, sp.check, sp.threshold) == (5, 9, 5)
    assert {"Mechanized", "Nimble", "Spotter", "Swarm"} <= set(sp.specials)
    assert c["regular"] == 19


@need_data
def test_elemental_iii_stealth_and_cost():
    # Stealth +1 TMM; the generated card's cost equals the official 26 (30).
    sp, skill, c = _card("Elemental III BA [AP Gauss](Sqd5).blk")
    assert (sp.tmm, sp.range, sp.damage, sp.check) == (3, (3, 6, 9), (10, 2), 9)
    assert (c["regular"], c["veteran"]) == (26, 30)


@need_data
def test_is_standard_ba_check_and_skill():
    sp, skill, c = _card("IS Standard BA [MG] (Sqd4).blk")
    assert (sp.damage, skill, sp.check) == ((5, 2), 6, 8)
