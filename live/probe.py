"""LIVE: inspects the running SC3U.exe (read-only). Prints windows (incl. hidden), modules, job state.

    python live/probe.py            # one snapshot
    python live/probe.py watch 20   # snapshot every second for 20 s (window/state changes only)
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402

u32 = win32.u32
k32 = win32.k32
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
u32.GetForegroundWindow.restype = wt.HWND


def windows_of(pid):
    out = []

    def cb(h, _):
        if win32.window_pid(h) == pid:
            cls = ctypes.create_unicode_buffer(256)
            txt = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(h, cls, 256)
            u32.GetWindowTextW(h, txt, 256)
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            style = u32.GetWindowLongW(h, -16) & 0xFFFFFFFF
            out.append(dict(hwnd=h, cls=cls.value, title=txt.value, visible=bool(u32.IsWindowVisible(h)),
                            rect=(r.left, r.top, r.right, r.bottom), style=style))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def snapshot(pid, show_modules=True):
    p = win32.Process(pid)
    lines = []
    inj = ctypes.c_int()
    k32.IsProcessInJob(p.handle, None, ctypes.byref(inj))
    fg = u32.GetForegroundWindow()
    lines.append(f"pid {pid} alive={p.alive()} in_job={bool(inj.value)} foreground_pid={win32.window_pid(fg) if fg else 0}")
    for w in windows_of(pid):
        lines.append(f"  hwnd {w['hwnd']:#x} cls={w['cls']!r} title={w['title']!r} vis={w['visible']} "
                     f"rect={w['rect']} style={w['style']:#010x}")
    if show_modules:
        mods = p.modules32()
        for name, base in sorted(mods.items(), key=lambda kv: kv[1]):
            lines.append(f"  mod {base:#010x} {name}")
    p.close()
    return "\n".join(lines)


def main():
    pids = win32.find_pids("SC3U.exe")
    if not pids:
        print("SC3U.exe not running")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        secs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        last = None
        for i in range(secs):
            pids = win32.find_pids("SC3U.exe")
            if not pids:
                print(f"t={i}s: SC3U.exe gone")
                return
            s = snapshot(pids[0], show_modules=False)
            if s != last:
                print(f"--- t={i}s\n{s}")
                last = s
            time.sleep(1)
        return
    for pid in pids:
        print(snapshot(pid))


if __name__ == "__main__":
    main()
