# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Checks for on-demand Sheet pull and push, against a fake Apps Script web
app on this computer (it answers POSTs with a redirect, like Google does)."""

import csv
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from bsp import sheet

ROOT = Path(__file__).resolve().parent.parent
MM = Path(os.environ.get("MM_DATA", ROOT / "mm-data" / "data" / "mekfiles"))

HEADER = sheet.OFFICIAL_COLUMNS
CARD = ["Puma", "(PAT-001)", "Vehicle", "32", "37", "6 (5)", "3", "t", "1",
        "6/12/18", "9x3", "10", "8", "IF5"]


@pytest.fixture
def fake_sheet():
    """Yields (settings, state); state['tabs'] is the Sheet, state['pushed'] the push requests."""
    state = {"tabs": {"Official": [HEADER, CARD, [""] * len(HEADER)]}, "pushed": [], "pending": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if req["key"] != "s3cret":
                out = {"ok": False, "error": "Wrong secret"}
            elif req["action"] == "pull":
                rows = state["tabs"].get(req["tab"])
                out = {"ok": True, "rows": rows} if rows else {"ok": False, "error": f'No tab named "{req["tab"]}"'}
            elif req["action"] == "push":
                state["pushed"].append(req)
                out = {"ok": True, "tab": req["tab"], "rows": len(req["rows"]) - 1}
            else:
                out = {"ok": True, "tabs": list(state["tabs"])}
            state["pending"] = out
            self.send_response(302)
            self.send_header("Location", "/result")
            self.end_headers()

        def do_GET(self):
            body = json.dumps(state["pending"]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    settings = {"url": f"http://127.0.0.1:{srv.server_port}/exec", "key": "s3cret",
                "official_tab": "Official"}
    yield settings, state
    srv.shutdown()


def test_pull_writes_tsv_the_app_can_read(fake_sheet, tmp_path):
    settings, _ = fake_sheet
    dest = tmp_path / "official.tsv"
    dest.write_text("old", encoding="utf-8")
    assert sheet.pull(settings, dest) == 1
    rows = list(csv.DictReader(open(dest, encoding="utf-8"), delimiter="\t"))
    assert rows[0]["name"] == "Puma" and rows[0]["range"] == "6/12/18" and rows[0]["skill"] == "6 (5)"
    assert (tmp_path / "official.tsv.bak").read_text(encoding="utf-8") == "old"


def test_pull_refuses_a_tab_without_the_columns(fake_sheet, tmp_path):
    settings, state = fake_sheet
    state["tabs"]["Official"] = [["Chassis", "Variant"], ["Puma", "PAT-001"]]
    dest = tmp_path / "official.tsv"
    dest.write_text("old", encoding="utf-8")
    with pytest.raises(sheet.SheetError, match="missing columns"):
        sheet.pull(settings, dest)
    assert dest.read_text(encoding="utf-8") == "old"


def test_wrong_secret_and_missing_tab_are_reported(fake_sheet, tmp_path):
    settings, _ = fake_sheet
    with pytest.raises(sheet.SheetError, match="No tab named"):
        sheet.pull({**settings, "official_tab": "Nope"}, tmp_path / "o.tsv")
    with pytest.raises(sheet.SheetError, match="Wrong secret"):
        sheet.tabs({**settings, "key": "guess"})
    with pytest.raises(sheet.SheetError, match="bsp.sheet setup"):
        sheet.tabs({})


def test_push_sends_every_row_to_a_new_dated_tab(fake_sheet, monkeypatch):
    settings, state = fake_sheet
    monkeypatch.setattr(sheet, "calculated_rows", lambda mm: [["Chassis"], ["Puma"], ["Pike"]])
    tab, n = sheet.push(settings, MM)
    assert tab.startswith("Calculated 20") and n == 2
    assert state["pushed"][0]["rows"] == [["Chassis"], ["Puma"], ["Pike"]]


def test_config_lives_apart_from_the_app(tmp_path):
    path = tmp_path / "sheet.json"
    assert sheet.load_config(path)["official_tab"] == "Official"
    sheet.save_config({"url": "u", "key": "k", "official_tab": "Cards"}, path)
    assert sheet.load_config(path) == {"url": "u", "key": "k", "official_tab": "Cards"}


@pytest.mark.skipif(not (MM.exists() and (ROOT / "cache" / "weapons.json").exists()),
                    reason="MegaMek data not downloaded")
def test_calculated_rows_cover_every_combat_vehicle():
    from bsp.listing import COLUMNS
    rows = sheet.calculated_rows(MM)
    assert rows[0] == COLUMNS
    assert len(rows) > 1000
    assert all(len(r) == len(COLUMNS) and all(isinstance(c, str) for c in r) for r in rows)
