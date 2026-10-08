"""Roofs as height fields: hip, gable, shed and pyramid roofs (and their unions, e.g. a cross gable meeting a hip
roof) turned into the Architect's block shapes.

A roof part is a rectangle of cells with a style and a pitch (1 = 45 degrees, rising one cell per cell; 0.5 = 26.6
degrees). Its height at every cell corner point is a function of the distance to its edges; several parts combine
by taking the highest. Each cell column is then cut into one-cell levels and, for each level, the four corner
heights (0, 1/2 or 1 within that level) pick the block shape whose top has exactly those corner heights - wedges and
half ramps on slopes, pyramid corners on hips, valley corners where two roofs meet - with the rotation that fits.
Where two shapes have the same corner heights (a convex cut corner and a concave valley), the one whose top at the
cell centre matches the roof surface is used.

Shape tops come from bldfile.SHAPES: vertex v sits at corner v & 3 ((+x,+y), (-x,+y), (-x,-y), (+x,-y)) at height
0 / 1 / 0.5 for v >> 2 = 0 / 1 / 2; rotation r moves corner c to (c + r) & 3.
"""

from __future__ import annotations

import math

from sc3k_mcp.game import GameError

from . import bldfile

CORNER_XY = {0: (1, 1), 1: (0, 1), 2: (0, 0), 3: (1, 0)}
LEVEL = {0: 0.0, 1: 1.0, 2: 0.5}
ROOF_SHAPES = (0, 2, 3, 4, 6, 9, 10, 11, 12, 13, 14)     # shapes with a full square base and a height-field top
STYLES = ("hip", "gable_x", "gable_y", "pyramid", "shed_+x", "shed_-x", "shed_+y", "shed_-y", "flat")


def _top_center(shape: int, rot: int) -> float:
    """Height of the shape's top surface above the cell centre (0.5, 0.5)."""
    best = 0.0
    for f in bldfile.SHAPES[shape][0]:
        pts = []
        for v in f.verts:
            c = ((v & 3) + rot) & 3
            x, y = CORNER_XY[c]
            pts.append((x, y, LEVEL[v >> 2]))
        if len(pts) < 3:
            continue
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = pts[0], pts[1], pts[2]
        nx = (y2 - y1) * (z3 - z1) - (z2 - z1) * (y3 - y1)
        ny = (z2 - z1) * (x3 - x1) - (x2 - x1) * (z3 - z1)
        nz = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
        if abs(nz) < 1e-9:
            continue                                     # vertical face
        # is the centre inside the face's projection?
        inside, n = False, len(pts)
        for i in range(n):
            ax, ay, _ = pts[i]
            bx, by, _ = pts[(i + 1) % n]
            if (ay > 0.5) != (by > 0.5) and 0.5 < (bx - ax) * (0.5 - ay) / (by - ay) + ax:
                inside = not inside
        if not inside:
            continue
        z = z1 - (nx * (0.5 - x1) + ny * (0.5 - y1)) / nz
        best = max(best, z)
    return best


_TABLE: dict[tuple, list] = {}


def shape_table() -> dict[tuple, list]:
    """{(h0, h1, h2, h3) corner heights: [(shape, rotation, centre height)]}."""
    if not _TABLE:
        for shape in ROOF_SHAPES:
            base = [0.0] * 4
            for f in bldfile.SHAPES[shape][0]:
                for v in f.verts:
                    base[v & 3] = max(base[v & 3], LEVEL[v >> 2])
            for r in range(4):
                h = [0.0] * 4
                for c in range(4):
                    h[(c + r) & 3] = base[c]
                _TABLE.setdefault(tuple(h), []).append((shape, r, _top_center(shape, r)))
    return _TABLE


def _part_height(p: dict, px: float, py: float) -> float | None:
    """Height above the part's base at corner point (px, py), or None outside the part."""
    x0, y0, x1, y1 = p["x0"], p["y0"], p["x1"] + 1, p["y1"] + 1
    if not (x0 <= px <= x1 and y0 <= py <= y1):
        return None
    k, s = p["pitch"], p["style"]
    if s in ("hip", "pyramid"):
        h = min(px - x0, x1 - px, py - y0, y1 - py)
    elif s == "gable_y":                                 # ridge along y
        h = min(px - x0, x1 - px)
    elif s == "gable_x":
        h = min(py - y0, y1 - py)
    elif s == "shed_+x":
        h = px - x0
    elif s == "shed_-x":
        h = x1 - px
    elif s == "shed_+y":
        h = py - y0
    elif s == "shed_-y":
        h = y1 - py
    else:
        h = 0.0
    h = k * h
    if p.get("max_height") is not None:
        h = min(h, p["max_height"])
    return p["z"] + h


def roof_blocks(parts: list[dict], z: int, pitch: float = 1.0) -> list[dict]:
    """Blocks for the union of roof parts {x0, y0, x1, y1, style, [pitch], [z], [max_height]} whose eaves sit at
    level z (the first roof cell level)."""
    ps = []
    for p in parts:
        q = {k: p[k] for k in ("x0", "y0", "x1", "y1")}
        q["x0"], q["x1"] = min(q["x0"], q["x1"]), max(q["x0"], q["x1"])
        q["y0"], q["y1"] = min(q["y0"], q["y1"]), max(q["y0"], q["y1"])
        q["style"] = p.get("style", "hip")
        if q["style"] not in STYLES:
            raise GameError(f"roof style: one of {list(STYLES)}")
        q["pitch"] = float(p.get("pitch", pitch))
        if q["pitch"] not in (0.5, 1.0):
            raise GameError("pitch: 1 (45 degrees) or 0.5 (half: 26.6 degrees)")
        q["z"] = int(p.get("z", z))
        q["max_height"] = p.get("max_height")
        ps.append(q)
    table = shape_table()

    def field(px, py):
        hs = [h for h in (_part_height(p, px, py) for p in ps) if h is not None]
        return max(hs) if hs else None

    cells = {(x, y) for p in ps for x in range(p["x0"], p["x1"] + 1) for y in range(p["y0"], p["y1"] + 1)}
    out = []
    for (x, y) in sorted(cells):
        own = max((p for p in ps if p["x0"] <= x <= p["x1"] and p["y0"] <= y <= p["y1"]), key=lambda p: p["z"])
        corners = []
        for c in range(4):
            cx, cy = CORNER_XY[c]
            h = field(x + cx, y + cy)
            corners.append(own["z"] if h is None else h)
        centre = field(x + 0.5, y + 0.5)
        base = min(p["z"] for p in ps if p["x0"] <= x <= p["x1"] and p["y0"] <= y <= p["y1"])
        top = max(corners)
        for lev in range(base, int(math.ceil(top)) + 1):
            hc = tuple(min(1.0, max(0.0, round((h - lev) * 2) / 2)) for h in corners)
            if max(hc) <= 0:
                continue
            if min(hc) >= 1:
                out.append({"x": x, "y": y, "z": lev})
                continue
            cands = table.get(hc)
            if not cands:                                # no exact shape: the nearest one by corner heights
                key = min(table, key=lambda t: (sum(abs(a - b) for a, b in zip(t, hc)), -sum(t)))
                cands = table[key]
            want = min(1.0, max(0.0, (centre if centre is not None else top) - lev))
            shape, rot, _c = min(cands, key=lambda s: abs(s[2] - want))
            out.append({"x": x, "y": y, "z": lev, "shape": shape, "rotation": rot})
    return out
