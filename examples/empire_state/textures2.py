"""Version 2 textures, after comparing with the game's own landmark: cooler palette, no 1 px features (the render
shows a 16 px face at about 8-11 px, so 1 px lines alias into stripes), slight variation between windows."""
import random

PAL = {
    "L": "226,220,202",   # limestone pier (lit)
    "l": "188,182,166",   # pier edge
    "G": "62,72,94",      # glass (blue-grey)
    "g": "84,96,120",     # glass, blind half down
    "m": "150,156,166",   # mullion (2 px)
    "S": "78,82,94",      # spandrel (dark aluminium)
    "C": "242,236,214",   # crown limestone (floodlit)
    "c": "214,206,180",
    "w": "196,182,140",   # crown window (warm light)
    "R": "74,76,82",      # setback roof (tar)
    "r": "64,66,72",
    "q": "86,88,94",
    "A": "150,158,174",   # mast
    "a": "112,120,138",
    "D": "60,66,82",
}


def _facade(seed, wide=7, narrow=5, win=10, glass_rows=range(0, 12), floors=2):
    rnd = random.Random(seed)
    cols = ("L" * (wide - 1) + "l" + "G" * 4 + "mm" + "G" * 4 + "L" * (narrow - 1) + "l" + "G" * 4 + "mm" + "G" * 4)
    assert len(cols) == 32, len(cols)
    rows = []
    for fl in range(floors):
        lit = [rnd.random() < 0.25 for _ in range(4)]          # some windows with blinds down
        for y in range(16):
            r = ""
            for x, c in enumerate(cols):
                if c in "Ll":
                    r += c
                elif y not in glass_rows:
                    r += "S"
                elif c == "m":
                    r += "m"
                else:
                    pane = (x > 16) * 2 + ((x % 16) > 11)
                    r += "g" if (lit[pane % 4] and y < 6) else "G"
            rows.append(r)
    return rows


FACADE = _facade(1931)
CROWN = [r.replace("L", "C").replace("l", "c").replace("G", "w").replace("g", "w").replace("S", "c")
         for r in _facade(86)]
BASE = [r.replace("S", "L") for r in _facade(5, glass_rows=range(3, 12))]
_rnd = random.Random(7)
ROOF = ["".join(_rnd.choice("RRRRRrq") for _ in range(32)) for _ in range(32)]
MAST = ["".join("a" if x % 8 in (0, 1) else ("D" if (x % 8 in (4, 5) and 2 <= y <= 12) else "A") for x in range(16))
        for y in range(16)]


def steps() -> list:
    def tex(name, rows, kind="paint"):
        used = {c for r in rows for c in r}
        return ("create_texture", {"name": name, "kind": kind, "rows": rows,
                                   "palette": {k: v for k, v in PAL.items() if k in used}, "overwrite": True})
    return [tex("esb2 facade", FACADE), tex("esb2 crown", CROWN), tex("esb2 base", BASE), tex("esb2 roof", ROOF),
            tex("esb2 mast", MAST)]
