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
    # Hardened x2 (fitted); ferro-lamellor x1.4: about +25% vs 5-point groups,
    # more vs small hits, and the least that keeps both Eurus cards at Check 11.
    "armor_mod": {4: 2.0, 16: 1.4},
    # Lower bound of armor BV for each Check value (fitted to official cards).
    # Midpoints between the official cards' ranges for neighbouring Checks.
    "check_cutoffs": [(754, 12), (559, 11), (395, 10), (353, 9), (199, 8),
                      (128, 7), (80, 6), (0, 5)],
    "threshold_heavy_tons": 75,              # vehicles this heavy get Threshold 8
    # Damage: cluster weapons count at this share of their average damage.
    "cluster_factor": 1.0,   # averages come from the Cluster Hits Table
    # Range bracket choice: maximise total damage x (long range ** exponent).
    "range_exponent": 1.5,
    # "top_bv": bracket from the highest-BV weapon type (91/110 official
    # ranges); "score": bracket maximising damage x range^exponent (87/110).
    "range_rule": "top_bv",
    "main_share": None,     # see derive_damage
    # Weapons add to damage only if their long range is at least this share
    # of the attack's long range (was the bracket's medium range, 2/3).
    # Will: Catalyst drops secondaries with clearly different ranges; 0.7
    # keeps the Marksman's MRMs (15 of 21) and drops SRMs and short lasers.
    "reach_pct": 0.7,
    "headcap": 12,          # limit headcapper (12+) groups to 10+ point guns
    # Weapon types with under this share of the top type's BV are secondary
    # and don't add to damage (Will: Catalyst throws secondaries away
    # aggressively). 40% keeps the Challenger X's LB 10-X (46%).
    "damage_main_share": 0.4,
    # A weapon type with hits over 5 sets the group size when it carries at
    # least this share of the attack's damage (a "significant minority"); otherwise
    # groups of 5 (Will). Same 30% as damage_main_share.
    "group_share": 0.3,
    "small_exact": 20,      # small-weapon totals up to this keep their total
    # Cluster weapons count this share of their missiles/pellets: a round
    # figure near the Cluster Hits Table average (0.63-0.71). Artemis IV's +2
    # on the roll raises the table average by about 1.2x (Will).
    "cluster_ratio": 0.6,
    "atm_artemis": True,    # ATMs have Artemis IV built in (Will)
    # ATM damage comes in 6-point clusters (Core rules); used for the group
    # size only when ATMs carry the most damage, else groups of 5 (Will).
    "atm_group": 6,
    "artemis_mult": 1.2,
    "mrm_mult": 0.9,        # MRM -1 on the Cluster Hits Table
    # IF X = indirect hits / 5, normal rounding (26/30 official vehicles).
    "if_round": 0.5,
    "rapid_one_group": False,  # UAC/RAC shots as one group (Hetzer (Cell): 30)
    "main_steps": 1,
    # Weapons reaching the bracket's medium range count toward damage.
    "reach_bracket": "medium",
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
    # Commander: C3 Master / C3 Boosted Master (not C3i or slaves), or this
    # many tons of communications equipment.
    "commander_comms_tons": 5.0,
    # Crit-Seeker: small-cluster weapons (SRM, Streak SRM, MML, any LB-X) in the
    # main attack deal at least crit_min_damage (and crit_share of it).
    # MRMs (5-point groups) and smaller LB-X don't count, matching the cards.
    "crit_share": 0.0,
    "crit_min_damage": 14,
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
    if_damage: float | None = None   # damage counted for IF, if not `damage`


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


