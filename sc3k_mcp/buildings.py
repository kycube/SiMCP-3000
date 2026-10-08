"""Per-building data read from the simulators' agent objects (re/agents/buildings/REPORT.md; verified live in
Berlin: residents summed over buildings = the game's population within 0.04%, coal plant / water tower fields).

Each manager-grid cell points to an agent O (the occupant scan's "ptr"): [O+4] = the building's +0x14 interface
(B14): [B14-8] occupant id, [B14+8] category, [B14+0x24/+0x28] size, [B14+0x12C] agent class; [O+0x14] state.
Zone buildings store no counts: residents/jobs = footprint x the category's SC3ValveLayer.ini effect while the
building is working (state 1), exactly as the game's valve agent adds them.
"""

from __future__ import annotations

import json
import os
import struct
from collections import Counter

from .city import City, agent_name
from .game import jdn_to_date

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EFFECTS = {int(k): v for k, v in json.load(open(os.path.join(_DATA, "valve_effects.json")))["effects"].items()}
_PARENTS = {int(k): int(v) for k, v in json.load(open(os.path.join(_DATA, "agent_types.json"))).get("parents", {}).items()}

STATES = {1: "working", 2: "abandoned", 4: "under_construction", 8: "destroyed", 0x10: "fire_damaged",
          0x20: "crops_eaten"}

POWER_PLANTS = {0x814A0FBD, 0x614A1014, 0xE14A102C, 0xC14A1040, 0xA14A106E, 0x414A1097, 0x214A10AE, 0x614A1057,
                0x2302193A}
WATER_BUILDINGS = {0xA2FD2580, 0x02FD2C92, 0xC2FD2C98}
CLASSES = {0x210D4D78: "police", 0x40FC7753: "fire", 0x22EE7A5B: "jail", 0x612A8F75: "school",
           0xC2EC529C: "college", 0x2123CB83: "hospital", 0xE3319EB4: "library", 0xA3319F62: "museum",
           0x0345776C: "incinerator", 0xC34ACD28: "recycling", 0x62FD2C9F: "water_treatment"}
FUNDING_OFFSET = {"school": 0x30, "college": 0x30, "hospital": 0x34, "library": 0x28, "museum": 0x24}
JAIL_CELLS = 300                                   # SIMSERV 0x1002426C InmateCapacity


def effects(cat: int) -> list:
    seen = 0
    while cat and cat not in EFFECTS and seen < 8:
        cat = _PARENTS.get(cat, 0)
        seen += 1
    return EFFECTS.get(cat, [])


def zone_kind(cat: int) -> dict:
    """Density and land-value band from the game's own type name (e.g. ResMedLVHighD, IndCleanLowDensity)."""
    name = agent_name(cat)
    out = {}
    for prefix, zone in (("Res", "residential"), ("Com", "commercial"), ("Ind", "industrial")):
        if name.startswith(prefix):
            out["zone"] = zone
    if "LV" in name:
        out["wealth"] = {"Low": "low", "Med": "medium", "High": "high"}[name[3:].split("LV")[0]]
    for d, v in (("LowD", "low"), ("MedD", "medium"), ("HighD", "high"), ("LowDensity", "low"),
                 ("MedDensity", "medium"), ("HighDensity", "high")):
        if name.endswith(d):
            out["density"] = v
    if name.startswith("Ind"):
        out["industry"] = "agricultural" if "Agri" in name else ("clean" if "Clean" in name else "dirty")
    return out


