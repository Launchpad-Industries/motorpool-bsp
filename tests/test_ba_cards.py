# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Battle armor in the app: which squad sizes are listed, and their cards."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from bsp import app as app_module
from bsp.squads import design_name, squad_names

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))

sys.path.insert(0, str(ROOT / "tools"))
from battle_armor_list import choose  # noqa: E402


def suit(name, troopers, clan=False):
    return SimpleNamespace(full_name=f"{name}(Sqd{troopers})", name=name, model=f"(Sqd{troopers})",
                           troopers=troopers, clan=clan)


def kept(units, available_sizes):
    """Names chosen when the force generator lists these sizes of each design."""
    available = {(u.name, u.model) for u in units if u.troopers in available_sizes}
    return choose(units, available)


def test_design_name_drops_only_the_squad_tag():
    assert design_name(SimpleNamespace(full_name="Elemental Battle Armor [MG](Sqd5)")) == "Elemental Battle Armor [MG]"
    assert design_name(SimpleNamespace(full_name="Achileus BA (WoB) (Sqn 6)")) == "Achileus BA (WoB)"


def test_clan_lists_five_suits():
    units = [suit("Elemental", n, clan=True) for n in (3, 4, 5, 6)]
    assert kept(units, {3, 4, 5, 6}) == ["Elemental(Sqd5)"]


def test_inner_sphere_lists_available_fours_and_sixes():
    units = [suit("Kage", n) for n in (4, 5, 6)]
    assert kept(units, {4, 5, 6}) == ["Kage(Sqd4)", "Kage(Sqd6)"]
    assert kept(units, {6}) == ["Kage(Sqd6)"]
    assert kept(units, {4}) == ["Kage(Sqd4)"]


def test_a_design_with_no_faction_is_not_listed():
    assert kept([suit("PowerLoader", 4)], set()) == []


def test_a_design_available_only_at_another_size_keeps_that_size():
    assert kept([suit("Ravager", n) for n in (4, 5, 6)], {5}) == ["Ravager(Sqd5)"]


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
    assert len({r["id"] for r in ba}) == len(ba) > 300
    assert "Elemental Battle Armor [MG](Sqd5)" in rows
    assert "Elemental Battle Armor [MG](Sqd4)" not in rows
    assert "IS Standard Battle Armor [MG](Sqd4)" in rows and "IS Standard Battle Armor [MG](Sqd6)" in rows
    assert "IS Standard Battle Armor [MG](Sqd5)" not in rows
    assert "Cavalier Battle Armor [MG](Sqd4)" in rows and "Cavalier Battle Armor [MG](Sqd6)" not in rows
    assert "Achileus Light Battle Armor (WoB)(Sqd6)" in rows
    assert "Achileus Light Battle Armor (WoB)(Sqd4)" not in rows
    assert "Ravager Assault Battle Armor (LRM)(Sqd5)" in rows
    # Exactly the list: a name that stops matching a MegaMek unit fails here.
    assert {r["name"] for r in ba} == squad_names()
    assert all(r["tons"] is None for r in ba)
    assert sum(r["source"] == "Official" for r in ba) == 4
    assert all(r["source"] == "Calculated" for r in ba if not r["has_official"])


def test_calculated_card_matches_the_model(client, rows):
    r = rows["Elemental Battle Armor [HMG](Sqd5)"]
    assert (r["mp"], r["mode"], r["tmm"], r["range"], r["damage"], r["cost"]) == (3, "j", 2, [1, 2, 3], "10d×2", 20)
    u = client.get(f"/api/unit/{r['id']}").get_json()
    assert u["calculated"]["check"] == 9 and u["official"] is None and not u.get("generic")
    h = client.get(f"/api/card/{r['id']}?view=generated&grade=reg").get_data(as_text=True)
    assert "Elemental Battle Armor" in h and "3j" in h and "Source: Calculated" in h and 'src="data:image' in h


@pytest.mark.parametrize("suit_name, card_name, variant, official_cost, calculated_cost, differs", [
    ("Elemental Battle Armor [MG](Sqd5)", "Elemental Battle Armor", "Standard", 17, 19, ["cost", "vet_cost"]),
    ("Elemental Battle Armor [AP Gauss](Sqd5)", "Elemental Battle Armor (AP Gauss)", "Standard", 19, 24, None),
    ("Elemental III Battle Armor [AP Gauss](Sqd5)", "Elemental III Battle Armor", "Standard", 26, 26, None),
    ("IS Standard Battle Armor [MG](Sqd4)", "Inner Sphere Battle Armor", "Standard", 13, 15, ["cost", "vet_cost"]),
])
def test_official_cards_are_linked_to_their_suits(client, rows, suit_name, card_name, variant,
                                                  official_cost, calculated_cost, differs):
    r = rows[suit_name]
    assert (r["has_official"], r["source"], r["chassis"], r["variant"], r["cost"]) == (
        True, "Official", card_name, variant, official_cost)
    assert r["old_id"] and not r.get("generic")
    u = client.get(f"/api/unit/{r['id']}").get_json()
    assert u["official"]["cost"] == official_cost and u["generated"]["cost"] == calculated_cost
    if differs is not None:
        assert u["differs"] == differs
    official = client.get(f"/api/card/{r['id']}?view=official").get_data(as_text=True)
    calculated = client.get(f"/api/card/{r['id']}?view=generated").get_data(as_text=True)
    assert "Official Catalyst BSP" in official and 'src="data:image' in official
    assert "Source: Calculated" in calculated


def test_linked_cards_are_no_longer_listed_on_their_own(rows):
    generic = {r["name"] for r in rows.values() if r.get("generic")}
    assert not any("Battle Armor" in n for n in generic)
    assert "Foot Conv. Infantry" in generic and "MG Nest" in generic


def test_only_the_linked_squad_size_gets_the_official_card(rows):
    assert not rows["IS Standard Battle Armor [MG](Sqd6)"]["has_official"]


def test_a_suit_with_no_attack_still_makes_a_card(client, rows):
    r = next(r for r in rows.values() if r["type"] == "Battle Armor" and r["range"] == "-")
    assert client.get(f"/api/card/{r['id']}?view=generated").status_code == 200
    assert client.post("/api/recost", json={"values": {**r, "skill": r["skill"]}}).status_code == 200


def test_printing_shows_no_tonnage_for_battle_armor(client, rows):
    r = rows["Elemental Battle Armor [HMG](Sqd5)"]
    doc = client.post("/api/print-html", json={"title": "T", "items": [
        {"id": r["id"], "qty": 1, "grade": "vet", "view": "official"}]}).get_data(as_text=True)
    assert "<td>Battle Armor</td><td>Veteran</td>" in doc and "<td class=n>—</td>" in doc
