"""Map rendering: exact ASCII layers and a colour PNG, from memory reads (no game calls except one occupant scan).

Coordinates: tile (x, y) as the game stores them (x = first index, 0..W-1; y = 0..H-1). Text maps print one row
per y (top to bottom) and one column per x (left to right). This is a top-down view of the map grid, independent
of the camera rotation in the game window.
"""

from __future__ import annotations

from .city import City, agent_name, ZONE_NAMES

ZONE_CH = {0: ".", 1: "r", 2: "R", 3: "W", 5: "c", 6: "C", 7: "X", 9: "i", 10: "I", 11: "Y", 13: "M", 14: "A",
           15: "S", 16: "P", 17: "L", 22: "B"}

# building/network glyphs by agent category (CitySim.ini [AgentTypes])
def occ_glyph(cat: int) -> str:
    if cat == 300:
        return "t"                                   # trees
    if cat in (1000, 1001, 1002):
        return "mae"[cat - 1000]                     # mixed land use, arcology, stock exchange
    if 3000 <= cat < 5000:
        return "h"                                   # residential building
    if 5000 <= cat < 8000:
        return "o"                                   # commercial building
    if 8000 <= cat < 10000:
        return "f"                                   # industrial building
    if cat in (12102, 12103, 12104) or 17100 <= cat < 17200:
        return "|"                                   # power lines (incl. over road/water)
    if cat in (16000, 16016, 16017):
        return "="                                   # road
    if cat == 16015:
        return "T"                                   # bus stop on road
    if cat == 16001 or 17203 <= cat <= 17209:
        return "H"                                   # highway pieces
    if 16002 <= cat <= 16012:
        return "b"                                   # bridges and tunnels
    if cat == 16014 or 17000 <= cat < 17100:
        return "#"                                   # rail
    if cat == 17202:
        return "^"                                   # ramps
    if 17300 <= cat < 17400:
        return ":"                                   # pipes
    if 17400 <= cat < 17500:
        return "u"                                   # subway
    if 12101 <= cat < 12200:
        return "E"                                   # power plants
    if 12800 <= cat < 12850 or cat == 12510:
        return "w"                                   # water buildings, dam
    if 12850 <= cat < 12860:
        return "G"                                   # garbage
    if 12200 <= cat < 12400:
        return "T"                                   # stations, ports
    if 15000 <= cat < 16000:
        return "x"                                   # undeveloped/abandoned/construction/rubble
    if cat in (13001, 13120, 13130):
        return "P"
    if cat == 13002:
        return "F"
    if cat in (13003, 13310, 13320):
        return "+"
    if cat in (13009, 13010) or 13870 <= cat <= 13874:
        return "K"
    if cat == 13881 or cat == 13006:
        return "J"
    if 13000 <= cat < 14000:
        return "s"
    if 14000 <= cat < 15000:
        return "p"
    if 10000 <= cat < 12000:
        return "g"
    if 18000 <= cat < 19000:
        return "!"
    if 19000 <= cat < 20000:
        return "$"
    return "?"


LEGEND = {
    "terrain": "~ water, 0-9 land height above the water level (each digit ~ 2 altitude steps)",
    "zones": "r/R/W residential light/medium/dense, c/C/X commercial, i/I/Y industrial, L landfill, S seaport, "
             "A airport, M military, P spaceport, B building lot, . none",
    "buildings": "= road, H highway, b bridge/tunnel, # rail, | power line, : pipe, u subway, ^ ramp, t trees, "
                 "h/o/f res/com/ind building, x abandoned/rubble/construction, E power plant, w water bldg, G garbage, T station/port, P police, F fire, + health, "
                 "K school/college, J jail, s other services, p park/culture, g government/military, ! landmark, "
                 "$ business deal, m mixed land use, a arcology, e stock exchange, ? other",
    "auto": "buildings over zones over terrain (see the other legends)",
    "landvalue/crime/police/fire": "0-9 (value/26)",
}