def weapons(unit: Unit, table: dict, rules=None) -> list[Weapon]:
    rules = rules or RULES
    # Artemis IV fire control: +2 on the Cluster Hits Table roll for its
    # launchers (applied to every LRM/SRM/MML when the unit carries any).
    artemis = any("artemis" in it.lower() for _, it in unit.weapons()) or \
        any("artemis" in it.lower() for it in getattr(unit, "equipment_names", lambda: [])())
    out = []
    for loc, raw in unit.weapons():
        name = _clean(raw)
        s = table.get(name)
        if not s or any(k in (s.get("name") or name).lower() for k in _NOT_ATTACKS):
            continue
        d = s.get("damage")
        av = s.get("shortAV")
        if d == "DAMAGE_VARIABLE":
            # Range-dependent direct-fire weapons (Heavy Gauss 25/20/10, snub-
            # nosed PPC 10/8, variable-speed lasers): use the medium-range
            # value, one hit (Alacorn Mk VII card: Heavy Gauss = 20).
            d = av = s.get("medAV") or av
        missile = not isinstance(d, (int, float))
        # Streak launchers always hit with the full cluster (no table roll),
        # so they aren't discounted like other cluster weapons.
        # Large missiles (Thunderbolts) are one big missile: full damage, one hit.
        large = "F_LARGE_MISSILE" in s.get("_flags", [])
        cluster = missile and not large and "streak" not in (s.get("name") or name).lower()
        if missile:
            # Cluster weapons land cluster_ratio (0.6) of their missiles, about
            # the Cluster Hits Table average (0.63-0.71); Artemis IV x1.2 (its
            # +2 on the roll). Streaks always hit with the full rack.
            avg = av if isinstance(av, (int, float)) else 0
            rack = s.get("rackSize")
            nm0 = (s.get("name") or name).upper()
            if large and isinstance(av, (int, float)):
                avg = av
            elif isinstance(rack, int) and rack > 0:
                pm = 2 if any(k in nm0 for k in ("SRM", "ATM", "SRT")) else 1
                art = artemis and any(k in nm0 for k in ("LRM", "SRM", "MML"))
                if "ATM" in nm0:
                    # ATMs have Artemis-style fire control built in.
                    art = rules.get("atm_artemis", False)
                hits = rack if not cluster else cluster_hits(rack, rules, art)
                if cluster and "MRM" in nm0:
                    # MRMs take -1 on the Cluster Hits Table: ~0.9x the average.
                    hits *= rules.get("mrm_mult", 0.9)
                avg = hits * pm
            per = rules.get("atm_group", 5) if "ATM" in (s.get("name") or name).upper() else 5
            if large:
                per = avg
        else:
            avg = av if isinstance(av, (int, float)) and av > d else d
            per = d
        if not avg:
            continue
        long = s.get("longRange") or 0
        nm = (s.get("name") or name)
        if not missile and ("Ultra" in nm or "Rotary" in nm):
            # UACs fire 2 shots and RACs are usually fired at 5 (avoiding the
            # jam risk at 6); both roll on the Cluster Hits Table (Will). A UAC
            # counts 1.5x (table average 1.42); a RAC 5 shots x cluster_ratio.
            hits = rules.get("uac_mult", 1.5) if "Ultra" in nm else cluster_hits(5, rules)
            avg = d * hits
            per = avg if rules.get("rapid_one_group") else d
        if_dmg = None
        if "MML" in nm:
            # MMLs fire SRMs (2 points per hit, 3/6/9) as their direct attack
            # and LRMs (1 point per hit) for indirect fire.
            m = re.search(r"(\d+)", nm)
            hits = cluster_hits(int(m.group(1)) if m else 3, rules, artemis)
            avg, if_dmg, long = 2 * hits, hits, 9
        out.append(Weapon(loc, nm, float(avg), float(per), int(long), cluster,
                          # Thunderbolts can fire indirectly too, at full damage (Will).
                          indirect=(("LRM" in nm or "MML" in nm) and "Streak" not in nm) or large,
                          bv=float(s.get("bv") or 0),
                          anti_infantry=("F_BURST_FIRE" in s.get("_flags", [])
                                         or "plasma" in nm.lower()),
                          if_damage=if_dmg))
    return out


# Cluster Hits Table (TW p. 74): hits for each 2D6 roll 2..12, by weapon size.
CLUSTER_TABLE = {
    2: [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2], 3: [1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3],
    4: [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4], 5: [1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5],
    6: [2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6], 7: [2, 2, 3, 4, 4, 4, 4, 6, 6, 7, 7],
    9: [3, 3, 4, 5, 5, 5, 5, 7, 7, 9, 9], 10: [3, 3, 4, 6, 6, 6, 6, 8, 8, 10, 10],
    12: [4, 4, 5, 8, 8, 8, 8, 10, 10, 12, 12], 15: [5, 5, 6, 9, 9, 9, 9, 12, 12, 15, 15],
    20: [6, 6, 9, 12, 12, 12, 12, 16, 16, 20, 20], 30: [10, 10, 12, 18, 18, 18, 18, 24, 24, 30, 30],
    40: [12, 12, 18, 24, 24, 24, 24, 32, 32, 40, 40]}
_P2D6 = [n / 36 for n in (1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1)]


