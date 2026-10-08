"""LIVE b2: does the Building Architect open a project given on its command line? Start Baapp.exe windowed with a
sample .bld path as an extra argument, attach, and read which building the program has open.

    python live/b2_cmdline.py ["Sample Name"]
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bat_mcp.server as B  # noqa: E402
from bat_mcp.app import APPS, BUILDINGS_DIR, EXE  # noqa: E402
from sc3k_mcp.game import CREATE_BREAKAWAY_FROM_JOB, DETACHED, GOG_COMPAT  # noqa: E402


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "The Joneses"
    print("quit running Architect:", B.app.quit())
    path = os.path.join(BUILDINGS_DIR, name + ".bld")
    env = dict(os.environ, __COMPAT_LAYER=GOG_COMPAT)
    pid = subprocess.Popen([EXE, "-w", "-r1024x768", path], cwd=APPS, env=env,
                           creationflags=DETACHED | CREATE_BREAKAWAY_FROM_JOB, close_fds=True).pid
    print("started", pid, "with", path)
    time.sleep(8)
    print("attach:", B.bat_launch())
    info = B.building_info()
    print("open building:", {k: info.get(k) for k in ("name", "path", "lot", "file", "error")} if isinstance(info, dict)
          else info)


if __name__ == "__main__":
    main()
