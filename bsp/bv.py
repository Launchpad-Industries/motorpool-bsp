# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
#
# Ammo statistics are read from MegaMek's source code (GPL v3) at run time.
"""Total Warfare Battle Value for combat vehicles, following TechManual
pp. 307-308 (Gunnery 4 / Driving 5)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .megamek import Unit

UNIT_TYPE_MOD = {"t": 0.9, "w": 0.8, "h": 0.7, "v": 0.7, "g": 0.7, "n": 0.6}
SPEED_FACTOR = [0.44, 0.54, 0.65, 0.77, 0.88, 1.0, 1.12, 1.24, 1.37, 1.5, 1.63,
                1.76, 1.89, 2.02, 2.16, 2.3, 2.44, 2.58, 2.72, 2.86, 3.0, 3.15,
                3.29, 3.44, 3.59, 3.74]

# Defensive equipment BV by name fragment (TechManual p. 317-318).
DEFENSIVE = [("angel", 100), ("watchdog", 68), ("guardian", 61), ("clecm", 61),
             ("ecm", 61), ("bloodhound", 25), ("clactiveprobe", 12),
             ("beagle", 10), ("activeprobe", 10), ("light active", 7),
             ("lightactiveprobe", 7)]


def speed_factor(mp: int) -> float:
    if mp < len(SPEED_FACTOR):
        return SPEED_FACTOR[mp]
    return round((1 + (mp - 5) / 10) ** 1.2, 2)


def tmm_for_moved(hexes: int) -> int:
    for lo, t in ((25, 6), (18, 5), (10, 4), (7, 3), (5, 2), (3, 1)):
        if hexes >= lo:
            return t
    return 0


# --- ammo table -----------------------------------------------------------

_AMMO_BLOCK = re.compile(r"AmmoType\s+ammo\s*=\s*new\s+AmmoType\(\);(.*?)return\s+ammo;", re.S)


def build_ammo_table(ammo_java: Path) -> dict[str, dict]:
    src = ammo_java.read_text(encoding="utf-8", errors="replace")
    table = {}
    for block in _AMMO_BLOCK.findall(src):
        names = re.findall(r'(?:setInternalName|addLookupName)\("([^"]+)"\)', block)
        bv = re.search(r"ammo\.bv\s*=\s*([\d.]+)", block)
        rack = re.search(r"ammo\.rackSize\s*=\s*(\d+)", block)
        atype = re.search(r"ammo\.ammoType\s*=\s*(?:AmmoTypeEnum\.)?(\w+)", block)
        info = {"bv": float(bv.group(1)) if bv else 0.0,
                "rackSize": int(rack.group(1)) if rack else None,
                "ammoType": atype.group(1) if atype else None}
        for n in names:
            table[n] = info
    return table


def load_ammo(cache: Path, ammo_java: Path | None = None) -> dict:
    if cache.exists():
        return json.loads(cache.read_text())
    t = build_ammo_table(ammo_java)
    cache.write_text(json.dumps(t, indent=1, sort_keys=True))
    return t


# --- BV ---------------------------------------------------------------------

def _clean(name: str) -> str:
    return re.sub(r"(:OMNI|\(ST\))$", "", name).strip()


def _ammo_key(atype) -> str:
    return str(atype or "").split(".")[-1]


def vehicle_bv(unit: Unit, weapons: dict, ammo: dict, detail: bool = False):
    """Return the Total Warfare BV of a combat vehicle (Gunnery 4/Driving 5)."""
    flank = math.ceil(unit.cruise_mp * 1.5)
    jump = 0
    # Defensive
    defensive_bv = 0.0
    off_items = []
    weapon_bv_by_ammo: dict[tuple, float] = {}
    tc = any("targeting computer" in it.lower() or "targetingcomputer" in it.lower()
             for _, it in unit.weapons())
    artemis = sum(1 for _, it in unit.weapons() if "artemis" in it.lower())
    ams_bv = 0.0
    for loc, raw in unit.weapons():
        name = _clean(raw)
        low = name.lower().replace(" ", "")
        s = weapons.get(name)
        if s and ("anti-missile" in (s.get("name") or "").lower() or "ams" == (s.get("name") or "").lower()
                  or "antimissile" in low):
            ams_bv += float(s.get("bv") or 0)
            continue
        if not s:
            for frag, bv in DEFENSIVE:
                if frag.replace(" ", "") in low:
                    defensive_bv += bv
                    break
            continue
        bv = float(s.get("bv") or 0)
        if not bv:
            continue
        key = (_ammo_key(s.get("ammoType")), s.get("rackSize"))
        weapon_bv_by_ammo[key] = weapon_bv_by_ammo.get(key, 0) + bv
        nm = (s.get("name") or "").upper()
        if artemis and ("LRM" in nm or "SRM" in nm) and "STREAK" not in nm:
            bv *= 1.2
        if tc and not any(k in nm for k in ("LRM", "SRM", "MRM", "ATM", "MML", "ROCKET", "FLAMER", "MACHINE GUN")):
            bv *= 1.25
        off_items.append((loc, bv))
    # Ammo (capped by the weapons that use it); AMS ammo is defensive.
    ammo_bv_by_key: dict[tuple, float] = {}
    ams_ammo = 0.0
    for loc, raw in [(l, it) for l, items in unit.equipment.items() for it in items]:
        if "ammo" not in raw.lower():
            continue
        name = _clean(raw)
        a = (ammo.get(name) or ammo.get(name.replace(" - Half", " - Full"))
             or ammo.get(name.replace(" - Full", "").replace(" - Half", "")))
        if not a:
            continue
        frac = 0.5 if "half" in raw.lower() else 1.0
        if _ammo_key(a.get("ammoType")) == "AMS":
            ams_ammo += a["bv"] * frac
            continue
        key = (_ammo_key(a.get("ammoType")), a.get("rackSize"))
        ammo_bv_by_key[key] = ammo_bv_by_key.get(key, 0) + a["bv"] * frac
    ammo_total = 0.0
    for key, v in ammo_bv_by_key.items():
        cap = weapon_bv_by_ammo.get(key)
        if cap is None:   # rack size mismatch (e.g. MG): cap by ammo type only
            cap = sum(b for k, b in weapon_bv_by_ammo.items() if k[0] == key[0])
        ammo_total += min(v, cap)
    # AMS: weapon BV + ammo up to the AMS BV
    defensive_bv += ams_bv + min(ams_ammo, ams_bv)

    # Rear-firing weapons count half (swap if rear is stronger)
    front = sum(b for l, b in off_items if l not in ("Rear",))
    rear = sum(b for l, b in off_items if l == "Rear")
    if rear > front:
        weapon_total = front * 0.5 + rear
    else:
        weapon_total = front + rear * 0.5

    structure = unit.structure
    dbr = unit.total_armor * 2.5 + structure * 1.5 + defensive_bv
    dbr *= UNIT_TYPE_MOD.get(unit.motion, 0.8)
    tmm = tmm_for_moved(flank) + (1 if unit.motion in ("v", "g") else 0)
    dbr *= 1 + tmm / 10
    wbr = weapon_total + ammo_total + unit.tonnage / 2
    obr = wbr * speed_factor(flank)
    bv = dbr + obr
    if detail:
        return {"bv": round(bv), "dbr": dbr, "obr": obr, "weapons": weapon_total,
                "ammo": ammo_total, "defensive": defensive_bv, "flank": flank, "tmm": tmm}
    return round(bv)
