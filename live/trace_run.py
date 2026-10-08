"""LIVE: trace virtual calls on chosen objects while something happens, then summarize by slot/caller.

    python live/trace_run.py run <seconds>                 # trace city + budget while the sim runs
    python live/trace_run.py click <x> <y> [seconds]        # trace city + budget around a UI click
Prints call counts per (object tag, slot, caller module+offset).
"""
import collections
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp.game import Game  # noqa: E402

PLAY, PAUSE = (750, 722), (722, 722)


def owner(mods, a):
    best = max(((n, b) for n, b in mods.items() if b <= a), key=lambda t: t[1], default=(None, 0))
    return f"{best[0]}+{a - best[1]:#x}" if best[0] and a - best[1] < 0x200000 else f"{a:#x}"


def main():
    g = Game()
    g.attach(launch=False)
    b = g.bridge
    c = g.city()
    budget = g.u32(c + 0xC4)
    targets = {1: ("city", c, 163), 2: ("budget", budget, 28)}
    extra = [a for a in sys.argv if a.startswith("obj=")]
    for i, e in enumerate(extra):
        _, spec = e.split("=")
        addr, n = spec.split(":")
        targets[10 + i] = (f"obj{i}", int(addr, 16), int(n))
    b.trace_stop()
    since = b.trace_read()[-1]["seq"] if b.trace_read() else 0
    for tag, (name, obj, n) in targets.items():
        r = b.trace_object(obj, n, tag)
        assert r.ok, r
    try:
        if sys.argv[1] == "run":
            g.click(*PLAY)
            time.sleep(float(sys.argv[2]))
            g.click(*PAUSE)
        elif sys.argv[1] == "click":
            g.click(int(sys.argv[2]), int(sys.argv[3]))
            time.sleep(float(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("obj=") else 1.0)
    finally:
        recs = b.trace_read(since)
        b.trace_stop()
    mods = g.proc.modules32()
    cnt = collections.Counter((r["tag"], r["slot"], owner(mods, r["ret"])) for r in recs)
    print(f"{len(recs)} calls")
    for (tag, slot, caller), n in sorted(cnt.items()):
        print(f"  {targets[tag][0]:7s} slot {slot:3d} (+{slot * 4:#05x})  x{n:5d}  from {caller}")


if __name__ == "__main__":
    main()
