"""LIVE t12: settle open data questions through the server functions.

1. City styles: are the landscape / tree / building styles saved with the city? Set non-default styles, save as a
   new test city, put the styles back in memory, load another city, load the test city again and read them.
2. Garbage: which yearly total is incinerators and which waste-to-energy (P+0x174 / P+0x17C)? Place one of each in
   turn and watch which total grows.
3. Power: is P+0x29C[0] the power bought from neighbours? Read it next to the deals in force in the shipped cities.

    python live/t12_data_checks.py [test city]          (default mcp_e2e; writes Cities\\mcp_t12_*.sc3)
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from sc3k_mcp.city import C_POLLUTION, C_POWER  # noqa: E402


def raw_waste():
    g, C = S.city.g, S.city.C
    P = g.u32(C + C_POLLUTION)
    return {"recycled": g.i64(P + 0x16C), "p174": g.i64(P + 0x174), "p17c": g.i64(P + 0x17C),
            "landfill": g.i64(P + 0x184)}


def power_raw():
    g, C = S.city.g, S.city.C
    P = g.u32(C + C_POWER)
    return list(struct.unpack("<10i", g.proc.read(P + 0x29C, 40)))


def styles():
    o = S.city_options()
    return {k: o.get(k) for k in ("landscape", "trees", "buildings")}


def check_styles(city):
    print("== styles")
    print(S.load_city(city).get("city", {}).get("name"))
    before = styles()
    want = {"landscape": "winter" if before["landscape"] != "winter" else "desert",
            "trees": "conifers" if before["trees"] != "conifers" else "palms",
            "buildings": "european" if before["buildings"] != "european" else "asian"}
    print("before", before, "-> set", want)
    print("set:", styles() if "error" not in S.set_city_options(**want) else "ERROR")
    r = S.save_city("mcp_t12_styles", overwrite=True)
    print("save:", r.get("error") or r.get("file") or r)
    S.set_city_options(**before)                                  # memory back to the old styles
    print("memory reset to", styles())
    S.load_city(city)
    print("other city loaded:", styles())
    S.load_city("mcp_t12_styles")
    after = styles()
    print("test city reloaded:", after, "-> saved with the city:", after == want)
    return after == want


def check_waste(city):
    print("== waste")
    S.load_city(city)
    S.set_auto_mode("info")
    opts = S.building_options("garbage")["buildings"]
    print("garbage picker:", opts)
    results = {}
    for name in [n for n in opts if "incinerator" in n.lower()] + [n for n in opts if "waste" in n.lower()]:
        area = S.find_empty_area(4, 4, limit=1)
        if not area.get("areas"):
            print("no space"); break
        x, y = area["areas"][0]["x"], area["areas"][0]["y"]
        r = S.place_building(name, x, y, picker="garbage")
        print("placed", name, "at", (x, y), "->", r.get("error") or r.get("placed") or "ok")
        w0 = raw_waste()
        S.advance_time(days=62)
        w1 = raw_waste()
        grew = {k: w1[k] - w0[k] for k in w1}
        print("  totals grew by", grew)
        results[name] = grew
    return results


def check_power():
    print("== neighbour power")
    out = []
    for c in S.list_cities().get("files", []):
        if c.get("kind") != "city":
            continue
        name = c["name"]
        if name.lower().startswith("mcp"):
            continue
        r = S.load_city(name)
        if "error" in r:
            continue
        deals = S.deals()
        buy = [d for d in deals.get("active", []) if d.get("type") == "buy_power"]
        pw = power_raw()
        out.append({"city": name, "buy_power_deals": buy, "p29c": pw})
        print(name, "| buy_power:", [(d.get("neighbor"), d.get("quantity")) for d in buy], "| P+0x29C:", pw)
    return out


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    S.game_launch()
    res = {"styles_saved_with_city": check_styles(city), "waste": check_waste(city), "power": check_power()}
    out = os.path.join(os.environ.get("TEMP", "."), "sc3k-mcp", "t12_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, "w"), indent=1, default=str)
    print("results:", out)


if __name__ == "__main__":
    main()
