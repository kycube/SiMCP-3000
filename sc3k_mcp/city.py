"""Reading (and changing) a loaded city through memory and the game's own methods.

Layouts and recipes: re/agents/{sim,economy,map,events}/REPORT.md, verified live where noted in
notes/LIVE_FACTS.md. C = the city object (*(STRTSIM 0x10032C9C)).
"""

from __future__ import annotations

import json
import os
import struct

from .game import Game, GameError, jdn_to_date

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


AGENTS = _load("agent_types.json")
AGENT_NAMES = {int(k): v for k, v in AGENTS["types"].items()}
AGENT_PARENTS = {int(k): v for k, v in AGENTS["parents"].items()}
ORDINANCES = _load("ordinances.json")
ORD_BY_ID = {o["id"]: o for o in ORDINANCES}
# advisor message id -> mood 1 (good news) .. 5 (crisis), from SYS.PAK AdvisorMoods.INI / GoldAdvisorMoods.INI
ADVISOR_MOODS = {int(k): v for k, v in
                 json.load(open(os.path.join(DATA, "advisor_moods.json")))["moods"].items()}

# city object fields
C_TERRAIN, C_ZONES, C_POWER, C_WATER = 0xA4, 0xB4, 0xB8, 0xBC
C_ORDINANCES, C_BUDGET, C_POLLUTION, C_CRIME, C_POLICE, C_FIRE = 0xC0, 0xC4, 0xD4, 0xD8, 0xDC, 0xE0
C_RES, C_COM, C_IND, C_LANDVALUE, C_NEIGHBORS, C_PETITIONS = 0xE4, 0xE8, 0xEC, 0xF0, 0xF4, 0x120
C_OCC_MANAGERS = (0x84, 0x88, 0x8C)
C_DISASTERS_ON = 0x1F2

ZONE_NAMES = {0: "none", 1: "res_light", 2: "res_medium", 3: "res_dense", 5: "com_light", 6: "com_medium",
              7: "com_dense", 9: "ind_light", 10: "ind_medium", 11: "ind_dense", 13: "military", 14: "airport",
              15: "seaport", 16: "spaceport", 17: "landfill", 22: "building"}
DEPARTMENTS = {"police": 0xA2963983, "fire": 0x62963928, "health": 0x42922A6C, "education": 0x02922A5D,
               "roads": 0x8290F605, "transit": 0xC290F609}
ZONE_TAX = {"residential": 0, "commercial": 1, "industrial": 2}


