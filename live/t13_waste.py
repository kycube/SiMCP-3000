"""LIVE t13: which yearly garbage total is incinerators and which waste-to-energy (P+0x174 / P+0x17C)? Read both
next to the incinerators and waste-to-energy plants standing in the shipped cities, and what the garbage picker
offers in each.

    python live/t13_waste.py [city ...]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from sc3k_mcp.city import C_POLLUTION  # noqa: E402

CITIES = ["Europolis", "Madrid, Spain", "Madison, WI", "Sacramento, CA", "Seoul, Korea", "Berlin, Germany",
          "Frankfurt, Germany", "London, England", "Liverpool, England", "Moscow, Russia", "Craterville"]


def main():
    S.game_launch()
    for name in sys.argv[1:] or CITIES:
        if "error" in S.load_city(name):
            print(name, "not loaded")
            continue
        g, C = S.city.g, S.city.C
        P = g.u32(C + C_POLLUTION)
        p174, p17c = g.i64(P + 0x174), g.i64(P + 0x17C)
        occ = S.buildings(limit=5000).get("occupants", [])
        names = {}
        for o in occ:
            n = o.get("building") or ""
            if "incinerat" in n.lower() or "waste" in n.lower():
                names[n] = names.get(n, 0) + 1
        opts = S.building_options("garbage")
        print(f"{name}: P+0x174 {p174:>10}  P+0x17C {p17c:>10}  | {names} | picker {opts.get('buildings', opts)}")


if __name__ == "__main__":
    main()
