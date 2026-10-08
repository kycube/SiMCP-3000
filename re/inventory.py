"""STATIC: inventory of every GZCOM module.

Writes re/out/strings/<module>.txt (every string with the code addresses that reference it) and
re/out/classes.txt (class IDs each director registers via AddCls(clsid, factory, 0) in its constructor).
"""
import glob
import os
import re
import struct
import sys

from pe import Image, APPS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def modules():
    seen = set()
    for p in sorted(glob.glob(os.path.join(APPS, "*.dll")) + glob.glob(os.path.join(APPS, "*.DLL")) + [os.path.join(APPS, "SC3U.exe")]):
        n = os.path.basename(p).upper()
        if n in seen or n in ("MSVCRT.DLL", "MSVCP60.DLL", "MSVCIRT.DLL", "DDRAW.DLL", "UV.DLL"):
            continue
        seen.add(n)
        yield p


def code_refs_index(im):
    """dword value -> [code addresses] for every 4-byte immediate in .text that points into the image."""
    idx = {}
    lo, hi = im.base, im.base + len(im.mem)
    for s in im.texts:
        o, n = s.VirtualAddress, s.Misc_VirtualSize
        blob = im.mem[o:o + n]
        for i in range(0, len(blob) - 3):
            v = struct.unpack_from("<I", blob, i)[0]
            if lo <= v < hi:
                idx.setdefault(v, []).append(im.base + o + i)
    return idx


def find_addcls(im):
    """Director constructors: push 0 / push factory / push clsid / mov ecx,esi / call AddCls, repeated."""
    out = []
    pat = re.compile(rb"\x6a\x00\x68(....)\x68(....)\x8b\xce\xe8(....)", re.S)
    for s in im.texts:
        o, n = s.VirtualAddress, s.Misc_VirtualSize
        blob = im.mem[o:o + n]
        for m in pat.finditer(blob):
            factory, clsid = struct.unpack("<II", m.group(1) + m.group(2))
            call_at = im.base + o + m.start() + 12
            target = (call_at + 5 + struct.unpack("<i", m.group(3))[0]) & 0xFFFFFFFF
            out.append((im.base + o + m.start(), clsid, factory, target))
    return out


def main():
    os.makedirs(os.path.join(OUT, "strings"), exist_ok=True)
    cls_lines = []
    for path in modules():
        im = Image(path)
        idx = code_refs_index(im)
        lines = []
        for va, s in im.strings(4):
            refs = idx.get(va, [])
            # print strings with code refs, and long unreferenced ones (tables)
            if refs or len(s) >= 8:
                lines.append(f"{va:08x} [{len(refs):2d}] {' '.join(hex(r) for r in refs[:6])} | {s.strip()[:200]!r}")
        with open(os.path.join(OUT, "strings", im.name + ".txt"), "w", encoding="utf-8") as f:
            f.write(f"# {im.name} base {im.base:#x}; format: va [nrefs] refs | string\n")
            f.write("\n".join(lines))
        regs = find_addcls(im)
        # the AddCls target is the most common call target among the matches
        if regs:
            from collections import Counter
            tgt = Counter(r[3] for r in regs).most_common(1)[0][0]
            regs = [r for r in regs if r[3] == tgt]
            cls_lines.append(f"## {im.name} (AddCls = {tgt:#x})")
            for at, clsid, factory, _ in regs:
                cls_lines.append(f"  clsid {clsid:#010x} factory {factory:#x} (at {at:#x})")
        print(im.name, len(lines), "strings,", len(regs), "classes", file=sys.stderr)
    with open(os.path.join(OUT, "classes.txt"), "w") as f:
        f.write("\n".join(cls_lines) + "\n")


if __name__ == "__main__":
    main()
