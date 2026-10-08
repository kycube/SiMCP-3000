"""LIVE t3: check the observation recipes from re/agents/{sim,map,economy}/REPORT.md against the running city."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp.game import Game  # noqa: E402


def grid_get(g, grid, x, y, size=1):
    rows = g.u32(grid + 0xC)
    row = g.u32(rows + 4 * x)
    raw = g.proc.read(row + size * y, size)
    return int.from_bytes(raw, "little")


def main():
    g = Game()
    g.attach(launch=False)
    C = g.city()
    u, i32 = g.u32, g.i32
    res = u(C + 0xE4)
    vr, vc, vi = u(res + 0x24), u(u(C + 0xE8) + 0x18), u(u(C + 0xEC) + 0x1C)
    for name, v in (("R", vr), ("C", vc), ("I", vi)):
        print(f"valve {name}: id {i32(v + 8)} supply {i32(v + 0xC)} demand {i32(v + 0x10)} value {i32(v + 0x2C)} "
              f"max {i32(v + 0x24)} min {i32(v + 0x28)}")
    print("population", i32(vr + 0xC))
    P, W = u(C + 0xB8), u(C + 0xBC)
    print("power cap", i32(P + 0x5C), "use", i32(P + 0x2D8), "unpowered", i32(P + 0x2D4))
    print("water supply", g.i64(W + 0xB0), "use", g.i64(W + 0xB8), "unwatered", i32(W + 0xC4))
    print("land value avg", g.proc.read(u(C + 0xF0) + 0xA4, 1)[0], "crime avg", g.proc.read(u(C + 0xD8) + 0xA8, 1)[0])
    B = u(C + 0xC4)
    print("taxes R/C/I", [g.proc.read(B + 0x8C + z * 0x88, 1)[0] for z in range(3)],
          "max", [g.proc.read(B + 0x8D + z * 0x88, 1)[0] for z in range(3)])
    # zone grid: Z = *(C+0xB4) - 0x10; grid = *(Z+0x0C)
    Z = u(C + 0xB4) - 0x10
    zg = u(Z + 0x0C)
    print("zone grid dims", i32(zg + 4), i32(zg + 8))
    print("zones x 199..205, y 149..156:")
    for y in range(149, 157):
        print("  ", y, [grid_get(g, zg, x, y) for x in range(199, 206)])
    # terrain
    dirt = u(C + 0xA4)
    alt, wat = u(dirt + 0x30), u(dirt + 0x38)
    print("terrain dims", i32(alt + 4), i32(alt + 8), "sea level", g.proc.read(dirt + 0x3C, 1)[0])
    for (x, y) in ((200, 150), (127, 127), (130, 120)):
        print(f"  vertex ({x},{y}) alt {grid_get(g, alt, x, y)} water {grid_get(g, wat, x, y)}")
    # occupants at the police tile and road tiles
    for mi, off in enumerate((0x84, 0x88, 0x8C)):
        m = u(C + off)
        cells, flags = u(m + 0x98), u(m + 0x9C)
        print(f"occupant manager {mi} (+{off:#x}) dims", i32(m + 0xA0) + 1, i32(m + 0xA4) + 1, "vector size",
              (u(m + 0x2C) - u(m + 0x28)) // 4)
        for (x, y) in ((197, 150), (200, 152), (202, 152), (208, 160)):
            f = grid_get(g, flags, x, y)
            p = grid_get(g, cells, x, y, 4) if f & 1 else 0
            if f & 2:
                p = grid_get(g, cells, p & 0xFFFF, p >> 16, 4)
            desc = ""
            if p:
                vt = u(p)
                desc = f"vt {vt:#x}"
                try:
                    tid = g.call(g.vfn(p, 0x88 // 4), this=p)
                    rect = g.scratch() + 0x200
                    g.call(g.vfn(p, 0xD0 // 4), [rect], this=p)
                    desc += f" type {tid:#x} rect {struct.unpack('<4i', g.proc.read(rect, 16))}"
                except Exception as e:
                    desc += f" ({e})"
            print(f"   ({x},{y}) flags {f:#x} occ {p:#x} {desc}")


if __name__ == "__main__":
    main()
