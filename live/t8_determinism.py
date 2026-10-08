"""LIVE t8: is the simulation reproducible? Load the same save several times, advance the same time and compare
a fingerprint of the city (population, funds, demand, every building's type/state/rect, zones).

    python live/t8_determinism.py [city] [days] [runs] [--seed N] [--fresh]

--seed N  uses the bridge's seeded randomness (game.set_random_seed) before each load
--fresh   restarts the game before each run
Result so far (2026-10-07): NOT reproducible even with --seed and --fresh; runs split at the first weekly
traffic pass (see notes/LIVE_FACTS.md, "Determinism").
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


def fingerprint():
    st = S.city_status()
    occ = sorted((o["category"], tuple(o["rect"]), o.get("state", 0)) for o in S.city.occupants() if o["layer"] == 0)
    zones = b"".join(S.city.zones())
    h = hashlib.sha1(json.dumps(occ).encode() + zones).hexdigest()[:12]
    return {"date": st["date"], "pop": st["population"], "funds": st["funds"], "demand": st["demand"],
            "occupants": len(occ), "hash": h}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    city = args[0] if args else "mcp_e2e"
    days = int(args[1]) if len(args) > 1 else 365
    runs = int(args[2]) if len(args) > 2 else 2
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else None
    fresh = "--fresh" in sys.argv
    out = []
    for i in range(runs):
        S.game_status()
        if fresh:
            if S.game.proc and S.game.proc.alive():
                S.quit_game()
                time.sleep(4)
            S.game_launch()
        S.set_auto_mode("info")
        if seed is not None:
            S.game.set_random_seed(seed)
        r = S.load_city(city)
        if "error" in r:
            print(r)
            return
        a = S.advance_time(days=days)
        fp = fingerprint()
        print(i, a.get("to"), fp, flush=True)
        out.append(fp)
    if seed is not None:
        S.game.set_random_seed(None)
    print("REPRODUCIBLE" if all(o == out[0] for o in out) else "DIFFERENT")


if __name__ == "__main__":
    main()
