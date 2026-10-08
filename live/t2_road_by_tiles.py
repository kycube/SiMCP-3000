"""LIVE t2: place a network (road) between two tiles without the mouse.

Replays the line tool's own button-up path (SIMNTWRK 0x10025B3C): points at tool+0x40 / +0x4C (world units,
256 per tile), 0x1002595F(tool), tool->vt[0x54](&start, &end, &plan), tool->vt[0x48](plan), 0x1002596B(tool),
plan->Release().
    python live/t2_road_by_tiles.py x1 y1 x2 y2 [command_id_hex]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp.game import Game  # noqa: E402


def main():
    x1, y1, x2, y2 = map(int, sys.argv[1:5])
    cmd = int(sys.argv[5], 16) if len(sys.argv) > 5 else 0xC2B5DE77
    g = Game()
    g.attach(launch=False, reload_bridge=True)
    c = g.city()
    iface = g.u32(g.mod("simspr.dll") + 0x72F24)
    view = g.call(g.vfn(iface, 0x74 // 4), this=iface)
    r = g.bridge.command(cmd)
    print("select tool:", r)
    tool = g.u32(view + 0x228)
    snt = g.mod("simntwrk.dll")
    print(f"tool {tool:#x} vtable SIMNTWRK+{g.u32(tool) - snt:#x}")
    f0 = g.city_basics(c)["funds"]
    g.proc.write(tool + 0x40, struct.pack("<3i", x1 * 256, y1 * 256, 0))
    g.proc.write(tool + 0x4C, struct.pack("<3i", x2 * 256, y2 * 256, 0))
    res = g.scratch()
    g.proc.write(res, b"\0" * 4)
    ret = g.call_seq([
        (snt + 0x2595F, tool, []),
        (21, tool, [tool + 0x40, tool + 0x4C, res], {"vslot": True}),
        (18, tool, [res], {"vslot": True, "deref_args": [0]}),
        (snt + 0x2596B, tool, []),
    ])
    plan = g.u32(res)
    print("seq ret", [hex(v & 0xFFFFFFFF) for v in ret[:4]], "plan", hex(plan))
    if plan:
        g.call(g.vfn(plan, 2), this=plan)
    time.sleep(0.5)
    print("funds", f0, "->", g.city_basics(c)["funds"])


if __name__ == "__main__":
    main()
