# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Generic official cards (infantry, battle armor, emplacements): official
only, not linked to a MegaMek unit, and printable like any other card."""

import os
from pathlib import Path

import pytest

from bsp.art import Art
from bsp.cards import card_from_generic, card_html, generic_official

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))

HEADER = "name\tvariant\ttype\tcostR\tcostV\tskill\tmp\tmtype\ttmm\trange\tdmg\tcheck\tthr\tspecials"
ROWS = [
    "Test Battle Armor\tStandard\tBattle Armor\t17\t20\t5\t3\tj\t2\t1/2/3\t6x2\t9\t5\tMechanized, Nimble",
    "Test Foot Infantry\tStandard\tInfantry\t7\t8\t6\t1\tf\t0\t1/2/3\t5x2\t8\t1\tNimble, Swarm",
    "Test Bunker\tHeavy\tEmplacement\t13\t15\t5\t0\tna\t0\t3/6/9\t15\t10\t8\tImmobile",
    "Test Tank\t(TT-1)\tVehicle\t30\t35\t5\t4\tt\t1\t6/12/18\t9x2\t10\t8\t-",
]


@pytest.fixture
def tsv(tmp_path):
    p = tmp_path / "official.tsv"
    p.write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="utf-8")
    return p


def test_generic_rows_are_infantry_ba_and_emplacements(tsv):
    assert [r["type"] for r in generic_official(tsv)] == ["Battle Armor", "Infantry", "Emplacement"]


def test_generic_card_renders_as_official(tsv):
    rows = {r["type"]: r for r in generic_official(tsv)}
    ba = card_from_generic(rows["Battle Armor"], None)
    assert (ba.source, ba.cost, ba.vet_cost, ba.mp, ba.mode, ba.damage) == ("Official", 17, 20, 3, "j", "6d×2")
    html = card_html(card_from_generic(rows["Emplacement"], None))
    assert "Official Catalyst BSP" in html and ">0<" in html and "0na" not in html


def test_generic_card_uses_megamek_default_sprite(tsv):
    units = MM.parent / "images" / "units"
    if not (units / "defaults" / "default_ba.png").exists():
        pytest.skip("MegaMek sprites not downloaded")
    ba = card_from_generic(generic_official(tsv)[0], Art(units))
    assert ba.image.startswith("data:image") and ba.image_source == "sprite"


def test_missing_linked_unit_file_is_skipped_not_fatal(tmp_path):
    # A card linked in card_links.yaml whose MegaMek file is absent (e.g. a
    # tester's unzip didn't finish) is skipped and reported.
    from bsp.cards import official_index
    p = tmp_path / "official.tsv"
    p.write_text(HEADER + "\nCondor Heavy Hover Tank\tLaser\tVehicle\t30\t35\t5\t8\th\t3\t6/12/18\t6x2\t9\t6\t-\n",
                 encoding="utf-8")
    missing = []
    assert official_index(p, tmp_path / "empty-mekfiles", [], missing) == {}
    assert missing == ["Condor Heavy Hover Tank Laser"]


@pytest.mark.skipif(not (MM.exists() and (ROOT / "cache" / "weapons.json").exists()),
                    reason="MegaMek data not downloaded")
def test_app_lists_previews_and_prints_generic_cards(tsv):
    from bsp.app import DEFAULTS, create_app
    c = create_app({**DEFAULTS, "official_tsv": str(tsv)}).test_client()
    rows = [r for r in c.get("/api/units").get_json() if r.get("generic")]
    assert sorted(r["type"] for r in rows) == ["Battle Armor", "Emplacement", "Infantry"]
    gid = next(r["id"] for r in rows if r["type"] == "Infantry")
    u = c.get(f"/api/unit/{gid}").get_json()
    assert u["generic"] and u["calculated"] is None and u["official"]["cost"] == 7
    assert c.get(f"/api/card/{gid}").status_code == 200
    doc = c.post("/api/print-html", json={"items": [{"id": gid, "qty": 2, "grade": "vet"}]}).get_data(as_text=True)
    assert doc.count("Test Foot Infantry") >= 2 and "Infantry" in doc
