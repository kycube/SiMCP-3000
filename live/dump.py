"""LIVE (read-only): annotated dword dump of game memory.

    python live/dump.py <addr> [len] [--back N]
Each dword is annotated: module+rva for code/data pointers (vtables marked), strings, small ints.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402

APPS = os.path.join(os.environ.get("SC3K_GAME_DIR") or r"C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited", "Apps")


class Mods:
    def __init__(self, p):
        self.p = p
        self.mods = sorted(((b, n) for n, b in p.modules32().items()), reverse=True)
        self.sizes = {}

    def find(self, v):
        for b, n in self.mods:
            if b <= v:
                if n not in self.sizes:
                    try:
                        e = self.p.u32(b + 0x3C)
                        self.sizes[n] = self.p.u32(b + e + 0x50)
                    except win32.WinError:
                        self.sizes[n] = 0
                if v - b < self.sizes[n]:
                    return n, v - b
                return None
        return None


def annotate(p, mods, v):
    m = mods.find(v)
    if m:
        n, rva = m
        try:
            first = p.u32(v)
            fm = mods.find(first)
            kind = " vtable?" if fm and fm[0] == n else ""
        except win32.WinError:
            kind = ""
        return f"{n}+{rva:#x}{kind}"
    if 0x10000 <= v < 0x7FFF0000:
        try:
            b = p.read(v, 48)
            s = b.split(b"\0")[0]
            if len(s) >= 4 and all(32 <= c < 127 for c in s):
                return f"-> {s.decode()!r}"
            first = struct.unpack_from("<I", b)[0]
            fm = mods.find(first)
            if fm:
                return f"-> obj vt {fm[0]}+{fm[1]:#x}"
            return "-> heap"
        except win32.WinError:
            pass
    if v < 0x10000 or v > 0xFFFF0000:
        return f"{struct.unpack('<i', struct.pack('<I', v))[0]}"
    f = struct.unpack("<f", struct.pack("<I", v))[0]
    return f"f={f:.4g}" if 1e-4 < abs(f) < 1e7 else ""


def dump(p, addr, length=0x80, mods=None):
    mods = mods or Mods(p)
    data = p.read(addr, length)
    lines = []
    for i in range(0, len(data) - 3, 4):
        v = struct.unpack_from("<I", data, i)[0]
        lines.append(f"{addr + i:#010x} +{i:#05x}: {v:#010x}  {annotate(p, mods, v)}")
    return "\n".join(lines)


def main():
    p = win32.Process(win32.find_pids("SC3U.exe")[0])
    addr = int(sys.argv[1], 16)
    length = int(sys.argv[2], 0) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 0x80
    if "--back" in sys.argv:
        addr -= int(sys.argv[sys.argv.index("--back") + 1], 0)
    print(dump(p, addr, length))


if __name__ == "__main__":
    main()
