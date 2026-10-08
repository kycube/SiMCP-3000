"""LIVE t8h: for the first SimTransit draws of two seeded runs, dump the traffic agent behind each draw (ESI)."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from t8g_draws import owner, REC  # noqa: E402


def run(seed, days):
    g = S.game
    g.set_random_seed(seed)
    S.load_city("mcp_e2e")
    g.bridge.rng(3)
    S.advance_time(days=days)
    st = g.bridge.rng(2)
    n = min(struct.unpack("<I", g.proc.read(st["next_trace"], 4))[0], 131072)
    raw = g.proc.read(st["next_trace"] + 4, REC * n)
    g.bridge.rng(4)
    recs = [struct.unpack_from("<8I", raw, REC * i) for i in range(n)]
    mods = g.proc.modules32()
    out = []
    for r in recs:
        if "simtransit" in owner(mods, r[4]) and len(out) < 6:
            a = r[6]
            try:
                fields = struct.unpack("<12I", g.proc.read(a, 48))
            except Exception:
                fields = ()
            out.append((owner(mods, r[4]), "esi", r[5], "agent", hex(a), [hex(x) for x in fields]))
    return out


def main():
    S.game_status()
    for i in range(2):
        print("run", i)
        for row in run(7, 20):
            print("  ", row)
    S.game.set_random_seed(None)


if __name__ == "__main__":
    main()
