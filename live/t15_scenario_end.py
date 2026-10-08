"""LIVE t15 (developer check): what does the end of a scenario look like to an agent? Start a scenario, end it with
the scenario engine's own EndScenario script op (SCENARIO 0x10006DB8, this = s = *(city+0x100), args = an
instruction record holding the final rank) the way a
script ending does, then read the results window (dialog_status), scenario_status, and press the button given on
the command line to see where each choice leads.

    python live/t15_scenario_end.py [scenario] [rank] [button]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else None
    rank = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    button = sys.argv[3] if len(sys.argv) > 3 else None
    S.game_launch()
    if not name:
        names = [c["name"] for c in S.list_cities(kind="scenario")["files"]]
        print("scenarios:", names)
        name = names[0]
    r = S.load_scenario(name)
    print("loaded:", r.get("error") or r.get("scenario", {}).get("name"))
    S.set_auto_mode("info")
    while S.dialog_status().get("dialog"):
        print("closing:", S.dialog_status()["dialog"].get("title"), S.close_dialog("ok"))
    g = S.game
    s = g.u32(g.need_city() + 0x100)
    # a script instruction record: +6 argument count, +8 -> 8-byte arguments {u8 is_variable, ..., u32 value at +4}
    buf = g.scratch() + 0x5000
    g.proc.write(buf, bytes(0x40))
    g.proc.write(buf + 6, bytes([1]))
    g.proc.write(buf + 8, (buf + 0x20).to_bytes(4, "little"))
    g.proc.write(buf + 0x24, rank.to_bytes(4, "little"))
    g.bridge.defer_call(g.mod("scenario.dll") + 0x6DB8, [buf, 1], this=s)
    time.sleep(2)
    print("dialog:", json.dumps(S.dialog_status())[:1500])
    print("scenario_status:", json.dumps(S.scenario_status())[:800])
    if button:
        print("press", button, "->", json.dumps(S.close_dialog(button))[:600])
        time.sleep(3)
        print("after: game_status", json.dumps(S.game_status())[:600])


if __name__ == "__main__":
    main()
