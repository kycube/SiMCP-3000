"""LIVE (read-only): Cheat-Engine-style value scanner for SC3U.exe, pure Python.

    python live/memscan.py first <type> <value> [name]      # type: i32 u32 i16 u16 u8 f32 f64 i64
    python live/memscan.py next <name> <value|changed|unchanged|increased|decreased>
    python live/memscan.py show <name> [n]
Candidates are kept in live/scans/<name>.txt (address + type).
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sc3k_mcp import win32  # noqa: E402

SCANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scans")
FMT = {"i32": "<i", "u32": "<I", "i16": "<h", "u16": "<H", "u8": "<B", "f32": "<f", "f64": "<d", "i64": "<q"}


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_ulonglong),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


win32.k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
win32.k32.VirtualQueryEx.restype = ctypes.c_size_t
WRITABLE = {0x04, 0x08, 0x40, 0x80}


def regions(p, writable_only=True):
    addr = 0x10000
    mbi = MBI()
    while addr < 0x7FFF0000:
        if not win32.k32.VirtualQueryEx(p.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress, mbi.RegionSize
        prot = mbi.Protect & 0xFF
        if mbi.State == 0x1000 and not (mbi.Protect & 0x100) and (prot in WRITABLE or not writable_only) and prot != 0x01:
            yield base, size
        addr = base + size


def read_region(p, base, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if not win32.k32.ReadProcessMemory(p.handle, ctypes.c_void_p(base), buf, size, ctypes.byref(got)):
        return b""
    return buf.raw[: got.value]


def first_scan(p, typ, value):
    fmt = FMT[typ]
    size = struct.calcsize(fmt)
    needle = struct.pack(fmt, value)
    align = min(size, 4)
    hits = []
    for base, rsize in regions(p):
        data = read_region(p, base, rsize)
        i = data.find(needle)
        while i != -1:
            if i % align == 0:
                hits.append(base + i)
            i = data.find(needle, i + 1)
    return hits


def read_value(p, addr, typ):
    fmt = FMT[typ]
    try:
        return struct.unpack(fmt, p.read(addr, struct.calcsize(fmt)))[0]
    except win32.WinError:
        return None


def save(name, typ, rows):
    os.makedirs(SCANS, exist_ok=True)
    with open(os.path.join(SCANS, name + ".txt"), "w") as f:
        f.write(typ + "\n")
        for a, v in rows:
            f.write(f"{a:#x} {v}\n")


def load(name):
    with open(os.path.join(SCANS, name + ".txt")) as f:
        typ = f.readline().strip()
        rows = []
        for line in f:
            a, v = line.split()
            rows.append((int(a, 16), float(v) if typ.startswith("f") else int(v)))
    return typ, rows


def module_of(p, addr, mods=None):
    mods = mods or p.modules32()
    best = max(((n, b) for n, b in mods.items() if b <= addr), key=lambda t: t[1], default=(None, 0))
    return f"{best[0]}+{addr - best[1]:#x}" if best[0] and addr - best[1] < 0x400000 else "heap"


def snapshot(p, name):
    """Save all writable memory (unknown-initial-value scan)."""
    import pickle
    snap = {base: read_region(p, base, size) for base, size in regions(p)}
    os.makedirs(SCANS, exist_ok=True)
    with open(os.path.join(SCANS, name + ".snap"), "wb") as f:
        pickle.dump(snap, f)
    return sum(len(v) for v in snap.values())


def diff(p, name, crit, typ="i32", lo=None, hi=None):
    """Compare current memory with a snapshot: crit in changed/unchanged/increased/decreased/delta:<n>."""
    import array
    import pickle
    with open(os.path.join(SCANS, name + ".snap"), "rb") as f:
        snap = pickle.load(f)
    code = {"i32": "i", "u32": "I", "i16": "h", "u16": "H", "u8": "B"}[typ]
    size = array.array(code).itemsize
    out = []
    for base, old in snap.items():
        new = read_region(p, base, len(old))
        if len(new) != len(old):
            continue
        n = len(old) // size * size
        if old[:n] == new[:n] and crit != "unchanged":
            continue
        a, b = array.array(code, old[:n]), array.array(code, new[:n])
        delta = int(crit.split(":")[1]) if crit.startswith("delta:") else None
        for i in range(len(a)):
            x, y = a[i], b[i]
            if delta is not None:
                ok = y - x == delta
            else:
                ok = {"changed": x != y, "unchanged": x == y, "increased": y > x, "decreased": y < x}[crit]
            if ok and (lo is None or lo <= y <= hi):
                out.append((base + i * size, y))
    # the diff result becomes a normal candidate list for `next`
    save(name, typ, out)
    with open(os.path.join(SCANS, name + ".snap"), "wb") as f:
        pickle.dump({base: read_region(p, base, len(old)) for base, old in snap.items()}, f)
    return out


def main():
    p = win32.Process(win32.find_pids("SC3U.exe")[0])
    flags = [a for a in sys.argv if a.startswith("--")]
    sys.argv = [a for a in sys.argv if not a.startswith("--")] + flags
    nflags = len(flags)
    argv = sys.argv[:len(sys.argv) - nflags]
    cmd = argv[1]
    if cmd == "snap":
        print(f"snapshot {sys.argv[2]}: {snapshot(p, sys.argv[2]) / 1e6:.1f} MB")
        return
    if cmd == "diff":
        name, crit = argv[2], argv[3]
        typ = argv[4] if len(argv) > 4 else "i32"
        lo = int(argv[5], 0) if len(argv) > 5 else None
        hi = int(argv[6], 0) if len(argv) > 6 else None
        out = diff(p, name, crit, typ, lo, hi)
        print(f"{len(out)} candidates")
        if "--clusters" in sys.argv:
            mods = p.modules32()
            clusters = []
            for a, v in sorted(out):
                if clusters and a - clusters[-1][1] <= 64:
                    clusters[-1][1] = a
                    clusters[-1][2] += 1
                else:
                    clusters.append([a, a, 1])
            for lo_, hi_, n in sorted(clusters, key=lambda c: -c[2])[:40]:
                print(f"  cluster {lo_:#010x}..{hi_:#010x} span {hi_ - lo_ + 1:6d} changes {n:5d} ({module_of(p, lo_, mods)})")
            return
        if len(out) <= 40:
            mods = p.modules32()
            for a, v in out:
                print(f"  {a:#010x} = {v}  ({module_of(p, a, mods)})")
        return
    if cmd == "first":
        typ, value = sys.argv[2], sys.argv[3]
        value = float(value) if typ.startswith("f") else int(value, 0)
        name = sys.argv[4] if len(sys.argv) > 4 else "scan"
        hits = first_scan(p, typ, value)
        save(name, typ, [(a, value) for a in hits])
        print(f"{len(hits)} hits")
    elif cmd == "next":
        name, crit = sys.argv[2], sys.argv[3]
        typ, rows = load(name)
        out = []
        for a, old in rows:
            v = read_value(p, a, typ)
            if v is None:
                continue
            ok = {"changed": v != old, "unchanged": v == old, "increased": v > old, "decreased": v < old}.get(crit)
            if ok is None:
                want = float(crit) if typ.startswith("f") else int(crit, 0)
                ok = v == want
            if ok:
                out.append((a, v))
        save(name, typ, out)
        print(f"{len(out)} left")
        if len(out) <= 30:
            mods = p.modules32()
            for a, v in out:
                print(f"  {a:#010x} = {v}  ({module_of(p, a, mods)})")
    elif cmd == "show":
        typ, rows = load(sys.argv[2])
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        mods = p.modules32()
        for a, v in rows[:n]:
            print(f"  {a:#010x} = {read_value(p, a, typ)} (was {v})  ({module_of(p, a, mods)})")


if __name__ == "__main__":
    main()
