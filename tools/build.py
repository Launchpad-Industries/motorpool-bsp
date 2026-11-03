# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Build the tester zip: dist/MotorPool-vX.Y.Z.zip.

    python tools/build.py             # use ./snapshot (built with --keep-data if missing)
    python tools/build.py --refresh   # refresh MegaMek data and pull the Sheet first

Builds in its own virtual environment (build/venv, pip packages from
requirements-dist.txt) so Anaconda's large libraries stay out of the exe,
then checks the result for anything that looks like a secret. The zip holds
private official card data: share it privately, never publish it."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bsp import __version__  # noqa: E402

BUILD, DIST = ROOT / "build", ROOT / "dist"
VENV = BUILD / "venv"
PACKAGING = ROOT / "packaging"

# Names and contents that must never ship.
SECRET_NAMES = re.compile(r"(^\.env|credentials.*\.json$|token.*\.json$|client_secret|\.pem$|\.key$|"
                          r"^signing_key|^sheet\.json$|^settings\.json$|\.tsv\.bak$)", re.I)
SECRET_TEXT = re.compile(rb"(-----BEGIN [A-Z ]*PRIVATE KEY-----|\"refresh_token\"|\"client_secret\"|"
                         rb"\"private_key\"|ghp_[0-9A-Za-z]{30,}|AIza[0-9A-Za-z_-]{30,})")
TEXT_EXT = {".txt", ".json", ".yaml", ".yml", ".tsv", ".csv", ".html", ".js", ".css", ".py", ".cfg", ".ini", ".env"}


def run(*cmd, **kw):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, **kw)


def pyinstaller_env() -> dict:
    """Anaconda's Python keeps DLLs that its modules need (libffi for ctypes,
    bz2, lzma, expat...) in Library\bin. Put that on PATH so PyInstaller finds
    and bundles them; otherwise the exe only works on machines with Anaconda."""
    env = dict(os.environ)
    lib_bin = Path(sys.base_prefix) / "Library" / "bin"
    if lib_bin.exists():
        env["PATH"] = str(lib_bin) + os.pathsep + env.get("PATH", "")
    return env


def scan_for_secrets(folder: Path) -> list[str]:
    found = []
    for f in folder.rglob("*"):
        if not f.is_file():
            continue
        if SECRET_NAMES.search(f.name):
            found.append(f"name: {f.relative_to(folder)}")
        elif f.suffix.lower() in TEXT_EXT and SECRET_TEXT.search(f.read_bytes()):
            found.append(f"contents: {f.relative_to(folder)}")
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the Motor Pool tester zip")
    ap.add_argument("--refresh", action="store_true", help="refresh MegaMek data and pull the Sheet first")
    a = ap.parse_args(argv)

    snap = [sys.executable, ROOT / "tools" / "build_snapshot.py"]
    if a.refresh:
        run(*snap)
    elif not (ROOT / "snapshot" / "snapshot.json").exists():
        run(*snap, "--keep-data")

    py = VENV / "Scripts" / "python.exe"
    if not py.exists():
        run(sys.executable, "-m", "venv", VENV)
    if subprocess.run([str(py), "-m", "pip", "--version"], capture_output=True).returncode:
        run(py, "-m", "ensurepip", "--upgrade")     # an interrupted earlier build
    run(py, "-m", "pip", "install", "-q", "--upgrade", "pip")
    run(py, "-m", "pip", "install", "-q", "-r", ROOT / "requirements-dist.txt")
    run(py, "-m", "PyInstaller", "motorpool.spec", "--noconfirm", "--clean",
        "--distpath", BUILD / "pyinstaller", "--workpath", BUILD / "work", env=pyinstaller_env())

    name = f"MotorPool-v{__version__}"
    stage = DIST / name
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(BUILD / "pyinstaller" / "MotorPool", stage)
    shutil.copy2(PACKAGING / "README-for-testers.txt", stage / "README-for-testers.txt")
    shutil.copy2(PACKAGING / "NOTICE.txt", stage / "NOTICE.txt")
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE.txt")
    shutil.copytree(ROOT / "snapshot" / "licenses", stage / "licenses")

    problems = scan_for_secrets(stage)
    if problems:
        raise SystemExit("Build stopped: possible secrets in the build:\n  " + "\n  ".join(problems))

    zip_path = DIST / f"{name}.zip"
    zip_path.unlink(missing_ok=True)
    shutil.make_archive(str(DIST / name), "zip", root_dir=DIST, base_dir=name)
    print(f"\nBuilt {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB). No secrets found.")
    print("It contains the private official cards: share it privately only.")


if __name__ == "__main__":
    main()
