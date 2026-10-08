"""LIVE t8f: does UI-thread concurrency cause the divergence? Step one day at a time and keep the game's UI thread
suspended while the engine processes each day (resumed between days). Compare fingerprints across seeded runs.

    python live/t8f_suspend_ui.py [city] [days] [runs] [seed]
"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402
from sc3k_mcp.game import (CITY_CLOCK, CITY_DATE, CITY_PAUSE_COUNT, CLOCK_ADVANCE, CLOCK_SLOT_PAUSE,  # noqa: E402
                           CLOCK_SLOT_RESUME, SLOT_PAUSE, SLOT_RESUME)
from t8_determinism import fingerprint  # noqa: E402

k32 = ctypes.windll.kernel32
k32.OpenThread.restype = ctypes.c_void_p
THREAD_SUSPEND_RESUME = 0x0002


def step(days):
    g = S.game
    c = g.need_city()
    clk = g.u32(c + CITY_CLOCK)
    was_running = g.i32(c + CITY_PAUSE_COUNT) == 0
    pause, resume = g.vfn(c, SLOT_PAUSE), g.vfn(c, SLOT_RESUME)
    cpause, cresume = g.vfn(clk, CLOCK_SLOT_PAUSE), g.vfn(clk, CLOCK_SLOT_RESUME)
    adv = g.mod("simcity.dll") + CLOCK_ADVANCE["day"]
    tid = ctypes.windll.user32.GetWindowThreadProcessId(g.bridge.hwnd, None)
    h = k32.OpenThread(THREAD_SUSPEND_RESUME, False, tid)
    g.call_seq(([(pause, c, [])] if was_running else []) + [(cpause, clk, []), (resume, c, [])])
    stalls = 0
    try:
        for _ in range(days):
            goal = g.i32(c + CITY_DATE + 4) + 1
            g.bridge.repeat(adv, 1, this=clk)
            g._post_engine_noop(c)
            k32.SuspendThread(ctypes.c_void_p(h))
            t0 = time.time()
            try:
                while not (g._engine_queue_empty(c) and g.i32(c + CITY_DATE + 4) >= goal):
                    if time.time() - t0 > 2.0:      # the engine is waiting for the UI thread: let it run
                        stalls += 1
                        break
                    time.sleep(0.001)
            finally:
                k32.ResumeThread(ctypes.c_void_p(h))
            while not (g._engine_queue_empty(c) and g.i32(c + CITY_DATE + 4) >= goal):
                time.sleep(0.002)
    finally:
        g.call_seq([(pause, c, []), (cresume, clk, [])] + ([(resume, c, [])] if was_running else []))
        k32.CloseHandle(ctypes.c_void_p(h))
    return stalls


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "mcp_e2e"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 7
    S.game_status()
    out = []
    for i in range(runs):
        S.game.set_random_seed(seed)
        S.load_city(city)
        t = time.time()
        stalls = step(days)
        fp = fingerprint()
        print(i, round(time.time() - t, 1), "s, stalls", stalls, fp, flush=True)
        out.append(fp)
    S.game.set_random_seed(None)
    print("REPRODUCIBLE" if all(o == out[0] for o in out) else "DIFFERENT")


if __name__ == "__main__":
    main()
