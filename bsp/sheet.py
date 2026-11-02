# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Offline pull and push between local files and the owner's Google Sheet.

Motor Pool never talks to the Sheet: it only reads local files. This
command-line tool is the only link, through the Apps Script web app in
bsp/sheet_sync.gs, and only when you run it:

    python -m bsp.sheet setup    # store the web app URL, secret and tab name
    python -m bsp.sheet tabs     # list the Sheet's tabs (checks the link)
    python -m bsp.sheet pull     # official-cards tab -> official.tsv
    python -m bsp.sheet push     # every calculated vehicle -> a new tab

The link settings live in ~/.motorpool/sheet.json, apart from the app's
settings. Pull checks the tab has the columns the app reads before replacing
official.tsv, and keeps the previous file as official.tsv.bak."""

from __future__ import annotations

import argparse
import csv
import getpass
import io
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path.home() / ".motorpool" / "sheet.json"
DEFAULTS = {"url": "", "key": "", "official_tab": "Official"}

# Columns the app and listing read from the official cards export.
OFFICIAL_COLUMNS = ["name", "variant", "type", "costR", "costV", "skill", "mp",
                    "mtype", "tmm", "range", "dmg", "check", "thr", "specials"]


class SheetError(Exception):
    pass


def load_config(path: Path = CONFIG) -> dict:
    c = dict(DEFAULTS)
    if path.exists():
        c.update(json.loads(path.read_text(encoding="utf-8")))
    return c


def save_config(c: dict, path: Path = CONFIG):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(c, indent=2), encoding="utf-8")


def call(config: dict, payload: dict, timeout: float = 180) -> dict:
    """POST to the Apps Script web app. Google answers with a redirect that
    urllib follows as a GET, which is how Apps Script returns its result."""
    url, key = config.get("url", "").strip(), config.get("key", "")
    if not url or not key:
        raise SheetError("No Sheet link set up yet. Run: python -m bsp.sheet setup")
    req = urllib.request.Request(url, data=json.dumps({**payload, "key": key}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise SheetError(f"Could not reach the Sheet link: {e}") from e
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        raise SheetError("The Sheet link didn't answer with Motor Pool data. Check the URL is the "
                         "web app deployment (…/exec) with access set to Anyone.") from None
    if not out.get("ok"):
        raise SheetError(out.get("error") or "The Sheet link reported an error.")
    return out


def tabs(config: dict) -> list[str]:
    return call(config, {"action": "tabs"})["tabs"]


def pull(config: dict, dest: Path) -> int:
    """Download the official-cards tab to dest (a TSV). Returns the card count."""
    tab = config.get("official_tab", "").strip()
    if not tab:
        raise SheetError("No official cards tab set. Run: python -m bsp.sheet setup")
    rows = [r for r in call(config, {"action": "pull", "tab": tab})["rows"]
            if any(str(c).strip() for c in r)]
    if not rows:
        raise SheetError(f'The "{tab}" tab is empty.')
    missing = [c for c in OFFICIAL_COLUMNS if c not in rows[0]]
    if missing:
        raise SheetError(f'The "{tab}" tab is missing columns the app needs: {", ".join(missing)}. '
                         "official.tsv was left as it was.")
    buf = io.StringIO()
    csv.writer(buf, delimiter="\t", lineterminator="\n").writerows(rows)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(buf.getvalue(), encoding="utf-8")
    if dest.exists():
        dest.replace(dest.with_name(dest.name + ".bak"))
    tmp.replace(dest)
    return len(rows) - 1


def calculated_rows(mm_root: Path) -> list[list]:
    """Header plus one Calculated row per combat vehicle, in the listing's
    column layout (approved cards show their approved values and label)."""
    from .listing import COLUMNS, calc_row
    from .megamek import load_all
    weapons = json.loads((ROOT / "cache" / "weapons.json").read_text())
    vehicles = [u for u in load_all(mm_root, folders=("vehicles",))
                if u.unit_type in ("Tank", "VTOL")]
    rows = [calc_row(u, weapons) for u in vehicles]
    rows.sort(key=lambda x: (x["Chassis"].lower(), x["Variant"].lower()))
    return [COLUMNS] + [["" if r[c] is None else str(r[c]) for c in COLUMNS] for r in rows]


def push(config: dict, mm_root: Path, tab: str | None = None) -> tuple[str, int]:
    """Send every calculated vehicle to a brand-new tab. Returns (tab, rows)."""
    rows = calculated_rows(mm_root)
    out = call(config, {"action": "push", "rows": rows,
                        "tab": tab or f"Calculated {date.today().isoformat()}"})
    return out["tab"], out["rows"]


def setup(config: dict) -> dict:
    """Ask for the link settings; Enter keeps the current value."""
    c = dict(config)
    url = input(f"Apps Script web app URL (…/exec) [{c['url'] or 'none'}]: ").strip()
    key = getpass.getpass("Secret (as set in the Apps Script; hidden) [Enter keeps current]: ").strip()
    tab = input(f"Official cards tab [{c['official_tab']}]: ").strip()
    c.update({k: v for k, v in (("url", url), ("key", key), ("official_tab", tab)) if v})
    return c


def main(argv=None):
    # The app's settings say where the MegaMek data and official.tsv are.
    from .app import ROOT as APP_ROOT, load_settings, official_path
    ap = argparse.ArgumentParser(description="Pull from or push to the Google Sheet (offline from the app)")
    ap.add_argument("action", choices=["setup", "tabs", "pull", "push"])
    ap.add_argument("--tab", help="push: name for the new tab (default 'Calculated <date>')")
    a = ap.parse_args(argv)
    config, s = load_config(), load_settings()
    try:
        if a.action == "setup":
            save_config(setup(config))
            print(f"Saved to {CONFIG}. Checking the link…")
            print("Tabs: " + ", ".join(tabs(load_config())))
        elif a.action == "tabs":
            print("\n".join(tabs(config)))
        elif a.action == "pull":
            dest = official_path(s) or APP_ROOT / "official.tsv"
            n = pull(config, dest)
            print(f"Pulled {n} official cards from \"{config['official_tab']}\" into {dest}")
            print("Restart Motor Pool to load them.")
        else:
            name, n = push(config, Path(s["mm_data"]), a.tab)
            print(f"Pushed {n} calculated vehicles to new tab \"{name}\"")
    except SheetError as e:
        raise SystemExit(f"Sheet: {e}")


if __name__ == "__main__":
    main()
