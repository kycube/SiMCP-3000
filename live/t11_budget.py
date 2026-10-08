"""LIVE t11: advance_time's max_seconds budget must not change the simulation. Fresh seeded trials: one straight run
(max_seconds=0), one checked every 30 days (large budget), one forced to stop early repeatedly (tiny budget,
continued with remaining_days). Compare the final fingerprints.

    python live/t11_budget.py [city] [days] [seed]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from t8_determinism import fingerprint  # noqa: E402


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    out = []
    for budget in (0, 1000, 0.05):
        S.start_trial(city, seed=seed)
        S.set_auto_mode("info")
        left, calls = days, 0
        while left:
            r = S.advance_time(days=left, max_seconds=budget)
            calls += 1
            left = r.get("remaining_days", 0)
            if r.get("dialog"):
                print("dialog", r["dialog"])
                break
        fp = fingerprint()
        print("max_seconds", budget, "calls", calls, fp, flush=True)
        out.append(fp)
    print("SAME" if all(o == out[0] for o in out) else "DIFFERENT")


if __name__ == "__main__":
    main()
