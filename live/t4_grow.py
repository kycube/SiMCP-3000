"""LIVE t4: grow the e2e test city year by year and log what the game raises (dialogs, petitions, news).

    python live/t4_grow.py [years]
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    if "--setup" in sys.argv:
        acts = [
            {"building": "Pumping Station", "x": 62, "y": 26},
            {"tool": "pipe", "x": 63, "y": 26, "x2": 80, "y2": 26},
            {"tool": "pipe", "x": 80, "y": 20, "x2": 80, "y2": 60},
            {"tool": "pipe", "x": 70, "y": 30, "x2": 95, "y2": 30},
            {"tool": "pipe", "x": 70, "y": 40, "x2": 95, "y2": 40},
            {"tool": "pipe", "x": 70, "y": 50, "x2": 95, "y2": 50},
            {"tool": "police_station", "x": 96, "y": 32},
            {"tool": "fire_station", "x": 96, "y": 42},
            {"tool": "school", "x": 66, "y": 32},
            {"tool": "res_light", "x": 71, "y": 51, "x2": 79, "y2": 59},
            {"tool": "res_light", "x": 81, "y": 51, "x2": 89, "y2": 59},
        ]
        print(json.dumps(S.build_many(acts)))
    for y in range(years):
        r = S.advance_time(years=1)
        st = S.city_status()
        print(f"== {st.get('date')} pop {st.get('population')} funds {st.get('funds')} demand {st.get('demand')} "
              f"water {st.get('water')} power {st.get('power')}")
        if "stopped_early" in r:
            print("   STOPPED:", r["stopped_early"], S.dialog_status())
        p = S.petitions()
        if p.get("petitions"):
            print("   petitions:", [(x["id"], x.get("heading"), x.get("button1"), x.get("button2"))
                                    for x in p["petitions"]])
        n = S.news()
        print("   news:", n.get("news", [])[:6], n.get("petitions"), n.get("alerts"), n.get("advisors"), n.get("other"))
        d = S.dialog_status()
        if d.get("dialog"):
            print("   DIALOG:", d)


if __name__ == "__main__":
    main()
