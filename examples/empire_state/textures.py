"""Empire State Building textures for create_texture (pixel rows + palette), one cell = one floor."""
import random

PAL = {
    "L": "232,226,210",   # Indiana limestone (lit)
    "l": "204,198,182",   # limestone shadow / pier edge
    "G": "62,68,80",      # window glass
    "g": "86,94,108",     # glass highlight
    "m": "168,170,172",   # nickel-chrome mullion
    "S": "128,88,72",     # aluminium spandrel (reads reddish-brown)
    "K": "34,34,38",      # black granite
    "k": "54,54,60",      # granite highlight
    "W": "120,138,150",   # storefront glass
    "R": "136,82,64",     # setback roof (red-brown)
    "r": "118,70,56",
    "q": "150,96,76",
    "A": "196,198,196",   # mast aluminium
    "a": "150,152,154",
    "D": "70,74,82",      # mast window / doors
    "Y": "212,170,60",    # gold lettering
    ".": "transparent",
}


def _strip(cols: str, glass_rows: range, height: int = 16) -> list[str]:
    """cols: one char per column: L/l pier, G window strip, m mullion. Window strips are glass in glass_rows and
    spandrel elsewhere; piers run full height."""
    rows = []
    for y in range(height):
        r = ""
        for c in cols:
            if c in "Ll":
                r += c
            elif c == "m":
                r += "m" if y in glass_rows else "S"
            else:
                r += ("g" if y == glass_rows.start else "G") if y in glass_rows else "S"
        rows.append(r)
    return rows


# tower: wide pier 9 | window 4, mullion 1, window 4 | narrow pier 5 | window 4, mullion 1, window 4 (32 x 16)
FACADE = _strip("LLLLLLLLl" + "GGGGmGGGG" + "LLLLl" + "GGGGmGGGG", range(0, 13))
# base floors 2-5: more stone, smaller windows
BASE = _strip("LLLLLl" + "GGGG" + "LLl" + "GGG" + "LLLLLl" + "GGGG" + "LLl" + "GGG", range(2, 12))
# ground floor: black granite with storefront glass
STORE = []
for y in range(16):
    if y < 3 or y > 13:
        STORE.append(("K" * 32) if y != 2 else ("k" * 32))
    else:
        STORE.append("".join("K" if x % 8 in (0, 1) else ("W" if y > 3 else "k") for x in range(32)))
# roof: mottled red-brown tar, 32 x 32, deterministic
_rnd = random.Random(1931)
ROOF = ["".join(_rnd.choice("RRRRRrq") for _ in range(32)) for _ in range(32)]
# mast: aluminium fins with narrow dark windows
MAST = ["".join("a" if x % 4 == 0 else ("D" if (x % 4 == 2 and 2 <= y <= 12) else "A") for x in range(16))
        for y in range(16)]


def steps() -> list:
    def tex(name, rows, kind="paint", scale=1):
        used = {c for r in rows for c in r}
        return ("create_texture", {"name": name, "kind": kind, "rows": rows,
                                   "palette": {k: v for k, v in PAL.items() if k in used},
                                   "scale": scale, "overwrite": True})
    return [tex("esb facade", FACADE), tex("esb base", BASE), tex("esb storefront", STORE), tex("esb roof", ROOF),
            tex("esb mast", MAST), tex("esb entrance", ENTRANCE, kind="detail")]


# Fifth Avenue entrance: 48 x 48 detail (3 x 3 faces): gold lettering band, geometric transom, three doors;
# '.' transparent so the wall paint shows around it
def _entrance():
    rows = []
    for y in range(48):
        r = ""
        for x in range(48):
            if y < 2 or x < 3 or x > 44:
                c = "."
            elif y < 8:                                        # "EMPIRE STATE" in gold on a dark band
                c = "Y" if (2 < y < 7 and x % 3 != 2 and 6 <= x <= 41 and x not in (23, 24)) else "K"
            elif y < 28:                                       # transom window with a deco grid
                if x < 5 or x > 42 or y in (8, 27):
                    c = "m"
                elif (x - 5) % 6 == 0 or (y - 8) % 5 == 0 or abs((x - 24) * 2) == abs(y - 18) * 3:
                    c = "m"
                else:
                    c = "G"
            else:                                              # three doors between granite piers
                if x < 5 or x > 42 or 17 <= x <= 19 or 28 <= x <= 30:
                    c = "K"
                elif y == 28 or y == 47:
                    c = "m"
                else:
                    c = "D" if (x % 5) else "m"
            r += c
        rows.append(r)
    return rows


ENTRANCE = _entrance()
