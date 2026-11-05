# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Strike cards (bsp-options.tsv): reading the rows, what each kind of card
shows, and their place in the app's search, force total and printout."""

import os
import re
from pathlib import Path

import pytest

from bsp import app as app_module
from bsp.cards import card_html, document
from bsp.sheet import OPTIONS_COLUMNS
from bsp.strikes import card_from_row, load, parse_stats, radius_svg, scatter_svg

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))
HEADER = "\t".join(OPTIONS_COLUMNS)


def row(name, category, cost, stats, per="", effect="Does a thing."):
    return {"name": name, "category": category, "costR": str(cost), "costV": "", "per": per, "stats": stats,
            "effect": effect, "source": "BT Core Rulebook p. 155", "notes": "Not printed."}


LONG_TOM = row("Long Tom", "Artillery", 24, "Support=Artillery; TN=8; Groups=5/3/1; Type=AE; Radius=2; Scatter=1D6")
SMOKE = row("Smoke (Sniper)", "Artillery", 8, "Support=Artillery; TN=8; Groups=none; Type=Smoke; Radius=1; Scatter=1D6")
COPPERHEAD = row("Copperhead (Sniper)", "Artillery", 8, "Support=Artillery; TN=4; Groups=2; Type=AE; Radius=0; Needs=TAG")
STRAFING = row("Strafing", "Air", 22, "Support=Offensive Aerospace; TN=7; Groups=3; Type=DE; Area=Up to 5 hexes in a line")
BOMBING = row("Light Bombing", "Air", 13, "Support=Offensive Aerospace; TN=5; Groups=3; Type=AE; Scatter=1D6")
COVER = row("Light Air Cover", "Air", 5, "Support=Defensive Aerospace; Not an attack; Light Air Strike=4; "
            "Light Bombing=4; Heavy Air Strike=9; Strafing=11; Heavy Bombing=11")
BLUFF = row("Bluff", "Air", 5, "Support=Offensive Aerospace; Not an attack")
MINES = row("Medium Density", "Minefield", 5, "Support=Minefield; TN=8; Groups=4; Type=AE", per="per hex")


def html(r):
    return card_html(card_from_row(r))


def test_stats_are_pairs_and_flags():
    assert parse_stats("TN=8; Not an attack; Groups=5/3/1") == {"TN": "8", "Not an attack": True, "Groups": "5/3/1"}


def test_header_shows_support_type_and_cost():
    h = html(LONG_TOM)
    assert "Artillery Support" in h and ">Long Tom<" in h and "<small>COST</small>24<" in h
    assert 'class="per"' not in h


def test_cost_box_says_per_hex():
    assert '<small class="per">/hex</small>' in html(MINES)


def test_stat_box_and_rules_page_reference():
    h = html(LONG_TOM)
    for text in ("Target No.", ">8+<", "Groups ×5", ">5/3/1<", ">AE<"):
        assert text in h
    assert "Does a thing." in h and "(Core Rulebook p. 155)</i>" in h and "Not printed." not in h


def test_footer_names_the_book_without_a_page():
    h = html(LONG_TOM)
    assert "BATTLEFIELD SUPPORT" in h and ">Source: BattleTech Core Rulebook<" in h


@pytest.mark.parametrize("r, chip", [(LONG_TOM, "STRIKE"), (MINES, "MINEFIELD"), (COVER, "NOT AN ATTACK")])
def test_chip_says_what_the_card_is(r, chip):
    h = html(r)
    assert f">{chip}</span>" in h and "REGULAR" not in h and "VETERAN" not in h


def test_radius_diagram_has_the_groups_in_each_ring():
    # Radius 2: 1 + 6 + 12 hexes, and a separate 7-hex scatter diagram.
    h = html(LONG_TOM)
    assert h.count("<path") == 19 + 7 and "Damage radius 2" in h and "Scatter (1D6)" in h
    assert h.count(">5</text>") == 1 + 1 and h.count(">3</text>") == 6 + 1 and h.count(">1</text>") == 12 + 1