class MapView:
    def __init__(self, city: City):
        self.c = city
        from .layers import Layers
        self.layers = Layers(city)

    def _terrain_tiles(self):
        alt, wat, sea = self.c.terrain()
        W, H = self.c.size()

        def tile(x, y):
            corners = [(alt[x + dx][y + dy], wat[x + dx][y + dy]) for dx in (0, 1) for dy in (0, 1)]
            wet = sum(1 for a, w in corners if w >= a)
            mean_alt = sum(a for a, _ in corners) / 4
            return wet, mean_alt, max(w for _, w in corners)
        return tile, sea, W, H

    def occupant_grid(self, rect=None):
        """{(x, y): (layer, category)} for every occupied tile (top layer wins)."""
        grid = {}
        for o in self.c.occupants(rect or (-1, -1, -1, -1)):
            x0, y0, x1, y1 = o["rect"]
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    prev = grid.get((x, y))
                    if prev is None or (prev[1] == 300 and o["category"] != 300):
                        grid[(x, y)] = (o["layer"], o["category"])
        return grid

    def free_areas(self, w: int, h: int, near=None, flat: bool = True, limit: int = 5) -> list[dict]:
        """Top-left tiles of w x h rectangles with nothing built (trees allowed), no zone, no water and (flat=True)
        level ground, nearest to `near` (default: the map centre)."""
        alt, wat, _ = self.c.terrain()
        W, H = self.c.size()
        zones = self.c.zones()
        blocked = [[False] * H for _ in range(W)]
        for o in self.c.occupants():
            if o["layer"] != 0 or o["category"] == 300:          # underground / trees don't block
                continue
            x0, y0, x1, y1 = o["rect"]
            for x in range(max(0, x0), min(W - 1, x1) + 1):
                for y in range(max(0, y0), min(H - 1, y1) + 1):
                    blocked[x][y] = True
        level = [[0] * H for _ in range(W)]
        for x in range(W):
            for y in range(H):
                c = [alt[x + dx][y + dy] for dx in (0, 1) for dy in (0, 1)]
                wet = any(wat[x + dx][y + dy] >= alt[x + dx][y + dy] for dx in (0, 1) for dy in (0, 1))
                if wet or zones[x][y]:
                    blocked[x][y] = True
                level[x][y] = c[0] if max(c) == min(c) else -1
        # prefix sums of blocked tiles and of non-level tiles
        P = [[0] * (H + 1) for _ in range(W + 1)]
        Q = [[0] * (H + 1) for _ in range(W + 1)]
        for x in range(W):
            for y in range(H):
                P[x + 1][y + 1] = P[x][y + 1] + P[x + 1][y] - P[x][y] + blocked[x][y]
                Q[x + 1][y + 1] = Q[x][y + 1] + Q[x + 1][y] - Q[x][y] + (level[x][y] < 0)

        def rsum(T, x, y):
            return T[x + w][y + h] - T[x][y + h] - T[x + w][y] + T[x][y]
        nx, ny = near if near else (W // 2, H // 2)
        cands = []
        for x in range(0, W - w + 1):
            for y in range(0, H - h + 1):
                if rsum(P, x, y):
                    continue
                if flat:
                    if rsum(Q, x, y):
                        continue
                    a0 = level[x][y]
                    if any(level[xx][yy] != a0 for xx in range(x, x + w) for yy in range(y, y + h)):
                        continue
                cands.append(((x + w / 2 - nx) ** 2 + (y + h / 2 - ny) ** 2, x, y))
        cands.sort()
        out, taken = [], []
        for _, x, y in cands:                      # non-overlapping suggestions
            if any(x < tx + w and tx < x + w and y < ty + h and ty < y + h for tx, ty in taken):
                continue
            taken.append((x, y))
            out.append({"x": x, "y": y, "x2": x + w - 1, "y2": y + h - 1})
            if len(out) >= limit:
                break
        return out

    def text(self, layer: str = "auto", x0: int = 0, y0: int = 0, x1: int | None = None, y1: int | None = None,
             step: int = 1) -> str:
        W, H = self.c.size()
        x1 = W - 1 if x1 is None else min(x1, W - 1)
        y1 = H - 1 if y1 is None else min(y1, H - 1)
        x0, y0 = max(0, x0), max(0, y0)
        step = max(1, step)
        xs, ys = range(x0, x1 + 1, step), range(y0, y1 + 1, step)
        if layer in ("terrain", "auto"):
            tile, sea, _, _ = self._terrain_tiles()
        if layer in ("zones", "auto"):
            zones = self.c.zones()
        if layer in ("buildings", "auto"):
            occ = self.occupant_grid((x0, y0, x1, y1))
        from . import layers as L
        data = None
        if layer in L.LAYERS:
            shift, rows = self.layers.get(layer)
            data = True
            if layer in L.BOOLEAN or layer == "traffic":
                zones = self.c.zones()
        elif layer not in ("auto", "terrain", "zones", "buildings"):
            raise ValueError(f"layer must be auto, terrain, zones, buildings or one of {list(L.LAYERS)}")
        lines = []
        for y in ys:
            row = []
            for x in xs:
                ch = " "
                if layer == "terrain" or layer == "auto":
                    wet, a, w = tile(x, y)
                    ch = "~" if wet >= 2 else str(max(0, min(9, int((a - w) // 2))))
                    if layer == "auto":
                        ch = "~" if wet >= 2 else "."
                if layer in ("zones", "auto"):
                    z = zones[x][y]
                    if layer == "zones" or z:
                        ch = ZONE_CH.get(z, "?") if (z or layer == "zones") else ch
                if layer in ("buildings", "auto"):
                    o = occ.get((x, y))
                    if o:
                        ch = occ_glyph(o[1])
                    elif layer == "buildings":
                        ch = "."
                if data:
                    v = rows[x >> shift][y >> shift]
                    ch = L.digit(layer, v)
                    if layer in ("power", "water") and not v and not zones[x][y]:
                        ch = " "                       # unzoned and unserved: nothing to show
                row.append(ch)
            lines.append(f"{y:3d} " + "".join(row))
        header = "    " + "".join(str((x // 10) % 10) if x % 10 == 0 else " " for x in xs)
        return (f"layer={layer} x {x0}..{x1} y {y0}..{y1} step {step}\n{header}\n" + "\n".join(lines)
                + f"\nlegend: {LEGEND.get(layer) or self._legend(layer)}")

    @staticmethod
    def _legend(layer: str) -> str:
        from . import layers as L
        if layer in L.BOOLEAN:
            extra = "; blank = unzoned and not served" if layer in ("power", "water") else ""
            return f"{L.LAYERS[layer]}: + yes, . no{extra}"
        return f"{L.LAYERS[layer]}: digit 0-9 = value scaled to the layer's range"

    def image(self, scale: int = 3, overlay: str | None = None):
        from PIL import Image
        W, H = self.c.size()
        tile, sea, _, _ = self._terrain_tiles()
        zones = self.c.zones()
        occ = self.occupant_grid()
        from . import layers as L
        ov = None
        if overlay:
            if overlay not in L.LAYERS:
                raise ValueError(f"overlay must be one of {list(L.LAYERS)}")
            shift0, rows0 = self.layers.get(overlay)
            scale_max = {"air": L.POLLUTION_MAX, "water_pollution": L.POLLUTION_MAX, "garbage": 32767}.get(overlay, 255)
            ov = (shift0, [[(255 if v else 0) if overlay in L.BOOLEAN else
                            int(255 * min(1.0, ((v + 128) if overlay == "aura" else v) / scale_max)) for v in r]
                           for r in rows0])
        img = Image.new("RGB", (W, H))
        px = img.load()
        zone_col = {1: (120, 220, 120), 2: (60, 190, 60), 3: (20, 140, 20), 5: (120, 160, 240), 6: (70, 110, 220),
                    7: (30, 60, 180), 9: (240, 220, 110), 10: (220, 190, 60), 11: (190, 150, 20), 17: (140, 110, 80),
                    14: (160, 160, 160), 15: (90, 140, 160), 22: (200, 200, 200)}
        for x in range(W):
            for y in range(H):
                wet, a, w = tile(x, y)
                if wet >= 2:
                    col = (40, 90, 200)
                else:
                    h = max(0, min(40, int(a - w)))
                    col = (110 + h * 2, 140 + h, 80 + h)
                z = zones[x][y]
                if z in zone_col:
                    col = zone_col[z]
                o = occ.get((x, y))
                if o:
                    g = occ_glyph(o[1])
                    col = {"t": (30, 110, 40), "=": (90, 90, 90), "H": (60, 60, 60), "#": (120, 80, 50),
                           "|": (230, 200, 0), ":": (0, 200, 220), "E": (255, 120, 0), "w": (0, 120, 255),
                           "h": (40, 160, 40), "o": (40, 80, 200), "f": (200, 160, 20), "P": (0, 0, 160),
                           "F": (220, 0, 0)}.get(g, (230, 230, 230))
                if ov:
                    shift, rows = ov
                    v = rows[x >> shift][y >> shift]
                    col = tuple(int(c * 0.4 + v * 0.6) for c in (col[0], col[1] // 2, col[2] // 2))
                px[x, y] = col
        if scale > 1:
            img = img.resize((W * scale, H * scale), Image.NEAREST)
        return img

    def tile_info(self, x: int, y: int) -> dict:
        alt, wat, sea = self.c.terrain()
        corners = {f"{dx}{dy}": {"altitude": alt[x + dx][y + dy], "water": wat[x + dx][y + dy]}
                   for dx in (0, 1) for dy in (0, 1)}
        zones = self.c.zones()
        occ = [o for o in self.c.occupants((x, y, x, y))]
        info = {"x": x, "y": y, "corners": corners, "sea_level": sea, "zone": ZONE_NAMES.get(zones[x][y], zones[x][y]),
                "occupants": [{"layer": o["layer"], "category": o["category"], "name": o["name"], "rect": o["rect"]}
                              for o in occ]}
        info.update(self.layers.at(x, y))
        if sum(1 for c in corners.values() if c["water"] >= c["altitude"]) >= 2:
            # pollution cell bit 30 = salt water (SIMDIRT salt flags; the Query's "Salt Water" / "Fresh Water")
            P = self.c.g.u32(self.c.C + 0xD4)
            s = self.c.g.i32(P - 8)
            info["water_body"] = "salt" if (self.layers._cell(self.c.g.u32(P - 4), "I", x >> s, y >> s) >> 30) & 1 \
                else "fresh"
        return info
