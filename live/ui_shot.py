"""LIVE: post a mouse click to the game window at client coords and save a capture.

    python live/ui_shot.py <x> <y> [out.png] [--wait S]
    python live/ui_shot.py shot [out.png]
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402
from probe import windows_of  # noqa: E402

SHOTS = os.environ.get("SC3K_SHOTS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots"))


def game_windows():
    pid = win32.find_pids("SC3U.exe")[0]
    ws = windows_of(pid)
    main = next(w["hwnd"] for w in ws if w["cls"] == "Gonzo")
    pres = next((w["hwnd"] for w in ws if w["title"].startswith("[DDrawCompat]")), main)
    return main, pres


def capture_client():
    """The game's client area (pixels == client coords), captured from DDrawCompat's presentation window."""
    main, pres = game_windows()
    img = win32.capture_window(pres)
    pr = wt.RECT()
    win32.u32.GetWindowRect(pres, ctypes.byref(pr))
    cr = wt.RECT()
    win32.u32.GetClientRect(main, ctypes.byref(cr))
    pt = wt.POINT(0, 0)
    win32.u32.ClientToScreen(main, ctypes.byref(pt))
    ox, oy = pt.x - pr.left, pt.y - pr.top
    return img.crop((ox, oy, ox + cr.right, oy + cr.bottom))


def shot(path, scale=2):
    img = capture_client()
    if scale > 1:
        img = img.resize((img.width // scale, img.height // scale))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)
    return path


def click(x, y, button="left"):
    main, _ = game_windows()
    lp = (y << 16) | (x & 0xFFFF)
    down, up, mk = (0x201, 0x202, 1) if button == "left" else (0x204, 0x205, 2)
    win32.post_message(main, 0x200, 0, lp)
    time.sleep(0.05)
    win32.post_message(main, down, mk, lp)
    time.sleep(0.08)
    win32.post_message(main, up, 0, lp)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wait = 1.5
    if "--wait" in sys.argv:
        wait = float(sys.argv[sys.argv.index("--wait") + 1])
        args = [a for a in args if a != str(sys.argv[sys.argv.index("--wait") + 1])]
    if args[0] == "shot":
        print(shot(args[1] if len(args) > 1 else os.path.join(SHOTS, "shot.png")))
        return
    x, y = int(args[0]), int(args[1])
    click(x, y)
    time.sleep(wait)
    print(shot(args[2] if len(args) > 2 else os.path.join(SHOTS, "click.png")))


if __name__ == "__main__":
    main()
