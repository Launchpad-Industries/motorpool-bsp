# BSP Card Generator
# Copyright (C) 2026 William Becker
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version. See the LICENSE file for details.
#
# Unit data read by this module comes from MegaMek Data
# (https://github.com/MegaMek/mm-data), (C) The MegaMek Team, licensed under
# CC BY-NC-SA 4.0. It is downloaded at run time, not stored in this repository.
"""Read MegaMek .blk unit files (vehicles, infantry, battle armor,
emplacements) into plain Python records."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

_TAG = re.compile(r"<([^/>][^>]*)>\s*\n(.*?)\n?</\1>", re.S)

# Location tags in vehicle files, in armor order.
_LOCATIONS = ["Front", "Right", "Left", "Rear", "Turret", "Front Turret",
              "Rear Turret", "Rotor", "Front Right", "Front Left",
              "Rear Right", "Rear Left", "Body"]

MOTION_CODE = {"tracked": "t", "wheeled": "w", "hover": "h", "vtol": "v",
               "wige": "g", "naval": "n", "hydrofoil": "n", "submarine": "n"}

# MegaMek armor_type codes we care about (others reported by number).
ARMOR_TYPES = {0: "Standard", 1: "Ferro-Fibrous", 2: "Reactive",
               3: "Reflective", 4: "Hardened", 5: "Light Ferro",
               6: "Heavy Ferro", 7: "Patchwork", 8: "Stealth",
               9: "Ferro-Fibrous Prototype", 10: "Commercial",
               14: "Industrial", 15: "Heavy Industrial", 16: "Ferro-Lamellor",
               17: "Primitive", 22: "Vehicle Stealth",
               26: "Ballistic-Reinforced"}


def parse_blk(text: str) -> dict[str, list[str]]:
    """Return {tag: [lines]} for a MegaMek .blk file."""
    out: dict[str, list[str]] = {}
    body = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    for tag, val in _TAG.findall(body):
        out[tag.strip()] = [l.strip() for l in val.splitlines() if l.strip()]
    return out


@dataclass
class Unit:
    path: str
    uuid: str
    mul_id: int | None
    unit_type: str          # Tank, VTOL, Infantry, BattleArmor, GunEmplacement...
    name: str
    model: str
    tonnage: float
    motion: str             # t, w, h, v, g, n, or '' for infantry/emplacements
    cruise_mp: int
    armor_type: int
    armor: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, list[str]] = field(default_factory=dict)
    omni: bool = False
    clan: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.model}".strip()

    @property
    def flank_mp(self) -> int:
        return math.ceil(self.cruise_mp * 1.5)

    @property
    def total_armor(self) -> int:
        return sum(self.armor.values())

    @property
    def has_turret(self) -> bool:
        return any(k in self.armor for k in ("Turret", "Front Turret", "Rear Turret"))

    @property
    def structure(self) -> int:
        """Combat vehicle internal structure: tonnage/10 (round up) per
        location, including turret(s) and rotor."""
        if self.unit_type not in ("Tank", "VTOL"):
            return 0
        per = math.ceil(self.tonnage / 10)
        return per * len(self.armor)

    @property
    def troop_space(self) -> float:
        """Tons of infantry compartment (MegaMek 'troopspace' transporters)."""
        total = 0.0
        for t in self.raw.get("transporters", []):
            if t.lower().startswith("troopspace:"):
                try:
                    total += float(t.split(":")[1])
                except ValueError:
                    pass
        return total

    @property
    def troopers(self) -> int:
        """Battle armor: suits in the squad/Point (1 for other units)."""
        v = (self.raw.get("Trooper Count") or ["1"])[0]
        return int(v) if v.isdigit() else 1

    @property
    def jump_mp(self) -> int:
        return int(float((self.raw.get("jumpingMP") or ["0"])[0] or 0))

    def weapons(self) -> list[tuple[str, str]]:
        """(location, item) pairs, excluding ammo."""
        return [(loc, it) for loc, items in self.equipment.items()
                for it in items if "ammo" not in it.lower()]

    def ammo(self) -> list[str]:
        return [it for items in self.equipment.values()
                for it in items if "ammo" in it.lower()]


def ba_suit_equipment(d: dict) -> list[str]:
    """One battle armor suit's equipment, item names only (mount tags such
    as ':RA', ':APM:LA' or ':Body:Shots2#' dropped; ammo keeps its shots as
    'Name|shots'). Clan files list it under 'Point Equipment', Inner Sphere
    under 'Squad Equipment'; per-trooper lists are added when every trooper
    carries the same thing. Anti-personnel mount weapons are left out."""
    raw = list(d.get("Squad Equipment") or d.get("Point Equipment") or [])
    troopers = [tuple(d.get(f"Trooper {i} Equipment", [])) for i in range(1, 7)
                if f"Trooper {i} Equipment" in d]
    if troopers and len(set(troopers)) == 1:
        raw += list(troopers[0])
    out = []
    for it in raw:
        parts = it.split(":")
        if "APM" in parts[1:]:
            continue
        name = parts[0].strip()
        m = re.search(r"Shots(\d+)#", it)
        out.append(f"{name}|{m.group(1)}" if m and "ammo" in name.lower() else name)
    return out


def load_unit(path: Path) -> Unit:
    d = parse_blk(path.read_text(encoding="utf-8", errors="replace"))
    one = lambda k, default="": (d.get(k) or [default])[0]
    utype = one("UnitType")
    motion = MOTION_CODE.get(one("motion_type").lower(), "")

    locs = [l for l in _LOCATIONS if f"{l} Equipment" in d]
    armor_vals = [int(float(x)) for x in d.get("armor", [])]
    armor: dict[str, int] = {}
    if utype in ("Tank", "VTOL"):
        # Armor lines follow location order; rotor comes after turret for VTOLs.
        order = ["Front", "Right", "Left", "Rear"]
        if utype == "VTOL":
            order.append("Rotor")
        order += [l for l in ("Turret", "Front Turret", "Rear Turret") if l in locs]
        if "Front Right Equipment" in d:   # large support vehicles
            order = ["Front", "Front Right", "Front Left", "Rear Right",
                     "Rear Left", "Rear"] + order[4:]
        armor = dict(zip(order, armor_vals))
    else:
        armor = {"Total": sum(armor_vals)}

    equipment = {l: d[f"{l} Equipment"] for l in locs}
    if utype == "BattleArmor":
        equipment = {"Squad": ba_suit_equipment(d)}
        motion = {"jump": "j", "vtol": "v", "umu": "n"}.get(one("motion_type").lower(), "f")
    mul = one("mul id:")
    return Unit(
        path=str(path), uuid=one("UUID"), mul_id=int(mul) if mul.isdigit() else None,
        unit_type=utype, name=one("Name"), model=one("Model"),
        tonnage=float(one("tonnage", "0") or 0), motion=motion,
        cruise_mp=int(float(one("cruiseMP", "0") or 0)),
        armor_type=int(float(one("armor_type", "0") or 0)),
        armor=armor, equipment=equipment,
        omni=one("omni") in ("1", "true", "TRUE"),
        clan="clan" in one("type").lower(), raw=d)


def load_all(root: Path, folders=("vehicles", "infantry", "battlearmor", "ge")) -> list[Unit]:
    units = []
    for f in folders:
        for p in sorted((root / f).rglob("*.blk")):
            units.append(load_unit(p))
    return units
