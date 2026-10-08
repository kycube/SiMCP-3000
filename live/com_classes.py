"""LIVE (read-only): dump the GZCOM class registry (clsid -> library) from the running game.

cRZCOM (= GZCOM(), global via 0x4708C4) keeps a VC6 std::map at +0x4C, filled by the EnumClassObjects
callback 0x48AA3A with node value {clsid, ?, version, library*}; library+0x0C = path char*.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import bridge, win32  # noqa: E402


def rb_inorder(p, head):
    """In-order walk of the cRZCOM class tree. Node: [4] parent, [8] left, [0xC] right, [0x10] clsid,
    [0x14] version, [0x18] library*. Children are NULL-terminated; head+4 = root."""
    out, stack, n = [], [], p.u32(head + 4)
    while stack or n:
        while n:
            stack.append(n)
            n = p.u32(n + 8)
        n = stack.pop()
        out.append(n)
        n = p.u32(n + 0xC)
    return out


def cstr(p, a, n=260):
    try:
        return p.read(a, n).split(b"\0")[0].decode("latin-1")
    except Exception:
        return "?"


def main():
    p = win32.Process(win32.find_pids("SC3U.exe")[0])
    plug = bridge.plugin_info(p)
    com = plug["com"]
    m = com + 0x4C
    head = p.u32(m)
    print(f"cRZCOM {com:#x}, map head {head:#x}, size? {p.u32(m + 8)}")
    rows = []
    for node in rb_inorder(p, head):
        clsid, a, b, c = struct.unpack("<4I", p.read(node + 0x10, 16))
        rows.append((clsid, a, b, c))
    libs = {}
    for clsid, a, b, c in rows:
        for v in (a, b, c):
            if v > 0x10000 and v not in libs:
                try:
                    path = cstr(p, p.u32(v + 0xC))
                except win32.WinError:
                    path = ""
                libs[v] = os.path.basename(path) if path.lower().endswith((".dll", ".exe")) else ""
    for clsid, a, b, c in rows:
        lib = next((libs[v] for v in (a, b, c) if libs.get(v)), "")
        print(f"{clsid:#010x}  {a:#010x} {b:#010x} {c:#010x}  {lib}")
    print(len(rows), "classes")


if __name__ == "__main__":
    main()
