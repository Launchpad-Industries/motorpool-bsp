# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Link asset cards (by name/variant and card stats) to MegaMek units.

Scoring favours: chassis-name overlap, the card variant appearing in the
unit's model, and card MP / movement type matching the unit. Matches below
a confidence threshold are flagged for human review."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .megamek import Unit

STOP = {"tank", "vehicle", "heavy", "light", "medium", "the", "standard", "mk",
        "conv", "infantry", "battle", "armor", "hover", "wheeled", "tracked"}


def tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower().replace("-", ""))}


@dataclass
class Match:
    unit: Unit | None
    score: float
    runner_up: float
    reasons: list[str]

    @property
    def confident(self) -> bool:
        return self.unit is not None and self.score >= 6 and self.score - self.runner_up >= 1.5


def score(card: dict, u: Unit) -> tuple[float, list[str]]:
    why = []
    name_t, var_t = tokens(card["name"]), tokens(card.get("variant", ""))
    var_t -= {"standard"}
    unit_name_t, model_t = tokens(u.name), tokens(u.model)
    key = name_t - STOP
    shared = key & (unit_name_t | model_t)
    if not shared:
        return -99, ["no name overlap"]
    s = 3.0 * len(shared) / max(1, len(key))
    why.append(f"name {len(shared)}/{len(key)}")
    if var_t:
        hit = var_t & (model_t | unit_name_t)
        s += 3.0 * len(hit) / len(var_t)
        if hit:
            why.append(f"variant {sorted(hit)}")
        elif not u.model:
            s -= 1
    else:
        # Standard card: prefer the base model (empty or standard-looking model).
        if u.model in ("", "(Standard)", "Standard") or "standard" in model_t:
            s += 2; why.append("base model")
    try:
        mp = int(card["mp"])
    except (KeyError, ValueError):
        mp = None
    if card.get("mtype") in ("t", "w", "h", "v", "g"):
        if u.motion == card["mtype"]:
            s += 1; why.append("motion")
        else:
            s -= 3
        if mp is not None:
            if u.cruise_mp == mp:
                s += 2; why.append("MP")
            elif abs(u.cruise_mp - mp) == 1:
                s += 0.5
            else:
                s -= 2
    return s, why


def best_match(card: dict, units: list[Unit]) -> Match:
    scored = sorted(((score(card, u), u) for u in units), key=lambda x: -x[0][0])
    if not scored or scored[0][0][0] <= 0:
        return Match(None, 0, 0, ["no candidate"])
    (s1, why), u1 = scored[0]
    s2 = next((s for (s, _), u in scored[1:] if u.full_name != u1.full_name), 0)
    return Match(u1, s1, s2, why)
