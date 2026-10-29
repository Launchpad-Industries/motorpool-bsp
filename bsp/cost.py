# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""BSP cost from an asset spec's own card stats.

Cost (Regular) = base + (offense + defense) / 20, rounded.
Cost (Veteran) = the unrounded Regular cost x 1.15, rounded.

Parameter values were fitted against 110 official vehicle cards (average
error about 2.9 points on cards left out of the fit). They are starting
points to tune, not published rules."""

from __future__ import annotations

import math
import re

SPEED_FACTOR = [0.44, 0.54, 0.65, 0.77, 0.88, 1.0, 1.12, 1.24, 1.37, 1.5, 1.63,
                1.76, 1.89, 2.02, 2.16, 2.3, 2.44, 2.58, 2.72, 2.86, 3.0, 3.15,
                3.29, 3.44, 3.59, 3.74]

COST_RULES = {
    "base": 7.991,              # points every asset costs
    "offense_scale": 9.563,
    "range_exponent": 0.579,    # offense grows with (long range / 9) ** this
    "if_weight": 0.833,         # IF X counts as X*5 damage at 7/14/21, x this
    "defense_scale": 0.574,     # x the Check value curve below
    "skill_step": 1.101,        # offense x this per point of Skill below 6
    "veteran": 1.15,
    # Fixed points per Arrow IV launcher, set by Will: between what the
    # Arrow IV Carrier (~24) and the newer Pilum (~42) imply.
    "arrow_points": 30,
    "special_mult": {"Crit-Seeker": 1.054, "TAG": 1.049, "ECM": 1.624,
                     "PRB": 1.079, "AMS": 1.028, "APC": 1.129,
                     "No Turret": 0.876,
                     "AI": 1.05}       # set by hand, not fitted (fit gave 0.44 on 4 cards)
}


def speed_factor(mp: int) -> float:
    if 0 <= mp < len(SPEED_FACTOR):
        return SPEED_FACTOR[mp]
    return round((1 + (mp - 5) / 10) ** 1.2, 2)


def check_value(check: int) -> float:
    """Will's rule: Check 7 = 75, +75 per step above, x2/3 per step below."""
    return 75 + 75 * (check - 7) if check >= 7 else 75 * (2 / 3) ** (7 - check)


def _has(specials: list[str], key: str) -> bool:
    return any(s.split()[0].rstrip("0123456789").lower() == key.lower().split()[0]
               or s.lower().startswith(key.lower()) for s in specials)


def cost(mp: int, tmm: int, damage: tuple | None, rng: tuple | None, skill: int,
         check: int, indirect: int = 0, specials: list[str] | None = None,
         rules=COST_RULES) -> dict:
    specials = specials or []
    off = 0.0
    if damage and rng:
        total = damage[0] * damage[1]
        direct = total * (rng[2] / 9) ** rules["range_exponent"]
        ind = rules["if_weight"] * indirect * 5 * (21 / 9) ** rules["range_exponent"]
        off = max(direct, ind)
    elif indirect:
        off = rules["if_weight"] * indirect * 5 * (21 / 9) ** rules["range_exponent"]
    off *= speed_factor(mp) * rules["offense_scale"]
    off *= rules["skill_step"] ** (6 - skill)
    for key, mult in rules["special_mult"].items():
        if any(s.lower().replace("-", "").startswith(key.lower().replace("-", ""))
               for s in specials):
            off *= mult
    de = rules["defense_scale"] * check_value(check) * (1 + tmm / 10)
    raw = rules["base"] + (off + de) / 20
    for sp in specials:
        m = re.fullmatch(r"arrow(\d*)", sp.strip().lower())
        if m:
            raw += rules["arrow_points"] * int(m.group(1) or 1)
    return {"regular": int(math.floor(raw + 0.5)),
            "veteran": int(math.floor(raw * rules["veteran"] + 0.5)),
            "unrounded": raw, "offense_bv": off, "defense_bv": de}
