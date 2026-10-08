"""LIVE t17: write a new scenario with create_scenario's machinery, play it and see it end.

    python live/t17_create_scenario.py [win|lose]
win: a goal already met (population >= 1): the monthly check marks it and ends the scenario with rank 1.
lose: a goal out of reach (population >= 100,000,000) and a 2-month limit: the scenario ends with rank 2.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from sc3k_mcp import scenarios as sc  # noqa: E402


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "win"
    name = f"MCP Test {mode.title()}"
    target = 1 if mode == "win" else 100_000_000
    r = sc.create(name, "Madison, WI", "A SiMCP 3000 test scenario.", overwrite=True, months=2,
                  briefing="Welcome, Mayor. Grow the city.", win_title="Well Done!", win_text="All goals met.",
                  lose_title="Out of Time", lose_text="The goals were not met in time.",
                  goals=[{"measure": "population", "at_least": target, "text": f"Reach a population of {target:,}."}])
    print("created:", r)
    S.game_launch()
    while S.dialog_status().get("dialog"):
        S.close_dialog("ok")
    print("load:", S.load_scenario(name).get("error") or "ok")
    S.set_auto_mode("info")
    for step in range(8):
        d = S.dialog_status().get("dialog")
        if d:
            print("dialog:", d.get("title"), "|", (d.get("text") or "")[:120], "| buttons", d.get("buttons"))
            if "Replay Scenario" in (d.get("buttons") or []):
                break
            S.close_dialog("ok")
            continue
        st = S.scenario_status()
        print("status:", json.dumps({k: st.get(k) for k in ("running", "months_elapsed", "goals", "ended", "rank")}))
        if st.get("ended"):
            break
        a = S.advance_time(months=1)
        print("advance:", {k: a.get(k) for k in ("date", "stopped_early", "remaining_days", "error")})
    print("final:", json.dumps(S.scenario_status())[:600])


if __name__ == "__main__":
    main()
