"""Client for the in-game sc3kbridge.dll command block (and the sc3kplug.dll GZCOM plugin block)."""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile
import threading
import time

from . import win32

BRIDGE_MAGIC = 0x42334353  # 'SC3B'
PLUG_MAGIC = 0x50334353    # 'SC3P'
WM_SC3KBRIDGE = 0x8000 + 0x3C3

OP_PING, OP_UNLOAD, OP_CALL, OP_CALL_SEQ = 1, 5, 7, 12
OP_MOUSE, OP_KEY, OP_TRACE, OP_WATCH, OP_REPEAT, OP_COMMAND, OP_DEFER, OP_TOOL_POINTS, OP_OCC_SCAN = 20, 21, 22, 23, 24, 25, 26, 27, 28
OP_RNG = 29
TRACE_SLOTS, TRACE_REC = 4096, 40
WATCH_HITS, WATCH_REC = 128, 36
MOUSE_ACTIONS = {"move": 0, "click": 1, "right_click": 2, "down": 3, "up": 4, "drag": 5, "wheel": 6, "release": 7}
KEY_ACTIONS = {"press": 0, "down": 1, "up": 2}

SC3U_BASE = 0x400000
SC3U_TIMESTAMP = 0x63732172

# BridgeBlock layout (see bridge/sc3kbridge.cpp); verified against the DLL's layout[] on attach
O_MAGIC, O_VERSION, O_READY, O_HWND_BRIDGE, O_HWND_MAIN, O_TID, O_HOOKS, O_LAYOUT = 0, 4, 8, 12, 16, 20, 24, 28
O_SEQ, O_OP, O_ARGS, O_STR = 60, 64, 68, 132
O_DONESEQ, O_STATUS, O_RET, O_MSGLEN, O_MSG = 652, 656, 660, 724, 728
O_STATE, O_EVENTS = 2776, 2840
STR_MAX, MSG_MAX = 520, 2048
EVENT_SIZE, EVENT_SLOTS = 256, 64
CALLDESC_SIZE = 36

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the bridge DLL built by bridge/build.bat; SC3K_BRIDGE_DLL points elsewhere (e.g. a downloaded build)
DEFAULT_DLL = os.environ.get("SC3K_BRIDGE_DLL") or os.path.join(PACKAGE_DIR, "bridge", "build", "sc3kbridge.dll")
# the game's install folder (GOG default); set SC3K_GAME_DIR for another location
GAME_DIR = os.environ.get("SC3K_GAME_DIR") or r"C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited"
GAME_APPS = os.path.join(GAME_DIR, "Apps")
PLUGIN_DLL = os.path.join(GAME_APPS, "PlugIn", "sc3kplug.dll")
STAGE_DIR = os.path.join(tempfile.gettempdir(), "sc3k-mcp")


class BridgeError(RuntimeError):
    pass


class BridgeResult:
    def __init__(self, status: int, ret: tuple[int, ...], msg: str):
        self.status = status
        self.ret = ret
        self.messages = [m for m in msg.splitlines() if m]

    @property
    def ok(self) -> bool:
        return self.status == 0

    def __repr__(self):
        return f"BridgeResult(status={self.status}, ret={self.ret[:6]}, messages={self.messages})"


def _staged_copy(dll_path: str) -> str:
    """Copy the DLL to a content-addressed temp name so rebuilds never hit a locked file."""
    if not os.path.exists(dll_path):
        raise BridgeError(f"the bridge DLL is missing ({dll_path}): build it with bridge/build.bat (Visual Studio or "
                          f"its Build Tools with C++), or download the bridge-dlls build and set SC3K_BRIDGE_DLL")
    data = open(dll_path, "rb").read()
    digest = hashlib.sha1(data).hexdigest()[:10]
    os.makedirs(STAGE_DIR, exist_ok=True)
    out = os.path.join(STAGE_DIR, f"sc3kbridge-{digest}.dll")
    if not os.path.exists(out):
        shutil.copyfile(dll_path, out)
    return out


KNOWN_EXES = ("sc3u.exe", "baapp.exe")      # the game and its Building Architect (same GOG build stamp)


