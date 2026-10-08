"""LIVE t7: soak test - advance the loaded city year by year (auto mode "info") and log speed, game memory,
handle count and a few observation calls, to catch slowdowns and leaks.

    python live/t7_soak.py [years]
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3k_mcp.server as S  # noqa: E402


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


def mem(handle):
    pmc = PMC()
    pmc.cb = ctypes.sizeof(pmc)
    ctypes.WinDLL("psapi").GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
    n = wt.DWORD()
    ctypes.windll.kernel32.GetProcessHandleCount(handle, ctypes.byref(n))
    return pmc.PrivateUsage >> 20, n.value


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    S.set_auto_mode("info")
    S.game_status()
    h = S.game.proc.handle
    print("start", S.city_status()["date"], "private MB / handles", mem(h))
    for y in range(years):
        t = time.time()
        r = S.advance_time(years=1)
        dt = time.time() - t
        st = S.city_status()
        t2 = time.time()
        S.map_text(step=16)
        S.advisors()
        S.deals()
        S.petitions()
        obs = time.time() - t2
        print(f"{r.get('to')} {dt:6.1f}s  pop {st.get('population')}  funds {st.get('funds')}  "
              f"closed {[a['title'] for a in r.get('auto_closed', [])]}  stop {r.get('stopped_early')}  "
              f"mem {mem(h)}  observe {obs:.2f}s", flush=True)
        if r.get("stopped_early"):
            print("   dialog:", (r.get("dialog") or {}).get("title"), (r.get("dialog") or {}).get("buttons"))
            break


if __name__ == "__main__":
    main()
