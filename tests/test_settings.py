# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Settings: the support address default, and moving saved old defaults to it."""

import json

from bsp import app


def saved(tmp_path, monkeypatch, **values):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(values), encoding="utf-8")
    monkeypatch.setattr(app, "SETTINGS", p)
    return app.load_settings()


def test_default_is_support_address(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "SETTINGS", tmp_path / "none.json")
    assert app.load_settings()["approval_email"] == "motorpool.support@gmail.com"


def test_old_default_moves_to_support_address(tmp_path, monkeypatch):
    s = saved(tmp_path, monkeypatch, name="Launchpad", approval_email="williamtbecker@gmail.com")
    assert s["approval_email"] == "motorpool.support@gmail.com" and s["name"] == "Launchpad"


def test_own_address_is_kept(tmp_path, monkeypatch):
    assert saved(tmp_path, monkeypatch, approval_email="me@example.org")["approval_email"] == "me@example.org"
