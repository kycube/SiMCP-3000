"""LIVE: from the main menu, start a new city through the UI (defaults, disasters off) and close the tip.

    python live/quick_city.py [--relaunch]
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402
from sc3k_mcp.game import Game  # noqa: E402


def frame_changes(g, secs=1.5):
    from PIL import ImageChops, ImageStat
    a = g.capture()
    time.sleep(secs)
    b = g.capture()
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean)


def main():
    if "--relaunch" in sys.argv:
        for pid in win32.find_pids("SC3U.exe"):
            p = win32.Process(pid)
            win32.k32.TerminateProcess(p.handle, 0)
        time.sleep(2)
    g = Game()
    st = g.attach(launch=True)
    print("attached", st.get("screen"))
    if st.get("screen") == "menu":
        time.sleep(2)
        g.click(357, 400, wait_ms=2500)       # Start New City
        g.click(213, 500, wait_ms=600)        # Disasters off
        g.click(797, 544, wait_ms=5000)       # OK -> terrain editor
        g.click(937, 590, wait_ms=4000)       # Accept this Terrain
        g.click(635, 497, wait_ms=1500)       # close the Llama tip
    print(g.status())
    print("frame changes over 1.5 s:", round(frame_changes(g), 3))


if __name__ == "__main__":
    main()