def cluster_hits(size: int, rules=None, artemis: bool = False) -> float:
    """Hits counted for a cluster weapon of this size: size x cluster_ratio,
    x artemis_mult with Artemis IV."""
    rules = rules or RULES
    return size * rules["cluster_ratio"] * (rules["artemis_mult"] if artemis else 1)


def average_cluster_hits(size: int, mod: int = 0) -> float:
    """Average hits on the Cluster Hits Table for a weapon of this size, over
    all 36 2D6 results; `mod` shifts the roll (Artemis IV +2), capped at 2-12."""
    col = CLUSTER_TABLE.get(size) or CLUSTER_TABLE[min(CLUSTER_TABLE, key=lambda k: abs(k - size))]
    return sum(p * col[min(10, max(0, i + mod))] for i, p in enumerate(_P2D6))


def _is_lbx(name: str) -> bool:
    n = name.upper()
    return "LB" in n and "X" in n


def _crit_seeker_weapon(name: str) -> bool:
    n = name.upper()
    return _is_lbx(name) or (("SRM" in n or "MML" in n) and "MRM" not in n)


def _crit_seeker_damage(w: "Weapon") -> float:
    """Average damage the weapon lands in 1-2 point clusters. LB-X fire
    cluster rounds: one point per pellet hit on the Cluster Hits Table."""
    if not _crit_seeker_weapon(w.name):
        return 0.0
    if _is_lbx(w.name):
        return cluster_hits(int(w.per_hit), RULES)
    return w.damage


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
                        w.indirect, w.bv, w.anti_infantry, w.if_damage) for w in front]
    if rules.get("range_rule") == "top_bv":
        # The weapon type with the most BV gives the unit its character;
        # its long range sets the bracket (e.g. Bulldog (Plasma): plasma rifle).
        groups: dict[str, list[Weapon]] = {}
        for w in front:
            groups.setdefault(w.name, []).append(w)
        gbv = lambda g: sum(x.bv for x in g)
        top = max(groups.values(), key=gbv)
        b = _bracket_for(top[0].long)
        # Other main weapons (BV at least main_share of the top type's) with a
        # similar bracket (one step away at most) pull the range down to the
        # shorter bracket: Will picks the shorter of two close main weapons
        # (Challenger X: Gauss 7/14/21 + LB 10-X 6/12/18 -> 6/12/18).
        share = rules.get("main_share")
        if share:
            i = STANDARD_BRACKETS.index(b)
            for g in groups.values():
                gb = _bracket_for(g[0].long)
                j = STANDARD_BRACKETS.index(gb)
                if gbv(g) >= share * gbv(top) and i - rules.get("main_steps", 1) <= j < i:
                    b, i = gb, j
        cands = [b]
    else:
        cands = sorted({_bracket_for(w.long) for w in front})
    best = None
    for b in cands:
        # Weapons count toward the attack if they reach this far.
        cut = b[2] if rules.get("reach_bracket", "long") == "long" else b[1]
        if rules.get("reach_steps") is not None:
            # Weapons count if their long range is within this many bracket
            # steps (3 hexes each) of the attack's long range (Will: Catalyst
            # drops secondaries with clearly different ranges).
            cut = b[2] - 3 * rules["reach_steps"]
        if rules.get("reach_pct") is not None:
            # Weapons count if their long range is at least this share of the
            # attack's long range (a relative gap instead of fixed 3-hex steps).
            cut = rules["reach_pct"] * b[2]
        reach = [w for w in front if w.long >= cut]
        dshare = rules.get("damage_main_share")
        if dshare and reach:
            # Secondary weapons (small BV next to the main weapons) don't add
            # to the attack (Will's hand method).
            tbv: dict[str, float] = {}
            for w in reach:
                tbv[w.name] = tbv.get(w.name, 0) + (
                    w.damage if rules.get("main_by") == "damage" else w.bv)
            top_bv = max(tbv.values())
            reach = [w for w in reach if tbv[w.name] >= dshare * top_bv]
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
    gshare = rules.get("group_share")
    if gshare is not None:
        # Will: small weapons (5 damage or less, cluster weapons included)
        # group in 5s; a weapon type with bigger hits that carries a
        # significant share of the damage sets the group size instead
        # (Clan ER medium lasers -> 7).
        tdmg = {k: sum(x.damage for x in g) for k, g in by_type.items()}
        big = [by_type[k][0].per_hit for k in by_type
               if (not by_type[k][0].cluster or by_type[k] is main)
               and tdmg[k] >= gshare * total]
        size = max([5.0] + big)
    size = max(1, min(int(round(size)), int(round(total))))
    hits = max(1, int(math.floor(total / size + rules.get("group_round", 0.5))))
    hc = rules.get("headcap")
    if hc and size >= hc and hits > 1:
        # Headcapper groups (12+) only as many as there are weapons that hit
        # for 10+ on their own: a 10-point gun can be nudged up to 12+, but
        # 5-point missile clusters shouldn't be (Will). Otherwise use 10s.
        big_guns = sum(max(1, int(round(w.damage / w.per_hit))) for w in reach
                       if not w.cluster and w.per_hit >= 10)   # UAC: 2 shots
        if hits > big_guns:
            size = 10
            hits = max(1, int(math.floor(total / size + rules.get("group_round", 0.5))))
    if hits == 1 or rules.get("group_spread"):
        size = int(round(total / hits))
    elif (size <= 5 and rules.get("small_exact") and 5 < total <= rules["small_exact"]
          and abs(size * hits - total) > 1):
        # Small weapons: getting the total right matters more than printing
        # 5-point groups (Will). When 5s miss the total by more than 1, use
        # groups of 3-6 that best keep it, closest to 5 on a tie (and 4 over
        # 6): 12 -> 4x3, 18 -> 6x3.
        # Only for totals up to small_exact; bigger attacks keep 5s.
        t = int(round(total))
        best = None
        for sz in (3, 4, 5, 6):
            for h in {max(1, t // sz), max(1, -(-t // sz))}:
                key = (abs(sz * h - t), abs(sz - 5), sz > 5)
                if best is None or key < best[0]:
                    best = (key, sz, h)
        _, size, hits = best
    return bracket, (size, hits), reach


def derive_indirect(ws: list[Weapon], rules=RULES) -> int:
    hits = sum(w.if_damage if w.if_damage is not None else w.damage
               for w in ws if w.indirect)
    if hits < rules["if_min_hits"]:
        return 0
    return int(math.floor(hits / 5 + rules.get("if_round", 0.5)))


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
    ws = weapons(unit, table, rules)
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
    crit_pool = ws if rules.get("crit_all_weapons") else reach
    crit = sum(_crit_seeker_damage(w) for w in crit_pool if w.location != "Rear")
    if total and crit >= rules["crit_share"] * total and crit >= rules["crit_min_damage"]:
        sp.specials.append("Crit-Seeker")
    if total and sum(w.damage for w in reach if w.anti_infantry) >= rules["ai_share"] * total:
        sp.specials.append("AI")
    sp.indirect = derive_indirect(ws, rules)
    sp.check, armor_bv = derive_check(unit, rules)
    sp.threshold = 8 if unit.tonnage >= rules["threshold_heavy_tons"] else 5
    if not unit.has_turret:          # VTOLs too: all four Warrior cards say No Turret
        sp.specials.append("No Turret")
    if sp.indirect:
        sp.specials.append(f"IF{sp.indirect}")
    if unit.troop_space > 0:
        step = rules["apc_ton_step"]
        apc = 1 if unit.troop_space < step else 2 * int(unit.troop_space // step)
        sp.specials.append(f"APC{apc}")
    comms = 0.0
    for _, it in unit.weapons():
        m = re.match(r"Communications Equipment:SIZE:([\d.]+)", it)
        if m:
            comms += float(m.group(1))
    if any(it in ("ISC3MasterUnit", "ISC3MasterBoostedSystemUnit") for _, it in unit.weapons()) \
            or comms >= rules["commander_comms_tons"]:
        sp.specials.append("Commander")
    special_armor = {2: "RCA", 3: "RFA", 26: "BRA"}.get(unit.armor_type)
    if special_armor:
        sp.specials.append(special_armor)
    names = " ".join(w for _, w in unit.weapons()).lower()
    if "tag" in names:
        sp.specials.append("TAG")
    if "anti-missile" in names or "antimissile" in names or " ams" in f" {names}":
        sp.specials.append("AMS")
    if "watchdog" in names:
        sp.specials.append("ECM3")          # Watchdog CEWS: 3-hex bubble
    elif "ecm" in names or "guardian" in names:
        sp.specials.append("ECM6")          # Guardian, Clan, Angel: 6-hex
    if "probe" in names or "beagle" in names:
        sp.specials.append("PRB")
    sp.notes.append(f"armor BV {armor_bv:.0f}")
    return sp
