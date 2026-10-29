# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""First-pass asset spec derivation from a MegaMek unit.

Every rule here is a tunable estimate fitted against the official cards,
not a published formula. All constants live in RULES so the app can expose
them for tuning."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .megamek import Unit

RULES = {
    # Check: armor BV = (armor*2.5 + structure*1.5) * armor mod * motive mod
    "motive_mod": {"t": 0.9, "w": 0.8, "h": 0.55, "v": 0.7, "g": 0.55, "n": 0.6},
    "armor_mod": {4: 2.0, 16: 1.5},          # hardened, ferro-lamellor
    # Lower bound of armor BV for each Check value (fitted to official cards).
    # Midpoints between the official cards' ranges for neighbouring Checks.
    "check_cutoffs": [(754, 12), (559, 11), (395, 10), (353, 9), (199, 8),
                      (128, 7), (80, 6), (0, 5)],
    "threshold_heavy_tons": 75,              # vehicles this heavy get Threshold 8
    # Damage: cluster weapons count at this share of their average damage.
    "cluster_factor": 0.75,
    # Range bracket choice: maximise total damage x (long range ** exponent).
    "range_exponent": 1.5,
    # Indirect fire: IF = round(average LRM/MML hits / 5), only if hits >= this.
    "if_min_hits": 5,
    # Leave LRMs/MMLs out of the direct attack when other weapons reach.
    "if_separate": False,
    # AI special: anti-infantry weapons (MegaMek burst-fire flag, plus all plasma
    # weapons) supply at least this share of the card's main attack.
    "ai_share": 0.5,
    # APC X from troop space (tons): under 4 t carries one platoon (APC1);
    # each full 4 t carries a battle armor squad, which needs 2 APC points.
    "apc_ton_step": 4.0,
    # Arrow IV units keep their other weapons as a regular attack.
    "arrow_keeps_weapons": True,
}

# Artillery pieces and their card codes ("Artillery (LT)" on official cards).
ARTILLERY_CODES = {"Long Tom": "LT", "Sniper": "Sniper", "Thumper": "Thumper"}

_NOT_ATTACKS = ("ams", "anti-missile", "tag", "narc", "arrow", "long tom",
                "sniper", "thumper", "c3", "ecm", "probe")

STANDARD_BRACKETS = [(1, 2, 3), (2, 4, 6), (3, 6, 9), (4, 8, 12), (5, 10, 15),
                     (6, 12, 18), (7, 14, 21), (8, 16, 24), (9, 18, 27)]


@dataclass
class Weapon:
    location: str
    name: str
    damage: float          # average damage per turn
    per_hit: float         # damage of one hit / one cluster group
    long: int
    cluster: bool
    indirect: bool
    bv: float
    anti_infantry: bool = False


@dataclass
class Spec:
    mp: int = 0
    mode: str = ""
    tmm: int = 0
    range: tuple | None = None
    damage: tuple | None = None        # (per hit, hits)
    indirect: int = 0
    arrow: int = 0                     # Arrow IV launchers
    artillery: dict = field(default_factory=dict)   # {"LT": 1, ...}
    check: int = 0
    threshold: int = 5
    specials: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def tmm_for_mp(mp: int) -> int:
    for lo, t in ((25, 6), (18, 5), (10, 4), (7, 3), (5, 2), (3, 1)):
        if mp >= lo:
            return t
    return 0


def _clean(name: str) -> str:
    return re.sub(r"(:OMNI|\(ST\))$", "", name).strip()


def weapons(unit: Unit, table: dict) -> list[Weapon]:
    out = []
    for loc, raw in unit.weapons():
        name = _clean(raw)
        s = table.get(name)
        if not s or any(k in (s.get("name") or name).lower() for k in _NOT_ATTACKS):
            continue
        d = s.get("damage")
        av = s.get("shortAV")
        cluster = not isinstance(d, (int, float))
        if cluster:
            avg = av if isinstance(av, (int, float)) else 0
            per = 5
        else:
            avg = av if isinstance(av, (int, float)) and av > d else d
            per = d
        if not avg:
            continue
        long = s.get("longRange") or 0
        nm = (s.get("name") or name)
        if "MML" in nm:
            long = 21
        out.append(Weapon(loc, nm, float(avg), float(per), int(long), cluster,
                          indirect=("LRM" in nm or "MML" in nm) and "Streak" not in nm,
                          bv=float(s.get("bv") or 0),
                          anti_infantry=("F_BURST_FIRE" in s.get("_flags", [])
                                         or "plasma" in nm.lower())))
    return out


def _bracket_for(long: int) -> tuple:
    best = STANDARD_BRACKETS[0]
    for b in STANDARD_BRACKETS:
        if b[2] <= long:
            best = b
    return best


