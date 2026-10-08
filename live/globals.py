"""LIVE (read-only): every pointer stored in a module's writable sections that points to a heap object
with a vtable (first dword points into a module). Shows the module/RVA of the global and of the vtable.

    python live/globals.py [module-filter]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402
from dump import Mods  # noqa: E402

import pefile  # noqa: E402

APPS = os.path.join(os.environ.get("SC3K_GAME_DIR") or r"C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited", "Apps")


def writable_sections(path):
    pe = pefile.PE(path, fast_load=True)
    for s in pe.sections:
        if s.Characteristics & 0x80000000:  # MEM_WRITE
            yield s.Name.rstrip(b"\0").decode(), s.VirtualAddress, max(s.Misc_VirtualSize, s.SizeOfRawData)


def main():
    p = win32.Process(win32.find_pids("SC3U.exe")[0])
    mods = Mods(p)
    flt = sys.argv[1].lower() if len(sys.argv) > 1 else None
    for name, base in sorted(p.modules32().items(), key=lambda kv: kv[1]):
        path = os.path.join(APPS, name)
        if not os.path.exists(path) or (flt and flt not in name):
            continue
        for sec, rva, size in writable_sections(path):
            try:
                data = p.read(base + rva, size)
            except win32.WinError:
                continue
            for i in range(0, len(data) - 3, 4):
                v = struct.unpack_from("<I", data, i)[0]
                if v < 0x10000 or mods.find(v):
                    continue
                try:
                    vt = p.u32(v)
                except win32.WinError:
                    continue
                m = mods.find(vt)
                if m and m[0] != "sc3kbridge":
                    print(f"{name}+{rva + i:#x} -> {v:#x} vt {m[0]}+{m[1]:#x}")


if __name__ == "__main__":
    main()
