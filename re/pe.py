"""Static RE helpers for the SC3U binaries (STATIC ONLY: never touches the live game).

Usage from another script in this folder:
    from pe import Image
    im = Image("SC3U.exe")            # name relative to the game's Apps dir, or a full path
    for va in im.find_str("PlugIn\\"): print(hex(va), im.xrefs(va))
    print(im.dis(0x4B4B54, 40))

Addresses are VAs at the module's *preferred* base (exe 0x400000, game DLLs 0x10000000).
Convert with im.rva(va) when recording them in the address table.
"""
import os
import re
import struct
import sys

import capstone
import pefile

APPS = os.path.join(os.environ.get("SC3K_GAME_DIR") or r"C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited", "Apps")


class Image:
    def __init__(self, path):
        if not os.path.isabs(path):
            path = os.path.join(APPS, path)
        self.path = path
        self.name = os.path.basename(path)
        self.pe = pefile.PE(path, fast_load=False)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.mem = self.pe.get_memory_mapped_image()
        self.names = {}  # va -> name
        self.imports = {}  # iat va -> "dll!func"
        if hasattr(self.pe, "DIRECTORY_ENTRY_IMPORT"):
            for entry in self.pe.DIRECTORY_ENTRY_IMPORT:
                dll = entry.dll.decode(errors="replace")
                for imp in entry.imports:
                    nm = imp.name.decode(errors="replace") if imp.name else f"#{imp.ordinal}"
                    self.imports[imp.address] = f"{dll}!{nm}"
                    self.names[imp.address] = f"[{dll}!{nm}]"
        self.exports = {}
        if hasattr(self.pe, "DIRECTORY_ENTRY_EXPORT"):
            for e in self.pe.DIRECTORY_ENTRY_EXPORT.symbols:
                nm = e.name.decode() if e.name else f"#{e.ordinal}"
                self.exports[nm] = self.base + e.address
                self.names[self.base + e.address] = nm
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = False
        self.texts = [s for s in self.pe.sections if s.Characteristics & 0x20000000]

    # ---- addressing
    def rva(self, va):
        return va - self.base

    def read(self, va, n):
        o = va - self.base
        return self.mem[o:o + n]

    def u32(self, va):
        return struct.unpack_from("<I", self.mem, va - self.base)[0]

    def cstr(self, va, maxlen=512):
        b = self.read(va, maxlen)
        return b.split(b"\0", 1)[0].decode("latin-1")

    def section_of(self, va):
        r = va - self.base
        for s in self.pe.sections:
            if s.VirtualAddress <= r < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
                return s.Name.rstrip(b"\0").decode()
        return None

    # ---- searching
    def find_bytes(self, pat, start=None, end=None):
        out = []
        for m in re.finditer(re.escape(pat), self.mem):
            out.append(self.base + m.start())
        return out

    def find_str(self, s, wide=False, exact=True):
        """VAs of a string. exact=True requires NUL termination and a NUL (or start) before it."""
        enc = s.encode("utf-16-le") if wide else s.encode("latin-1")
        res = []
        for va in self.find_bytes(enc):
            if exact:
                o = va - self.base
                term = b"\0\0" if wide else b"\0"
                if self.mem[o + len(enc):o + len(enc) + len(term)] != term:
                    continue
            res.append(va)
        return res

    def strings(self, minlen=5):
        """All printable ASCII strings in non-code sections: list of (va, str)."""
        out = []
        for s in self.pe.sections:
            if s in self.texts:
                continue
            o, n = s.VirtualAddress, max(s.Misc_VirtualSize, s.SizeOfRawData)
            for m in re.finditer(rb"[\x20-\x7e\t\r\n]{%d,}" % minlen, self.mem[o:o + n]):
                out.append((self.base + o + m.start(), m.group().decode("latin-1")))
        return out

    def xrefs(self, va):
        """Code locations whose instruction contains imm/disp32 == va (push, mov, lea, cmp...)."""
        pat = struct.pack("<I", va)
        res = []
        for s in self.texts:
            o, n = s.VirtualAddress, s.Misc_VirtualSize
            blob = self.mem[o:o + n]
            for m in re.finditer(re.escape(pat), blob):
                hit = self.base + o + m.start()
                ins = self.insn_containing(hit)
                if ins:
                    res.append(ins[0])
        return sorted(set(res))

    def data_refs(self, va):
        """Non-code locations holding the dword va (vtables, pointer tables)."""
        pat = struct.pack("<I", va)
        res = []
        for s in self.pe.sections:
            if s in self.texts:
                continue
            o, n = s.VirtualAddress, max(s.Misc_VirtualSize, s.SizeOfRawData)
            for m in re.finditer(re.escape(pat), self.mem[o:o + n]):
                res.append(self.base + o + m.start())
        return res

    def calls_to(self, target):
        """Direct E8 rel32 calls / E9 jmps to target, plus call [iat] if target is an IAT slot."""
        res = []
        for s in self.texts:
            o, n = s.VirtualAddress, s.Misc_VirtualSize
            blob = self.mem[o:o + n]
            for i in range(len(blob) - 5):
                if blob[i] in (0xE8, 0xE9):
                    rel = struct.unpack_from("<i", blob, i + 1)[0]
                    src = self.base + o + i
                    if (src + 5 + rel) & 0xFFFFFFFF == target:
                        res.append(src)
        if target in self.imports:
            res += [x for x in self.xrefs(target)]
        return sorted(set(res))

    def insn_containing(self, va, back=15):
        """Find an instruction that decodes cleanly and contains byte va (heuristic)."""
        for start in range(va - back, va + 1):
            try:
                insns = list(self.md.disasm(self.read(start, 16), start, count=1))
            except Exception:
                continue
            if insns and insns[0].address <= va < insns[0].address + insns[0].size:
                # sanity: decode a few following instructions too
                follow = list(self.md.disasm(self.read(start, 48), start, count=4))
                if len(follow) >= 3:
                    return (start, insns[0])
        return None

    # ---- disassembly
    def annotate(self, ins):
        txt = f"{ins.mnemonic} {ins.op_str}"
        notes = []
        for m in re.finditer(r"0x[0-9a-f]{5,8}", ins.op_str):
            v = int(m.group(), 16)
            if v in self.names:
                notes.append(self.names[v])
            elif self.base <= v < self.base + len(self.mem):
                sec = self.section_of(v)
                if sec in (".rdata", ".data"):
                    s = self.cstr(v, 80)
                    if len(s) >= 3 and all(32 <= ord(c) < 127 or c in "\r\n\t" for c in s):
                        notes.append(repr(s))
        return txt + (("    ; " + " ".join(notes)) if notes else "")

    def dis(self, va, count=30, stop_at_ret=False):
        out = []
        for ins in self.md.disasm(self.read(va, count * 16), va):
            out.append(f"{ins.address:08x}  {ins.bytes.hex():<20} {self.annotate(ins)}")
            count -= 1
            if count <= 0 or (stop_at_ret and ins.mnemonic.startswith("ret")):
                break
        return "\n".join(out)

    def around(self, va, before=0x60, after=0x80):
        """Disassemble a window around va, synced from the enclosing function start."""
        f = self.func_start(va) or (va - before)
        out = []
        for ins in self.md.disasm(self.read(f, va - f + after), f):
            if ins.address >= va - before:
                mark = ">>" if ins.address <= va < ins.address + ins.size else "  "
                out.append(f"{mark}{ins.address:08x}  {self.annotate(ins)}")
        return "\n".join(out)

    def follow_jmp(self, f):
        """Follow a leading `jmp rel32` thunk."""
        for _ in range(4):
            b = self.read(f, 5)
            if b[0] != 0xE9:
                break
            f = (f + 5 + struct.unpack("<i", b[1:5])[0]) & 0xFFFFFFFF
        return f

    def stack_args(self, f, limit=0x3000):
        """Number of stack args a thiscall/stdcall function pops (from its first `ret N`; cdecl -> 0).
        Linear scan, so a function with an early `ret` in a branch still gives the right N."""
        f = self.follow_jmp(f)
        for ins in self.md.disasm(self.read(f, limit), f):
            if ins.mnemonic == "ret":
                return int(ins.op_str, 16) // 4 if ins.op_str else 0
            if ins.mnemonic == "jmp" and ins.op_str.startswith("dword ptr ["):
                return None  # import thunk
        return None

    def is_code(self, va):
        r = va - self.base
        return any(s.VirtualAddress <= r < s.VirtualAddress + s.Misc_VirtualSize for s in self.texts)

    def vtable(self, va, maxn=200):
        """[(slot, fn, nargs)] for a vtable at va: stops at the first non-code entry. VC6 vtables are
        contiguous with no RTTI separator, so the last few slots may belong to the next vtable; compare
        with data_refs() of the following addresses to find where another vtable begins."""
        out = []
        for i in range(maxn):
            f = self.u32(va + 4 * i)
            if not self.is_code(f):
                break
            out.append((i, f, self.stack_args(f)))
        return out

    def vtable_starts(self):
        """Addresses in non-code sections referenced by `mov dword ptr [reg], imm32` (C7 00..07 imm32 /
        C7 4x disp8 imm32): constructor vtable stores. Returns {vtable_va: [code addrs]}."""
        res = {}
        for s in self.texts:
            o, n = s.VirtualAddress, s.Misc_VirtualSize
            blob = self.mem[o:o + n]
            for m in re.finditer(rb"\xc7[\x00-\x07](....)|\xc7[\x40-\x47].(....)", blob, re.S):
                v = struct.unpack("<I", m.group(1) or m.group(2))[0]
                if self.base <= v < self.base + len(self.mem) and not self.is_code(v) and self.is_code(self.u32(v)):
                    res.setdefault(v, []).append(self.base + o + m.start())
        return res

    def func_start(self, va, maxback=0x4000):
        """Heuristic: walk back to the nearest 'push ebp; mov ebp,esp' (VC6 frame functions).
        Frameless leaf functions are not found; check the result with calls_to()."""
        for a in range(va, va - maxback, -1):
            if self.read(a, 3) == b"\x55\x8b\xec":
                return a
        return None


def main():
    im = Image(sys.argv[1])
    cmd = sys.argv[2]
    if cmd == "str":
        for va in im.find_str(sys.argv[3], exact=False):
            print(hex(va), im.section_of(va), [hex(x) for x in im.xrefs(va)])
    elif cmd == "dis":
        print(im.dis(int(sys.argv[3], 16), int(sys.argv[4]) if len(sys.argv) > 4 else 40))
    elif cmd == "xref":
        print([hex(x) for x in im.xrefs(int(sys.argv[3], 16))])
    elif cmd == "calls":
        print([hex(x) for x in im.calls_to(int(sys.argv[3], 16))])


if __name__ == "__main__":
    main()
