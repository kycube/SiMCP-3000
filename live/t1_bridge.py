"""LIVE t1: bridge skeleton end-to-end against the running SC3U.exe.

Checks: identity, plugin block, injection, ready, OP_PING on the UI thread, OP_CALL of a game getter
(GZCOM() must equal the cIGZCOM* the plugin received), OP_CALL_SEQ, a deliberate crash caught by SEH,
then hot reload (unload + re-inject) and a final ping.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import bridge, win32  # noqa: E402

FN_GZCOM = 0x4708C4        # cdecl GZCOM() -> cIGZCOM*
FN_DIRS = 0x470463         # cdecl -> directory manager


def main():
    pids = win32.find_pids("SC3U.exe")
    assert pids, "SC3U.exe not running"
    p = win32.Process(pids[0])
    bridge.check_game_identity(p)
    print("identity ok")
    plug = bridge.plugin_info(p)
    print("plugin:", {k: (hex(v) if isinstance(v, int) else v) for k, v in plug.items()} if plug else None)

    b = bridge.Bridge(p)
    t0 = time.time()
    b.attach()
    print(f"attached {b.module_name} in {time.time() - t0:.2f}s, cmd hwnd {b.hwnd:#x}, main hwnd {b.hwnd_main:#x}")
    ui_tid = win32.u32.GetWindowThreadProcessId(b.hwnd_main, None)
    r = b.ping()
    print("ping:", r, "ui tid", ui_tid)
    assert r.ok and r.ret[1] == ui_tid, "command did not run on the UI thread"

    r = b.call_function(FN_GZCOM)
    print(f"GZCOM() = {r.ret[0] & 0xFFFFFFFF:#x}")
    if plug:
        assert (r.ret[0] & 0xFFFFFFFF) == plug["com"], "GZCOM() differs from the plugin's cIGZCOM*"

    r = b.call_sequence([(FN_GZCOM, 0, []), (FN_DIRS, 0, []), (FN_GZCOM, 0, [])])
    print("seq:", [hex(v & 0xFFFFFFFF) for v in r.ret[:3]])
    assert r.ret[0] == r.ret[2] and r.ret[1] == p.u32(0x4FAC9C)

    r = b.call_function(0x10)  # call into unmapped memory: must come back as status -100
    print("crash test:", r)
    assert r.status == -100

    r = b.ping()
    assert r.ok, "bridge dead after crash test"
    t0 = time.time()
    b.attach(reload=True)
    print(f"hot reload ok in {time.time() - t0:.2f}s ->", b.module_name, b.ping())
    print("loaded bridges:", b._loaded_bridges())
    print("ALL OK")


if __name__ == "__main__":
    main()
