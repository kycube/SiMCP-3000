"""Queen Anne (Haas-Lilienthal House) textures for create_texture: pixel rows + palette. Lessons applied: features
2 px or wider, 32 px repeats, and colours chosen for the renderer's light (a neutral grey 128 renders about 0.93x on
tops, 1.25-1.3x and warm on walls / slopes facing left, 0.47x and bluish on walls facing right, 1.07x bluish on
slopes facing right): the roof is painted dark and a little blue so its lit slope does not turn pink."""
import random

PAL = {
    "B": "104,124,104",   # sage clapboard body
    "H": "126,146,124",   # board highlight
    "S": "76,92,78",     # board shadow
    "F": "112,132,110",   # fish-scale shingle
    "f": "96,108,94",     # shingle outline
    "T": "84,96,86",      # trim (dark green-grey)
    "t": "110,122,110",
    "G": "186,190,186",   # foundation stone
    "g": "150,154,150",   # mortar joint
    "R": "54,58,70",      # roof shingles
    "r": "44,48,58",
    "q": "62,66,78",
}


def siding():
    rows = []
    for y in range(16):                       # two 8 px boards per face: highlight, body, 2 px shadow
        k = y % 8
        rows.append(("H" if k == 0 else "S" if k >= 6 else "B") * 32)
    return rows


def fish_scale():
    """Rows of 8 x 8 px scallops (each course offset by half a scallop), outlined 2 px thick."""
    import math
    rows = []
    for y in range(16):
        r = ""
        for x in range(32):
            off = 4 if (y // 8) % 2 else 0
            cx = ((x + off) % 8) - 3.5
            yy = y % 8
            arc = 0.3 + math.sqrt(max(0.0, 16.5 - cx * cx)) * 1.65    # U-shaped bottom edge of the scallop
            r += "f" if abs(yy - arc) < 0.95 else "F"
        rows.append(r)
    return rows


def foundation():
    rows = []
    for y in range(16):
        if y % 8 in (6, 7):
            rows.append("g" * 32)
        else:
            off = 8 if (y // 8) % 2 else 0
            rows.append("".join("g" if (x + off) % 16 in (14, 15) else "G" for x in range(32)))
    return rows


def trim():
    return [("t" * 16) if y < 2 else ("T" * 16) for y in range(16)]


def roof():
    rnd = random.Random(1886)
    rows = []
    for y in range(32):
        if y % 4 == 3:
            rows.append("r" * 32)
        else:
            off = 4 if (y // 4) % 2 else 0
            rows.append("".join("r" if (x + off) % 8 == 0 else rnd.choice("RRRRq") for x in range(32)))
    return rows


def steps() -> list:
    def tex(name, rows):
        used = {c for r in rows for c in r}
        return ("create_texture", {"name": name, "kind": "paint", "rows": rows,
                                   "palette": {k: v for k, v in PAL.items() if k in used}, "overwrite": True})
    return [tex("vic siding", siding()), tex("vic shingle", fish_scale()), tex("vic foundation", foundation()),
            tex("vic trim", trim()), tex("vic roof", roof())]
