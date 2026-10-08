"""Empire State Building massing on a 4x4 lot (32 x 32 cells, 144 high), one cell = one floor.
Long axis along y (the 33rd / 34th Street facades face +x / -x); the Fifth Avenue front is the +y end.
Centre cell (15, 15). Each tier: (x0, y0, x1, y1, z0, z1, notch) - notch = size of the corner columns left out."""

TIERS = [
    ("base",   8, 0, 22, 30, 1, 5, 0),     # five-storey base over the whole site
    ("lower",  9, 4, 21, 26, 6, 20, 1),    # setback above the 5th floor
    ("t21",   10, 5, 20, 25, 21, 24, 1),   # setbacks at 21, 25, 30 (21 steps back to the recessed plane)
    ("t25",   10, 7, 20, 23, 25, 29, 1),
    ("shaft", 10, 8, 20, 22, 30, 71, 1),   # the shaft up to the 72nd floor (11 x 15)
    ("t72",   11, 9, 19, 21, 72, 80, 1),
    ("t81",   12, 10, 18, 20, 81, 84, 1),
    ("t85",   13, 11, 17, 19, 85, 85, 0),
    ("obs86", 13, 12, 17, 18, 86, 86, 0),  # 86th-floor observatory (open deck around it on the 85 roof)
    ("mast1", 13, 13, 17, 17, 87, 89, 1),  # mooring mast: rectangular tiers
    ("mast2", 14, 14, 16, 16, 90, 94, 0),  # chamfered (octagonal) tiers, see CHAMFER
    ("mast3", 14, 14, 16, 16, 95, 97, 0),
]
TOP = 97
CHAMFER = [("mast2", 1), ("mast3", 1)]    # corner cells replaced by diagonal half-cubes (shape 1)


def chamfer_steps() -> list:
    """Shape 1 keeps the +x/-y half at rotation 0; rotation r turns it r quarter turns counter-clockwise, so the
    kept half faces the inside of the tier at: (x0, y1) rot 0, (x0, y0) rot 1, (x1, y0) rot 2, (x1, y1) rot 3."""
    T = {t[0]: t for t in TIERS}
    blocks = []
    for name, _n in CHAMFER:
        _, x0, y0, x1, y1, z0, z1, _k = T[name]
        for (x, y, r) in ((x0, y1, 0), (x0, y0, 1), (x1, y0, 2), (x1, y1, 3)):
            blocks += [{"x": x, "y": y, "z": z, "shape": 1, "rotation": r} for z in range(z0, z1 + 1)]
    return [("place_blocks", {"blocks": blocks})]


def fill_steps() -> list:
    out = []
    for name, x0, y0, x1, y1, z0, z1, n in TIERS:
        out.append(("fill_box", {"x0": x0, "y0": y0, "z0": z0, "x1": x1, "y1": y1, "z1": z1}))
        if n:
            cells = [{"x": x, "y": y, "z": z} for z in range(z0, z1 + 1)
                     for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1))
                     for x in range(cx, cx + sx * n, sx) for y in range(cy, cy + sy * n, sy)]
            out.append(("remove_blocks", {"cells": cells}))
    return out


def bbox():
    return (min(t[1] for t in TIERS), min(t[2] for t in TIERS), 1,
            max(t[3] for t in TIERS), max(t[4] for t in TIERS), TOP)


# the lower tower's long faces: end wings (y 4..9 and 21..26) project one cell past a recessed centre
RECESS = [(x, y, z) for x in (9, 21) for y in range(10, 21) for z in range(6, 21)]


def recess_steps() -> list:
    return [("remove_blocks", {"cells": [{"x": x, "y": y, "z": z} for x, y, z in RECESS]})]
