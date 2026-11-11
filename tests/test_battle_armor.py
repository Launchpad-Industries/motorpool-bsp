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
    # 1/2/3, 6x2, Skill 5, Check 9, Threshold 5. Cost 21 by the formula (card 17):
    # Skill 5 is priced like Veteran, x1.15 on the whole cost (Will, 10 Nov).
    sp, skill, c = _card("Elemental BA [MG] (Sqd5).blk")
    assert (sp.mp, sp.mode, sp.tmm, sp.range, sp.damage) == (3, "j", 2, (1, 2, 3), (6, 2))
    assert (skill, sp.check, sp.threshold) == (5, 9, 5)
    assert {"Mechanized", "Nimble", "Spotter", "Swarm"} <= set(sp.specials)
    assert c["regular"] == 21


@need_data
def test_elemental_iii_stealth_and_cost():
    # Stealth +1 TMM; 19 damage in groups of up to 6 (6x3). Cost 29 (card 26)
    # since Skill 5 is priced like Veteran.
    sp, skill, c = _card("Elemental III BA [AP Gauss](Sqd5).blk")
    assert (sp.tmm, sp.range, sp.damage, sp.check) == (3, (3, 6, 9), (6, 3), 9)
    assert c["regular"] == 29


def test_ba_groups_keep_the_total_in_small_hits():
    from bsp.derive import ba_groups
    assert ba_groups(12.68, 6) == (6, 2)     # Elemental, as printed
    assert ba_groups(10.56, 6) == (5, 2)     # IS Standard, as printed
    assert ba_groups(21.12, 6) == (5, 4)     # Rottweiler (Close Combat) Sqd4
    assert ba_groups(32, 6) == (6, 5)


@need_data
def test_is_standard_ba_check_and_skill():
    sp, skill, c = _card("IS Standard BA [MG] (Sqd4).blk")
    assert (sp.damage, skill, sp.check) == ((5, 2), 6, 8)
