"""LIVE t5: city switching robustness - load a city and run every observation tool against it.

    python live/t5_switch.py "<city name>" [--save-first <name>]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


def show(label, r, n=600):
    s = json.dumps(r, default=str)
    print(f"-- {label}: {s[:n]}{' ...' if len(s) > n else ''}")


def main():
    name = sys.argv[1]
    if "--save-first" in sys.argv:
        show("save", S.save_city(sys.argv[sys.argv.index("--save-first") + 1]))
    t = time.time()
    show("load", S.load_city(name))
    print(f"   ({time.time() - t:.1f}s)")
    show("status", S.city_status())
    b = S.get_budget()
    show("budget", {k: b.get(k) for k in ("funds", "taxes", "bonds", "debt")} if "error" not in b else b)
    show("ordinances", S.ordinances(), 300)
    show("petitions", S.petitions())
    show("news", S.news(), 400)
    g = S.graphs("years")
    show("graphs", {k: (v[:3] if isinstance(v, list) else v) for k, v in list(g.items())[:6]})
    show("building_counts", S.building_counts(), 500)
    print(S.map_text(step=8))
    show("dialog", S.dialog_status())


if __name__ == "__main__":
    main()
