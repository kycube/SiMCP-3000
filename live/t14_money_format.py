"""LIVE t14: how does the game print advisor-text numbers? The advice token formatter (SIMADV 0x1002A8C8) prints
type 3 with the locale object's vt[0x3C] and type 2 with vt[0x40] (locale = SIMADV 0x10027B3D()->vt[0x94](0)).
Call both on a few values and show the strings the game makes.

    python live/t14_money_format.py          (the game running with a city)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


def main():
    S.game_launch()
    g = S.game
    base = g.mod("simadv.dll")
    va = lambda x: base + (x - 0x10000000)
    app = g.call(va(0x10027B3D))
    loc = g.call(g.vfn(app, 0x94 // 4), [0], this=app)
    print(f"app {app:#x} locale {loc:#x}")
    buf = g.scratch() + 0x400
    for slot in (0x3C, 0x40):
        out = []
        for v in (0, 7, 1234, 1234567, -5000):
            g.proc.write(buf, b"\0" * 0x20)
            g.call(va(0x10003A5F), [], this=buf)                    # the game's own empty string
            g.call(g.vfn(loc, slot // 4), [v & 0xFFFFFFFF, 0xFFFFFFFF if v < 0 else 0, buf], this=loc)
            b, e = g.u32(buf + 4), g.u32(buf + 8)
            out.append(g.proc.read(b, e - b).decode("cp1252", "replace") if b and e > b else "")
        print(f"vt[{slot:#x}]:", out)


if __name__ == "__main__":
    main()