class Buildings:
    def __init__(self, city: City, layers):
        self.c = city
        self.g = city.g
        self.layers = layers

    def _age_months(self, built_jdn: int, now) -> int | None:
        if not 2000000 < built_jdn < 3000000:
            return None
        b = jdn_to_date(built_jdn)
        return (now.year * 12 + now.month) - (b.year * 12 + b.month)

    # ---------------------------------------------------------------- Query-window numbers
    # (re/agents/viewsnap/REPORT.md sections 5-6: the game computes these lines when a building is queried)
    TRAFFIC_LEVELS = ((0.8, "Light"), (1.1, "Medium"), (1.5, "Heavy"))

    def _layer(self, name):
        if name not in self._qcache:
            self._qcache[name] = self.layers.get(name)
        return self._qcache[name]

    def _aura(self) -> int:
        from .layers import Layers
        M = Layers(self.c)._find_layer("simmisc.dll", Layers.AURA_VTS)
        return struct.unpack("<b", self.g.proc.read(M + 0xA4, 1))[0] if M else 0

    def _count(self, cat: int) -> int:
        """Buildings of a category as the game counts them (SIMGEOM 0x10003D85: static map category -> count)."""
        n = self.g.call(self.g.mod("simgeom.dll") + 0x3D85, [cat])
        return 0 if n in (0, 0xFFFFFFFF) else n

    def ports(self) -> dict:
        """The airport and seaport Query lines (SIMMISC 0x1000F49C / 0x1000FC5D): traffic = valve supply vs 4,000
        per port building, on-time flights / barnacles from the city aura."""
        out = {}
        aura = self._aura()
        a = (aura + 128) / 255
        for key, cat, valve, label in (("airport", 12310, "commercial", "air_traffic"),
                                       ("seaport", 12330, "industrial", "port_traffic")):
            n = self._count(cat)
            if not n:
                continue
            C = self.c.C
            v = (self.g.i32(self.g.u32(self.g.u32(C + 0xE8) + 0x18) + 0xC) if valve == "commercial"
                 else self.g.i32(self.g.u32(self.g.u32(C + 0xEC) + 0x1C) + 0xC))
            r = v / (4000 * n)
            d = {"buildings": n, label: next((name for lim, name in self.TRAFFIC_LEVELS if r < lim), "Congested")}
            if key == "airport":
                d["on_time_flights_percent"] = min(98, int(a / r * 100)) if r > 0 else 98
            else:
                d["barnacles_removed"] = int((1 - a) * r * 1_000_000)
            out[key] = d
        return out

    def records(self, rect=(-1, -1, -1, -1), details: bool = True) -> list[dict]:
        """Every building (layer-0 occupant with a building object) in the rectangle."""
        self._qcache = {}
        now = jdn_to_date(self.g.i32(self.c.C + 0x138))
        grids = None
        out = []
        for o in self.c.occupants(rect):
            if o["layer"] != 0 or "occupant_id" not in o:
                continue
            O, cat = o["ptr"], o["category"]
            x0, y0, x1, y1 = o["rect"]
            area = (x1 - x0 + 1) * (y1 - y0 + 1)
            state = o.get("state", 0)
            sb = state & 0xFF
            r = {"name": o.get("building") or o["name"], "type": o["name"], "category": cat, "rect": o["rect"],
                 "state": STATES.get(sb, sb)}
            if state & 0x100:
                r["covered_in_garbage"] = True
            if state & 0x200:
                r["historical"] = True
            r.update(zone_kind(cat))
            eff = effects(cat)
            if sb == 1:
                res = sum(area * s for v, s, d in eff if v == 3000)
                jobs = sum(area * d for v, s, d in eff if v == 7000)
                if res:
                    r["residents"] = res
                if jobs:
                    r["jobs"] = jobs
            if details:
                if grids is None:
                    grids = {k: self.layers.get(k) for k in ("power", "water", "landvalue")}
                pw, wa = grids["power"][1], grids["water"][1]
                tiles = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
                r["powered"] = any(pw[x][y] for x, y in tiles)
                r["watered"] = any(wa[x][y] for x, y in tiles)
                ls, lrows = grids["landvalue"]
                r["land_value"] = lrows[x0 >> ls][y0 >> ls]
                r.update(self._class_details(O, now))
            out.append(r)
        return out

    STATIONS = {12210: "bus", 12230: "rail", 12360: "subway", 12361: "subway_rail"}

    def _station(self, cat: int, rect) -> dict:
        """Passengers per day as the game's Query shows it: the traffic density at the station tile x 4.3
        (0 while transit workers strike, T+0x108 == 1)."""
        T = self.g.u32(self.c.C + 0xAC)
        if self.g.proc.read(T + 0x108, 1)[0] == 1:
            return {"kind": "station", "mode": self.STATIONS[cat], "passengers_per_day": 0, "strike": True}
        x0, y0, x1, y1 = rect
        best = max(self.layers._cell(self.g.u32(T + 0x60), "B", x, y)
                   for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))
        return {"kind": "station", "mode": self.STATIONS[cat], "passengers_per_day": round(best * 4.3)}

    def _class_details(self, O: int, now) -> dict:
        g = self.g
        B14 = g.u32(O + 4)
        if not B14:
            return {}
        cls = g.u32(B14 + 0x12C)
        cat = g.u32(B14 + 8)
        if cat in self.STATIONS:
            return self._station(cat, [g.u32(O + 0x10) & 0x7FF, (g.u32(O + 0x10) >> 11) & 0x7FF,
                                       (g.u32(O + 0x10) & 0x7FF) + max(1, g.i32(B14 + 0x24)) - 1,
                                       ((g.u32(O + 0x10) >> 11) & 0x7FF) + max(1, g.i32(B14 + 0x28)) - 1])
        d = {}
        if cls in POWER_PLANTS:
            P = O - 0x30
            usage, cur, nom = g.i32(P + 4), g.i32(P + 8), g.i32(P + 0xC)
            fuel = g.call(g.vfn(P, 0x4C // 4), this=P)
            d.update({"kind": "power_plant", "fuel": self.c.FUELS[fuel] if 0 <= fuel < 10 else fuel,
                      "power_used": usage, "power_capacity": cur, "power_capacity_new": nom,
                      "overworked_months": struct.unpack("<H", g.proc.read(P + 0x10, 2))[0],
                      "max_life_months": g.i32(P + 0x1C), "aging_from_month": g.i32(P + 0x20)})
            if fuel == 8:                               # waste-to-energy: garbage side at P+0x54
                d.update({"garbage_capacity_tons_per_month": round(g.i32(P + 0x58) * 30 * 0.1),
                          "garbage_burned_tons_this_month": round(g.i32(P + 0x5C) * 0.1),
                          "garbage_burned_tons_last_month": round(g.i32(P + 0x60) * 0.1)})
            age = self._age_months(g.i32(P + 0x18), now)
            if age is not None:
                d["age_months"] = age
                d["built"] = jdn_to_date(g.i32(P + 0x18)).isoformat()
        elif cls in WATER_BUILDINGS:
            W = O + 0x24
            mx, cur, use = struct.unpack("<HHH", g.proc.read(W + 8, 6))
            src, intake = struct.unpack("<HH", g.proc.read(W + 0xE, 4))
            d.update({"kind": "water", "source": {2: "tower", 3: "pump", 5: "desalination"}.get(src, src),
                      "water_capacity_new": mx, "water_capacity": cur, "water_used": use,
                      "max_life_months": g.i32(W + 0x1C), "aging_from_month": g.i32(W + 0x20)})
            pos = g.u32(O + 0x10)
            Wm = g.u32(self.c.C + 0xBC)                 # "Connected to Pipe Network" = W vt[0x48](x, y)
            d["connected_to_pipes"] = bool(g.call(g.vfn(Wm, 0x48 // 4), [pos & 0x7FF, (pos >> 11) & 0x7FF],
                                                  this=Wm) & 0xFF)
            if src in (3, 5):     # monthly intake check: pump 0 water next to it, 1 only 2 tiles away (20%), 3 none
                d["intake"] = {0: "ok", 1: "reduced", 3: "no_water"}.get(intake, intake)
            age = self._age_months(g.i32(W + 0x18), now)
            if age is not None:
                d["age_months"] = age
                d["built"] = jdn_to_date(g.i32(W + 0x18)).isoformat()
        elif cls in CLASSES:
            kind = CLASSES[cls]
            d["kind"] = kind
            if kind in ("police", "fire"):
                radius = g.proc.read(O + 0x24, 1)[0]
                d.update({"coverage_radius": radius, "monthly_cost": g.i32(O + 0x2C)})
            elif kind == "jail":
                d.update({"inmates": g.i32(O + 0x24), "cells": JAIL_CELLS, "monthly_cost": g.i32(O + 0x28)})
            elif kind in FUNDING_OFFSET:
                d["monthly_cost"] = g.i32(O + FUNDING_OFFSET[kind])
            elif kind == "water_treatment":
                d.update({"treatment_capacity_per_day": g.i32(O + 0x2C), "treated_this_month": g.i32(O + 0x38)})
            elif kind == "recycling":
                d.update({"garbage_reduction_percent": g.i32(O + 0x28), "population_served": g.i32(O + 0x2C)})
            elif kind == "incinerator":
                d["tons_per_month"] = round(g.i32(O + 0x28) * 30 * 0.125)
                age = self._age_months(g.i32(O + 0x30), now)
                if age is not None:
                    d["age_months"] = age
        return d

    def summary(self) -> dict:
        """City-wide totals by zone, density and wealth, and building states."""
        recs = self.records(details=False)
        out = {"buildings": len(recs), "states": dict(Counter(r["state"] for r in recs)),
               "residents": sum(r.get("residents", 0) for r in recs), "jobs": sum(r.get("jobs", 0) for r in recs)}
        by = {}
        for r in recs:
            if "zone" not in r:
                continue
            key = f"{r['zone']}/{r.get('density', '-')}/{r.get('industry') or r.get('wealth', '-')}"
            b = by.setdefault(key, {"buildings": 0, "working": 0, "abandoned": 0, "residents": 0, "jobs": 0})
            b["buildings"] += 1
            b["working"] += r["state"] == "working"
            b["abandoned"] += r["state"] == "abandoned"
            b["residents"] += r.get("residents", 0)
            b["jobs"] += r.get("jobs", 0)
        out["zones"] = dict(sorted(by.items()))
        # zoned land: tiles per zone type and how many have no building yet (empty lots waiting to develop)
        from .city import ZONE_NAMES
        built = set()
        for r in recs:
            x0, y0, x1, y1 = r["rect"]
            built.update((x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))
        land = {}
        for x, col in enumerate(self.c.zones()):
            for y, z in enumerate(col):
                if 1 <= z <= 11:
                    t = land.setdefault(ZONE_NAMES.get(z, str(z)), {"tiles": 0, "undeveloped": 0})
                    t["tiles"] += 1
                    t["undeveloped"] += (x, y) not in built
        out["zoned_land"] = dict(sorted(land.items()))
        return out
