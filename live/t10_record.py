"""LIVE t10: advance_time(record=...) must not change the simulation: fresh seeded trials, one run straight and one
recording metrics monthly (or weekly), compare the final fingerprints.

    python live/t10_record.py [city] [days] [seed] [unit]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from t8_determinism import fingerprint  # noqa: E402


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    unit = sys.argv[4] if len(sys.argv) > 4 else "month"
    out = []
    for rec in ("", unit, ""):
        S.start_trial(city, seed=seed)
        S.set_auto_mode("info")
        r = S.advance_time(days=days, record=rec)
        fp = fingerprint()
        print(repr(rec), r.get("to"), r.get("seconds"), "points", len(r.get("series", [])), fp, flush=True)
        if rec:
            print("  first", r["series"][0]["date"], r["series"][0]["population"], " last", r["series"][-1]["date"],
                  r["series"][-1]["population"])
        out.append(fp)
    print("SAME" if all(o == out[0] for o in out) else "DIFFERENT")


if __name__ == "__main__":
    main()
