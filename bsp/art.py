# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Card images.

Order of preference:
1. The owner's fluff folder: one image per chassis, simplified names such as
   ``drillson.jpg`` or ``scimitar.png`` (case-insensitive; spaces, hyphens and
   underscores are interchangeable). The longest name that matches the start
   of the chassis wins. An optional variant file such as
   ``drillson-streak.png`` overrides it for that variant only.
2. MegaMek's top-down unit sprite (MegaMek Data, CC BY-NC-SA 4.0), looked up
   through mm-data's ``mekset.txt``.
3. None: the card lays out without an image.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

EXTS = (".png", ".jpg", ".jpeg", ".webp")
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp"}
SPRITE_CREDIT = "Unit sprite: MegaMek Data (CC BY-NC-SA 4.0)"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class Art:
    def __init__(self, units_dir: Path | None = None, fluff_dir: Path | None = None):
        """units_dir: mm-data's data/images/units folder (may be None)."""
        self.units_dir = units_dir if units_dir and units_dir.exists() else None
        self.fluff = {}
        if fluff_dir and fluff_dir.exists():
            for f in fluff_dir.iterdir():
                if f.suffix.lower() in EXTS:
                    self.fluff[_slug(f.stem)] = f
        self.exact, self.chassis = {}, {}
        if self.units_dir and (self.units_dir / "mekset.txt").exists():
            for line in (self.units_dir / "mekset.txt").read_text(
                    encoding="utf-8", errors="replace").splitlines():
                m = re.match(r'\s*(exact|chassis)\s+"([^"]+)"\s+"([^"]+)"', line)
                if m:
                    (self.exact if m.group(1) == "exact" else self.chassis)[m.group(2)] = m.group(3)

    def find(self, unit) -> tuple[Path | None, str]:
        """Return (image path, source) for a MegaMek unit: source is
        "fluff", "sprite" or ""."""
        chassis, full = _slug(unit.name), _slug(unit.full_name)
        if full in self.fluff and full != chassis:
            return self.fluff[full], "fluff"
        # Variant override: "<chassis words...> <variant words>" not needed
        # exactly; accept "<first word(s)> <model>".
        model = _slug(unit.model or "")
        best = None
        for key, path in self.fluff.items():
            if model and key.endswith(" " + model) and chassis.startswith(key[: -len(model) - 1]):
                return path, "fluff"
            if chassis == key or chassis.startswith(key + " "):
                if best is None or len(key) > len(best[0]):
                    best = (key, path)
        if best:
            return best[1], "fluff"
        rel = self.exact.get(unit.full_name) or self.chassis.get(unit.name)
        if rel and self.units_dir and (self.units_dir / rel).exists():
            return self.units_dir / rel, "sprite"
        return None, ""

    @staticmethod
    def data_uri(path: Path) -> str:
        mime = MIME.get(path.suffix.lower(), "image/png")
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
