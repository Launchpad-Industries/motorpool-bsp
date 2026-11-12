# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Publish the website with the latest cards, in one command.

    python -m bsp.publish              # pull, test, export, commit site/, push
    python -m bsp.publish --dry-run    # everything except the commit and push
    python -m bsp.publish --no-tests   # skip the tests (not recommended)

Steps:
  1. Stop if this folder has uncommitted changes to tracked files: the website
     would otherwise show numbers that aren't in git.
  2. git pull, to get the latest model and app changes.
  3. Run the tests.
  4. Export the website (python -m bsp.export_site). The data label becomes
     today's date, or date.1, .2... if the data already changed today. The app
     version (bsp/__init__.py) is not touched: bump that only for app releases.
  5. If site/ changed, commit just site/ as "Website: data <label>" and push.
     GitHub's "Deploy site" workflow then puts it live in about a minute.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://launchpad-industries.github.io/motorpool-bsp/"


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def step(text: str) -> None:
    print(f"\n== {text}", flush=True)


def data_label() -> str:
    data = json.loads((ROOT / "site" / "data" / "motorpool.json").read_text(encoding="utf-8"))
    return data["info"]["about"].get("data_date", "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Publish the website with the latest cards.")
    ap.add_argument("--dry-run", action="store_true", help="export but don't commit or push")
    ap.add_argument("--no-tests", action="store_true", help="skip the tests")
    a = ap.parse_args(argv)

    step("Checking for uncommitted changes")
    dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!site")
    if dirty:
        sys.exit("These files have uncommitted changes. Commit them (or ask Claude to) "
                 "before publishing, so the website matches what's in git:\n" + dirty)
    # site/ is generated output (e.g. left by a dry run): set it back so the
    # pull can't clash with it; the export below writes it again.
    git("checkout", "--", "site")

    step("Getting the latest changes (git pull)")
    print(git("pull", "--rebase") or "Up to date.")

    if not a.no_tests:
        step("Running the tests")
        if subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT).returncode:
            sys.exit("Tests failed: nothing was published.")

    step("Exporting the website")
    if subprocess.run([sys.executable, "-m", "bsp.export_site"], cwd=ROOT).returncode:
        sys.exit("The export failed: nothing was published.")

    if not git("status", "--porcelain", "--", "site"):
        print("\nThe website is already up to date: nothing to publish.")
        return 0
    label = data_label()
    if a.dry_run:
        print(f"\nDry run: site/ is ready with data {label}, but not committed or pushed.\n"
              "Look at it with: python -m bsp.serve_site")
        return 0

    step(f"Publishing data {label}")
    git("add", "--", "site")
    git("commit", "-q", "-m", f"Website: data {label}")
    git("push", "-q", "origin", "HEAD")
    print(f"\nPushed. The website updates in about a minute: {SITE_URL}\n"
          "(Ctrl+F5 if your browser still shows the old data.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
