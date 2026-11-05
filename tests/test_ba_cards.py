# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Battle armor in the app: which squad sizes are listed, and their cards."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from bsp import app as app_module
from bsp.squads import design_name, standard_squads

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))


def suit(name, troopers, clan=False):
    return SimpleNamespace(full_name=name, troopers=troopers, clan=clan)


def kept(*units):
    return sorted(u.full_name for u in standard_squads(list(units)))


def test_design_name_drops_only_the_squad_tag():
    assert design_name(suit("Elemental Battle Armor [MG](Sqd5)", 5)) == "Elemental Battle Armor [MG]"
    assert design_name(suit("Achileus BA (WoB) (Sqn 6)", 6)) == "Achileus BA (WoB)"


def test_clan_keeps_five_suits():
    assert kept(*(suit(f"Elemental(Sqd{n})", n, clan=True) for n in (3, 4, 5, 6))) == ["Elemental(Sqd5)"]


def test_inner_sphere_keeps_four_and_six():
    assert kept(*(suit(f"Kage(Sqd{n})", n) for n in (4, 5, 6))) == ["Kage(Sqd4)", "Kage(Sqd6)"]


def test_a_design_without_a_standard_size_keeps_what_it_has():
    assert kept(suit("Interface Armor(Sqd1)", 1, clan=True)) == ["Interface Armor(Sqd1)"]
    assert kept(suit("Gnome 'Dwarf'(Sqd4)", 4, clan=True)) == ["Gnome 'Dwarf'(Sqd4)"]


@pytest.fixture(scope="module")
def client():
    if not (MM.exists() and (ROOT / "cache" / "weapons.json").exists()):
        pytest.skip("MegaMek data not downloaded")
    return app_module.create_app().test_client()


@pytest.fixture(scope="module")
def rows(client):
    return {r["name"]: r for r in client.get("/api/units").get_json()}


def test_app_lists_standard_sizes_with_unique_ids(rows):
    ba = [r for r in rows.values() if r["type"] == "Battle Armor" and not r.get("generic")]
    assert len({r["id"] for r in ba}) == len(ba) > 500
    assert "Elemental Battle Armor [MG](Sqd5)" in rows
    assert "Elemental Battle Armor [MG](Sqd4)" not in rows
    assert "IS Standard Battle Armor [MG](Sqd4)" in rows and "IS Standard Battle Armor [MG](Sqd6)" in rows
    assert "IS Standard Battle Armor [MG](Sqd5)" not in rows
    assert all(r["tons"] is None and r["source"] == "Calculated" for r in ba)


def test_calculated_card_matches_the_model(client, rows):
    r = rows["Elemental Battle Armor [MG](Sqd5)"]
    assert (r["mp"], r["mode"], r["tmm"], r["range"], r["damage"], r["cost"]) == (3, "j", 2, [1, 2, 3], "6d×2", 19)
    u = client.get(f"/api/unit/{r['id']}").get_json()
    assert u["calculated"]["check"] == 9 and u["official"] is None and not u.get("generic")
    h = client.get(f"/api/card/{r['id']}?view=generated&grade=reg").get_data(as_text=True)
    assert "Elemental Battle Armor" in h and "3j" in h and "Source: Calculated" in h and 'src="data:image' in h


def test_a_suit_with_no_attack_still_makes_a_card(client, rows):
    r = next(r for r in rows.values() if r["type"] == "Battle Armor" and r["range"] == "-")
    assert client.get(f"/api/card/{r['id']}?view=generated").status_code == 200
    assert client.post("/api/recost", json={"values": {**r, "skill": r["skill"]}}).status_code == 200


def test_printing_shows_no_tonnage_for_battle_armor(client, rows):
    r = rows["Elemental Battle Armor [MG](Sqd5)"]
    doc = client.post("/api/print-html", json={"title": "T", "items": [
        {"id": r["id"], "qty": 1, "grade": "vet", "view": "official"}]}).get_data(as_text=True)
    assert "<td>Battle Armor</td><td>Veteran</td>" in doc and "<td class=n>—</td>" in doc
