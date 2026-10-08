"""LIVE t8c: run the same save twice with the same seed and report where the sequences of rand() callers
(non-UI threads) first diverge, to find the remaining sources of non-determinism.

    python live/t8c_divergence.py [city] [days] [seed]
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


def owner(mods, a):
    best = max(((n, b) for n, b in mods.items() if b <= a and n != "uv.dll"), key=lambda t: t[1], default=(None, 0))
    return f"{best[0]}+{a - best[1]:#x}" if best[0] else hex(a)


def run(city, days, seed):
    S.game.set_random_seed(seed)
    S.load_city(city)
    S.advance_time(days=days)
    st = S.game.bridge.rng(2)
    n = min(struct.unpack("<I", S.game.proc.read(st["trace"], 4))[0], 65536)
    raw = S.game.proc.read(st["trace"] + 4, 28 * n)
    recs = []
    for i in range(n):
        tid, *frames = struct.unpack_from("<7I", raw, 28 * i)
        recs.append((tuple(frames), tid))
    return st, recs


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    S.set_auto_mode("info")
    S.game_status()
    mods = S.game.proc.modules32()
    a_st, a = run(city, days, seed)
    b_st, b = run(city, days, seed)
    S.game.bridge.rng(0)
    print("run A", a_st["rands_drawn"], "run B", b_st["rands_drawn"], "seeds", a_st["seeds_drawn"], b_st["seeds_drawn"])
    print("threads A", collections.Counter(t for _, t in a).most_common(4))
    print("threads B", collections.Counter(t for _, t in b).most_common(4))
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x[0] != y[0]), None)
    print("first divergence at call", first)
    stack = lambda fr: " < ".join(owner(mods, f) for f in fr if f)
    if first is not None:
        for i in range(max(0, first - 3), min(len(a), first + 4)):
            print(i, "A:", stack(a[i][0]))
            print(i, "B:", stack(b[i][0]) if i < len(b) else "")
    ca = collections.Counter(stack(r) for r, _ in a)
    cb = collections.Counter(stack(r) for r, _ in b)
    diff = {k: (ca[k], cb[k]) for k in set(ca) | set(cb) if ca[k] != cb[k]}
    print("callers with different counts:", sorted(diff.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1]))[:15])


if __name__ == "__main__":
    main()
