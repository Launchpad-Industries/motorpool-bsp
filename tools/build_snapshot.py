# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Gather the data the packaged Motor Pool reads into ./snapshot.

    python tools/build_snapshot.py               # refresh MegaMek data, pull the Sheet, then copy
    python tools/build_snapshot.py --keep-data   # use the MegaMek data and official.tsv already here
    python tools/build_snapshot.py --offline     # fetch nothing at all (needs an earlier snapshot's fonts)

Run before each release. It may use the network and your Sheet link
(~/.motorpool/sheet.json); the built app uses neither. The snapshot is
build input and is git-ignored (the Sheet stays the master for official cards).

Contents (laid out as the app expects them inside the bundle):
  mm-data/data/mekfiles/vehicles     MegaMek vehicle units (CC BY-NC-SA 4.0)
  mm-data/data/images/units/...      MegaMek vehicle sprites + mekset.txt
  cache/                             weapon and ammo tables from MegaMek source
  data/                              card links and approvals
  official.tsv                       official card stats (from the Sheet)
  bsp-options.tsv                    strike cards (from the Sheet)
  fonts/fonts.css                    Barlow, Barlow Condensed, Oswald (OFL), inlined
  licenses/                          MegaMek data licence, font licences
  snapshot.json                      date, MegaMek commits, counts
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bsp import __version__  # noqa: E402

OUT = ROOT / "snapshot"
MM = ROOT / "mm-data"
UNIT_FOLDERS = ["data/mekfiles/vehicles"]          # what the app loads (Tank, VTOL)
IMAGE_FOLDERS = ["data/images/units/vehicles", "data/images/units/defaults"]
IMAGE_FILES = ["data/images/units/mekset.txt"]
DATA_FILES = ["approvals.yaml", "card_links.yaml", "trusted_keys.yaml"]

FONTS_URL = ("https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&"
             "family=Barlow+Condensed:wght@400;600;700&family=Oswald:wght@400;500;600;700&display=swap")
FONT_LICENCES = {"Barlow": "barlow", "Barlow Condensed": "barlowcondensed", "Oswald": "oswald"}
# A current browser's user agent, so Google Fonts answers with woff2.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def git_commit(repo: Path) -> str:
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip()


def copy_tree(src: Path, dst: Path):
    if not src.exists():
        raise SystemExit(f"Missing {src}. Run python -m bsp.setup_data first.")
    shutil.copytree(src, dst, dirs_exist_ok=True)


def build_fonts(dest: Path):
    """Latin subsets only, embedded as data URIs so the CSS works anywhere
    (including the file Edge prints from)."""
    css = fetch(FONTS_URL).decode("utf-8")
    blocks = re.findall(r"/\* latin \*/\s*(@font-face\s*{[^}]*})", css)
    if not blocks:
        raise SystemExit("Google Fonts answer had no latin font faces.")
    out = []
    for block in blocks:
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        data = base64.b64encode(fetch(url)).decode()
        out.append(block.replace(url, f"data:font/woff2;base64,{data}"))
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "fonts.css").write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the offline data snapshot for the packaged app")
    ap.add_argument("--keep-data", action="store_true",
                    help="don't refresh MegaMek data or pull the Sheet; use what's already here")
    ap.add_argument("--offline", action="store_true",
                    help="--keep-data, and reuse the fonts from the previous snapshot")
    a = ap.parse_args(argv)

    if not (a.offline or a.keep_data):
        from bsp import setup_data
        print("Refreshing MegaMek data and caches...")
        setup_data.main([])
        from bsp import sheet
        if sheet.CONFIG.exists():
            print("Pulling official cards from the Sheet...")
            sheet.main(["pull"])
        else:
            print("No Sheet link set up (python -m bsp.sheet setup); using the existing official.tsv.")

    official = ROOT / "official.tsv"
    if not official.exists():
        raise SystemExit("No official.tsv. Pull it first (python -m bsp.sheet pull).")
    options = ROOT / "bsp-options.tsv"
    if not options.exists():
        raise SystemExit("No bsp-options.tsv. Pull it first (python -m bsp.sheet pull).")

    fonts = OUT / "fonts"
    kept_fonts = OUT.with_name("snapshot-fonts.tmp")
    if a.offline and (fonts / "fonts.css").exists():
        shutil.copytree(fonts, kept_fonts, dirs_exist_ok=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    print("Copying MegaMek units and sprites...")
    for rel in UNIT_FOLDERS + IMAGE_FOLDERS:
        copy_tree(MM / rel, OUT / "mm-data" / rel)
    for rel in IMAGE_FILES:
        (OUT / "mm-data" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MM / rel, OUT / "mm-data" / rel)
    copy_tree(ROOT / "cache", OUT / "cache")
    (OUT / "data").mkdir()
    for name in DATA_FILES:
        if (ROOT / "data" / name).exists():
            shutil.copy2(ROOT / "data" / name, OUT / "data" / name)
    shutil.copy2(official, OUT / "official.tsv")
    shutil.copy2(options, OUT / "bsp-options.tsv")

    lic = OUT / "licenses"
    lic.mkdir()
    mm_licence = subprocess.run(["git", "-C", str(MM), "show", "HEAD:LICENSE"],
                                capture_output=True, text=True, encoding="utf-8")
    if mm_licence.returncode != 0:
        raise SystemExit("Couldn't read mm-data's LICENSE from git.")
    (lic / "MegaMek-Data-LICENSE.txt").write_text(mm_licence.stdout, encoding="utf-8")

    if kept_fonts.exists():
        shutil.copytree(kept_fonts, fonts)
        shutil.rmtree(kept_fonts)
    elif a.offline:
        raise SystemExit("No fonts in an earlier snapshot; run once without --offline.")
    else:
        print("Downloading fonts...")
        build_fonts(fonts)
    for family, folder in FONT_LICENCES.items():
        ofl = fonts / f"OFL-{folder}.txt"
        if not ofl.exists():
            ofl.write_bytes(fetch(f"https://raw.githubusercontent.com/google/fonts/main/ofl/{folder}/OFL.txt"))
        shutil.copy2(ofl, lic / f"Font-{family.replace(' ', '')}-OFL.txt")

    n_units = sum(1 for _ in (OUT / "mm-data" / "data" / "mekfiles" / "vehicles").rglob("*.blk"))
    n_official = sum(1 for line in official.read_text(encoding="utf-8").splitlines()[1:] if line.strip())
    manifest = {
        "app_version": __version__,
        "data_date": date.today().isoformat(),
        "megamek_data_commit": git_commit(MM),
        "megamek_source_commit": git_commit(ROOT / "megamek-src"),
        "vehicle_files": n_units,
        "official_rows": n_official,
    }
    (OUT / "snapshot.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"Snapshot ready in {OUT} ({size / 1e6:.1f} MB): {json.dumps(manifest)}")


if __name__ == "__main__":
    main()
