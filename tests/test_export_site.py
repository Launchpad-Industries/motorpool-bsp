# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""The site export matches the field list in docs/site-data-schema.md."""

import json
import re
from pathlib import Path

import pytest

from bsp.cards import Card
from bsp.export_site import (CardPages, assign_ids, export_strikes, spec_of, standalone_svg,
                              strike_entry, unit_entry)

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


def card_file_ok(site: Path | None, src: str):
    assert src.startswith("cards/") and src.endswith(".html"), src
    if site:
        page = (site / src).read_text(encoding="utf-8")
        assert 'href="card.css"' in page and 'class=one' in page, src


def validate_unit(u: dict, site: Path | None = None):
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
    assert set(u["cards"]) == {"regular", "veteran"}
    assert (u["cards"]["veteran"] is None) == (u["cost"]["veteran"] is None)
    for src in u["cards"].values():
        if src:
            card_file_ok(site, src)


STRIKE = schema_table("Strike")


def validate_strike(s: dict, site: Path | None = None):
    required = {k for k, t in STRIKE.items() if "?" not in t}
    assert required <= set(s), f"missing {required - set(s)}"
    assert set(s) <= set(STRIKE), f"not in schema: {set(s) - set(STRIKE)}"
    card_file_ok(site, s["card"])
    for k, v in s.items():
        check_value(k, STRIKE[k], v)
    assert re.fullmatch(r"strike(-[a-z0-9]+)+", s["id"])
    assert s["category"] in ("Air", "Artillery", "Minefield")
    assert s["chip"] in ("STRIKE", "MINEFIELD", "NOT AN ATTACK")
    assert isinstance(s["cost"], int)
    assert s.get("writeOn") in (None, "target", "hex")
    for c in s.get("cancels", []):
        assert set(c) == {"strike", "tn"} and isinstance(c["tn"], int)
    for d in s["diagrams"]:
        assert set(d) == {"src", "caption"} and d["src"].endswith(".svg")
        if site:
            svg = (site / d["src"]).read_text(encoding="utf-8")
            assert 'xmlns="http://www.w3.org/2000/svg"' in svg and 'width="' in svg


def validate(data: dict, site: Path | None = None):
    for k in ("schemaVersion", "generatedOn", "generator", "disclaimer", "credits", "units"):
        assert k in data, k
    assert data["schemaVersion"] == 1
    ids = [u["id"] for u in data["units"]] + [s["id"] for s in data.get("strikes", [])]
    assert len(ids) == len(set(ids)), "duplicate ids"
    names = [u["name"].lower() for u in data["units"]]
    assert names == sorted(names), "units not sorted by name"
    for u in data["units"]:
        validate_unit(u, site)
    for s in data.get("strikes", []):
        validate_strike(s, site)


def card(**kw) -> Card:
    d = dict(chassis="Scorpion Light Tank", variant="(LRM)", unit_type="Vehicle", tons=25.0,
             mp=4, mode="t", tmm=1, range=(7, 14, 21), skill=6, vet_skill=5, damage="5d×4",
             check=8, threshold=4, cost=30, vet_cost=35, specials=["IF2"])
    d.update(kw)
    return Card(**d)


def test_unit_entry_matches_schema(tmp_path):
    plain = card()
    approved = card(source="Approved", approver="Launchpad", verified=False, drift=["damage"])
    official = card(source="Official", range="Artillery", damage="-", vet_skill=None, vet_cost=None)
    units = assign_ids([
        ("a", unit_entry(plain, "Scorpion Light Tank (LRM)", motive="Tracked", tonnage=25.0,
                         tech="IS", year=3021, mul_id=2730, has_official=True)),
        ("b", unit_entry(approved, "Scorpion Light Tank (LRM)", approval={"on": "2026-10-31"},
                         art={"src": "img/units/x.png", "credit": "c"})),
        ("c", unit_entry(official, "Long Tom Battery")),
    ])
    pages = CardPages(tmp_path)
    for u, c in zip(units, (official, plain, approved)):
        u["cards"] = pages.unit(u["id"], c, u.get("art"))
    pages.finish()
    validate({"schemaVersion": 1, "generatedOn": "x", "generator": "x", "disclaimer": "x",
              "credits": [], "units": units}, tmp_path)
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
    # Card pages are Motor Pool's own card drawing, with the styles shared.
    assert arty["cards"] == {"regular": "cards/long-tom-battery.html", "veteran": None}
    reg = (tmp_path / appr["cards"]["regular"]).read_text(encoding="utf-8")
    vet = (tmp_path / appr["cards"]["veteran"]).read_text(encoding="utf-8")
    assert 'class="grade">REGULAR' in reg and 'class="grade vet">VETERAN' in vet
    assert 'src="../img/units/x.png"' in reg and 'class="sprite"' in reg
    assert "Unverified-Launchpad" in reg and ".hd .chassis" not in reg
    assert ".hd .chassis" in (tmp_path / "cards" / "card.css").read_text(encoding="utf-8")
    assert sorted(f.name for f in (tmp_path / "cards").iterdir()) == [
        "card.css", "long-tom-battery.html", "scorpion-light-tank-lrm-2-vet.html",
        "scorpion-light-tank-lrm-2.html", "scorpion-light-tank-lrm-vet.html", "scorpion-light-tank-lrm.html"]


def test_spec_without_veteran_hides_vet_skill():
    assert spec_of(card(vet_cost=None))["skill"] == {"regular": 6, "veteran": None}


def test_strike_entries_match_schema(tmp_path):
    from bsp.strikes import load
    cards, skipped = load(ROOT / "bsp-options.tsv")
    assert not skipped
    strikes = export_strikes(cards.values(), tmp_path, CardPages(tmp_path))
    for s in strikes:
        validate_strike(s, tmp_path)
    assert "LONG TOM" in (tmp_path / "cards" / "strike-long-tom.html").read_text(encoding="utf-8").upper()
    by_id = {s["id"]: s for s in strikes}
    assert len(by_id) == len(strikes)
    lt = by_id["strike-long-tom"]
    assert (lt["tn"], lt["groups"], lt["radius"], lt["scatter"], lt["writeOn"]) == (8, "5/3/1", 2, "1D6", "target")
    assert [d["caption"] for d in lt["diagrams"]] == ["Damage radius 2", "Scatter (1D6)"]
    mine = by_id["strike-light-density-minefield"]
    assert (mine["chip"], mine["per"], mine["writeOn"]) == ("MINEFIELD", "per hex", "hex")
    cover = by_id["strike-light-air-cover"]
    assert cover["chip"] == "NOT AN ATTACK" and "tn" not in cover
    assert {"strike": "Strafing", "tn": 11} in cover["cancels"]


def test_standalone_svg():
    from bsp.strikes import single_svg
    svg = standalone_svg(single_svg("3"))
    assert 'xmlns="http://www.w3.org/2000/svg" width="0.42in">' in svg.split("<path", 1)[0]
    assert "style=" not in svg and 'font-family="Oswald"' not in svg


SITE_DATA = ROOT / "site" / "data" / "units.json"


@pytest.mark.skipif(not SITE_DATA.exists(), reason="no site export")
def test_site_data_matches_schema():
    validate(json.loads(SITE_DATA.read_text(encoding="utf-8")), SITE_DATA.parent.parent)