def _writable_regions(proc):
    import ctypes
    import ctypes.wintypes as wt
    from .win32 import k32

    class MBI(ctypes.Structure):
        _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                    ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_ulonglong),
                    ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]
    k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    addr, mbi = 0x10000, MBI()
    while addr < 0x7FFF0000:
        if not k32.VirtualQueryEx(proc.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if mbi.State == 0x1000 and (mbi.Protect & 0xFF) in (0x04, 0x08, 0x40, 0x80) and not (mbi.Protect & 0x100):
            yield mbi.BaseAddress, mbi.RegionSize
        addr = mbi.BaseAddress + mbi.RegionSize


def agent_name(cat: int) -> str:
    return AGENT_NAMES.get(cat, f"type_{cat}")


def agent_root(cat: int) -> int:
    """Walk the agent hierarchy up to the child of Buildings/Networks/etc. (for classification)."""
    seen = 0
    while cat in AGENT_PARENTS and AGENT_PARENTS[cat] not in (0, 50, 100, 500) and seen < 20:
        cat = AGENT_PARENTS[cat]
        seen += 1
    return cat


class City:
    def __init__(self, game: Game):
        self.g = game
        self._occ_buf = 0
        self._occ_pid = None

    # ------------------------------------------------------------ helpers
    @property
    def C(self) -> int:
        return self.g.need_city()

    def u8(self, a):
        return self.g.proc.read(a, 1)[0]

    def grid(self, grid_obj: int):
        """{vt, dimX, dimY, rows}: returns (dimX, dimY, rows_ptr)."""
        dx, dy, rows = struct.unpack("<iiI", self.g.proc.read(grid_obj + 4, 12))
        return dx, dy, rows

    def grid_rows(self, grid_obj: int, elem: int = 1, x0: int = 0, x1: int | None = None) -> list[bytes]:
        dx, dy, rows = self.grid(grid_obj)
        x1 = dx - 1 if x1 is None else min(x1, dx - 1)
        ptrs = struct.unpack(f"<{dx}I", self.g.proc.read(rows, 4 * dx))
        return [self.g.proc.read(ptrs[x], elem * dy) for x in range(x0, x1 + 1)]

    def tree(self, head: int, limit: int = 100000) -> list[int]:
        """In-order nodes of an RW/VC6 tree (node +4 parent, +8 left, +0xC right, key at +0x10)."""
        out, stack, n = [], [], self.g.u32(head + 4)
        while (stack or n) and len(out) < limit:
            while n and n != head:
                stack.append(n)
                n = self.g.u32(n + 8)
            if not stack:
                break
            n = stack.pop()
            out.append(n)
            n = self.g.u32(n + 0xC)
            if n == head:
                n = 0
        return out

    def call64(self, fn: int, args=(), this: int = 0) -> int:
        r = self.g._check(self.g.bridge.call_function(fn, args, this))
        return struct.unpack("<q", struct.pack("<ii", r.ret[0], r.ret[1]))[0]

    # ------------------------------------------------------------ statistics
    def demand(self) -> dict:
        C, u, i32 = self.C, self.g.u32, self.g.i32
        valves = {"residential": u(u(C + C_RES) + 0x24), "commercial": u(u(C + C_COM) + 0x18),
                  "industrial": u(u(C + C_IND) + 0x1C)}
        out = {}
        for k, v in valves.items():
            val, mx, mn = i32(v + 0x2C), i32(v + 0x24), i32(v + 0x28)
            out[k] = round(val / mx if val >= 0 else val / abs(mn), 3) if mx and mn else 0
        return out

    def stats(self) -> dict:
        C, u, i32 = self.C, self.g.u32, self.g.i32
        vr, vc, vi = u(u(C + C_RES) + 0x24), u(u(C + C_COM) + 0x18), u(u(C + C_IND) + 0x1C)
        P, W = u(C + C_POWER), u(C + C_WATER)
        pol = u(C + C_POLLUTION)
        return {
            "population": i32(vr + 0xC),
            "commercial_jobs": i32(vc + 0xC),
            "industrial_jobs": i32(vi + 0xC),
            "demand": self.demand(),
            "power": {"capacity": i32(P + 0x5C), "used": i32(P + 0x2D8), "unpowered_buildings": i32(P + 0x2D4),
                      "produced_mwh_last_12_months": self.power_by_type()},
            "water": {"capacity": self.g.i64(W + 0xB0), "used": self.g.i64(W + 0xB8),
                      "unwatered_buildings": i32(W + 0xC4), **self.water_service()},
            "approval": self.approval(),
            "land_value_avg": self.u8(u(C + C_LANDVALUE) + 0xA4),
            "crime_avg": self.u8(u(C + C_CRIME) + 0xA8),
            "pollution": {"air": i32(pol + 0xD0), "water": i32(pol + 0xD4),
                          "garbage": struct.unpack("<H", self.g.proc.read(pol + 0x138, 2))[0]},
            "disasters_enabled": bool(self.u8(C + C_DISASTERS_ON)),
            "auto_budget": bool(self.u8(C + 0x1F1)),
            "disaster_active": self._clock_has_minute_listeners(),
        }

    # plant type index (plant vt[0x4C]) -> fuel; index 0 = power bought from neighbours (verified live: of the shipped
    # cities only Moscow has a buy-power deal, and only Moscow has index 0 non-zero)
    FUELS = ("neighbor_deal", "coal", "fusion", "gas", "microwave", "nuclear", "oil", "solar", "waste_to_energy",
             "wind")

    def power_by_type(self) -> dict:
        """Energy produced over the last 12 months per plant type, MWh: int[10] at P+0x29C (SIMUTIL; the pie chart
        "Annually Averaged Electricity Usage by Type"). Verified in Berlin: coal, nuclear, solar, wind non-zero."""
        P = self.g.u32(self.C + C_POWER)
        vals = struct.unpack("<10i", self.g.proc.read(P + 0x29C, 40))
        return {f: v for f, v in zip(self.FUELS, vals) if v}

    def water_service(self) -> dict:
        """W+0xC0 = buildings that need water (when some lack it), W+0xC4 = buildings without water; served % =
        100 * (C0 - C4) / C0 (re/agents/fields/REPORT.md section 2; Berlin 13,718 / 25)."""
        W = self.g.u32(self.C + C_WATER)
        c0, c4 = self.g.i32(W + 0xC0), self.g.i32(W + 0xC4)
        return {"served_percent": round(100 * (c0 - c4) / c0, 1) if c0 > 0 else 100.0}

    def approval(self) -> dict:
        """The "Approval Rating" graph is owned by the aura simulator: its city-wide aura (s8 at M+0xA4, the average
        of the aura layer, -127..127) is recorded monthly as aura + 127 (0..254) - the values graphs() returns."""
        from .layers import Layers
        M = Layers(self)._find_layer("simmisc.dll", Layers.AURA_VTS)
        if not M:
            return {}
        aura = struct.unpack("<b", self.g.proc.read(M + 0xA4, 1))[0]
        return {"city_aura": aura, "graph_value": aura + 127}

    def _clock_has_minute_listeners(self) -> bool:
        """Disasters subscribe to the clock's minute events (and freeze the calendar) while they run."""
        clk = self.g.u32(self.C + 0x130)
        head = self.g.u32(clk + 4)
        return self.g.u32(head) != head

    # ------------------------------------------------------------ budget
    def budget(self) -> dict:
        C, u = self.C, self.g.u32
        B = u(C + C_BUDGET)
        taxes = {}
        for name, z in ZONE_TAX.items():
            row = B + 0x70 + z * 0x88
            monthly = struct.unpack("<12q", self.g.proc.read(row + 0x20, 96))
            taxes[name] = {"rate": self.u8(row + 0x1C), "max": self.u8(row + 0x1D),
                           "income_ytd": self.g.i64(row + 0x80), "income_by_month": list(monthly)}
        depts = {}
        for node in self.tree(u(B + 0x60)):
            did = u(node + 0x10)
            val = node + 0x18
            item = u(val + 4)
            name = next((k for k, v in DEPARTMENTS.items() if v == did), f"{did:#010x}")
            depts[name] = {"funding_pct": self.u8(val + 8), "monthly_cost": self.g.i64(val + 0x10),
                           "spent_ytd": self.g.i64(val + 0x78), "item": item}
        vt = u(B)
        ytd = {k: self.call64(u(vt + off), this=B) for k, off in
               (("income_ytd", 0x20), ("income_estimate_year", 0x24), ("expense_ytd", 0x28),
                ("expense_estimate_year", 0x2C))}
        bonds = []
        arr, n = u(B + 0x550), self.g.i32(B + 0x554)
        for i in range(max(0, min(n, 50))):
            rec = struct.unpack("<7i", self.g.proc.read(arr + 0x1C * i, 0x1C))
            bonds.append({"month": rec[0], "maturity_year": rec[1], "principal": rec[2], "total_due": rec[3],
                          "remaining": rec[4], "monthly_payment": rec[6]})
        months = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
        ledgers = {}
        for name, off in self.LEDGERS:
            vals = struct.unpack("<12q", self.g.proc.read(B + off, 96))
            ledgers[name] = {"ytd": self.g.i64(B + off + 0x60), "by_month": dict(zip(months, vals))}
        ytd["ledgers"] = ledgers
        return {"funds": self.g.i64(B + 0x38), "taxes": taxes, "departments": depts, **ytd,
                "bonds": bonds, "bond_payments_ytd": self.g.i64(B + 0x588), "debt": self.g.i64(B + 0x590)}

    def set_tax(self, zone: str, rate: int) -> dict:
        """Set a zone tax rate like the budget window's slider does (SIMMISC 0x10023F42): byte + demand valve."""
        if zone not in ZONE_TAX:
            raise GameError(f"zone must be one of {list(ZONE_TAX)}")
        C, u = self.C, self.g.u32
        B = u(C + C_BUDGET)
        z = ZONE_TAX[zone]
        row = B + 0x70 + z * 0x88
        mx = self.u8(row + 0x1D)
        rate = max(0, min(int(rate), mx))
        valve = u(row + 0x18)
        fbits = u(B + 0x208 + 4 * min(rate, 22))
        self.g.call_seq([
            (self.g.vfn(C, 141), C, []),                       # sim-data lock
            (self.g.vfn(valve, 0x6C // 4), valve, [fbits]),
            (self.g.vfn(C, 142), C, []),
        ])
        self.g.proc.write(row + 0x1C, bytes([rate]))
        return {"zone": zone, "rate": rate}

    def set_department_funding(self, dept: str, pct: int) -> dict:
        if dept not in DEPARTMENTS:
            raise GameError(f"department must be one of {list(DEPARTMENTS)}")
        C, u = self.C, self.g.u32
        B = u(C + C_BUDGET)
        out = self.g.scratch() + 0x300
        self.g.proc.write(out, b"\0" * 4)
        found = self.g.call(self.g.vfn(B, 0x38 // 4), [DEPARTMENTS[dept], out], this=B) & 0xFF
        item = u(out)
        if not found or not item:
            raise GameError(f"department {dept} not found (no such service yet?)")
        pct = max(0, min(int(pct), 200))
        self.g.call_seq([(self.g.vfn(item, 0x20 // 4), item, [pct]), (self.g.vfn(B, 0x40 // 4), B, [item])])
        return {"department": dept, "funding_pct": self.g.call(self.g.vfn(item, 0x24 // 4), this=item) & 0xFF}

    def issue_bond(self, amount: int) -> dict:
        B = self.g.u32(self.C + C_BUDGET)
        f0 = self.g.i64(B + 0x38)
        ok = self.g.call(self.g.vfn(B, 0x5C // 4), [int(amount)], this=B) & 0xFF
        return {"ok": bool(ok), "funds_before": f0, "funds": self.g.i64(B + 0x38)}

    # ------------------------------------------------------------ ordinances
    # ledgers in the budget object: int64[12] by calendar month, then the year-to-date int64 at +0x60 (verified in
    # Berlin: deals 1,071 = the Upper Marazan garbage deal; ordinances match the ordinance manager's totals)
    LEDGERS = (("transit_fares", 0x3A0), ("neighbor_deals_income", 0x470), ("neighbor_deals_expense", 0x408),
               ("business_deals_income", 0x4E8), ("ordinances_income", 0x2D0), ("ordinances_expense", 0x268),
               ("other_income", 0x338))

    def ordinances(self) -> list[dict]:
        O = self.g.u32(self.C + C_ORDINANCES)
        out = []
        for node in self.tree(self.g.u32(O + 0x28)):
            oid = self.g.u32(node + 0x10)
            rec = self.g.u32(node + 0x14)          # map value = ordinance record*
            meta = ORD_BY_ID.get(oid, {})
            d = {"id": f"{oid:#010x}", "name": meta.get("name", f"{oid:#010x}"),
                 "enacted": bool(self.u8(rec + 4)), "available": bool(self.u8(rec + 5)),
                 "advisor": meta.get("advisor")}
            if d["enacted"]:
                d["monthly"] = self.g.i32(rec + 0x20)     # + income / - cost this month (sums to O+0x68 / O+0x6C)
            # what the Ordinances window shows for every row: O vt[0x30](id) (SIMMISC 0x1001ABDD, pure; it ignores
            # the enacted flag; re/agents/features/REPORT.md section 5)
            est = self.g.call(self.g.vfn(O, 0x30 // 4), [oid], this=O)
            d["monthly_estimate"] = est - (1 << 32) if est & 0x80000000 else est
            out.append(d)
        return out

    def ordinance_totals(self) -> dict:
        O = self.g.u32(self.C + C_ORDINANCES)
        return {"monthly_income": self.g.i32(O + 0x68), "monthly_cost": self.g.i32(O + 0x6C)}

    def set_ordinance(self, name_or_id, enabled: bool) -> dict:
        O = self.g.u32(self.C + C_ORDINANCES)
        oid = None
        if isinstance(name_or_id, int):
            oid = name_or_id
        else:
            s = str(name_or_id).strip().lower()
            for o in ORDINANCES:
                if o["name"].lower() == s or f"{o['id']:#010x}" == s:
                    oid = o["id"]
            if oid is None:
                cands = [o for o in ORDINANCES if s in o["name"].lower()]
                if len(cands) == 1:
                    oid = cands[0]["id"]
        if oid is None:
            raise GameError(f"unknown ordinance {name_or_id!r}")
        avail = self.g.call(self.g.vfn(O, 0x10 // 4), [oid], this=O) & 0xFF
        if enabled and not avail:
            raise GameError(f"ordinance {ORD_BY_ID.get(oid, {}).get('name', hex(oid))} is not available yet")
        self.g.call(self.g.vfn(O, 0x1C // 4), [oid, 1 if enabled else 0], this=O)
        return {"ordinance": ORD_BY_ID.get(oid, {}).get("name", hex(oid)),
                "enacted": bool(self.g.call(self.g.vfn(O, 0x0C // 4), [oid], this=O) & 0xFF)}

    # ------------------------------------------------------------ petitions
    def petitions(self) -> list[dict]:
        PM = self.g.u32(self.C + C_PETITIONS)
        Q = self.g.u32(PM + 0x28)
        head = self.g.u32(self.g.u32(Q + 4))
        out, node, k = [], self.g.u32(head), 0
        while node and node != head and k < 200:
            e = self.g.u32(node + 8)
            pid, param = struct.unpack("<ii", self.g.proc.read(e, 8))
            out.append({"id": pid, "param": param})
            node = self.g.u32(node)
            k += 1
        return out

    def answer_petition(self, pid: int, accept: bool) -> dict:
        PM = self.g.u32(self.C + C_PETITIONS)
        fn = self.g.mod("simadv.dll") + 0x2096A
        f0 = self.g.i64(self.g.u32(self.C + C_BUDGET) + 0x38)
        self.g.call(fn, [int(pid), 1 if accept else 2], this=PM)
        return {"id": pid, "accepted": accept, "funds_before": f0,
                "funds": self.g.i64(self.g.u32(self.C + C_BUDGET) + 0x38)}

    # ------------------------------------------------------------ neighbors
    def neighbors(self) -> list[dict]:
        """The four neighbor cities: name, mayor, population (records at *(city+0xF4)+0x50, 0x54 bytes each:
        +0x00 name, +0x14 mayor (cRZString), +0x28 population)."""
        N = self.g.u32(self.C + C_NEIGHBORS)
        out = []
        for i in range(4):
            r = N + 0x50 + i * 0x54
            out.append({"name": self.g.rz_string(r), "mayor": self.g.rz_string(r + 0x14),
                        "population": self.g.i32(r + 0x28)})
        return out

    # ------------------------------------------------------------ demographics (re/agents/layers/REPORT.md)
    GRADES = "ABCDF"

    def population_details(self) -> dict:
        """Age structure, education (EQ) and life expectancy, workforce, unemployment, schools / colleges /
        hospitals (city-wide, as the game's Query and graphs show them), aura and garbage figures."""
        g, C = self.g, self.C
        R = g.u32(C + C_RES)
        pop = g.i32(g.u32(R + 0x24) + 0x0C)
        frac = struct.unpack("<90f", g.proc.read(R + 0x354, 360))
        eq = struct.unpack("<90f", g.proc.read(R + 0x84, 360))
        le = struct.unpack("<90f", g.proc.read(R + 0x4BC, 360))

        def mean(vals, a, b):
            xs = [vals[i] for i in range(a, b + 1) if frac[i] > 0]
            return round(sum(xs) / len(xs)) if xs else 0
        work_frac = sum(frac[20:66])
        workers = round(pop * work_frac)
        Wl = g.u32(C + 0xC8)
        jobs = g.i32(g.u32(Wl + 0x28) + 0x10)
        if pop == 0 or jobs >= workers:
            unemployment = 0
        elif jobs == 0:
            unemployment = 100
        else:
            unemployment = (100 * workers - 100 * jobs) // (2 * workers)
        ages = {f"{a}-{a + 9}": round(pop * sum(frac[a:a + 10])) for a in range(0, 90, 10)}
        i32 = lambda o: g.i32(R + o)
        grade = lambda o: self.GRADES[min(4, g.proc.read(R + o, 1)[0])]
        strikes = g.proc.read(R + 0x650, 3)
        # the Population window's three pages: residents, education and life expectancy per age (by decade)
        by_age = {k: {"residents": v, "education_eq": mean(eq, a, a + 9), "life_expectancy": mean(le, a, a + 9)}
                  for (k, v), a in zip(ages.items(), range(0, 90, 10))}
        out = {
            "population": pop, "ages": ages, "by_age": by_age,
            "children_0_19": round(pop * sum(frac[0:20])), "workforce_20_65": workers,
            "seniors_66_plus": round(pop * sum(frac[66:90])), "workforce_percent": round(100 * work_frac),
            "education_eq": mean(eq, 0, 89), "workforce_eq": mean(eq, 20, 65),
            "life_expectancy": mean(le, 0, 89), "workforce_life_expectancy": mean(le, 20, 65),
            "jobs": jobs, "unemployment_percent": unemployment,
            "schools": {"grade": grade(0x660), "students": i32(0x66C), "desks": i32(0x670), "teachers": i32(0x684),
                        "on_strike": bool(strikes[0])},
            "colleges": {"grade": grade(0x661), "students": i32(0x674), "capacity": i32(0x678),
                         "professors": i32(0x688), "on_strike": bool(strikes[1])},
            "hospitals": {"grade": grade(0x662), "patients": i32(0x664), "beds": i32(0x668), "doctors": i32(0x68C),
                          "on_strike": bool(strikes[2])},
        }
        R = g.u32(C + 0xE4)
        out["libraries"] = {"capacity": g.i32(R + 0x67C)}       # sum of the libraries' PopServed (41,000 each)
        out["museums"] = {"capacity": g.i32(R + 0x680)}         # sum of the museums' PopServed (83,000 each)
        P = g.u32(C + C_POLLUTION)
        V = g.u32(P + 0x13C)                                    # landfill valve: +0x10 free units, +0xC pending
        cap = g.u32(P + 0x468) * 0x7FFF
        free = g.i32(V + 0x10) if V else 0
        used = cap - min(cap, max(free, 0))
        out["garbage"] = {"produced_tons_per_year": round(g.i64(P + 0x154) * 0.1),
                          "imported_tons_per_year": round(g.i64(P + 0x15C) * 0.1),
                          "uncollected_tons": round(g.u32(P + 0x464) * 0.1),
                          "recycled_percent": round(struct.unpack("<f", g.proc.read(P + 0x148, 4))[0] * 100),
                          "landfill_used_percent": -(-100 * used // cap) if cap else 0,
                          "landfill_free_tons": round(max(free, 0) * 0.1),
                          "to_landfill": round(g.i64(P + 0x184) * 0.1), "recycled": round(g.i64(P + 0x16C) * 0.1),
                          "incinerated": round(g.i64(P + 0x174) * 0.1),            # incinerators
                          "waste_to_energy": round(g.i64(P + 0x17C) * 0.1),        # burned for power
                          "exported_by_deals": round(g.i64(P + 0x164) * 0.1),
                          "landfill_capacity_tons": round(g.u32(P + 0x468) * 0x7FFF * 0.1),
                          "landfill_tiles": g.u32(P + 0x468)}
        out["pollution_average"] = {"air": g.i32(P + 0xD0), "water": g.i32(P + 0xD4),
                                    "garbage": struct.unpack("<H", g.proc.read(P + 0x138, 2))[0]}
        return out

    # ------------------------------------------------------------ deals (re/agents/deals/REPORT.md)
    DEAL_TYPES = ("buy_power", "sell_power", "buy_water", "sell_water", "export_garbage", "import_garbage")
    CONNECTIONS = (("road", 0x34), ("rail", 0x38), ("water_pipe", 0x3C), ("power_line", 0x40),
                   ("highway", 0x44), ("subway", 0x48))
    NEIGHBOR_EDGES = ("x=0", "y=0", "x=max", "y=max")       # neighbor index -> the map edge it borders

    def _std_list(self, head_ptr: int, limit: int = 500):
        head = self.g.u32(head_ptr)
        node, k = (self.g.u32(head) if head else 0), 0
        while head and node and node != head and k < limit:
            yield self.g.u32(node + 8)
            node = self.g.u32(node)
            k += 1

    def deals(self, which: str = "active") -> list[dict]:
        """Neighbor deals from the game's deal objects: N+0x24 active, N+0x28 pending proposals."""
        N = self.g.u32(self.C + C_NEIGHBORS)
        out = []
        for d in self._std_list(N + (0x24 if which == "active" else 0x28)):
            if not d:
                continue
            raw = self.g.proc.read(d + 0x2C, 0x24)
            qty, monthly = struct.unpack_from("<ii", raw, 0)
            nb, dt = raw[8], raw[9]
            months, minimum, penalty, rate = struct.unpack_from("<iiii", raw, 0x0C)
            jdn = self.g.i32(d + 0x4C)
            from .game import jdn_to_date
            out.append({"neighbor": nb, "type": self.DEAL_TYPES[dt] if dt < 6 else dt, "quantity": qty,
                        "monthly": monthly, "rate_per_1000": rate, "minimum_monthly": minimum,
                        "cancel_penalty": penalty, "months": months,
                        "since": jdn_to_date(jdn).isoformat() if 2000000 < jdn < 3000000 else None})
        return out

    def connections(self, nb: int) -> dict:
        r = self.g.u32(self.C + C_NEIGHBORS) + 0x50 + nb * 0x54
        raw = self.g.proc.read(r + 0x34, 0x18)
        return {name: raw[off - 0x34] for name, off in self.CONNECTIONS if raw[off - 0x34]}

    def deal_penalties_pending(self) -> int:
        return self.g.i32(self.g.u32(self.C + C_NEIGHBORS) + 0x1A8)

    BUSINESS = {19001: "Toxic Waste Conversion Plant", 19002: "Gigamall", 19003: "Casino", 19004: "Prison"}

    def business_deals(self) -> list[dict]:
        """The Budget advisor's business-deal records (F = city+0x108, list at F+0xA4)."""
        F = self.g.u32(self.C + 0x108)
        out = []
        for r in self._std_list(F + 0xA4, 16):
            if not r:
                continue
            pid, bld, year = struct.unpack("<III", self.g.proc.read(r + 4, 12))
            out.append({"building": self.BUSINESS.get(bld, bld), "petition": pid, "from_year": year,
                        "monthly": self.g.i32(r + 0x24), "placed": bool(self.g.proc.read(r + 0x28, 1)[0]),
                        "enabled": bool(self.g.proc.read(r + 0x34, 1)[0])})
        return out

    # ------------------------------------------------------------ advisors (re/agents/advisors/REPORT.md)
    ADVISORS = (("utilities", 0x104), ("budget", 0x108), ("city_planner", 0x10C), ("environment", 0x110),
                ("health_education", 0x114), ("public_safety", 0x118), ("transportation", 0x11C))

    def advice(self) -> dict:
        """What each advisor currently says (the visible entries of its advice list; memory only - asking the
        game for the text would mark it read)."""
        from .text import text as tx
        out = {}
        for name, off in self.ADVISORS:
            adv = self.g.u32(self.C + off)
            if not adv:
                continue
            L = self.g.u32(adv + 0x84)
            items = []
            for e in self._std_list(L + 4, 200):
                if not e or self.g.proc.read(e + 0x13, 1)[0]:
                    continue
                mid = self.g.u32(e + 4)
                tokens = {}
                for_rec = self.g.u32(e + 0x18)
                node, k = (self.g.u32(for_rec) if for_rec else 0), 0
                while for_rec and node and node != for_rec and k < 20:
                    r = node + 8
                    b, en = self.g.u32(r + 0xC), self.g.u32(r + 0x10)
                    tok = self.g.proc.read(b, min(en - b, 40)).decode("cp1252", "replace") if b and en > b else ""
                    typ, val = self.g.i32(r + 4), self.g.i32(r + 0x24)
                    if typ == 1:
                        v = tx(self.g.u32(r + 0x20), self.g.u32(r + 0x1C)) or ""
                    elif typ == 4:
                        v = self.neighbors()[self.g.u32(r + 0x1C)]["name"] if self.g.u32(r + 0x1C) < 4 else ""
                    elif typ == 3:                    # money, as the game's locale prints it (live/t14)
                        v = f"-${-val:,}" if val < 0 else f"${val:,}"
                    elif typ == 2:                    # a locale-formatted number
                        v = f"{val:,}"
                    else:                             # 5: "%d"
                        v = str(val)
                    if tok:
                        tokens[tok] = v
                    node = self.g.u32(node)
                    k += 1
                heading = tx(self.g.u32(L + 0x18), mid) or ""
                message = tx(self.g.u32(L + 0x14), mid) or ""
                for t, v in tokens.items():
                    heading, message = heading.replace(t, v), message.replace(t, v)
                items.append({"id": mid, "heading": heading, "message": message})
            out[name] = items
        return out

    # ------------------------------------------------------------ disasters (re/agents/features/REPORT.md section 2)
    DISASTER_KINDS = {0x621CDA33: "fire", 0x42963812: "earthquake", 0x4296380E: "riot", 0x02963821: "tornado",
                      0x22963800: "toxic_cloud", 0xE2963828: "ufo", 0x13873254: "whirlpool", 0x13873255: "locusts",
                      0x13873256: "space_debris", 0xC4C90997: "parade"}

    def disasters(self) -> dict:
        """Disaster manager DM = *(city+0xD0): instance sets +0x14 (warning phase) and +0x20 (active); each instance
        (one per burning building, riot, swarm...) answers vt[0x20] id, vt[0x10](&x, &y) tile, vt[0x30] buildings
        destroyed, vt[0x34] damage in $ (pure getters)."""
        g, u = self.g, self.g.u32
        DM = u(self.C + 0xD0)
        buf = g.scratch() + 0x380

        def describe(inst):
            did = g.call(g.vfn(inst, 0x20 // 4), this=inst)
            g.proc.write(buf, b"\0" * 8)
            g.call(g.vfn(inst, 0x10 // 4), [buf, buf + 4], this=inst)
            x, y = struct.unpack("<ii", g.proc.read(buf, 8))
            return {"kind": self.DISASTER_KINDS.get(did, f"{did:#010x}"), "x": x, "y": y,
                    "buildings_destroyed": g.call(g.vfn(inst, 0x30 // 4), this=inst),
                    "damage": g.call(g.vfn(inst, 0x34 // 4), this=inst)}

        def instances(off):
            head = u(DM + off)
            return [describe(u(n + 0x10)) for n in self.tree(head, 500)] if head else []

        active = instances(0x20)
        kinds = {}
        for a in active:
            kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
        return {"disaster_mode": bool(self.u8(self.C + 0x38) & 1), "active": active, "active_by_kind": kinds,
                "warning_phase": instances(0x14), "early_warning_on": bool(self.u8(DM + 0xA4)),
                "damage_of_finished": self.g.i32(DM + 0xB4),
                "note": "damage_of_finished is refunded in part (25%, 35% after an early warning) when the "
                        "disaster ends, if it exceeds $500"}

    @staticmethod
    def advisor_mood(items: list[dict]) -> int:
        """The advisor's mood as its panel shows it (SIMADV A vt[0x50] -> 0x100018A5): the integer average of the
        visible messages' moods (unlisted ids count as 0), 3 when it has nothing to say. 1 good .. 5 crisis."""
        if not items:
            return 3
        return sum(ADVISOR_MOODS.get(i["id"], 0) for i in items) // len(items)

    # ------------------------------------------------------------ scenario
    def scenario(self) -> dict:
        """The running scenario (SCENARIO object *(city+0x100)): name, description, goals and their status,
        months elapsed, final rank once ended."""
        from .text import text as tx
        S = self.g.u32(self.C + 0x100)
        if not S:
            return {"scenario": False}
        running = bool(self.g.proc.read(S + 9, 1)[0])
        rank = self.g.i32(S + 0x8D8)
        table = self.g.u32(S + 0x8BC)
        if not running and rank == -1 and not table:
            return {"scenario": False}
        t = self.g.u32(S + 0x8F4)
        name = tx(self.g.u32(t + 0xC), self.g.u32(t + 0x10)) if t else None
        m0, y0, _d, m, y = (self.g.i32(S + o) for o in (0x5C, 0x60, 0x64, 0x68, 0x6C))
        goals = []

        def walk(n, depth=0):
            if not n or depth > 40:
                return
            walk(self.g.u32(n + 8), depth + 1)
            goals.append({"id": self.g.u32(n + 0x10), "met": bool(self.g.proc.read(n + 0x18, 1)[0]),
                          "goal": tx(self.g.u32(n + 0x1C), self.g.u32(n + 0x20))})
            walk(self.g.u32(n + 0xC), depth + 1)
        H = self.g.u32(S + 0x8C0)
        if H:
            root = self.g.u32(H + 4)
            if root != H:
                walk(root)
        out = {"scenario": True, "running": running, "name": name or tx(table, 1),
               "description": tx(table, 0), "months_elapsed": (y - y0) * 12 - m0 + m, "goals": goals}
        if not running and rank != -1:
            out["ended"] = True
            out["rank"] = rank
            r = self.g.u32(S + 0x8DC)
            if r:
                out["result"] = tx(self.g.u32(r + 0xC), self.g.u32(r + 0x10))
        return out

    # ------------------------------------------------------------ news ticker
    TICKER_VT = (0x4D0F4C, 0x4D0D64)       # SC3U.exe ticker window: vtables at +0, +4
    TICKER_CATEGORIES = {0: "status", 1: "alerts", 2: "news", 3: "petitions", 4: "advisors", 5: "other"}

    def _ticker(self) -> int:
        if getattr(self, "_ticker_pid", None) == self.g.proc.pid and self._ticker_obj:
            if self.g.u32(self._ticker_obj) == self.TICKER_VT[0]:
                return self._ticker_obj
        import ctypes
        from .win32 import k32
        pat = struct.pack("<II", *self.TICKER_VT)
        found = 0
        for base, size in _writable_regions(self.g.proc):
            buf = ctypes.create_string_buffer(size)
            got = ctypes.c_size_t()
            if not k32.ReadProcessMemory(self.g.proc.handle, ctypes.c_void_p(base), buf, size, ctypes.byref(got)):
                continue
            i = buf.raw[: got.value].find(pat)
            while i != -1 and i % 4:
                i = buf.raw.find(pat, i + 1)
            if i != -1:
                found = base + i
                break
        if not found:
            raise GameError("news ticker not found")
        self._ticker_obj, self._ticker_pid = found, self.g.proc.pid
        return found

    def ticker_entries(self) -> list[dict]:
        """Every ticker entry with its sequence number (entry +0x04, increasing as items are posted)."""
        obj = self._ticker()
        out = []
        for cat, name in self.TICKER_CATEGORIES.items():
            head = self.g.u32(obj + 0x13C + 4 * cat)
            node, k = self.g.u32(head) if head else 0, 0
            while head and node and node != head and k < 70:
                e = self.g.u32(node + 8)
                s = self.g.u32(e + 0x0C) if e else 0
                if s:
                    out.append({"seq": self.g.u32(e + 4), "category": name, "text": self.g.rz_string(s, 400)})
                node = self.g.u32(node)
                k += 1
        return sorted(out, key=lambda x: x["seq"])

    def news(self) -> dict:
        """Headlines currently in the ticker, per category (the ticker keeps up to 64 per category)."""
        obj = self._ticker()
        out = {}
        for cat, name in self.TICKER_CATEGORIES.items():
            head = self.g.u32(obj + 0x13C + 4 * cat)
            items, node, k = [], self.g.u32(head) if head else 0, 0
            while head and node and node != head and k < 70:
                e = self.g.u32(node + 8)
                s = self.g.u32(e + 0x0C) if e else 0
                if s:
                    items.append(self.g.rz_string(s, 400))
                node = self.g.u32(node)
                k += 1
            if items:
                out[name] = items
        return out

    # ------------------------------------------------------------ graphs (history)
    GRAPH_VTABLES = (("simeco.dll", 0x1CB58), ("simmisc.dll", 0x41B78), ("simrci.dll", 0x4DE78),
                     ("simserv.dll", 0x1FEB4), ("simtransit.dll", 0x1B458))   # graph interface vtables

    def _graph_ifaces(self) -> list[int]:
        key = (self.g.proc.pid, self.C)
        if getattr(self, "_graphs_key", None) == key:
            return self._graphs
        import ctypes
        from .win32 import k32
        vts = {self.g.mod(m) + rva for m, rva in self.GRAPH_VTABLES}
        found = []
        for base, size in _writable_regions(self.g.proc):
            buf = ctypes.create_string_buffer(size)
            got = ctypes.c_size_t()
            if not k32.ReadProcessMemory(self.g.proc.handle, ctypes.c_void_p(base), buf, size, ctypes.byref(got)):
                continue
            data = buf.raw[: got.value]
            for v in vts:
                pat = struct.pack("<I", v)
                i = data.find(pat)
                while i != -1:
                    if i % 4 == 0:
                        found.append(base + i)
                    i = data.find(pat, i + 1)
        # memory still holds graphs of previous cities: keep only those the current city's simulators point to
        C = self.C
        sims = {self.g.u32(C + o) for o in range(0x84, 0x134, 4)}
        vb, ve = self.g.u32(C + 0x94), self.g.u32(C + 0x98)
        if vb and vb < ve <= vb + 0x400:
            sims.update(struct.unpack(f"<{(ve - vb) // 4}I", self.g.proc.read(vb, ve - vb)))
        refs = set()
        for s in sims:
            if s:
                try:
                    refs.update(struct.unpack("<1024I", self.g.proc.read(s - 0x40, 0x1000)))
                except Exception:
                    pass
        found = [i for i in found if (i - 8) in refs or i in refs]
        self._graphs, self._graphs_key = found, key
        return found

    def graphs(self, span: str = "months") -> dict:
        """{name: values} for every simulation graph; months = last 12 (newest first), years = last 10,
        decades = last 10."""
        slot, n = {"months": (10, 12), "years": (13, 10), "decades": (16, 10)}[span]
        buf = self.g.scratch() + 0x800
        out = {}
        for gi in self._graph_ifaces():
            if self.g.u32(gi) not in {self.g.mod(m) + rva for m, rva in self.GRAPH_VTABLES}:
                continue
            s = self.g.call(self.g.vfn(gi, 3), this=gi)
            name = self.g.rz_string(s) if s else f"{gi:#x}"
            self.g.proc.write(buf, b"\0" * (4 * n))
            self.g.call(self.g.vfn(gi, slot), [buf], this=gi)
            out[name] = list(struct.unpack(f"<{n}i", self.g.proc.read(buf, 4 * n)))
        return out

    # ------------------------------------------------------------ map
    def size(self) -> tuple[int, int]:
        return struct.unpack("<ii", self.g.proc.read(self.C + 0x3C, 8))

    def terrain(self):
        """(altitude rows, water rows, sea level): per-vertex u8 grids, (W+1) x (H+1)."""
        dirt = self.g.u32(self.C + C_TERRAIN)
        alt = self.grid_rows(self.g.u32(dirt + 0x30))
        wat = self.grid_rows(self.g.u32(dirt + 0x38))
        return alt, wat, self.u8(dirt + 0x3C)

    def zones(self) -> list[bytes]:
        Z = self.g.u32(self.C + C_ZONES) - 0x10
        return self.grid_rows(self.g.u32(Z + 0x0C))

    def layer(self, which: str) -> tuple[int, list[bytes]]:
        """Per-area byte layer -> (shift, rows). which: crime, police, fire, landvalue."""
        off = {"crime": C_CRIME, "police": C_POLICE, "fire": C_FIRE, "landvalue": C_LANDVALUE}[which]
        main = self.g.u32(self.C + off) - 0x1C
        shift = self.g.i32(main + 0x14)
        return shift, self.grid_rows(self.g.u32(main + 0x18))

    def occupants(self, rect=(-1, -1, -1, -1)) -> list[dict]:
        if self._occ_pid != self.g.proc.pid:
            self._occ_buf = self.g.proc.alloc(0x400000)
            self._occ_pid = self.g.proc.pid
        maxrec = 0x400000 // 32
        out = []
        from .catalog import OCCUPANTS
        for mi, off in enumerate(C_OCC_MANAGERS):
            m = self.g.u32(self.C + off)
            if not m:
                continue
            n, trunc = self.g.bridge.occ_scan(m, self._occ_buf, maxrec, rect)
            raw = self.g.proc.read(self._occ_buf, 32 * n) if n else b""
            for i in range(n):
                p, cat, x0, y0, x1, y1, oid, state = struct.unpack_from("<Ii4iII", raw, 32 * i)
                d = {"layer": mi, "ptr": p, "category": cat, "name": agent_name(cat), "rect": [x0, y0, x1, y1]}
                if oid and oid in OCCUPANTS:
                    d["building"] = OCCUPANTS[oid]["name"]
                    d["occupant_id"] = oid
                    d["state"] = state
                out.append(d)
        return out
