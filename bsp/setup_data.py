# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Download the MegaMek files this tool needs and build the local caches.

Usage:  python -m bsp.setup_data            (downloads into ./mm-data and ./megamek-src)
        python -m bsp.setup_data --local PATH   (use an existing MegaMek install's data folder)

Only the needed folders are fetched (sparse, shallow clones). Nothing
downloaded here is committed to this repository."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .bv import build_ammo_table
from .weapons import build_table

ROOT = Path(__file__).resolve().parent.parent
DATA_FOLDERS = ["data/mekfiles/vehicles", "data/mekfiles/infantry",
                "data/mekfiles/battlearmor", "data/mekfiles/ge",
                "data/mekfiles/battlefieldsupport",
                # Unit sprites (MegaMek's own art, CC BY-NC-SA) for card images
                "data/images/units/vehicles", "data/images/units/Infantry",
                "data/images/units/battle armor", "data/images/units/GunEmplacements",
                "data/images/units/defaults"]
DATA_FILES = ["data/images/units/mekset.txt"]
SRC_FOLDERS = ["megamek/src/megamek/common/weapons",
               "megamek/src/megamek/common/equipment"]


def sparse_clone(url: str, dest: Path, folders: list[str], files: list[str] = ()):
    patterns = [f"/{f}/" for f in folders] + [f"/{f}" for f in files]
    if (dest / ".git").exists():
        subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone",
                        *patterns], check=True)
        subprocess.run(["git", "-C", str(dest), "pull", "--depth", "1"], check=True)
        return
    dest.mkdir(parents=True, exist_ok=True)
    run = lambda *a: subprocess.run(["git", "-C", str(dest), *a], check=True)
    run("init", "-q")
    run("remote", "add", "origin", url)
    run("sparse-checkout", "set", "--no-cone", *patterns)
    run("fetch", "--depth", "1", "--filter=blob:none", "origin", "HEAD")
    run("checkout", "-q", "FETCH_HEAD")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch MegaMek data and build caches")
    ap.add_argument("--local", type=Path, help="existing MegaMek data/mekfiles folder")
    a = ap.parse_args(argv)
    if not a.local:
        sparse_clone("https://github.com/MegaMek/mm-data.git", ROOT / "mm-data", DATA_FOLDERS, DATA_FILES)
    sparse_clone("https://github.com/MegaMek/megamek.git", ROOT / "megamek-src", SRC_FOLDERS)
    src = ROOT / "megamek-src" / "megamek" / "src" / "megamek" / "common"
    cache = ROOT / "cache"
    cache.mkdir(exist_ok=True)
    import json
    (cache / "weapons.json").write_text(json.dumps(build_table(src / "weapons"), indent=1, sort_keys=True))
    (cache / "ammo.json").write_text(json.dumps(build_ammo_table(src / "equipment" / "AmmoType.java"), indent=1, sort_keys=True))
    print("MegaMek data:", a.local or ROOT / "mm-data" / "data" / "mekfiles")
    print("Caches built in", cache)


if __name__ == "__main__":
    main()
