"""LIVE (read-only): find every dword in readable memory that points into [addr, addr+span).

    python live/refs.py <addr> [span] [--all]   (--all: also scan read-only/image memory)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402
from memscan import regions, read_region  # noqa: E402
from dump import Mods, annotate  # noqa: E402


def find_refs(p, lo, hi, writable_only=True):
    hits = []
    for base, size in regions(p, writable_only):
        data = read_region(p, base, size)
        n = len(data) // 4
        if not n:
            continue
        vals = struct.unpack_from(f"<{n}I", data)
        for i, v in enumerate(vals):
            if lo <= v < hi:
                hits.append((base + 4 * i, v))
    return hits


def main():
    p = win32.Process(win32.find_pids("SC3U.exe")[0])
    addr = int(sys.argv[1], 16)
    span = int(sys.argv[2], 0) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 4
    mods = Mods(p)
    for where, v in find_refs(p, addr, addr + span, "--all" not in sys.argv):
        m = mods.find(where)
        loc = f"{m[0]}+{m[1]:#x}" if m else "heap"
        # what object contains `where`? look back for a vtable
        print(f"{where:#010x} ({loc}) -> {v:#x} (+{v - addr:#x})")


if __name__ == "__main__":
    main()
