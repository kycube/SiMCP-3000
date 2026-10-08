"""LIVE t8i: fresh game process per run: traffic agent order after load + fingerprint after N days (seeded).

    python live/t8i_fresh_agents.py [city] [days] [runs] [seed]
"""
import ctypes
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from sc3k_mcp.city import _writable_regions  # noqa: E402
from sc3k_mcp.win32 import k32  # noqa: E402
from t8_determinism import fingerprint  # noqa: E402


def agent_ids():
    g = S.game
    pat = struct.pack("<I", g.mod("simtransit.dll") + 0x1A594)
    out = {}
    for base, size in _writable_regions(g.proc):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(g.proc.handle, ctypes.c_void_p(base), buf, size, ctypes.byref(got)):
            continue
        d = buf.raw[:got.value]
        i = d.find(pat)
        while i != -1:
            if i % 4 == 0:
                out[base + i] = struct.unpack_from("<I", d, i + 4)[0]
            i = d.find(pat, i + 1)
    return [out[a] for a in sorted(out)]


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 7
    res = []
    for i in range(runs):
        S.game_status()
        if S.game.proc and S.game.proc.alive():
            S.quit_game()
            time.sleep(4)
        S.game_launch()
        S.game.set_random_seed(seed)
        S.load_city(city)
        ids = agent_ids()
        S.set_auto_mode("info")
        S.advance_time(days=days)
        fp = fingerprint()
        print(i, "agents", ids, fp, flush=True)
        res.append((ids, fp))
    print("agents same:", all(r[0] == res[0][0] for r in res), " result same:", all(r[1] == res[0][1] for r in res))


if __name__ == "__main__":
    main()
