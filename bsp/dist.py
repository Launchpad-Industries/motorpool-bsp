# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Distribution mode: the packaged Motor Pool.exe for testers.

On when running frozen (PyInstaller) or with MOTORPOOL_DIST=1. Then the app
reads only the data bundled with it (built by tools/build_snapshot.py):
MegaMek units and sprites, the weapon cache, official cards, approvals and
fonts. Nothing reaches the network: fonts are served locally and PDFs are
printed by the copy of Microsoft Edge that Windows already has, instead of
Playwright's Chromium. Normal development runs are unaffected."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__

DIST = bool(getattr(sys, "frozen", False)) or os.environ.get("MOTORPOOL_DIST") == "1"
# Frozen, this is PyInstaller's bundle folder; otherwise the repository.
ROOT = Path(__file__).resolve().parent.parent
FONTS_CSS = ROOT / "fonts" / "fonts.css"
FONTS_LINK = '<link rel="stylesheet" href="/fonts/fonts.css">'
MANIFEST = ROOT / "snapshot.json"


def manifest() -> dict:
    """What the bundle was built from (empty in development)."""
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def about() -> dict:
    m = manifest()
    return {"version": __version__, "dist": DIST, "data_date": m.get("data_date", ""),
            "megamek_data_commit": m.get("megamek_data_commit", ""),
            "megamek_source_commit": m.get("megamek_source_commit", "")}


def local_fonts() -> bool:
    return DIST and FONTS_CSS.exists()


def long_path(p: Path) -> Path:
    """Windows extended-length form (\\\\?\\C:\\...), so unit files deep in the
    bundle still open when testers unzip into a long folder path: most PCs
    keep the 260-character path limit."""
    if os.name != "nt" or str(p).startswith("\\\\"):
        return p
    return Path("\\\\?\\" + str(p.resolve()))


# --- PDF through Microsoft Edge ---------------------------------------------

PRINT_CSS = "<style>*{-webkit-print-color-adjust:exact;print-color-adjust:exact}</style>"


def edge_path() -> Path | None:
    found = shutil.which("msedge")
    if found:
        return Path(found)
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return p
    return None


def html_to_pdf_edge(html_doc: str) -> bytes:
    """Print an HTML document to PDF with headless Edge (page size and margins
    come from the document's @page rule). Fonts are inlined so nothing loads
    from the network."""
    edge = edge_path()
    if edge is None:
        raise RuntimeError("Microsoft Edge was not found. Use Print view and your browser's "
                           "Print > Save as PDF instead")
    if FONTS_CSS.exists():
        html_doc = html_doc.replace(FONTS_LINK, "<style>" + FONTS_CSS.read_text(encoding="utf-8") + "</style>")
    html_doc = html_doc.replace("</head>", PRINT_CSS + "</head>", 1)
    with tempfile.TemporaryDirectory(prefix="motorpool-") as d:
        src, out = Path(d) / "cards.html", Path(d) / "cards.pdf"
        src.write_text(html_doc, encoding="utf-8")
        subprocess.run(
            [str(edge), "--headless", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", "--disable-extensions", "--disable-sync",
             "--disable-background-networking", "--disable-component-update",
             f"--user-data-dir={Path(d) / 'profile'}", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", src.as_uri()],
            check=False, timeout=180, capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("Edge did not produce a PDF. Use Print view and your browser's "
                               "Print > Save as PDF instead")
        return out.read_bytes()