def text_positions(svg):
    return {m[2]: (float(m[0]), float(m[1]))
            for m in re.findall(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>([^<]+)</text>', svg)}


def test_scatter_has_1_directly_above_the_target_then_goes_clockwise():
    pos = text_positions(scatter_svg())
    tx, ty = pos["T"]
    assert pos["1"][0] == tx and pos["1"][1] < ty      # straight up
    assert pos["2"][0] > tx and pos["2"][1] < ty       # upper right
    assert pos["3"][0] > tx and pos["3"][1] > ty       # lower right
    assert pos["4"][0] == tx and pos["4"][1] > ty      # straight down
    assert pos["5"][0] < tx and pos["5"][1] > ty       # lower left
    assert pos["6"][0] < tx and pos["6"][1] < ty       # upper left


def test_radius_diagram_has_a_hex_directly_above_the_target():
    svg = radius_svg(["5", "3"], 1)
    x = {float(m) for m in re.findall(r'<text x="([-\d.]+)"', svg)}
    assert x == {-15.0, 0.0, 15.0}                     # three columns: flat-topped hexes
    assert len(re.findall(r'<text x="0.00"', svg)) == 3   # above, target, below


def test_smoke_is_hatched_with_no_group_numbers():
    h = html(SMOKE)
    assert 'url(#hatch)' in h and "Smoke radius 1" in h and ">—<" in h


def test_strafing_is_a_line_of_five_hexes():
    h = html(STRAFING)
    assert h.count("<path") == 5 and "Up to 5 hexes in a line" in h


def test_bombing_is_a_target_hex_and_scatter():
    h = html(BOMBING)
    assert h.count("<path") == 1 + 7 and "Target hex" in h and "Scatter (1D6)" in h


def test_copperhead_is_one_tag_hex_with_only_a_used_box():
    h = html(COPPERHEAD)
    assert h.count("<path") == 1 and "TAG-painted target" in h and "Turn<i>" not in h and ">Used<" in h


def test_air_cover_lists_its_five_cancel_numbers():
    h = html(COVER)
    assert "Cancels on" in h and "Target No." not in h
    for name, tn in (("Light Air Strike", 4), ("Light Bombing", 4), ("Heavy Air Strike", 9),
                     ("Strafing", 11), ("Heavy Bombing", 11)):
        assert f'{name}</span><span class="val">{tn}+<' in h


def test_artillery_has_target_turn_and_used_boxes():
    h = html(LONG_TOM)
    assert "Target hex<i>" in h and "Turn<i>" in h and h.count(">Used<") == 1


def test_minefield_has_hex_and_a_group_countdown():
    h = html(MINES)
    assert "Hex<i>" in h and ">Used<" not in h
    assert "<span>4</span><span>3</span><span>2</span><span>1</span>" in h


def test_minefield_titles_say_minefield():
    assert '<div class="chassis long">Medium Density Minefield<' in html(MINES)
    assert card_from_row(row("Minefield (Light)", "Minefield", 3, "Groups=2")).title == "Minefield (Light)"
    assert card_from_row(LONG_TOM).title == "Long Tom"


def test_other_cards_get_a_used_box():
    for r in (STRAFING, BOMBING, COVER, BLUFF):
        assert html(r).count(">Used<") == 1


def test_bad_rows_are_skipped_and_named(tmp_path):
    p = tmp_path / "o.tsv"
    lines = [HEADER] + ["\t".join(r[c] for c in OPTIONS_COLUMNS) for r in (
        LONG_TOM, row("No Cost", "Air", "free", ""), row("Bad Mines", "Minefield", 3, "Groups=lots"),
        row("Bad Radius", "Artillery", 3, "Radius=9"))] + ["\t" * 8]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cards, skipped = load(p)
    assert [c.name for c in cards.values()] == ["Long Tom"]
    assert skipped == ["No Cost", "Bad Mines", "Bad Radius"]


def test_summary_page_has_no_grade_or_skill_for_strikes():
    doc = document([card_from_row(LONG_TOM)], summary=True)
    assert "<td>Long Tom</td><td>Artillery Support</td><td>—</td><td class=n>—</td><td class=n>24</td><td class=n>480</td>" in doc


def test_real_data_file_loads_every_row():
    p = ROOT / "bsp-options.tsv"
    if not p.exists():
        pytest.skip("bsp-options.tsv not pulled")
    cards, skipped = load(p)
    assert skipped == [] and len(cards) >= 22


@pytest.fixture
def client(tmp_path, monkeypatch):
    if not (MM.exists() and (ROOT / "cache" / "weapons.json").exists()):
        pytest.skip("MegaMek data not downloaded")
    p = tmp_path / "bsp-options.tsv"
    p.write_text("\n".join([HEADER] + ["\t".join(r[c] for c in OPTIONS_COLUMNS) for r in (LONG_TOM, MINES)]) + "\n",
                 encoding="utf-8")
    monkeypatch.setattr(app_module, "options_path", lambda: p)
    return app_module.create_app().test_client()


def test_app_lists_strikes_apart_from_units(client):
    rows = client.get("/api/strikes").get_json()
    assert [(r["name"], r["cost"], r["per"]) for r in rows] == [("Long Tom", 24, ""), ("Medium Density Minefield", 5, "per hex")]
    assert not any(r.get("strike") for r in client.get("/api/units").get_json())
    assert client.get("/api/info").get_json()["strikes"] == 2


def test_app_previews_a_strike_card(client):
    i = client.get("/api/strikes").get_json()[0]["id"]
    u = client.get(f"/api/unit/{i}").get_json()
    assert u["strike"] and u["notes"] == "Not printed." and u["calculated"] is None
    r = client.get(f"/api/card/{i}?view=official&grade=reg")
    assert r.status_code == 200 and "Long Tom" in r.get_data(as_text=True)


def test_printing_puts_strikes_after_units_and_counts_their_cost(client):
    strikes = client.get("/api/strikes").get_json()
    unit = client.get("/api/units").get_json()[0]
    doc = client.post("/api/print-html", json={"title": "T", "items": [
        {"id": strikes[1]["id"], "qty": 3, "grade": "reg", "view": "official"},
        {"id": unit["id"], "qty": 1, "grade": "reg", "view": "official"},
    ]}).get_data(as_text=True)
    body = doc[doc.index("<tbody>"):]
    assert body.index(unit["chassis"]) < body.index("Medium Density")
    assert f'<td class=n>{unit["cost"] + 15}</td>' in body
    assert doc.count('<div class="chassis long">Medium Density Minefield<') == 3