def check_game_identity(proc: win32.Process) -> None:
    """Refuse anything but the pinned stock GOG SC3U.exe or Baapp.exe (checked in memory, like the DLL does)."""
    mods = proc.modules32()
    exe = next((e for e in KNOWN_EXES if mods.get(e) == SC3U_BASE), None)
    if not exe:
        raise BridgeError("neither SC3U.exe nor Baapp.exe is loaded at 0x400000")
    e_lfanew = proc.u32(SC3U_BASE + 0x3C)
    stamp = proc.u32(SC3U_BASE + e_lfanew + 8)
    if stamp != SC3U_TIMESTAMP:
        raise BridgeError(f"unsupported {exe} build (TimeDateStamp {stamp:#x}, expected {SC3U_TIMESTAMP:#x})")


class Bridge:
    def __init__(self, proc: win32.Process, dll_path: str = DEFAULT_DLL):
        self.proc = proc
        self.dll_path = dll_path
        self.lock = threading.RLock()
        self.block = 0
        self.hwnd = 0        # the bridge's message-only command window
        self.hwnd_main = 0   # the game's Gonzo window
        self.module_name = ""

    # -- attach / inject -------------------------------------------------
    def _loaded_bridges(self) -> dict[str, int]:
        return {n: b for n, b in self.proc.modules32().items() if n.startswith("sc3kbridge")}

    def attach(self, reload: bool = False, timeout: float = 30.0) -> None:
        with self.lock:
            check_game_identity(self.proc)
            staged = _staged_copy(self.dll_path)
            want = os.path.basename(staged).lower()
            self.busy_old = []
            for name, base in self._loaded_bridges().items():
                if reload or name != want:
                    if not self._unload(name, base):
                        self.busy_old.append(name)      # still inside a game dialog: unloaded on a later attach
            loaded = self._loaded_bridges()
            if reload and want in self.busy_old:
                raise BridgeError("the bridge is busy inside a game dialog; answer the dialog first")
            base = loaded[want] if want in loaded else win32.inject_dll(self.proc, staged)
            self.block = base + win32.pe_exports(staged)["g_bridge"]
            self.module_name = want
            deadline = time.time() + timeout
            while True:
                magic, _ver, ready, hwnd, hwnd_main = struct.unpack("<5I", self.proc.read(self.block, 20))
                if magic != BRIDGE_MAGIC:
                    raise BridgeError("bridge block magic mismatch")
                if ready == 1:
                    break
                if ready >= 0xBAD:
                    raise BridgeError(f"bridge failed to initialise (code {ready:#x})")
                if time.time() > deadline:
                    raise BridgeError("timed out waiting for the bridge to initialise")
                time.sleep(0.05)
            layout = struct.unpack("<8I", self.proc.read(self.block + O_LAYOUT, 32))
            if (layout[0], layout[1], layout[3]) != (O_EVENTS, O_STATE, O_SEQ):
                raise BridgeError(f"bridge block layout mismatch {layout[:4]}; rebuild the client constants")
            self.hwnd, self.hwnd_main = hwnd, hwnd_main

    def _unload(self, name: str, base: int) -> bool:
        """Unload a bridge module. False when it is busy (its call is waiting inside a game dialog) and was left
        loaded; its hooks only restore IAT slots that still point at them, so a newer bridge can hook over it."""
        # the loaded module may be an older build: take the export from its own staged file
        staged = os.path.join(STAGE_DIR, name)
        rva = win32.pe_exports(staged if os.path.exists(staged) else self.dll_path)["g_bridge"]
        block = base + rva
        try:
            magic, _v, ready, hwnd = struct.unpack("<IIII", self.proc.read(block, 16))
            if magic == BRIDGE_MAGIC and ready == 1 and win32.u32.IsWindow(hwnd):
                if win32.send_message(hwnd, WM_SC3KBRIDGE, OP_UNLOAD, 0, 5000) == -99:
                    return False
        except win32.WinError:
            return False
        deadline = time.time() + 5
        while name in self._loaded_bridges() and time.time() < deadline:
            time.sleep(0.05)
        if name in self._loaded_bridges():
            raise BridgeError(f"old bridge {name} did not unload")
        return True

    def detach(self) -> None:
        """Unload every bridge DLL from the game (hooks removed, command window destroyed)."""
        with self.lock:
            for name, base in self._loaded_bridges().items():
                self._unload(name, base)
            self.block = self.hwnd = 0

    # -- calls -----------------------------------------------------------
    def call(self, op: int, args=(), text: str | None = None, raw: bytes | None = None,
             timeout_ms: int = 20000) -> BridgeResult:
        if not self.block:
            raise BridgeError("bridge not attached")
        with self.lock:
            a = list(args)[:16] + [0] * (16 - min(len(args), 16))
            seq = self.proc.u32(self.block + O_SEQ) + 1
            self.proc.write(self.block + O_ARGS, struct.pack("<16I", *[int(v) & 0xFFFFFFFF for v in a]))
            if text is not None:
                raw = text.encode("mbcs")[: STR_MAX - 1] + b"\0"
            if raw is not None:
                self.proc.write(self.block + O_STR, raw[:STR_MAX])
            self.proc.write(self.block + O_SEQ, struct.pack("<II", seq, op))
            win32.send_message(self.hwnd, WM_SC3KBRIDGE, op, 0, timeout_ms)
            hdr = self.proc.read(self.block + O_DONESEQ, O_MSG - O_DONESEQ)
            done, status = struct.unpack_from("<Ii", hdr, 0)
            ret = struct.unpack_from("<16i", hdr, O_RET - O_DONESEQ)
            msglen = struct.unpack_from("<I", hdr, O_MSGLEN - O_DONESEQ)[0]
            msg = self.proc.read(self.block + O_MSG, min(msglen, MSG_MAX)).decode("mbcs", "replace") if msglen else ""
            if done != seq:
                raise BridgeError(f"bridge did not process the command (status {status})")
            return BridgeResult(status, ret, msg)

    def ping(self) -> BridgeResult:
        """ret: [0] version, [1] executing thread id (must be the UI thread), [2] hooks installed, [3] module base."""
        return self.call(OP_PING)

    def call_function(self, addr: int, args=(), this: int = 0) -> BridgeResult:
        """Call a game function on the UI thread (cdecl/stdcall, or thiscall when `this` is given)."""
        args = list(args)[:8]
        return self.call(OP_CALL, [addr, 1 if this else 0, len(args), this] + args + [0] * (8 - len(args)) + [0])

    def call_sequence(self, calls) -> BridgeResult:
        """Run several game functions back-to-back in one UI-thread turn.
        calls: [(fn, this_or_0, [args...], {opts}), ...] (max 14 calls, 6 args each). ret[i] = result of call i.
        opts: deref_args=[j...] (pass the dword stored at args[j] instead), deref_this=True (this = dword at
        `this`), vslot=True (fn is a vtable slot index of this)."""
        calls = list(calls)
        if len(calls) > STR_MAX // CALLDESC_SIZE:
            raise BridgeError(f"at most {STR_MAX // CALLDESC_SIZE} calls per sequence")
        raw = b""
        for call in calls:
            fn, this, args = call[:3]
            opts = call[3] if len(call) > 3 else {}
            args = list(args)[:6]
            flags = len(args)
            for j in opts.get("deref_args", ()):      # arg j is an address; the dword there is passed
                flags |= 1 << (8 + j)
            if opts.get("deref_this"):                # this is an address; the dword there is `this`
                flags |= 1 << 14
            if opts.get("vslot"):                     # fn is a vtable slot index of `this`
                flags |= 1 << 15
            raw += struct.pack("<IIi6I", fn, this or 0, flags, *[int(v) & 0xFFFFFFFF for v in args + [0] * (6 - len(args))])
        return self.call(OP_CALL_SEQ, (len(calls), 0), raw=raw)

    def command(self, cmd_id: int, params=(), defer: bool = False) -> BridgeResult:
        """Run a game command (menu item / tool id from MenuItem.INI) through the game's command server.
        ret[0] = the command's Execute result. defer=True posts it to run from the message loop (use for
        commands that open modal windows); poll deferred_state() for completion."""
        p = [int(v) & 0xFFFFFFFF for v in list(params)[:3]]
        return self.call(OP_COMMAND, [cmd_id, len(p)] + p + [0] * (3 - len(p)) + [1 if defer else 0])

    def tool_points(self, tool: int, camera: int, points, click_each: bool = False, keys: int = 0,
                    defer: bool = False) -> BridgeResult:
        """Drive a city tool's own mouse handlers through world points [(x, y, z), ...] (256 units per tile):
        press at the first, move through the rest, release at the last (or click each point).
        defer=True runs it from the message loop (a dialog the tool opens then doesn't block the bridge);
        poll deferred_state()."""
        pts = list(points)[:16]
        raw = b"".join(struct.pack("<3i", *p) for p in pts)
        return self.call(OP_TOOL_POINTS, (tool, camera, len(pts), 1 if click_each else 0, keys, 1 if defer else 0),
                         raw=raw)

    def occ_scan(self, manager: int, out_buf: int, max_records: int, rect=(-1, -1, -1, -1)) -> tuple[int, bool]:
        """Scan an occupant manager's grid inside the game; records {ptr, category, x0, y0, x1, y1, occupant id, state} (8 dwords)
        are written to out_buf (game memory). Returns (count, truncated)."""
        r = self.call(OP_OCC_SCAN, (manager, out_buf, max_records) + tuple(rect), timeout_ms=60000)
        if not r.ok:
            raise BridgeError(f"occupant scan failed (status {r.status})")
        return r.ret[0], r.ret[1] == 1

    def rng(self, action: int, seed: int = 0) -> dict:
        """Deterministic randomness: action 1 = enable with seed, 0 = disable, 2 = status, 3 = trace every
        generator draw (hooks Next() in all modules), 4 = stop tracing."""
        r = self.call(OP_RNG, (action, seed & 0xFFFFFFFF))
        if not r.ok:
            raise BridgeError(f"rng op failed (status {r.status})")
        return {"seeds_drawn": r.ret[0], "rands_drawn": r.ret[1], "seeders_patched": r.ret[2], "enabled": bool(r.ret[3]),
                "trace": r.ret[4] & 0xFFFFFFFF, "next_hooks": r.ret[5], "next_trace": r.ret[6] & 0xFFFFFFFF,
                "load_rands": r.ret[7]}

    def defer_call(self, addr: int, args=(), this: int = 0) -> BridgeResult:
        args = list(args)[:8]
        return self.call(OP_DEFER, [addr, 1 if this else 0, len(args), this] + args + [0] * (8 - len(args)))

    def deferred_state(self) -> dict:
        posted, done, status, ret = struct.unpack("<IIii", self.proc.read(self.block + O_STATE + 0x10, 16))
        return {"posted": posted, "done": done, "running": posted != done, "status": status, "ret": ret}

    def repeat(self, fn: int, count: int, this: int = 0, args=(), timeout_ms: int = 120000) -> BridgeResult:
        """Call fn (thiscall when this is given) count times in one UI-thread turn (max 4 args)."""
        args = list(args)[:4]
        return self.call(OP_REPEAT, [fn, this, count, len(args)] + args, timeout_ms=timeout_ms)

    def mouse(self, action: str, x: int, y: int, x2: int = 0, y2: int = 0, hold_ms: int = 600) -> BridgeResult:
        """Synthetic mouse input at game-window client coords. The game's GetCursorPos/GetAsyncKeyState
        report the fake cursor/buttons for hold_ms afterwards (the real mouse is never moved).
        drag: from (x, y) to (x2, y2); wheel: x2 = delta (120 per notch)."""
        return self.call(OP_MOUSE, (MOUSE_ACTIONS[action], x, y, hold_ms, x2, y2))

    def key(self, vk: int, action: str = "press", shift: bool = False, ctrl: bool = False, alt: bool = False,
            char: str | None = None) -> BridgeResult:
        mods = (1 if shift else 0) | (2 if ctrl else 0) | (4 if alt else 0)
        return self.call(OP_KEY, (vk, KEY_ACTIONS[action], mods, ord(char) if char else 0))

    # -- call tracing (dynamic RE) --------------------------------------
    def trace_object(self, obj: int, nslots: int, tag: int = 1) -> BridgeResult:
        """Log every virtual call made on this one object (its vtable pointer is swapped)."""
        return self.call(OP_TRACE, (1, obj, nslots, tag))

    def trace_class(self, vtable: int, nslots: int, tag: int = 1) -> BridgeResult:
        """Log every virtual call through this vtable (all objects of the class)."""
        return self.call(OP_TRACE, (2, vtable, nslots, tag))

    def trace_stop(self) -> BridgeResult:
        return self.call(OP_TRACE, (3,))

    def _trace_block(self) -> int:
        staged = os.path.join(STAGE_DIR, self.module_name)
        base = self.proc.modules32()[self.module_name]
        return base + win32.pe_exports(staged)["g_trace"]

    def trace_read(self, since: int = 0) -> list[dict]:
        blk = self._trace_block()
        seq = self.proc.u32(blk + 4)
        first = max(since + 1, seq - TRACE_SLOTS + 1, 1)
        raw = self.proc.read(blk + 16, TRACE_REC * TRACE_SLOTS)
        out = []
        for s in range(first, seq + 1):
            off = ((s - 1) % TRACE_SLOTS) * TRACE_REC
            rs, tick, tag_slot, this, ret, a0, a1, a2, a3, tid = struct.unpack_from("<10I", raw, off)
            if rs != s:
                continue
            out.append({"seq": s, "tick": tick, "tag": tag_slot >> 16, "slot": tag_slot & 0xFFFF, "this": this,
                        "ret": ret, "args": [a0, a1, a2, a3], "tid": tid})
        return out

    # -- hardware watchpoints (dynamic RE) --------------------------------
    def watch(self, addr: int, length: int = 4, rw: str = "w", slot: int = 0) -> BridgeResult:
        """Count the instructions that write (rw="w") or read/write (rw="rw") [addr, addr+length)."""
        return self.call(OP_WATCH, (1, addr, length, 1 if rw == "w" else 3, slot))

    def watch_clear(self) -> BridgeResult:
        return self.call(OP_WATCH, (2,))

    def watch_hits(self) -> dict:
        staged = os.path.join(STAGE_DIR, self.module_name)
        blk = self.proc.modules32()[self.module_name] + win32.pe_exports(staged)["g_watch"]
        hdr = self.proc.read(blk, 28)
        _magic, total, a0, a1, a2, a3, n = struct.unpack("<7I", hdr)
        raw = self.proc.read(blk + 28, WATCH_REC * min(n, WATCH_HITS))
        hits = []
        for i in range(min(n, WATCH_HITS)):
            eip, count, slot, ret, value, tid, f1, f2, f3 = struct.unpack_from("<9I", raw, i * WATCH_REC)
            hits.append({"eip": eip, "count": count, "slot": slot, "ret": ret, "value": value, "tid": tid,
                         "callers": [f for f in (f1, f2, f3) if f]})
        return {"total": total, "addr": [a0, a1, a2, a3], "hits": hits}

    def type_text(self, text: str) -> None:
        for ch in text:
            vk = ord(ch.upper()) if ch.isalnum() else 0
            self.call(OP_KEY, (vk, 0, 0, ord(ch)))


def plugin_info(proc: win32.Process) -> dict | None:
    """Read the sc3kplug.dll GZCOM plugin block (None if the plugin isn't loaded)."""
    base = proc.modules32().get("sc3kplug.dll")
    if not base or not os.path.exists(PLUGIN_DLL):
        return None
    blk = base + win32.pe_exports(PLUGIN_DLL)["g_plug"]
    magic, ver, pcom, pfw, director = struct.unpack("<5I", proc.read(blk, 20))
    if magic != PLUG_MAGIC:
        return None
    calls = struct.unpack("<32I", proc.read(blk + 20, 128))
    return {"version": ver, "com": pcom, "framework": pfw, "director": director,
            "calls": {i: c for i, c in enumerate(calls) if c}}
