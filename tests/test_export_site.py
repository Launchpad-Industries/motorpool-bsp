# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""The site export matches the field list in docs/site-data-schema.md."""

import json
import re
from pathlib import Path

import pytest

from bsp.cards import Card
from bsp.export_site import assign_ids, spec_of, unit_entry

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "docs" / "site-data-schema.md").read_text(encoding="utf-8")


def schema_table(heading: str) -> dict[str, str]:
    """Field name -> type text from the table under '## <heading>'."""
    section = SCHEMA.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `(\w+)` \| (.+?) \|", section, re.M)
    assert rows, f"no fields found under {heading}"
    return dict(rows)


UNIT, SPEC = schema_table("Unit"), schema_table("Spec")
TYPES = re.findall(r"`([^`]+)`", UNIT["type"]) or None


def check_value(name: str, kind: str, v):
    """Check one value against the schema's type text."""
    kind = kind.strip("` ")
    if kind.startswith("string"):
        assert isinstance(v, str), name
    elif kind.startswith("number"):
        assert isinstance(v, (int, float)) and not isinstance(v, bool), name
    elif kind.startswith("bool"):
        assert isinstance(v, bool), name


def validate_unit(u: dict):
    required = {k for k, t in UNIT.items() if "?" not in t}
    assert required <= set(u), f"missing {required - set(u)}"
    assert set(u) <= set(UNIT), f"not in schema: {set(u) - set(UNIT)}"
    for k, v in u.items():
        check_value(k, UNIT[k], v)
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", u["id"])
    assert u["provenance"] in ("official", "approved", "calculated")
    assert u["type"] in ("Vehicle", "VTOL", "WiGE", "Infantry", "Battle Armor", "Emplacement",
                         "Artillery", "Support Vehicle")
    if u["provenance"] != "approved":
        assert "approvedBy" not in u and "approvedOn" not in u
    assert set(u["cost"]) == {"regular", "veteran"} and isinstance(u["cost"]["regular"], int)
    assert u["cost"]["veteran"] is None or isinstance(u["cost"]["veteran"], int)
    if "art" in u:
        assert set(u["art"]) == {"src", "credit"} and not u["art"]["src"].startswith("/")
    s = u["spec"]
    required = {k for k, t in SPEC.items() if "?" not in t}
    assert required <= set(s) <= set(SPEC), sorted(s)
    for k in ("tmm", "check", "threshold"):
        assert isinstance(s[k], int), k
    assert isinstance(s["move"], str) and isinstance(s["damage"], str)
    assert set(s["skill"]) == {"regular", "veteran"}
    assert (s["skill"]["veteran"] is None) == (u["cost"]["veteran"] is None)
    assert len(s["range"]) == 3 and all(isinstance(x, int) for x in s["range"])
    assert isinstance(s["specials"], list) and all(isinstance(x, str) for x in s["specials"])


def validate(data: dict):
    for k in ("schemaVersion", "generatedOn", "generator", "disclaimer", "credits", "units"):
        assert k in data, k
    assert data["schemaVersion"] == 1
    ids = [u["id"] for u in data["units"]]
    assert len(ids) == len(set(ids)), "duplicate ids"
    names = [u["name"].lower() for u in data["units"]]
    assert names == sorted(names), "units not sorted by name"
    for u in data["units"]:
        validate_unit(u)


def card(**kw) -> Card:
    d = dict(chassis="Scorpion Light Tank", variant="(LRM)", unit_type="Vehicle", tons=25.0,
             mp=4, mode="t", tmm=1, range=(7, 14, 21), skill=6, vet_skill=5, damage="5d×4",
             check=8, threshold=4, cost=30, vet_cost=35, specials=["IF2"])
    d.update(kw)
    return Card(**d)


def test_unit_entry_matches_schema():
    approved = card(source="Approved", approver="Launchpad", verified=False, drift=["damage"])
    official = card(source="Official", range="Artillery", damage="-", vet_skill=None, vet_cost=None)
    units = assign_ids([
        ("a", unit_entry(card(), "Scorpion Light Tank (LRM)", motive="Tracked", tonnage=25.0,
                         tech="IS", year=3021, mul_id=2730, has_official=True)),
        ("b", unit_entry(approved, "Scorpion Light Tank (LRM)", approval={"on": "2026-10-31"},
                         art={"src": "img/units/x.png", "credit": "c"})),
        ("c", unit_entry(official, "Long Tom Battery")),
    ])
    validate({"schemaVersion": 1, "generatedOn": "x", "generator": "x", "disclaimer": "x",
              "credits": [], "units": units})
    calc, appr, arty = units[1], units[2], units[0]
    assert [u["id"] for u in units] == ["long-tom-battery", "scorpion-light-tank-lrm",
                                        "scorpion-light-tank-lrm-2"]
    assert calc["provenance"] == "calculated" and calc["hasOfficialCard"] is True
    assert calc["tonnage"] == 25 and isinstance(calc["tonnage"], int)
    assert calc["spec"]["move"] == "4t" and calc["spec"]["damage"] == "5dx4"
    assert calc["spec"]["indirect"] == 2
    assert appr["approvedBy"] == "Launchpad" and appr["verified"] is False
    assert appr["approvedOn"] == "2026-10-31" and "damage" in appr["notes"]
    assert arty["cost"]["veteran"] is None and arty["spec"]["skill"]["veteran"] is None
    assert arty["spec"]["range"] == [0, 0, 0] and "Artillery" in arty["spec"]["specials"]
    assert "hasOfficialCard" not in arty


def test_spec_without_veteran_hides_vet_skill():
    assert spec_of(card(vet_cost=None))["skill"] == {"regular": 6, "veteran": None}


SITE_DATA = ROOT / "site" / "data" / "units.json"


@pytest.mark.skipif(not SITE_DATA.exists(), reason="no site export")
def test_site_data_matches_schema():
    validate(json.loads(SITE_DATA.read_text(encoding="utf-8")))
