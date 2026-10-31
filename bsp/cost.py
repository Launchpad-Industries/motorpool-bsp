# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""BSP cost from an asset spec's own card stats.

Cost (Regular) = base + (offense + defense) / 20, rounded.
Cost (Veteran) = the unrounded Regular cost x 1.15, rounded.

Parameter values were fitted against the official vehicle cards, then
rounded to one decimal place (TechManual style); rounding changed the
average error from 2.30 to 2.36 points. They are starting points to tune,
not published rules."""

from __future__ import annotations

import math
import re

SPEED_FACTOR = [0.44, 0.54, 0.65, 0.77, 0.88, 1.0, 1.12, 1.24, 1.37, 1.5, 1.63,
                1.76, 1.89, 2.02, 2.16, 2.3, 2.44, 2.58, 2.72, 2.86, 3.0, 3.15,
                3.29, 3.44, 3.59, 3.74]

COST_RULES = {
    "base": 7.1,              # points every asset costs
    "offense_scale": 10.1,
    "range_exponent": 0.6,    # offense grows with (long range / 9) ** this
    "if_weight": 0.8,         # IF X counts as X*5 damage at 7/14/21, x this
    "defense_scale": 0.5,
    "tmm_base_tn": 5,           # TMM by 2D6 hit chance from 5+ (see tmm_factor)
    "skill_step": 1.1,        # offense x this per point of Skill below 6
    "veteran": 1.15,
    # Fixed points per launcher / piece. Long Tom (57) from the two Mobile
    # Long Tom cards; the rest scaled from it by one-shot Strike cost
    # (Long Tom 24, Arrow IV 16, Sniper 16, Thumper 12). The early Arrow IV
    # Carrier card (58) is a known outlier; the Pilum fits.
    "arrow_points": 38,
    "artillery_points": {"LT": 57, "Sniper": 38, "Thumper": 29},
    # Flat points for specials that don't scale with firepower.
    # ECM6 from the Savannah (Interdictor) and Browning cards; ECM3 scaled
    # by radius.
    "flat_points": {"Commander": 15, "ECM6": 7, "ECM3": 3.5, "ECM": 7,
                    "PRB": 1,     # sensor, so flat; Beagle 10 BV ~ 0.5 pt
                    "TAG": 2},   # support, so flat; cards fit 2.5-3, Will felt 2 is the most it's worth
    # Special armors multiply defensive BV (MegaMek/TacOps: reactive,
    # reflective and ballistic-reinforced x1.5). Applied to the defense part
    # of cost, not to Check: putting it in Check broke two official cards.
    # AMS works like a special armor against missiles only (-4 on the cluster
    # roll), so it is worth more on tougher units. x1.15 is the most the
    # official AMS cards support; they value AMS at under a point.
    "armor_defense_mult": {"RCA": 1.5, "RFA": 1.5, "BRA": 1.5, "AMS": 1.15},
    # APC X: flat points per level, scaled by how well the carrier protects
    # its troops: sqrt(defensive BV / defensive BV at Check 7, TMM 0). Faster
    # and tougher carriers keep troops alive (Will). Square root so a Check 11
    # carrier pays about twice a Check 7 one, not five times. 1.1 per level
    # fitted on the 7 official APC cards (all Check 5-7).
    "apc_points": 1.1,
    "special_mult": {"Crit-Seeker": 1.1,   # +55% crits per crit roll; cards fit best at 1.1
                     "No Turret": 0.9,     # 10% off offense; Will: 10-20% is right
                     "AI": 1.05}       # set by hand, not fitted (fit gave 0.44 on 4 cards)
}


def speed_factor(mp: int) -> float:
    if 0 <= mp < len(SPEED_FACTOR):
        return SPEED_FACTOR[mp]
    return round((1 + (mp - 5) / 10) ** 1.2, 2)


def check_value(check: int) -> float:
    """Will's rule: Check 7 = 75, +75 per step above, x2/3 per step below."""
    return 75 + 75 * (check - 7) if check >= 7 else 75 * (2 / 3) ** (7 - check)


def p_hit(tn: int) -> float:
    """Chance of rolling tn or more on 2D6 (12 is the best you can need)."""
    tn = max(2, min(12, tn))
    return sum(1 for a in range(1, 7) for b in range(1, 7) if a + b >= tn) / 36


def tmm_factor(tmm: int, rules=None) -> float:
    """How much TMM multiplies defense. With tmm_base_tn set: how many more
    attacks it takes to land a hit, P(hit at base) / P(hit at base + TMM).
    Otherwise the TechManual's 1 + TMM/10."""
    rules = rules or COST_RULES
    base = rules.get("tmm_base_tn")
    if base is None:
        return 1 + tmm / 10
    return p_hit(base) / p_hit(base + tmm)


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
    de = rules["defense_scale"] * check_value(check) * tmm_factor(tmm, rules)
    for key, mult in rules["armor_defense_mult"].items():
        if key in (sp.strip() for sp in specials):
            de *= mult
    raw = rules["base"] + (off + de) / 20
    for key, pts in rules["flat_points"].items():
        if key in (sp.strip() for sp in specials):
            raw += pts
    for sp in specials:
        m = re.fullmatch(r"apc(\d*)", sp.strip().lower())
        if m:
            durability = math.sqrt(de / (rules["defense_scale"] * 75))
            raw += rules["apc_points"] * int(m.group(1) or 1) * durability
    artillery = False
    for sp in specials:
        m = re.fullmatch(r"arrow(\d*)", sp.strip().lower())
        if m:
            raw += rules["arrow_points"] * int(m.group(1) or 1)
        m = re.fullmatch(r"artillery \((\w+)\)(\d*)", sp.strip(), re.I)
        if m:
            artillery = True
            raw += rules["artillery_points"].get(m.group(1), 0) * int(m.group(2) or 1)
    return {"regular": int(math.floor(raw + 0.5)),
            # Artillery assets can't buy Skill upgrades (BSP rules).
            "veteran": None if artillery else int(math.floor(raw * rules["veteran"] + 0.5)),
            "unrounded": raw, "offense_bv": off, "defense_bv": de}
