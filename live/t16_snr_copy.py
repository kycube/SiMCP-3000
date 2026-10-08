"""LIVE t16: can a program write a scenario the game accepts, carrying its own texts? Copy a shipped scenario into
Cities\\Scenarios\\MCP <name>.SNR with every text embedded under a NEW text-table id (no Res\\Text file has it),
the header / SNR chunk / script references moved to that id and the name changed, then load it and read
scenario_status.

    python live/t16_snr_copy.py ["Rags To Riches"]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from sc3k_mcp import ixf, scenarios as sc  # noqa: E402

NEW_TABLE = 0x5143D0A1


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "Rags To Riches"
    info = sc.read(src)
    old = int(info["header"][0], 16)
    recs = ixf.read(open(info["file"], "rb").read())
    texts = {int(k): v for k, v in info["texts"].items()}
    texts[1] = "MCP " + texts.get(1, src)
    out = []
    for t, g, i, d in recs:
        if t == sc.T_TEXT and g == old:
            continue                                            # re-added below under the new id
        if (t, g, i) == (sc.T_HEADER, sc.G_HEADER, 0):
            d = struct.pack("<I", NEW_TABLE) + d[4:]
        elif (t, g, i) == (sc.T_SNR, sc.G_SNR, 0):
            d = d.decode("cp1252").replace(str(sc.s32(old)), str(sc.s32(NEW_TABLE))).encode("cp1252")
        elif t == sc.T_SCRIPT:
            ins = sc.parse_script(d.decode("cp1252"))
            for x in ins:
                x["args"] = [[a, sc.s32(NEW_TABLE) if (a == 0 and v == sc.s32(old)) else v] for a, v in x["args"]]
            d = sc.format_script(ins).encode("cp1252")
        out.append((t, g, i, d))
    out += [(sc.T_TEXT, NEW_TABLE, k, sc.text_record(v)) for k, v in sorted(texts.items())]
    path = os.path.join(sc.folder(), f"MCP {src}.SNR")
    ixf.write(path, out)
    print("wrote", path, len(out), "records,", len(texts), "texts embedded")
    S.game_launch()
    while S.dialog_status().get("dialog"):
        S.close_dialog("ok")
    r = S.load_scenario(f"MCP {src}")
    print("load:", r.get("error") or "ok")
    print(json.dumps(S.scenario_status())[:900])
    g = S.game
    o = g.u32(g.u32(g.mod("scenario.dll") + 0x1EB44) + 0x8F4)
    print("the game's scenario name:", repr(g.rz_string(g.u32(o + 4))))
    print("briefing:", json.dumps(S.dialog_status())[:400])


if __name__ == "__main__":
    main()
