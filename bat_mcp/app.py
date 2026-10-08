"""The Building Architect process: launch (windowed), attach the bridge, status, quit.

Baapp.exe is built on the same Maxis GZ framework as SC3U.exe (same GOG build stamp, same base address), so the
game's bridge DLL and the generic parts of sc3k_mcp.game.Game (calls on the UI thread, memory, input, GZ messages)
are reused unchanged; only the process-specific parts are overridden here.
"""

from __future__ import annotations

import os
import subprocess
import time

from sc3k_mcp import bridge as bridge_mod
from sc3k_mcp import win32
from sc3k_mcp.game import APPS, CREATE_BREAKAWAY_FROM_JOB, DETACHED, GOG_COMPAT, Game, GameError, _windows_of

EXE = os.path.join(APPS, "Baapp.exe")
GAME_DIR = os.path.dirname(APPS)
BUILDINGS_DIR = os.path.join(GAME_DIR, "Buildings")          # the Architect's projects (*.bld)
RENDER_DAT = os.path.join(APPS, "BARender", "BAT.DAT")       # rendered buildings the game reads


class BatApp(Game):
    """The Building Architect (Baapp.exe), driven through the injected bridge."""

    def _find(self) -> int | None:
        pids = win32.find_pids("Baapp.exe")
        return pids[0] if pids else None

    def _launch(self, windowed: bool = True) -> int:
        w, h = self.resolution
        args = [EXE] + (["-w", f"-r{w}x{h}"] if windowed else [])
        env = dict(os.environ)
        env["__COMPAT_LAYER"] = GOG_COMPAT
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 1
        last = None
        for flags in (DETACHED | CREATE_BREAKAWAY_FROM_JOB, DETACHED):
            try:
                return subprocess.Popen(args, cwd=APPS, env=env, startupinfo=si, creationflags=flags,
                                        close_fds=True).pid
            except OSError as e:
                last = e
        raise GameError(f"could not start Baapp.exe: {last}")

    def _msg_server_getter(self) -> int:
        return 0x44F773                                           # Baapp message server getter (cdecl, cached)

    def status(self) -> dict:
        with self.lock:
            if not self.proc or not self.proc.alive():
                pid = self._find()
                return {"running": bool(pid), "pid": pid, "bridge": False} if pid else {"running": False}
            wins = [w for w in _windows_of(self.proc.pid) if w["cls"] == "Gonzo"]
            return {"running": True, "pid": self.proc.pid, "bridge": bool(self.bridge and self.bridge.block),
                    "window": wins[0]["title"] if wins else None}

    def quit(self, timeout: float = 15.0) -> dict:
        """Close the Architect with its framework's Quit (framework *(0x4971C8), vtable slot 16 -> PostQuitMessage;
        the program ignores WM_CLOSE, as the game does); no save prompt: unsaved work is lost."""
        with self.lock:
            if not self.proc or not self.proc.alive():
                pid = self._find()
                if not pid:
                    return {"running": False}
                self.proc = win32.Process(pid)
            try:
                if not self.bridge:
                    self.attach(launch=False)
                fw = self.u32(0x4971C8)
                self.call(self.vfn(fw, 16), [0], this=fw)
            except Exception:                                   # no bridge: ask the window instead
                for w in _windows_of(self.proc.pid):
                    if w["cls"] == "Gonzo":
                        win32.post_message(w["hwnd"], 0x10)
            deadline = time.time() + timeout
            while self.proc.alive() and time.time() < deadline:
                time.sleep(0.2)
            alive = self.proc.alive()
            if not alive:
                self.proc, self.bridge = None, None
            return {"running": alive}


def bridge_identity_ok(proc: win32.Process) -> bool:
    try:
        bridge_mod.check_game_identity(proc)
        return True
    except bridge_mod.BridgeError:
        return False