def derive_damage(ws: list[Weapon], rules=RULES):
    """Pick a range bracket and a damage grouping."""
    front = [w for w in ws if w.location != "Rear"]
    if not front:
        return None, None, []
    if all(w.long < 3 for w in front):
        front = [Weapon(w.location, w.name, w.damage, w.per_hit, 3, w.cluster,
                        w.indirect, w.bv) for w in front]
    cands = sorted({_bracket_for(w.long) for w in front})
    best = None
    for b in cands:
        reach = [w for w in front if w.long >= b[2]]
        if not reach:
            continue
        if rules.get("if_separate") and any(not w.indirect for w in reach):
            # Indirect-capable launchers feed the IF special, not the main attack,
            # when the unit has other weapons at this range.
            reach = [w for w in reach if not w.indirect] or reach
        total = sum(w.damage * (rules["cluster_factor"] if w.cluster else 1) for w in reach)
        score = total * (b[2] ** rules["range_exponent"])
        if best is None or score > best[0]:
            best = (score, b, total, reach)
    if best is None:
        return None, None, []
    _, bracket, total, reach = best
    # Group size: the per-hit damage of the weapon type carrying most damage.
    by_type: dict[str, list[Weapon]] = {}
    for w in reach:
        by_type.setdefault(w.name, []).append(w)
    main = max(by_type.values(), key=lambda g: sum(x.damage for x in g))
    size = main[0].per_hit if not main[0].cluster else min(10, max(5, round(total / max(1, len(reach)))))
    size = max(1, min(int(round(size)), int(round(total))))
    hits = max(1, int(round(total / size)))
    if hits == 1:
        size = int(round(total))
    return bracket, (size, hits), reach


def derive_indirect(ws: list[Weapon], rules=RULES) -> int:
    hits = sum(w.damage for w in ws if w.indirect)
    if hits < rules["if_min_hits"]:
        return 0
    return int(math.floor(hits / 5 + 0.5))


def derive_check(unit: Unit, rules=RULES) -> tuple[int, float]:
    v = (2.5 * unit.total_armor + 1.5 * unit.structure)
    v *= rules["armor_mod"].get(unit.armor_type, 1.0)
    v *= rules["motive_mod"].get(unit.motion, 0.8)
    for lo, chk in rules["check_cutoffs"]:
        if v >= lo:
            return chk, v
    return 5, v


def derive_vehicle(unit: Unit, table: dict, rules=RULES) -> Spec:
    sp = Spec()
    sp.mp = unit.cruise_mp
    sp.mode = unit.motion
    sp.tmm = tmm_for_mp(sp.mp) + (1 if unit.motion in ("v", "g") else 0)
    if unit.armor_type == 22:          # vehicle stealth armor
        sp.tmm += 1
    ws = weapons(unit, table)
    sp.range, sp.damage, reach = derive_damage(ws, rules)
    sp.arrow = sum(1 for _, it in unit.weapons()
                   if (table.get(_clean(it)) or {}).get("name") == "Arrow IV")
    if sp.arrow:
        # Official cards drop the regular attack on Arrow units; the rules allow
        # one (Arrow or regular each turn), so keeping it is a switch.
        if not rules["arrow_keeps_weapons"]:
            sp.range, sp.damage, reach = None, None, []
        sp.specials.append("Arrow" if sp.arrow == 1 else f"Arrow{sp.arrow}")
    for _, it in unit.weapons():
        code = ARTILLERY_CODES.get((table.get(_clean(it)) or {}).get("name"))
        if code:
            sp.artillery[code] = sp.artillery.get(code, 0) + 1
    for code, n in sorted(sp.artillery.items()):
        sp.specials.append(f"Artillery ({code})" + (str(n) if n > 1 else ""))
    total = sum(w.damage for w in reach)
    if total and sum(w.damage for w in reach if w.anti_infantry) >= rules["ai_share"] * total:
        sp.specials.append("AI")
    sp.indirect = derive_indirect(ws, rules)
    sp.check, armor_bv = derive_check(unit, rules)
    sp.threshold = 8 if unit.tonnage >= rules["threshold_heavy_tons"] else 5
    if not unit.has_turret and unit.unit_type == "Tank":
        sp.specials.append("No Turret")
    if sp.indirect:
        sp.specials.append(f"IF{sp.indirect}")
    if unit.troop_space > 0:
        step = rules["apc_ton_step"]
        apc = 1 if unit.troop_space < step else 2 * int(unit.troop_space // step)
        sp.specials.append(f"APC{apc}")
    special_armor = {2: "RCA", 3: "RFA", 26: "BRA"}.get(unit.armor_type)
    if special_armor:
        sp.specials.append(special_armor)
    names = " ".join(w for _, w in unit.weapons()).lower()
    if "tag" in names:
        sp.specials.append("TAG")
    if "anti-missile" in names or "antimissile" in names or " ams" in f" {names}":
        sp.specials.append("AMS")
    if "ecm" in names or "guardian" in names:
        sp.specials.append("ECM")
    if "probe" in names or "beagle" in names:
        sp.specials.append("PRB")
    sp.notes.append(f"armor BV {armor_bv:.0f}")
    return sp
