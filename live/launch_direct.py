"""LIVE: launches SC3U.exe directly with CreateProcess (as the MCP server would) and exits immediately.

    python live/launch_direct.py [extra args...]   (default args: -w -r1024x768 -intro:off)
Replaces the inherited __COMPAT_LAYER with GOG's flags, tries CREATE_BREAKAWAY_FROM_JOB first.
"""
import os
import subprocess
import sys

APPS = os.path.join(os.environ.get("SC3K_GAME_DIR") or r"C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited", "Apps")
GOG_COMPAT = "16BITCOLOR 8And16BitAggregateBlts DISABLEDWM HIGHDPIAWARE"
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def main():
    args = sys.argv[1:] or ["-w", "-r1024x768", "-intro:off"]
    env = dict(os.environ)
    env["__COMPAT_LAYER"] = GOG_COMPAT
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 1  # SW_SHOWNORMAL
    for flags, label in ((DETACHED | CREATE_BREAKAWAY_FROM_JOB, "breakaway"), (DETACHED, "no breakaway")):
        try:
            p = subprocess.Popen([os.path.join(APPS, "SC3U.exe")] + args, cwd=APPS, env=env, startupinfo=si,
                                 creationflags=flags, close_fds=True)
            print(f"started pid {p.pid} ({label})")
            return
        except OSError as e:
            print(f"{label}: {e}")


if __name__ == "__main__":
    main()
