"""LIVE: measures SC3U.exe CPU use while focused vs. unfocused, and what happens to its windows.

    python live/focus_test.py <game_main_hwnd_hex>
Moves the foreground to another visible top-level window (any other program), then restores the game.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402
from probe import windows_of, EnumWindowsProc  # noqa: E402

k32, u32 = win32.k32, win32.u32
k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
u32.GetForegroundWindow.restype = wt.HWND
u32.SetForegroundWindow.argtypes = [wt.HWND]
u32.IsIconic.argtypes = [wt.HWND]
u32.SwitchToThisWindow.argtypes = [wt.HWND, wt.BOOL]


def cpu_seconds(h):
    c, e, kt, ut = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
    f = lambda ft: (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7
    return f(kt) + f(ut)


def measure(p, secs=3.0):
    a = cpu_seconds(p.handle)
    time.sleep(secs)
    return (cpu_seconds(p.handle) - a) / secs


def other_window(game_pid):
    found = []

    def cb(h, _):
        if u32.IsWindowVisible(h) and win32.window_pid(h) != game_pid:
            t = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, t, 256)
            if t.value and not t.value.startswith(("SimCity", "[DDrawCompat]", "Program Manager")):
                found.append((h, t.value))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def state(pid):
    fg = u32.GetForegroundWindow()
    ws = [w for w in windows_of(pid) if w["visible"]]
    return f"fg_pid={win32.window_pid(fg) if fg else 0} " + "; ".join(
        f"{w['cls']} rect={w['rect']} iconic={bool(u32.IsIconic(w['hwnd']))}" for w in ws)


def main():
    game = int(sys.argv[1], 16)
    pid = win32.window_pid(game)
    p = win32.Process(pid)
    print("focused   :", state(pid), f"cpu={measure(p):.2f} cores")
    others = other_window(pid)
    print("other windows:", others[:3])
    if not others:
        return
    h = others[0][0]
    ok = u32.SetForegroundWindow(h)
    time.sleep(0.5)
    if win32.window_pid(u32.GetForegroundWindow()) == pid:
        u32.SwitchToThisWindow(h, True)
        time.sleep(0.5)
    print("SetForegroundWindow ->", ok)
    print("unfocused :", state(pid), f"cpu={measure(p):.2f} cores")
    time.sleep(2)
    print("unfocused+2s:", state(pid), f"cpu={measure(p):.2f} cores")
    u32.SwitchToThisWindow(game, True)
    time.sleep(1)
    print("restored  :", state(pid), f"cpu={measure(p):.2f} cores")


if __name__ == "__main__":
    main()
