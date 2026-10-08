"""Per-tile data layers, read straight from the simulators' grids (re/agents/layers/REPORT.md, verified live in
Berlin): the same values the game's data views and Query tool show.

Every layer is returned as (shift, rows): value(x, y) = rows[x >> shift][y >> shift] (shift 0 = per tile).
"""

from __future__ import annotations

import struct

from .city import City, C_CRIME, C_FIRE, C_LANDVALUE, C_POLICE, C_POLLUTION, C_POWER, C_WATER

C_TRAFFIC = 0xAC
POLLUTION_MAX = 11000                         # the game's air / water pollution scale (SIMECO 0x1002025C)

# layer -> what it holds (for the legend)
LAYERS = {
    "landvalue": "land value 0..255",
    "crime": "crime 0..255",
    "police": "police coverage 0..255",
    "fire": "fire coverage 0..255",
    "air": "air pollution 0..~11000 (2x2-tile cells)",
    "water_pollution": "water pollution 0..~11000 (2x2-tile cells)",
    "radiation": "radiation 0/1",
    "garbage": "garbage in landfills 0..32767 (landfill tiles only)",
    "power": "powered 1/0",
    "water": "watered 1/0",
    "pipes": "water pipe network 1/0",
    "traffic": "traffic density 0..255 on roads, rail, highways and subways",
    "aura": "aura / mayor approval -128..127 (4x4-tile cells, higher is better)",
    "flammability": "flammability 0..255 (filled in by the game as needed; 0 = not computed)",
    "density": "the game's Density data map 0..255: residents and jobs per tile of working buildings, last month",
}
BOOLEAN = ("power", "water", "pipes", "radiation")

# the game's Query-tool wording (thresholds from the query code)
_POLL_LABELS = ((0, "None"), (POLLUTION_MAX / 8, "Low"), (POLLUTION_MAX / 4, "Medium"), (POLLUTION_MAX / 2, "High"),
                (POLLUTION_MAX * 4 / 5, "Very High"))
LABELS = {
    "crime": ((0, "None"), (47, "Low"), (84, "Medium"), (122, "High"), (151, "Very High")),
    "landvalue": ((35, "Very Low"), (75, "Low"), (130, "Medium"), (175, "High"), (225, "Very High")),
    "traffic": ((0, "None"), (65, "Light"), (130, "Medium"), (180, "Heavy")),
}


def label(layer: str, v: int) -> str | None:
    if layer in ("air", "water_pollution"):
        if v == 0:
            return "None"
        for lim, name in _POLL_LABELS[1:]:
            if v < lim:
                return name
        return "Hazardous"
    table = LABELS.get(layer)
    if not table:
        return None
    if layer in ("crime", "traffic") and v == 0:
        return "None"
    for lim, name in (table if layer == "landvalue" else table[1:]):
        if v < lim:
            return name
    return {"crime": "Rampant", "landvalue": "Astronomical", "traffic": "Congested"}[layer]


