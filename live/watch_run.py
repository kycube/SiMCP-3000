"""LIVE: hardware-watch an address while the sim runs (or around a click) and list the writers.

    python live/watch_run.py <addr|city+OFF|budget+OFF> [len] [run SECONDS | click X Y] [rw]
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp.game import Game  # noqa: E402

PLAY, PAUSE = (750, 722), (722, 722)


def owner(mods, a):
    best = max(((n, b) for n, b in mods.items() if b <= a), key=lambda t: t[1], default=(None, 0))
    return f"{best[0]}+{a - best[1]:#x}" if best[0] and a - best[1] < 0x200000 else f"{a:#x}"


def resolve(g, spec):
    c = g.city()
    if spec.startswith("city+"):
        return c + int(spec[5:], 16)
    if spec.startswith("budget+"):
        return g.u32(c + 0xC4) + int(spec[7:], 16)
    return int(spec, 16)


def main():
    g = Game()
    g.attach(launch=False)
    b = g.bridge
    addr = resolve(g, sys.argv[1])
    length = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    mode = sys.argv[3] if len(sys.argv) > 3 else "run"
    rw = sys.argv[-1] if sys.argv[-1] in ("w", "rw") else "w"
    print(f"watching {addr:#x} len {length} ({rw})")
    r = b.watch(addr, length, rw)
    assert r.ok, r
    try:
        if mode == "run":
            g.click(*PLAY)
            time.sleep(float(sys.argv[4]))
            g.click(*PAUSE)
        elif mode == "click":
            g.click(int(sys.argv[4]), int(sys.argv[5]))
            time.sleep(1.0)
        else:
            time.sleep(float(sys.argv[4]) if len(sys.argv) > 4 else 5)
        res = b.watch_hits()
    finally:
        b.watch_clear()
    mods = g.proc.modules32()
    print(f"total hits {res['total']}")
    for h in sorted(res["hits"], key=lambda h: -h["count"]):
        print(f"  x{h['count']:6d} eip {owner(mods, h['eip'])}  [esp] {owner(mods, h['ret'])}  value {h['value']:#x} tid {h['tid']}")


if __name__ == "__main__":
    main()
