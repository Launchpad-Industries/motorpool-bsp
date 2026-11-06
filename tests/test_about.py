# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""The About page. If the first test fails after a rule change, update the
worked example and the "Last updated" date in bsp/web/about.html."""

from pathlib import Path

from bsp.cost import cost

ABOUT = Path(__file__).resolve().parent.parent / "bsp" / "web" / "about.html"


def test_worked_example_matches_the_cost_formula():
    c = cost(3, 2, (6, 2), (1, 2, 3), 5, 9, 0, ["Mechanized", "Nimble", "Spotter", "Swarm"])
    text = ABOUT.read_text(encoding="utf-8")
    assert (c["regular"], c["veteran"]) == (19, 21)
    assert f'{c["offense_bv"]:.1f}' in text and f'{c["defense_bv"]:.1f}' in text
    assert f'= {c["unrounded"]:.1f}, which rounds to <b>{c["regular"]}</b>' in text
    assert f'{c["unrounded"] * 1.15:.1f}, which rounds to <b>{c["veteran"]}</b>' in text


def test_about_page_carries_the_required_notices():
    text = ABOUT.read_text(encoding="utf-8")
    for notice in ("unofficial", "The Topps Company", "CC BY-NC-SA 4.0", "MegaMek"):
        assert notice in text
