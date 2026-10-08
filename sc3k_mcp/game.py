"""The live SimCity 3000 Unlimited game: launch/attach, pointer paths, observation, UI input."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import datetime
import os
import struct
import subprocess
import threading
import time

from . import bridge as bridge_mod
from . import win32

APPS = bridge_mod.GAME_APPS
EXE = os.path.join(APPS, "SC3U.exe")
GOG_COMPAT = "16BITCOLOR 8And16BitAggregateBlts DISABLEDWM HIGHDPIAWARE"
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

# ---- pointer paths (module, RVA) / offsets; see notes/LIVE_FACTS.md
CITY_GLOBAL = ("strtsim.dll", 0x32C9C)   # -> current city object (0 at the main menu)
CITY_SIZE = 0x3C                          # int32 x3 (width, height, ?)
CITY_NAME = 0x48                          # string object: vtable, begin, end, cap
CITY_MAYOR = 0x5C
CITY_DATE = 0x134                         # embedded date object: +4 JDN, +8 year, +0xC month
CITY_BUDGET = 0xC4                        # -> budget object (SIMMISC)
BUDGET_FUNDS = 0x38                       # int64

# simulation clock (re/agents/core/REPORT.md)
CITY_CLOCK = 0x130            # -> clock (SIMCITY vtable 0x10013988)
CITY_ENGINE = 0x124           # -> sim engine (its own thread); +0x14 message queue
CITY_PAUSE_COUNT = 0x140      # user pause count (slot 131 pause / 132 resume)
CITY_SYS_PAUSE = 0x144        # system/modal pause count
CITY_SPEED = 0x14C            # effective speed 0..4 (+0x150 requested)
CITY_FOUNDED = 0x13C          # founding year
SLOT_PAUSE, SLOT_RESUME, SLOT_SET_SPEED, SLOT_GET_DATE = 131, 132, 129, 121
CLOCK_SLOT_PAUSE, CLOCK_SLOT_RESUME = 11, 12
CLOCK_ADVANCE = {"minute": 0xA915, "hour": 0xA9B1, "day": 0xAA4D}   # SIMCITY.DLL RVAs, thiscall(clock)
ENGINE_NOOP_MSG = 99          # message type the engine dispatcher ignores (> 8): used as a drain sentinel

VK = {"esc": 0x1B, "escape": 0x1B, "enter": 0x0D, "return": 0x0D, "space": 0x20, "tab": 0x09,
      "backspace": 0x08, "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21,
      "pagedown": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "pause": 0x13,
      "plus": 0xBB, "minus": 0xBD, "add": 0x6B, "subtract": 0x6D, "comma": 0xBC, "period": 0xBE}
VK.update({f"f{i}": 0x6F + i for i in range(1, 13)})

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
win32.u32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
win32.u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]


class GameError(RuntimeError):
    pass


def jdn_to_date(jdn: int) -> datetime.date:
    """Julian Day Number -> proleptic Gregorian date (Fliegel & Van Flandern)."""
    l = jdn + 68569
    n = 4 * l // 146097
    l -= (146097 * n + 3) // 4
    i = 4000 * (l + 1) // 1461001
    l = l - 1461 * i // 4 + 31
    j = 80 * l // 2447
    day = l - 2447 * j // 80
    l = j // 11
    month = j + 2 - 12 * l
    year = 100 * (n - 49) + i + l
    return datetime.date(year, month, day)


def date_to_jdn(d: datetime.date) -> int:
    return d.toordinal() + 1721425


def calendar_days(jdn: int, days: int = 0, months: int = 0, years: int = 0) -> int:
    """Days from JDN `jdn` to the date `years` years, `months` months and `days` days later (the day of month is
    clamped to the target month's length, as calendars do)."""
    d = jdn_to_date(jdn)
    m = d.month - 1 + months + 12 * years
    y, m = d.year + m // 12, m % 12 + 1
    last = (datetime.date(y + (m == 12), m % 12 + 1, 1) - datetime.timedelta(days=1)).day
    return date_to_jdn(datetime.date(y, m, min(d.day, last))) + days - jdn


def _windows_of(pid: int) -> list[dict]:
    out = []

    def cb(h, _):
        if win32.window_pid(h) == pid:
            cls = ctypes.create_unicode_buffer(128)
            txt = ctypes.create_unicode_buffer(256)
            win32.u32.GetClassNameW(h, cls, 128)
            win32.u32.GetWindowTextW(h, txt, 256)
            out.append({"hwnd": h, "cls": cls.value, "title": txt.value, "visible": bool(win32.u32.IsWindowVisible(h))})
        return True

    win32.u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


class Game:
    def __init__(self, resolution: tuple[int, int] = (1024, 768)):
        self.resolution = resolution
        self.proc: win32.Process | None = None
        self.bridge: bridge_mod.Bridge | None = None
        self.lock = threading.RLock()
        self._mods: dict[str, int] = {}
        self.pending: dict | None = None     # a tool operation waiting for the player's answer to a game dialog

    # ------------------------------------------------------------ process
    def _find(self) -> int | None:
        pids = win32.find_pids("SC3U.exe")
        return pids[0] if pids else None

    def _launch(self, windowed: bool = True) -> int:
        w, h = self.resolution
        args = [EXE, "-intro:off"] + (["-w", f"-r{w}x{h}"] if windowed else [])
        env = dict(os.environ)
        env["__COMPAT_LAYER"] = GOG_COMPAT  # replace the inherited DetectorsAppHealth layer
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 1
        last = None
        for flags in (DETACHED | CREATE_BREAKAWAY_FROM_JOB, DETACHED):
            try:
                p = subprocess.Popen(args, cwd=APPS, env=env, startupinfo=si, creationflags=flags, close_fds=True)
                return p.pid
            except OSError as e:
                last = e
        raise GameError(f"could not start SC3U.exe: {last}")

    def _main_window(self) -> int:
        for w in _windows_of(self.proc.pid):
            if w["cls"] == "Gonzo":
                return w["hwnd"]
        return 0

    def _error_dialogs(self) -> list[str]:
        return [w["title"] for w in _windows_of(self.proc.pid) if w["cls"] == "#32770" and w["visible"]]

    def attach(self, launch: bool = True, reload_bridge: bool = False, windowed: bool = True,
               timeout: float = 60.0) -> dict:
        with self.lock:
            launched = False
            if self.proc and not self.proc.alive():
                self.proc, self.bridge, self.pending = None, None, None
            if not self.proc:
                pid = self._find()
                if not pid:
                    if not launch:
                        raise GameError("SimCity 3000 is not running")
                    pid = self._launch(windowed)
                    launched = True
                self.proc = win32.Process(pid)
            deadline = time.time() + timeout
            while not self._main_window():
                if not self.proc.alive():
                    raise GameError("SC3U.exe exited during startup")
                errs = self._error_dialogs()
                if errs:
                    raise GameError(f"the game shows an error dialog: {errs}")
                if time.time() > deadline:
                    raise GameError("timed out waiting for the game window")
                time.sleep(0.2)
            try:
                bridge_mod.check_game_identity(self.proc)
            except bridge_mod.BridgeError as e:
                raise GameError(str(e))
            self._mods = {}
            if not self.bridge:
                self.bridge = bridge_mod.Bridge(self.proc)
            try:
                self.bridge.attach(reload=reload_bridge)
            except (bridge_mod.BridgeError, win32.WinError) as e:
                raise GameError(f"bridge attach failed: {e}")
            st = self.status()
            st["launched"] = launched
            return st

    def ensure(self) -> None:
        if not self.proc or not self.proc.alive() or not self.bridge or not self.bridge.block:
            self.attach(launch=False)

    # ------------------------------------------------------------ memory
    def mod(self, name: str) -> int:
        name = name.lower()
        if name not in self._mods:
            self._mods = self.proc.modules32()
        base = self._mods.get(name)
        if not base:
            raise GameError(f"module {name} not loaded")
        return base

    def u32(self, a: int) -> int:
        return self.proc.u32(a)

    def i32(self, a: int) -> int:
        return self.proc.i32(a)

    def i64(self, a: int) -> int:
        return struct.unpack("<q", self.proc.read(a, 8))[0]

    def rz_string(self, a: int, maxlen: int = 256) -> str:
        """A string object: vtable, begin, end, capacity (char*)."""
        begin, end = struct.unpack("<II", self.proc.read(a + 4, 8))
        if not begin or end < begin:
            return ""
        return self.proc.read(begin, min(end - begin, maxlen)).decode("cp1252", "replace")

    def city(self) -> int:
        """Address of the current city object, 0 when no city is loaded."""
        m, rva = CITY_GLOBAL
        return self.u32(self.mod(m) + rva)

    def need_city(self) -> int:
        self.ensure()
        c = self.city()
        if not c:
            raise GameError("no city is loaded (the game is at a menu)")
        return c

    def vfn(self, obj: int, slot: int) -> int:
        """Address of virtual method `slot` of the object at obj."""
        return self.u32(self.u32(obj) + 4 * slot)

    def scratch(self) -> int:
        """A 64 KB read/write buffer inside the game for call arguments (allocated once per process)."""
        if getattr(self, "_scratch_pid", None) != self.proc.pid:
            self._scratch = self.proc.alloc(0x10000)
            self._scratch_pid = self.proc.pid
        return self._scratch

    def call(self, fn: int, args=(), this: int = 0) -> int:
        """Call a game function on the UI thread; returns EAX (unsigned)."""
        self.ensure()
        return self._check(self.bridge.call_function(fn, args, this)).ret[0] & 0xFFFFFFFF

    def call_seq(self, calls) -> tuple:
        self.ensure()
        return self._check(self.bridge.call_sequence(calls)).ret

    # ------------------------------------------------------------ city view (SIMSPR) and camera
    def view(self) -> int:
        """The city view object (SIMSPR vtable 0x10067894): iface = *(SIMSPR 0x10072F24); view = iface->vt[0x74]()."""
        iface = self.u32(self.mod("simspr.dll") + 0x72F24)
        if not iface:
            raise GameError("no city view")
        return self.call(self.vfn(iface, 0x74 // 4), this=iface)

    # ------------------------------------------------------------ GZ messages (re/agents/viewsnap/REPORT.md s. 1)
    def _msg(self, mid: int, p1: int, p2: int, p3: int) -> tuple[int, int]:
        ms = self.call(self._msg_server_getter())
        if not ms:
            raise GameError("no message server")
        buf = self.scratch() + 0x3C0
        self.proc.write(buf, struct.pack("<4I", *(v & 0xFFFFFFFF for v in (mid, p1, p2, p3))))
        return ms, buf

    def _msg_server_getter(self) -> int:
        return self.mod("sc3u.exe") + 0x70247                    # SC3U 0x470247 (cdecl, cached)

    def post_message(self, mid: int, p1: int = 0, p2: int = 0, p3: int = 0) -> None:
        """Post {id, p1, p2, p3} to the game's message server (vt[0x10], queued; delivered on the UI thread),
        as menu PMSG items do."""
        ms, buf = self._msg(mid, p1, p2, p3)
        self.call(self.vfn(ms, 0x10 // 4), [buf, 0], this=ms)

    def send_message(self, mid: int, p1: int = 0, p2: int = 0, p3: int = 0) -> tuple[int, int, int]:
        """Send {id, p1, p2, p3} synchronously (vt[0x0C]); query messages write their answers into p1..p3."""
        ms, buf = self._msg(mid, p1, p2, p3)
        self.call(self.vfn(ms, 0x0C // 4), [buf], this=ms)
        return struct.unpack("<3i", self.proc.read(buf + 4, 12))

    # ------------------------------------------------------------ camera and view layers
    DATA_VIEWS = {"normal": 0, "subways": 1, "pipes": 2, "aura": 0xA, "crime": 0xB, "power": 0xC,
                  "flammability": 0xD, "landvalue": 0xE, "pollution": 0xF, "traffic": 0x10, "density": 0x11}
    VIEW_LAYERS = {"zones": 2, "transport": 4, "power_lines": 8, "trees": 0x10, "zoned_buildings": 0x20,
                   "other_buildings": 0x40}

    def view_state(self) -> dict:
        """Camera centre tile, zoom (0 far .. 4 close), rotation (0..3), data view and shown layers, from memory:
        cam = *(view+0xB8); projection *(cam+0x158) +0x28 zoom / +0x2C rotation; centre cam+0xB0/+0xB4;
        layer manager *(cam+0x154) +0xCC mode / +0xD0 flags."""
        v = self.view()
        cam = self.u32(v + 0xB8)
        P, lm = self.u32(cam + 0x158), self.u32(cam + 0x154)
        mode, flags = self.i32(lm + 0xCC), self.i32(lm + 0xD0)
        return {"center": [self.i32(cam + 0xB0), self.i32(cam + 0xB4)], "zoom": self.i32(P + 0x28),
                "rotation": self.i32(P + 0x2C),
                "data_view": next((n for n, m in self.DATA_VIEWS.items() if m == mode), mode),
                "layers": {n: bool(flags & b) for n, b in self.VIEW_LAYERS.items()}, "grid": bool(flags & 1),
                "_flags": flags}

    def set_view(self, x=None, y=None, zoom=None, rotation=None, data_view=None, layers=None, grid=None) -> dict:
        v = self.view()
        if grid is not None:                   # terrain grid = layer flag bit 0; the game's toggle (G key / Layer
            r = self.u32(v + 0xB8)             # Views button): renderer vt[0x34](1, on, redraw=1) (SIMSPR 0x1001C409)
            self.call(self.vfn(r, 0x34 // 4), [1, 1 if grid else 0, 1], this=r)
        if x is not None and y is not None:
            self.call(self.vfn(v, 0x20 // 4), [int(x), int(y), 1], this=v)
        if zoom is not None or rotation is not None:
            cur = self.view_state()
            z = cur["zoom"] if zoom is None else max(0, min(4, int(zoom)))
            r = -1 if rotation is None else int(rotation) % 4          # -1 keeps the rotation (0 would reset it)
            self.call(self.vfn(v, 0xB0 // 4), [z, r, 1], this=v)
        if data_view is not None or layers:
            cur = self.view_state()
            if data_view is not None and data_view not in self.DATA_VIEWS:
                raise GameError(f"data_view must be one of {list(self.DATA_VIEWS)}")
            mode = self.DATA_VIEWS[data_view if data_view is not None else "normal"] if data_view is not None \
                else next((m for n, m in self.DATA_VIEWS.items() if n == cur["data_view"]), 0)
            flags = cur["_flags"]
            for n, on in (layers or {}).items():
                if n not in self.VIEW_LAYERS:
                    raise GameError(f"layers: any of {list(self.VIEW_LAYERS)}")
                flags = flags | self.VIEW_LAYERS[n] if on else flags & ~self.VIEW_LAYERS[n]
            self.call(self.vfn(v, 0xB4 // 4), [mode, flags, 1], this=v)   # SIMSPR 0x10043662 (Layer Views apply)
        out = self.view_state()
        out.pop("_flags")
        return out

    def pick(self, sx: int, sy: int) -> tuple[int, int, int] | None:
        """World point (256 units per tile) under client pixel (sx, sy), or None if off the map."""
        v = self.view()
        cam = self.u32(v + 0xB8)
        out = self.scratch() + 0x100
        self.proc.write(out, b"\0" * 12)
        ok = self.call(self.vfn(cam, 0x8C // 4), [sx, sy, out, 0], this=cam) & 0xFF
        if not ok:
            return None
        return struct.unpack("<3i", self.proc.read(out, 12))

    # ------------------------------------------------------------ tools
    def select_tool(self, cmd_id: int, params=()) -> int:
        """Run a menu/tool command (MenuItem.INI id) and return the tool it installed in the city view.
        The current tool is dropped first (as Esc does), so a command that installs nothing is detected."""
        v = self.view()
        self.call(self.vfn(v, 0x58 // 4), [0], this=v)
        r = self._check(self.bridge.command(cmd_id, params))
        if not r.ret[0]:
            raise GameError(f"command {cmd_id:#010x} was refused by the game")
        tool = self.u32(v + 0x228)
        if not tool:
            raise GameError(f"command {cmd_id:#010x} did not install a city tool (not available now?)")
        return tool

    def apply_tool(self, cmd_id: int, tiles, click_each: bool = False, params=()) -> dict:
        """Select a tool and drive its own mouse handlers through tile coordinates (camera picking is overridden
        inside the game for those points), so costs and rules are the game's. tiles: [(x, y), ...]."""
        with self.lock:
            c = self.need_city()
            v = self.view()
            cam = self.u32(v + 0xB8)
            tool = self.select_tool(cmd_id, params)
            if not tool:
                raise GameError("the command did not install a city tool")
            pts = [(int(x) * 256, int(y) * 256, 0) for x, y in tiles]
            return self.run_tool(tool, cam, pts, click_each)

    def modal_depth(self) -> int:
        return self.i32(self.u32(0x4FAC90) + 0x194)

    def run_tool(self, tool: int, cam: int, pts, click_each: bool, what: str = "build") -> dict:
        """Drive a tool through world points from the game's message loop, so a question the game asks on the
        way (e.g. "connect to your neighbor for $2,000?") does not block. Returns {"cost", "funds"}, or
        {"pending": what} when a dialog is waiting for an answer (see finish_pending)."""
        if self.pending and "pending" in self.finish_pending(timeout=0.3):   # (answered some other way?)
            raise GameError("a game dialog from an earlier action is waiting for an answer (close_dialog)")
        if self.bridge.deferred_state()["running"]:
            raise GameError("a deferred game action is still running (is a game dialog open?)")
        c = self.need_city()
        budget = self.u32(c + CITY_BUDGET)
        self.pending = {"what": what, "funds0": self.i64(budget + BUDGET_FUNDS), "depth0": self.modal_depth()}
        self._check(self.bridge.tool_points(tool, cam, pts, click_each, defer=True))
        return self.finish_pending()

    def finish_pending(self, timeout: float = 30.0) -> dict:
        """Wait for the pending tool operation: its cost once done, or {"pending": ...} while a dialog is open."""
        p = self.pending
        if not p:
            return {}
        deadline = time.time() + timeout
        while True:
            st = self.bridge.deferred_state()
            if not st["running"]:
                self.pending = None
                f1 = self.i64(self.u32(self.need_city() + CITY_BUDGET) + BUDGET_FUNDS)
                if st["status"] == -100:
                    raise GameError("the game raised an exception inside the tool (game state unchanged)")
                return {"cost": p["funds0"] - f1, "funds": f1}
            if self.modal_depth() > p["depth0"]:
                return {"pending": p["what"]}
            if time.time() > deadline:
                return {"pending": p["what"], "note": "still running"}
            time.sleep(0.02)

    def select_building(self, occupant_id: int) -> int:
        """Install the game's ploppable-building tool for any building occupant id (as the building pickers
        do): SIMGEOM operator new(0x120), ctor 0x10009443(&key{0x207EDC0E, 0x57E, id}, 0, 0), then execute
        its command interface (+0x58). Returns the installed tool."""
        sg = self.mod("simgeom.dll")
        key = self.scratch() + 0x400
        self.proc.write(key, struct.pack("<3I", 0x207EDC0E, 0x57E, occupant_id))
        obj = self.call(sg + 0x262A6, [0x120])
        if not obj:
            raise GameError("allocation failed")
        self.call(sg + 0x9443, [key, 0, 0], this=obj)
        cmd = obj + 0x58
        # the factory hands the command out through QueryInterface, which takes a reference; without it the
        # final Release frees the tool while the city view still uses it (crashed the game on the next frame)
        self.call_seq([
            (self.vfn(cmd, 1), cmd, []),     # AddRef (as QueryInterface would)
            (self.vfn(cmd, 11), cmd, []),    # Execute: installs the tool in the city view (view takes a ref)
            (self.vfn(cmd, 2), cmd, []),     # Release our reference
        ])
        ok = 1
        tool = self.u32(self.view() + 0x228)
        if not ok or not tool or self.u32(tool + 0x110) != occupant_id:
            raise GameError(f"could not select building {occupant_id:#x}")
        return tool

    def place_building(self, occupant_id: int, x: int, y: int) -> dict:
        """Place one building with its top-left tile at (x, y) using the game's own tool (cost and rules apply)."""
        with self.lock:
            c = self.need_city()
            tool = self.select_building(occupant_id)
            cam = self.u32(self.view() + 0xB8)
            return self.run_tool(tool, cam, [(x * 256, y * 256, 0)], True, "place_building")

    # ------------------------------------------------------------ time
    def _clock_granularity(self, clk: int) -> str:
        """What the clock's own timer would step by: minute/hour if anyone listens to those, else day."""
        for kind, off in (("minute", 4), ("hour", 8)):
            head = self.u32(clk + off)
            if self.u32(head) != head:
                return kind
        return "day"

    def _engine_queue_empty(self, c: int) -> bool:
        q = self.u32(self.u32(c + CITY_ENGINE) + 0x14)
        head = self.u32(q + 4)
        return self.u32(head) == head

    def _post_engine_noop(self, c: int) -> None:
        q = self.u32(self.u32(c + CITY_ENGINE) + 0x14)
        msg = self.scratch()
        self.proc.write(msg, struct.pack("<4I", ENGINE_NOOP_MSG, 0, 0, 0))
        self.call(self.vfn(q, 3), [msg], this=q)   # queue->vt[0xC](msg*): post

    def advance_days(self, days: int | None = None, chunk: int = 1, timeout_per_day: float = 20.0,
                     until: int | None = None) -> dict:
        """Run the simulation exactly `days` days (or until JDN `until`), as fast as the engine can, then leave
        it paused as before.

        The clock gets an extra pause so real time adds nothing; the engine thread is unpaused; the clock's
        own Advance{Day,Hour,Minute} (whichever its timer would use) queues the day/week/month/year messages;
        a no-op sentinel message proves the engine finished them all. Days still queued from an interrupted
        call run first and count toward the target; the 1st of each month (when the game opens its monthly /
        year-end windows) is stepped alone so a window there leaves nothing queued behind it."""
        with self.lock:
            c = self.need_city()
            if self.i32(c + CITY_SYS_PAUSE) > 0:
                raise GameError("a game window is holding the simulation (system pause); close it first")
            clk = self.u32(c + CITY_CLOCK)
            pause, resume = self.vfn(c, SLOT_PAUSE), self.vfn(c, SLOT_RESUME)
            cpause, cresume = self.vfn(clk, CLOCK_SLOT_PAUSE), self.vfn(clk, CLOCK_SLOT_RESUME)
            was_running = self.i32(c + CITY_PAUSE_COUNT) == 0
            start = self.i32(c + CITY_DATE + 4)
            target = until if until is not None else start + (days or 0)
            simcity = self.mod("simcity.dll")
            seq = ([(pause, c, [])] if was_running else []) + [(cpause, clk, []), (resume, c, [])]
            self.call_seq(seq)
            t0 = time.time()
            stopped = None

            def wait(goal, k):
                """Wait for the engine to drain its queue and reach JDN `goal`; returns a stop reason or None."""
                deadline = time.time() + timeout_per_day * max(1, k)
                idle_since = None
                while not (self._engine_queue_empty(c) and self.i32(c + CITY_DATE + 4) >= goal):
                    if self.i32(c + CITY_SYS_PAUSE) > 0:
                        return "a game dialog opened (see dialog_status)"
                    if self._engine_queue_empty(c):
                        idle_since = idle_since or time.time()
                        if time.time() - idle_since > 3.0:   # queue drained but the date did not move
                            return "the calendar is frozen (a disaster is in progress?)"
                    else:
                        idle_since = None
                    if time.time() > deadline:
                        raise GameError(f"simulation engine did not reach {jdn_to_date(goal)} in time")
                    time.sleep(0.002)
                return None
            try:
                self._post_engine_noop(c)                 # drain days left queued by an interrupted call
                stopped = wait(start, 0)
                while not stopped:
                    now = self.i32(c + CITY_DATE + 4)
                    if now >= target:
                        break
                    nxt = jdn_to_date(now + 1)
                    if nxt.day == 1:
                        k = 1                                 # the 1st of a month alone
                    else:
                        month_end = (datetime.date(nxt.year + (nxt.month == 12), nxt.month % 12 + 1, 1)
                                     - nxt).days              # days up to the month's last day
                        k = max(1, min(chunk, target - now, month_end))
                    gran = self._clock_granularity(clk)
                    if gran != "day":
                        k = 1
                    reps = k * {"day": 1, "hour": 24, "minute": 1440}[gran]
                    self._check(self.bridge.repeat(simcity + CLOCK_ADVANCE[gran], reps, this=clk))
                    self._post_engine_noop(c)
                    stopped = wait(now + k, k)
            finally:
                seq = [(pause, c, []), (cresume, clk, [])] + ([(resume, c, [])] if was_running else [])
                self.call_seq(seq)
            end = self.i32(c + CITY_DATE + 4)
            out = {"days": end - start, "from": jdn_to_date(start).isoformat(), "to": jdn_to_date(end).isoformat(),
                   "seconds": round(time.time() - t0, 3), "paused": not was_running}
            if end < target:
                out["stopped_early"] = ("a game dialog is open" if self.i32(c + CITY_SYS_PAUSE) > 0
                                        else "the calendar did not advance (disaster in progress?); use run_realtime "
                                             "to let it play out")
            return out

    # ------------------------------------------------------------ reproducible randomness (research mode)
    def set_random_seed(self, seed: int | None) -> dict:
        """Make the game's randomness reproducible (None turns it off). The bridge feeds a seeded sequence to
        the generators created from now on (Seed(-1) normally reads the clock) and to the simulators' rand();
        the global generators created at game start (re/agents/rng/global_rngs.json) are reset here too."""
        if seed is None:
            return self.bridge.rng(0)
        st = self.bridge.rng(1, seed)
        import json
        data = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "global_rngs.json")))
        mods = {k.lower(): v for k, v in self.proc.modules32().items()}
        x, n = (seed * 2654435761 + 1) & 0xFFFFFFFF, 0
        for m, items in sorted(data.items()):
            base = mods.get(m.lower())
            if not base:
                continue
            for kind, rva in items:
                a = self.u32(base + rva) if kind == "ptr" else base + rva
                if not a:
                    continue
                state, sd, z = struct.unpack("<III", self.proc.read(a, 12))
                if sd == 0 or z != 0:                 # not a generator {state, seed, 0}
                    continue
                x = (x * 1103515245 + 12345) & 0xFFFFFFFF
                self.proc.write(a, struct.pack("<II", x, x))
                n += 1
        return {**st, "global_generators_reset": n}

    def set_paused(self, paused: bool) -> None:
        c = self.need_city()
        n = self.i32(c + CITY_PAUSE_COUNT)
        if paused and n == 0:
            self.call(self.vfn(c, SLOT_PAUSE), this=c)
        elif not paused:
            for _ in range(n):
                self.call(self.vfn(c, SLOT_RESUME), this=c)

    def set_speed(self, speed: int) -> None:
        c = self.need_city()
        self.call(self.vfn(c, SLOT_SET_SPEED), [max(0, min(4, speed))], this=c)

    # ------------------------------------------------------------ observation
    def city_basics(self, c: int) -> dict:
        jdn, founded, pauses, sys_pauses = struct.unpack("<iiii", self.proc.read(c + CITY_DATE + 4, 16))
        d = jdn_to_date(jdn)
        w, h = struct.unpack("<ii", self.proc.read(c + CITY_SIZE, 8))
        budget = self.u32(c + CITY_BUDGET)
        return {
            "name": self.rz_string(c + CITY_NAME),
            "mayor": self.rz_string(c + CITY_MAYOR),
            "date": d.isoformat(),
            "julian_day": jdn,
            "founded": founded,
            "map_size": [w, h],
            "funds": self.i64(budget + BUDGET_FUNDS) if budget else None,
            "paused": pauses > 0,
            "speed": self.i32(c + CITY_SPEED),
            "game_window_open": sys_pauses > 0,
        }

    def status(self) -> dict:
        with self.lock:
            if not self.proc or not self.proc.alive():
                return {"running": False}
            out = {"running": True, "pid": self.proc.pid, "bridge": bool(self.bridge and self.bridge.block)}
            c = self.city()
            out["screen"] = "city" if c else "menu"
            if c:
                out["city"] = self.city_basics(c)
            dialogs = self._error_dialogs()
            if dialogs:
                out["system_dialogs"] = dialogs
            return out

    # ------------------------------------------------------------ screen + UI input
    def _presentation_window(self) -> int:
        ws = _windows_of(self.proc.pid)
        pres = [w["hwnd"] for w in ws if w["title"].startswith("[DDrawCompat]") and w["visible"]]
        return pres[0] if pres else self._main_window()

    def capture(self):
        """The game's client area as a PIL image (pixel coords == ui_click coords)."""
        self.ensure()
        main, pres = self._main_window(), self._presentation_window()
        img = win32.capture_window(pres)
        pr, cr, pt = wt.RECT(), wt.RECT(), wt.POINT(0, 0)
        win32.u32.GetWindowRect(pres, ctypes.byref(pr))
        win32.u32.GetClientRect(main, ctypes.byref(cr))
        win32.u32.ClientToScreen(main, ctypes.byref(pt))
        ox, oy = pt.x - pr.left, pt.y - pr.top
        img = img.crop((ox, oy, ox + cr.right, oy + cr.bottom))
        if img.getextrema() == ((0, 0), (0, 0), (0, 0)):
            raise GameError("the game window is not presenting (all black): this happens after the monitor slept "
                            "or when the game started with the display off. The game itself is running; click the "
                            "game window once to make it render again.")
        return img

    def _check(self, r: bridge_mod.BridgeResult) -> bridge_mod.BridgeResult:
        if not r.ok:
            raise GameError(f"bridge status {r.status}: {'; '.join(r.messages)}")
        return r

    def click(self, x: int, y: int, button: str = "left", wait_ms: int = 300) -> None:
        self.ensure()
        self._check(self.bridge.mouse("click" if button == "left" else "right_click", x, y))
        time.sleep(wait_ms / 1000)

    def drag(self, x1: int, y1: int, x2: int, y2: int, wait_ms: int = 300) -> None:
        self.ensure()
        self._check(self.bridge.mouse("drag", x1, y1, x2, y2))
        time.sleep(wait_ms / 1000)

    def move(self, x: int, y: int) -> None:
        self.ensure()
        self._check(self.bridge.mouse("move", x, y))

    def key(self, key: str, shift: bool = False, ctrl: bool = False, alt: bool = False, wait_ms: int = 200) -> None:
        self.ensure()
        k = key.lower()
        if k in VK:
            vk, ch = VK[k], {"enter": "\r", "return": "\r", "space": " ", "tab": "\t", "backspace": "\b",
                             "esc": "\x1b", "escape": "\x1b"}.get(k)
        elif len(key) == 1:
            vk, ch = (ord(key.upper()) if key.isalnum() else 0), key
        else:
            raise GameError(f"unknown key {key!r}")
        self._check(self.bridge.key(vk, "press", shift, ctrl, alt, ch))
        time.sleep(wait_ms / 1000)

    def type_text(self, text: str) -> None:
        self.ensure()
        self.bridge.type_text(text)
