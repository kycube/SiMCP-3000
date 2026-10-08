"""LIVE t9: start_trial reproducibility through the server functions: same seed twice (+ a build in between to
show actions replay identically), then another seed.

    python live/t9_trials.py [city] [days]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from t8_determinism import fingerprint  # noqa: E402


def trial(city, seed, days):
    r = S.start_trial(city, seed)
    if "error" in r:
        return r
    S.set_auto_mode("info")
    S.advance_time(days=days // 2)
    b = S.build("res_light", 66, 36, 69, 39)              # the same action mid-way
    S.advance_time(days=days - days // 2)
    return {**fingerprint(), "build": b.get("zone_tiles_now")}


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    res = [(seed, trial(city, seed, days)) for seed in (11, 11, 12)]
    for seed, fp in res:
        print(seed, fp)
    print("seed 11 reproducible:", res[0][1] == res[1][1], " seed 12 differs:", res[2][1] != res[0][1])


if __name__ == "__main__":
    main()
