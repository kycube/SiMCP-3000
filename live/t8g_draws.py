"""LIVE t8g: compare every generator draw (all modules' Next(), via the bridge's draw tracing) between two seeded
runs from the same save, and print where the sequences first differ with their call chains.

    python live/t8g_draws.py [city] [days] [seed]
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402

REC = 8 * 4


def owner(mods, a):
    best = max(((n, b) for n, b in mods.items() if b <= a and n != "uv.dll"), key=lambda t: t[1], default=(None, 0))
    return f"{best[0]}+{a - best[1]:#x}" if best[0] else hex(a)


def run(city, days, seed):
    g = S.game
    g.set_random_seed(seed)
    S.load_city(city)
    st = g.bridge.rng(3)                     # hook Next() everywhere, reset the log
    S.advance_time(days=days)
    st = g.bridge.rng(2)
    n = min(struct.unpack("<I", g.proc.read(st["next_trace"], 4))[0], 131072)
    raw = g.proc.read(st["next_trace"] + 4, REC * n)
    g.bridge.rng(4)
    recs = [struct.unpack_from("<8I", raw, REC * i) for i in range(n)]
    return st, recs


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    S.set_auto_mode("info")
    S.game_status()
    mods = S.game.proc.modules32()
    st, a = run(city, days, seed)
    _, b = run(city, days, seed)
    S.game.set_random_seed(None)
    print("hooks", st["next_hooks"], "draws A", len(a), "B", len(b))
    print("threads A", collections.Counter(r[1] for r in a).most_common(3), "B",
          collections.Counter(r[1] for r in b).most_common(3))
    # compare only (module, caller, state): thread ids and object addresses differ between runs
    key = lambda r: (r[0], r[4], r[3])
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if key(x) != key(y)), None)
    print("first difference at draw", first)
    chain = lambda r: f"mod{r[0]} state {r[3]:#x} " + " < ".join(owner(mods, f) for f in r[4:] if f)
    if first is not None:
        for i in range(max(0, first - 4), min(len(a), len(b), first + 6)):
            mark = "**" if key(a[i]) != key(b[i]) else "  "
            print(mark, i, "A:", chain(a[i]))
            print(mark, i, "B:", chain(b[i]))


if __name__ == "__main__":
    main()