def digit(layer: str, v: int) -> str:
    """One character for map_text."""
    if layer in BOOLEAN:
        return "+" if v else "."
    if layer in ("air", "water_pollution"):
        return str(min(9, v * 10 // (POLLUTION_MAX + 1)))
    if layer == "garbage":
        return str(min(9, v * 10 // 32768))
    if layer == "aura":
        return str(min(9, (v + 128) * 10 // 256))
    return str(min(9, v * 10 // 256))


class Layers:
    def __init__(self, city: City):
        self.c = city
        self.g = city.g

    # ---- raw grid helpers
    def _rows(self, grid_obj: int, fmt: str) -> list[tuple]:
        dx, dy, rows = struct.unpack("<iiI", self.g.proc.read(grid_obj + 4, 12))
        ptrs = struct.unpack(f"<{dx}I", self.g.proc.read(rows, 4 * dx))
        size = struct.calcsize(fmt)
        return [struct.unpack(f"<{dy}{fmt}", self.g.proc.read(p, size * dy)) for p in ptrs]

    def _bits_xy(self, bitgrid: int) -> list[list[int]]:
        """Bit grid {+4 W, +8 H, +0xC words per row, +0x10 rows}: rows[x] words, bit y (power)."""
        w, h, wpr, rows = struct.unpack("<iiiI", self.g.proc.read(bitgrid + 4, 16))
        ptrs = struct.unpack(f"<{w}I", self.g.proc.read(rows, 4 * w))
        out = []
        for p in ptrs:
            words = struct.unpack(f"<{wpr}I", self.g.proc.read(p, 4 * wpr))
            out.append([(words[y >> 5] >> (y & 31)) & 1 for y in range(h)])
        return out

    def _bits_rowmajor(self, ptr: int, dim: int) -> list[list[int]]:
        """dim x dim bit array, index y*dim + x (water)."""
        n = (dim * dim + 31) // 32
        words = struct.unpack(f"<{n}I", self.g.proc.read(ptr, 4 * n))
        return [[(words[(y * dim + x) >> 5] >> ((y * dim + x) & 31)) & 1 for y in range(dim)] for x in range(dim)]

    def _find_layer(self, module: str, vtables: dict) -> int:
        """Main object of a simulator found through the city's layer vector (city+0x94..+0x98)."""
        base = self.g.mod(module)
        vts = {base + rva: off for rva, off in vtables.items()}
        b, e = self.g.u32(self.c.C + 0x94), self.g.u32(self.c.C + 0x98)
        for p in struct.unpack(f"<{(e - b) // 4}I", self.g.proc.read(b, e - b)):
            off = vts.get(self.g.u32(p))
            if off is not None:
                return p - off
        return 0

    AURA_VTS = {0x3C250: 0, 0x3C208: 0x1C, 0x3C1C0: 0x20, 0x3C190: 0x24, 0x3C168: 0x28, 0x3C150: 0x2C}
    FLAM_VTS = {0x1F2C8: 0, 0x1F2B0: 0x10, 0x1F268: 0x14, 0x1F238: 0x18, 0x1F220: 0x1C, 0x1F20C: 0x20}

    # ---- layers
    def get(self, name: str) -> tuple[int, list]:
        C = self.c.C
        if name in ("landvalue", "crime", "police", "fire"):
            off = {"crime": C_CRIME, "police": C_POLICE, "fire": C_FIRE, "landvalue": C_LANDVALUE}[name]
            main = self.g.u32(C + off) - 0x1C
            return self.g.i32(main + 0x14), self._rows(self.g.u32(main + 0x18), "B")
        if name in ("air", "water_pollution", "radiation"):
            P = self.g.u32(C + C_POLLUTION)
            cells = self._rows(self.g.u32(P - 4), "I")
            f = {"air": lambda v: (v >> 15) & 0x7FFF, "water_pollution": lambda v: v & 0x7FFF,
                 "radiation": lambda v: v >> 31}[name]
            return self.g.i32(P - 8), [[f(v) for v in row] for row in cells]
        if name == "garbage":
            P = self.g.u32(C + C_POLLUTION)
            return 0, [[v & 0x7FFF for v in row] for row in self._rows(self.g.u32(P + 0x128 + 0xC), "H")]
        if name == "power":
            main = self.g.u32(C + C_POWER) - 0x14
            return 0, self._bits_xy(self.g.u32(main + 0xC))
        if name in ("water", "pipes"):
            W = self.g.u32(C + C_WATER)
            dim = struct.unpack("<H", self.g.proc.read(W + 8, 2))[0]
            return 0, self._bits_rowmajor(self.g.u32(W + (0x68 if name == "water" else 0x70)), dim)
        if name == "traffic":
            T = self.g.u32(C + C_TRAFFIC)
            flags = self._rows(self.g.u32(T + 0x5C), "H")
            surf, hwy, sub = (self._rows(self.g.u32(T + o), "B") for o in (0x60, 0x64, 0x68))
            out = []
            for x, frow in enumerate(flags):
                row = []
                for y, f in enumerate(frow):
                    v = 0
                    if f & 0x35:
                        v = surf[x][y]
                    if f & 2:
                        v = max(v, hwy[x][y])
                    if f & 8:
                        v = max(v, sub[x][y])
                    row.append(v)
                out.append(row)
            return 0, out
        if name == "aura":
            M = self._find_layer("simmisc.dll", self.AURA_VTS)
            if not M:
                raise ValueError("aura layer not found")
            return self.g.i32(M + 0x14), self._rows(self.g.u32(M + 0x18), "b")
        if name == "flammability":
            M = self._find_layer("simserv.dll", self.FLAM_VTS)
            if not M:
                raise ValueError("flammability layer not found")
            return 0, self._rows(self.g.u32(M + 0xC), "B")
        if name == "density":
            return 0, self._rows(self._density_grid(), "B")
        raise ValueError(f"unknown layer {name!r}: one of {list(LAYERS)}")

    def _density_grid(self) -> int:
        """Valve layer V = *(budget+0x30): V+0x38 = last month's per-tile density map (SIMRCI map object, grid at
        +0xC): each working building adds its residents (R/C/I supply) and jobs per tile, capped at 255
        (re/agents/fields/REPORT.md section 4)."""
        V = self.g.u32(self.g.u32(self.c.C + 0xC4) + 0x30)
        return self.g.u32(self.g.u32(V + 0x38) + 0xC)

    def traffic_networks(self) -> list[tuple]:
        """Per-tile network flags (1 road, 2 highway, 4 rail, 8 subway, 0x10 station)."""
        T = self.g.u32(self.c.C + C_TRAFFIC)
        return self._rows(self.g.u32(T + 0x5C), "H")

    # ---- single cells (tile_info)
    def _cell(self, grid_obj: int, fmt: str, x: int, y: int):
        dx, dy, rows = struct.unpack("<iiI", self.g.proc.read(grid_obj + 4, 12))
        if not (0 <= x < dx and 0 <= y < dy):
            raise IndexError
        size = struct.calcsize(fmt)
        return struct.unpack("<" + fmt, self.g.proc.read(self.g.u32(rows + 4 * x) + size * y, size))[0]

    def value(self, name: str, x: int, y: int) -> int:
        C = self.c.C
        if name in ("landvalue", "crime", "police", "fire"):
            off = {"crime": C_CRIME, "police": C_POLICE, "fire": C_FIRE, "landvalue": C_LANDVALUE}[name]
            main = self.g.u32(C + off) - 0x1C
            s = self.g.i32(main + 0x14)
            return self._cell(self.g.u32(main + 0x18), "B", x >> s, y >> s)
        if name in ("air", "water_pollution", "radiation"):
            P = self.g.u32(C + C_POLLUTION)
            s = self.g.i32(P - 8)
            v = self._cell(self.g.u32(P - 4), "I", x >> s, y >> s)
            return {"air": (v >> 15) & 0x7FFF, "water_pollution": v & 0x7FFF, "radiation": v >> 31}[name]
        if name == "garbage":
            P = self.g.u32(C + C_POLLUTION)
            return self._cell(self.g.u32(P + 0x128 + 0xC), "H", x, y) & 0x7FFF
        if name == "power":
            B = self.g.u32(self.g.u32(C + C_POWER) - 0x14 + 0xC)
            rows = self.g.u32(B + 0x10)
            return (self.g.u32(self.g.u32(rows + 4 * x) + 4 * (y >> 5)) >> (y & 31)) & 1
        if name in ("water", "pipes"):
            W = self.g.u32(C + C_WATER)
            dim = struct.unpack("<H", self.g.proc.read(W + 8, 2))[0]
            i = y * dim + x
            return (self.g.u32(self.g.u32(W + (0x68 if name == "water" else 0x70)) + 4 * (i >> 5)) >> (i & 31)) & 1
        if name == "traffic":
            T = self.g.u32(C + C_TRAFFIC)
            f = self._cell(self.g.u32(T + 0x5C), "H", x, y)
            v = 0
            for mask, off in ((0x35, 0x60), (2, 0x64), (8, 0x68)):
                if f & mask:
                    v = max(v, self._cell(self.g.u32(T + off), "B", x, y))
            return v
        if name == "density":
            return self._cell(self._density_grid(), "B", x, y)
        if name in ("aura", "flammability"):
            if name == "aura":
                M = self._find_layer("simmisc.dll", self.AURA_VTS)
                s = self.g.i32(M + 0x14)
                return self._cell(self.g.u32(M + 0x18), "b", x >> s, y >> s)
            M = self._find_layer("simserv.dll", self.FLAM_VTS)
            return self._cell(self.g.u32(M + 0xC), "B", x, y)
        raise ValueError(f"unknown layer {name!r}")

    def at(self, x: int, y: int, names=None) -> dict:
        out = {}
        for n in names or LAYERS:
            try:
                v = self.value(n, x, y)
            except (ValueError, IndexError):
                continue
            lab = label(n, v)
            out[n] = {"value": v, "label": lab} if lab else v
        return out


# ---- region filters and statistics (layer_stats)
ZONE_GROUPS = {"residential": (1, 2, 3), "commercial": (5, 6, 7), "industrial": (9, 10, 11),
               "zoned": (1, 2, 3, 5, 6, 7, 9, 10, 11)}
NETWORK_FLAGS = {"roads": 1, "highways": 2, "rail": 4, "subways": 8, "stations": 0x10, "network": 0x1F}


def tile_filter(layers: Layers, where: str):
    """A predicate (x, y) -> bool for: all | zoned | residential | commercial | industrial | a zone name
    (res_light, com_dense, landfill...) | roads | highways | rail | subways | stations | network."""
    from .city import ZONE_NAMES
    if where in (None, "", "all"):
        return lambda x, y: True
    if where in NETWORK_FLAGS:
        flags, mask = layers.traffic_networks(), NETWORK_FLAGS[where]
        return lambda x, y: bool(flags[x][y] & mask)
    codes = ZONE_GROUPS.get(where) or tuple(k for k, v in ZONE_NAMES.items() if v == where)
    if not codes:
        raise ValueError(f"where must be all, {list(ZONE_GROUPS)}, a zone name {list(ZONE_NAMES.values())} "
                         f"or {list(NETWORK_FLAGS)}")
    zones = layers.c.zones()
    return lambda x, y: zones[x][y] in codes


def stats(layers: Layers, name: str, where: str = "all", thresholds=None) -> dict:
    shift, rows = layers.get(name)
    W, H = layers.c.size()
    keep = tile_filter(layers, where)
    vals = sorted(rows[x >> shift][y >> shift] for x in range(W) for y in range(H) if keep(x, y))
    n = len(vals)
    out = {"layer": name, "where": where, "tiles": n}
    if not n:
        return out
    q = lambda f: vals[min(n - 1, int(f * n))]
    out.update({"mean": round(sum(vals) / n, 2), "min": vals[0], "p10": q(0.1), "p25": q(0.25), "median": q(0.5),
                "p75": q(0.75), "p90": q(0.9), "max": vals[-1]})
    if name in BOOLEAN:
        out["share_yes"] = round(sum(1 for v in vals if v) / n, 4)
    for t in thresholds or []:
        out[f"share_at_least_{t}"] = round(sum(1 for v in vals if v >= t) / n, 4)
    lab = LABELS.get(name) or (_POLL_LABELS if name in ("air", "water_pollution") else None)
    if lab:
        from collections import Counter
        out["labels"] = dict(Counter(label(name, v) for v in vals))
    return out
