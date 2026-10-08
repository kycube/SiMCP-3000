r"""SimCity 3000 Unlimited Building Architect project files (*.bld): parser, writer, editor helpers.

(Copied from re/agents/bld/bld.py - the static RE deliverable, see re/agents/bld/REPORT.md; verified live: a file
written by this module loads in Baapp.exe and renders with its renderer.)

STATIC reverse engineering (no running program). Loader/saver read in SIMBABLD.DLL (base 0x12000000; the game's
copy of the BAT engine); Baapp.exe (base 0x400000) has instruction-identical copies (matched by mnemonics):

  bld load      SIMBABLD 0x12003ED3 / Baapp 0x4063C8     bld save      SIMBABLD 0x12003BF6 / Baapp 0x4060EB
  model read    SIMBABLD 0x1200975B / Baapp 0x413E1A     model write   SIMBABLD 0x1200A849 / Baapp 0x414F08
  info read     SIMBABLD 0x1200B348 / Baapp 0x415A07     info write    SIMBABLD 0x1200B7EF / Baapp 0x415EAE
  tex-meta read SIMBABLD 0x1200ADBA / Baapp 0x415479     image read    SIMBABLD 0x1201BC09 (res-file vt[17])
  face masks    SIMBABLD 0x12011C4A / Baapp 0x40E77A     paint uv      SIMBABLD 0x12039F42 / Baapp 0x43B8A0
  insert block  SIMBABLD 0x1200F55A / Baapp 0x40C08A     compaction    SIMBABLD 0x1200D86E / Baapp 0x40A330
  new building  Baapp 0x41DA42 (grid/height tables 0x493EC0 / 0x493EC5), ground layer Baapp 0x409E58
  RefPack       compressor vtable SIMBABLD 0x1206CC34 (size bound n*10/9 + 1000 at 0x12059F0F)

Container: IXF = magic D7 81 C3 80, then a fixed 1024-slot index of 20-byte entries
{group, instance, type, offset, size} (zero entry terminates, rest of the 20480-byte index is zero), then the
resource data, contiguous, in index order. In-memory GZ key order is {type, group, instance}.

Every .bld resource has group 0xC3F8D4A9. See REPORT (returned to the caller) for the field-level catalogue.

Usage:
  python bld.py summary [FILE ...]        structured summary (default: all <game>\Buildings\*.bld)
  python bld.py roundtrip [FILE ...]      parse -> serialize, byte compare; also re-encode the model from
                                          its block list and check the decoded geometry is identical
  python bld.py thumbs OUTDIR [FILE ...]  write the stored 200x200 thumbnails (and embedded textures) as PNG
  python bld.py render FILE OUT.png       flat-shaded isometric preview of the 3D model (PIL)
  python bld.py example OUT.bld           build the minimal example (UNTESTED in the BAT / game)
"""
from __future__ import annotations

import glob
import os
import struct
import sys
from dataclasses import dataclass, field

from sc3k_mcp.bridge import GAME_DIR as GAME   # the game folder (SC3K_GAME_DIR overrides)
APPS = os.path.join(GAME, "Apps")
BUILDINGS = os.path.join(GAME, "Buildings")

IXF_MAGIC = b"\xd7\x81\xc3\x80"
IXF_SLOTS = 1024                      # index capacity in every sample (first data offset 0x5004)

GROUP = 0xC3F8D4A9                    # group of every .bld resource
# (type, instance) of the fixed resources
T_MODEL, I_MODEL = 0xE3F87B0C, 0xA3F8D615      # 3D block model + texture name table
T_INFO, I_INFO = 0xE3F87B0F, 0x63FBE1CC        # lot size, name, architect
T_DESC, I_DESC = 0x644D7178, 0xA44D71AA        # description
T_BTYPE, I_BTYPE = 0x644D7179, 0xA44D71AB      # building type (BATStringsMain id 0x208..0x217)
T_B9EC, I_B9EC = 0xB9EC8F72, 0x99EC9601        # u32 (model+0x54, always 1 in samples)
T_FLAGS, I_FLAGS = 0x99F88B9E, 0xB9F88BD2      # 4 bytes (model+0x50..0x53: model/ground version)
T_REG, I_REG = 0xDA6DC9A9, 0x63FBE1CC          # registration string + u32 (written by shipped BAT, absent in samples)
T_THUMB, I_THUMB = 0xE3F87B0E, 0xE3F8D655      # 200x200 RGB565 thumbnail
T_TEXMETA = 0xE3F87B0D                         # embedded custom texture: metadata  (instance = 0..n-1)
T_TEXIMG = 0xE3F87B10                          # embedded custom texture: ARGB8888 pixels
T_PROPMET = 0xFA662D17                         # embedded custom prop: the .MET line (4 view bitmaps + size)

TYPE_NAMES = {T_MODEL: "model", T_INFO: "info", T_DESC: "description", T_BTYPE: "building_type",
              T_B9EC: "b9ec8f72", T_FLAGS: "flags", T_REG: "registration", T_THUMB: "thumbnail",
              T_TEXMETA: "tex_meta", T_TEXIMG: "tex_image", T_PROPMET: "prop_met"}

BUILDING_TYPES = {0x208: "Residential", 0x209: "Commercial", 0x20A: "Industrial", 0x20B: "Police Station",
                  0x20C: "Jail", 0x20D: "Fire Station", 0x20E: "Hospital", 0x20F: "School", 0x210: "College",
                  0x211: "Library", 0x212: "Museum", 0x213: "Historic Statue", 0x214: "Mayor's House",
                  0x215: "City Hall", 0x216: "Performing Arts Center", 0x217: "Other"}

GRID_PER_TILE = 8                     # block cells per city tile edge (SIMBABLD 0x12076800: 08 10 18 20 28)
DEFAULT_HEIGHT = {1: 28, 2: 64, 3: 108, 4: 144, 5: 80}  # BAT "New Building" (Baapp 0x41DA42, table 0x493EC5);
#                                                        samples also show 65/109/257/288/385
MAX_POOL = 0x20000                    # record pool capacity (17-bit indices; pool = 0x400000 bytes)

PAD8, PAD16, PAD32 = 0xEA, 0xEAEA, 0xEAEAEAEA


# ----------------------------------------------------------------------------------------------- RefPack (QFS)
def refpack_decompress(src: bytes) -> bytes:
    """EA RefPack. Header 10 FB + 3-byte big-endian size (variants with 4-byte size / extra size handled)."""
    flags = src[0] << 8 | src[1]
    if flags & 0xFF != 0xFB:
        raise ValueError("not RefPack")
    w = 4 if flags & 0x8000 else 3
    i = 2 + (w if flags & 0x0100 else 0)
    size = int.from_bytes(src[i:i + w], "big")
    i += w
    out = bytearray()
    n = len(src)
    while i < n:
        b0 = src[i]
        if b0 < 0x80:
            b1 = src[i + 1]; i += 2
            plain = b0 & 3; cnt = ((b0 >> 2) & 7) + 3; off = ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            b1, b2 = src[i + 1], src[i + 2]; i += 3
            plain = b1 >> 6; cnt = (b0 & 0x3F) + 4; off = ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:
            b1, b2, b3 = src[i + 1], src[i + 2], src[i + 3]; i += 4
            plain = b0 & 3; cnt = ((b0 & 0x0C) << 6) + b3 + 5; off = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            i += 1; plain = ((b0 & 0x1F) << 2) + 4; cnt = 0; off = 0
        else:
            i += 1; plain = b0 & 3
            out += src[i:i + plain]
            break
        out += src[i:i + plain]; i += plain
        if cnt:
            start = len(out) - off
            if off >= cnt:
                out += out[start:start + cnt]
            else:
                for k in range(cnt):
                    out.append(out[start + k])
    if len(out) < size:
        raise ValueError("RefPack stream ended early (%d < %d)" % (len(out), size))
    return bytes(out[:size])


def refpack_compress(src: bytes, max_chain: int = 24) -> bytes:
    """Greedy LZ77 RefPack encoder (10 FB + 3-byte size). Output is decodable by refpack_decompress and by the
    standard EA decoder (2/3/4-byte copy opcodes, E0..FB literal runs, FC..FF terminator)."""
    n = len(src)
    if n >= 1 << 24:
        raise ValueError("too large for a 3-byte RefPack size")
    out = bytearray(b"\x10\xfb" + n.to_bytes(3, "big"))
    head: dict[bytes, int] = {}
    prev = [-1] * n
    lit = 0
    i = 0

    def flush_literals(upto, keep):
        nonlocal lit
        # emit 4-aligned literal blocks, leave `keep` (0..3) bytes for the following opcode
        while upto - lit > keep:
            k = min(112, (upto - lit - keep) & ~3) if (upto - lit - keep) >= 4 else 0
            if k == 0:
                break
            out.append(0xE0 + (k >> 2) - 1)
            out.extend(src[lit:lit + k])
            lit += k

    def insert(p):
        if p + 3 <= n:
            key = src[p:p + 3]
            prev[p] = head.get(key, -1)
            head[key] = p

    while i < n:
        best_l = 0
        best_off = 0
        if i + 3 <= n:
            j = head.get(src[i:i + 3], -1)
            chain = 0
            maxl = min(1028, n - i)
            while j >= 0 and chain < max_chain:
                off = i - j
                if off > 131072:
                    break
                if best_l < maxl and src[j + best_l] == src[i + best_l]:
                    l = 3
                    while l < maxl and src[j + l] == src[i + l]:
                        l += 1
                    # encodability
                    if off > 16384:
                        ok = l >= 5
                    elif off > 1024:
                        ok = l >= 4
                    else:
                        ok = True
                    if ok and l > best_l:
                        best_l, best_off = l, off
                        if l == maxl:
                            break
                j = prev[j]
                chain += 1
        if best_l >= 3:
            flush_literals(i, (i - lit) & 3)
            plain = i - lit
            assert plain <= 3
            l, o = best_l, best_off - 1
            if l <= 10 and o < 1024:
                out += bytes((((o >> 3) & 0x60) | ((l - 3) << 2) | plain, o & 0xFF))
            elif l <= 67 and o < 16384:
                out += bytes((0x80 | (l - 4), (plain << 6) | (o >> 8), o & 0xFF))
            else:
                out += bytes((0xC0 | ((o >> 16) << 4) | (((l - 5) >> 8) << 2) | plain, (o >> 8) & 0xFF, o & 0xFF,
                              (l - 5) & 0xFF))
            out += src[lit:i]
            for p in range(i, i + l):
                insert(p)
            i += l
            lit = i
        else:
            insert(i)
            i += 1
    rem = (n - lit) & 3
    flush_literals(n, rem)
    out.append(0xFC + (n - lit))
    out += src[lit:n]
    return bytes(out)


def compress_block(data: bytes) -> bytes:
    """The BAT compressor's output (SIMBABLD 0x12059E86): u32 total length (incl. itself) + RefPack."""
    rp = refpack_compress(data)
    return struct.pack("<I", 4 + len(rp)) + rp


def decompress_block(blob: bytes) -> bytes:
    total = struct.unpack_from("<I", blob)[0]
    if total != len(blob):
        raise ValueError("compressed block length mismatch %d != %d" % (total, len(blob)))
    return refpack_decompress(blob[4:])


def pool_bound(used: int) -> int:
    """Bytes of the record pool the BAT compresses: its compressor's size bound applied to used*32 (SIMBABLD
    0x12059F0F: n*10/9 + 1000) - the saver passes the bound as the source length (0x1200AA2E), so the free-list
    records after the used ones are saved too."""
    return min(used * 32 * 10 // 9 + 1000, MAX_POOL * 32)


# ------------------------------------------------------------------------------------------------------ IXF
@dataclass
class Entry:
    group: int
    instance: int
    type: int
    data: bytes


def read_ixf(blob: bytes):
    if blob[:4] != IXF_MAGIC:
        raise ValueError("not an IXF file")
    entries = []
    o = 4
    first = None
    while o + 20 <= len(blob):
        g, i, t, off, size = struct.unpack_from("<5I", blob, o)
        o += 20
        if g == 0 and i == 0 and t == 0:
            break
        entries.append(Entry(g, i, t, blob[off:off + size]))
        first = off if first is None else min(first, off)
    slots = ((first or (4 + 20 * IXF_SLOTS)) - 4) // 20
    return entries, slots


def write_ixf(entries, slots=IXF_SLOTS) -> bytes:
    slots = max(slots, len(entries) + 1)
    head = bytearray(IXF_MAGIC + b"\0" * (20 * slots))
    data = bytearray()
    base = 4 + 20 * slots
    for k, e in enumerate(entries):
        struct.pack_into("<5I", head, 4 + 20 * k, e.group, e.instance, e.type, base + len(data), len(e.data))
        data += e.data
    return bytes(head + data)


# ------------------------------------------------------------------------------------------- stream helpers
class R:
    def __init__(self, b: bytes, o: int = 0):
        self.b, self.o = b, o

    def u8(self):
        v = self.b[self.o]; self.o += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.o)[0]; self.o += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.o)[0]; self.o += 4; return v

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.o)[0]; self.o += 4; return v

    def f32(self):
        v = struct.unpack_from("<f", self.b, self.o)[0]; self.o += 4; return v

    def raw(self, n):
        v = self.b[self.o:self.o + n]
        if len(v) != n:
            raise ValueError("truncated")
        self.o += n; return v

    def str32(self):                       # u32 length + bytes (stream vt+0x54 / +0xA4)
        return self.raw(self.u32()).decode("latin-1")

    def str8(self):                        # u8 length + bytes (info / description)
        return self.raw(self.u8()).decode("latin-1")

    def rest(self):
        v = self.b[self.o:]; self.o = len(self.b); return v


def s32(s: str) -> bytes:
    b = s.encode("latin-1")
    return struct.pack("<I", len(b)) + b


def s8(s: str) -> bytes:
    b = s.encode("latin-1")
    if len(b) > 255:
        raise ValueError("string too long for a u8 length")
    return bytes([len(b)]) + b


# ------------------------------------------------------------------------------------------------- images
@dataclass
class Image:
    """GZ image resource (SIMBABLD 0x1201BC09): u8 kind (F0 = 16 bpp, F1 = 32 bpp), u8 pixel format
    (7 = RGB565, 0x0E = ARGB8888 stored B,G,R,A), u16 width, u16 height, compressed block (u32 len + RefPack)
    holding width*height*bpp bytes, rows top to bottom."""
    kind: int
    fmt: int
    width: int
    height: int
    pixels: bytes
    raw: bytes | None = None               # original bytes, reused when pixels are unchanged

    @classmethod
    def parse(cls, b: bytes) -> "Image":
        r = R(b)
        kind, fmt, w, h = r.u8(), r.u8(), r.u16(), r.u16()
        blob = r.rest()
        return cls(kind, fmt, w, h, decompress_block(blob), raw=b)

    def to_bytes(self) -> bytes:
        if self.raw is not None and Image.parse(self.raw).pixels == self.pixels:
            return self.raw
        return struct.pack("<BBHH", self.kind, self.fmt, self.width, self.height) + compress_block(self.pixels)

    def rgba(self) -> bytes:
        out = bytearray()
        p = self.pixels
        if self.kind == 0xF0:
            for k in range(self.width * self.height):
                v = p[2 * k] | p[2 * k + 1] << 8
                r5, g6, b5 = v >> 11, (v >> 5) & 63, v & 31
                out += bytes((r5 * 255 // 31, g6 * 255 // 63, b5 * 255 // 31, 255))
        else:
            for k in range(self.width * self.height):
                b_, g_, r_, a_ = p[4 * k:4 * k + 4]
                out += bytes((r_, g_, b_, a_))
        return bytes(out)

    @classmethod
    def from_rgb565(cls, w, h, rgb: bytes) -> "Image":
        px = bytearray()
        for k in range(w * h):
            r_, g_, b_ = rgb[3 * k:3 * k + 3]
            v = (r_ * 31 // 255) << 11 | (g_ * 63 // 255) << 5 | (b_ * 31 // 255)
            px += struct.pack("<H", v)
        return cls(0xF0, 7, w, h, bytes(px))

    def save_png(self, path):
        from PIL import Image as PImage
        PImage.frombytes("RGBA", (self.width, self.height), self.rgba()).save(path)


# ------------------------------------------------------------------------------- small property resources
@dataclass
class Info:
    """0xE3F87B0F: u8 lot size (tiles per edge, 1..4), u8+name, u8+architect. The samples carry 8 more bytes
    (u32 0, u32 render id: equals the instance of the building's record in Apps/BARender/BAT.DAT for 13 of the
    15 rendered samples) that the shipped reader (0x1200B348) ignores and the shipped writer does not write."""
    lot: int
    name: str
    architect: str
    extra: bytes = b""

    @classmethod
    def parse(cls, b):
        r = R(b)
        return cls(r.u8(), r.str8(), r.str8(), r.rest())

    def to_bytes(self):
        return bytes([self.lot]) + s8(self.name) + s8(self.architect) + self.extra


@dataclass
class TexMeta:
    """0xE3F87B0D (instance n): embedded custom texture metadata (reader 0x1200ADBA, version 0x0A).
    rect = used pixel area (x0,y0,x1,y1) twice; uid -> texture+0x10; flags -> +0x14 (bit 3 cleared on load);
    width/height/1/width/1/height of the power-of-two image; name = file name used in the model's texture table;
    image_key = {type 0xE3F87B10, group, instance} of the pixels; category byte (7/6 paints/details?, 0x10 prop)."""
    version: int
    rect_a: tuple
    rect_b: tuple
    uid: int
    flags: int
    floats: tuple
    name: str
    image_key: tuple
    category: int | None
    tail: bytes = b""

    @classmethod
    def parse(cls, b):
        r = R(b)
        ver = r.u8()
        ra = tuple(r.i32() for _ in range(4))
        rb = tuple(r.i32() for _ in range(4))
        uid, flags = r.u32(), r.u32()
        fl = tuple(r.raw(4) for _ in range(4))
        name = r.str32()
        key = (r.u32(), r.u32(), r.u32())
        cat = r.u32() if ver >= 10 else None
        return cls(ver, ra, rb, uid, flags, fl, name, key, cat, r.rest())

    def to_bytes(self):
        b = bytes([self.version]) + struct.pack("<8i", *self.rect_a, *self.rect_b)
        b += struct.pack("<II", self.uid, self.flags) + b"".join(self.floats) + s32(self.name)
        b += struct.pack("<3I", *self.image_key)
        if self.category is not None:
            b += struct.pack("<I", self.category)
        return b + self.tail

    def float_values(self):
        return tuple(struct.unpack("<f", f)[0] for f in self.floats)


@dataclass
class PropMet:
    """0xFA662D17 (instance n): u8 version 0x0A, 4 x str32 view bitmaps, u32 x, y, z size in blocks (= one line of
    a .MET file: 'x,y,z:"v0","v1","v2","v3"')."""
    version: int
    views: list
    size: tuple
    tail: bytes = b""

    @classmethod
    def parse(cls, b):
        r = R(b)
        ver = r.u8()
        views = [r.str32() for _ in range(4)]
        size = (r.u32(), r.u32(), r.u32())
        return cls(ver, views, size, r.rest())

    def to_bytes(self):
        return bytes([self.version]) + b"".join(s32(v) for v in self.views) + struct.pack("<3I", *self.size) + self.tail


# ------------------------------------------------------------------------------------------ block geometry
# Shape table SIMBABLD 0x12078750: 16 shapes x 0x78 bytes = 8 face slots x 9 bytes {code, v0..v3, uv0..uv3}
# (v3/uv3 = FF for triangles, code FF ends the list), then at +0x48 four 6-byte lists (one per block rotation) of
# the faces visible from the BAT camera in back-to-front order (used by the face renderer SIMBABLD 0x1201F51C),
# then at +0x60 a second set of 4 lists that also contains faces seen edge-on (e.g. shape 1's diagonal).
# Face code byte: low 3 bits = facing direction (1 +y, 2 -x+y, 3 -x, 4 -x-y, 5 -y, 6 +x-y, 7 +x, 0 +x+y),
# high bits = slope class (0x00 vertical, 0x08 45 deg up, 0x10 top, 0x20 half slope, 0x28 45 deg down,
# 0x30 bottom, 0x38 plate); the paint tool (0x12039F42) maps 0x10/0x38 faces with the top-face rule.
_SHAPE_HEX = [
    "100407060500010203030506020100010203050607030200010203070704000300010203010405010000010203300003020100010203ff0000000000000000ff0000000000000000000304ffffff000203ffffff000102ffffff000104ffffff000304ffffff000203ffffff000102ffffff000104ffffff",
    "10040706ff000102ff02040602000001020305060703020001020307070400030001020330020300ff010203ffff0000000000000000ff0000000000000000ff00000000000000000003ffffffff000203ffffff0002ffffffff0001ffffffff000301ffffff000203ffffff000201ffffff0001ffffffff",
    "01040100ff000203ff0b040702010001020305070302ff010203ff070704000300010203300003020100010203ff0000000000000000ff0000000000000000ff00000000000000000003ffffffff0203ffffffff0102ffffffff0001ffffffff000301ffffff020301ffffff0102ffffffff0001ffffffff",
    "09070601ff000102ff0b040701ff000103ff05060703020001020307070400030001020301040100ff000203ff03060201ff010203ff300003020100010203ff0000000000000000000304ffffff0203ffffffff010502ffffff00050401ffff00030401ffff02030001ffff01050200ffff00050401ffff",
    "09070100ff000203ff0b070201ff010203ff05070302ff010203ff07070003ff000203ff300003020100010203ff0000000000000000ff0000000000000000ff00000000000000000003ffffffff0203ffffffff0102ffffffff0001ffffffff0003ffffffff0203ffffffff0102ffffffff0001ffffffff",
    "10040706050001020305060703ff000102ff07070400030001020301040500ff000103ff280506030000010203ff0000000000000000ff0000000000000000ff0000000000000000000203ffffff000102ffffff0001ffffffff0003ffffffff000203ffffff000102ffffff0001ffffffff0003ffffffff",
    "10040706ff000102ff03060201ff010203ff05060703020001020307070400030001020301040100ff000203ff1a040601ff000103ff300003020100010203ff000000000000000000030405ffff000203ffffff00010205ffff00010405ffff00030405ffff000203ffffff00010205ffff00010405ffff",
    "1a070200ff010203ff05070302ff010203ff07070003ff000203ff30020300ff010203ffff0000000000000000ff0000000000000000ff0000000000000000ff00000000000000000002ffffffff0102ffffffff0001ffffffff00ffffffffff0002ffffffff0102ffffffff0001ffffffff00ffffffffff",
    "380003020100010203ff0000000000000000ff0000000000000000ff0000000000000000ff0000000000000000ff0000000000000000ff0000000000000000ff000000000000000000ffffffffff00ffffffffff00ffffffffff00ffffffffff00ffffffffff00ffffffffff00ffffffffff00ffffffffff",
    "0104090100000602032304070a0900010203050703020a0102030407070400030001020303090a020104060203300003020100010203ff0000000000000000ff0000000000000000000301ffffff020301ffffff010204ffffff000104ffffff000301ffffff020301ffffff010204ffffff000104ffffff",
    "01080100ff040203ff23080b020100010203050b0302ff060203ff070b08000304060203300003020100010203ff0000000000000000ff0000000000000000ff0000000000000000000301ffffff020301ffffff0102ffffffff0001ffffffff000301ffffff020301ffffff0102ffffffff0001ffffffff",
    "21070609ff000102ff23040709ff000103ff050607030200010203070704000300010203010409010000060203030602010901020304300003020100010203ff000000000000000000030401ffff02030001ffff01050200ffff00050401ffff00030401ffff02030001ffff01050200ffff00050401ffff",
    "210b0a01ff000102ff23080b01ff000103ff050a0b030204060203070b0800030405020301080100ff040203ff030a0201ff060203ff300003020100010203ff000000000000000000030401ffff02030001ffff01050200ffff00050401ffff00030401ffff02030001ffff01050200ffff00050401ffff",
    "21070908ff000203ff23070a09ff010203ff050703020a0102030407070800030006020301080901000406020303090a020104060203300003020100010203ff000000000000000000030104ffff02030001ffff01020005ffff00010405ffff00030104ffff02030001ffff01020005ffff00010405ffff",
    "210b0100ff000203ff230b0201ff010203ff050b0302ff060203ff070b0003ff040203ff300003020100010203ff0000000000000000ff0000000000000000ff0000000000000000000301ffffff02030001ffff010200ffffff0001ffffffff000301ffffff02030001ffff010200ffffff0001ffffffff",
    "100407060500010203030506020100010203050607030200010203070704000300010203010405010000010203300003020100010203ff0000000000000000ff0000000000000000000304ffffff000203ffffff000102ffffff000104ffffff000304ffffff000203ffffff000102ffffff000104ffffff",
]

# Vertex positions in a unit cell (x, y, z), derived from the neighbour tables SIMBABLD 0x120795E0 (directions +
# vertex masks) and 0x12077A8C (neighbour vertex mapping): 0..3 bottom corners, 4..7 above them, 8..11 at half
# height above them.
VERTS = {0: (1, 1, 0), 1: (0, 1, 0), 2: (0, 0, 0), 3: (1, 0, 0)}
VERTS.update({v + 4: (x, y, 1) for v, (x, y, _) in list(VERTS.items())})
VERTS.update({v + 8: (x, y, 0.5) for v, (x, y, _) in list(VERTS.items()) if v < 4})
# Block rotation r (record bits 30-31) renames vertex v -> ROT[r][v] (SIMBABLD 0x12078258); vertex order
# 0->1->2->3 runs (1,1)->(0,1)->(0,0)->(1,0), i.e. r=1 turns the shape 90 degrees counter-clockwise (x right, y up).
ROT = [[(v & ~3) | ((v + r) & 3) for v in range(12)] for r in range(4)]
# texture corner ids used by the shape faces (u right, v down, in block-face units)
UV = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1), 4: (0, 0.5), 5: (1, 0.5), 6: (1, 0.5)}

SHAPE_NAMES = {
    0: "cube",
    1: "half-cube prism: vertical diagonal cut (0,0)-(1,1), keeps the +x/-y half",
    2: "wedge/ramp: full height along the +x edge, down to 0 at the -x edge",
    3: "valley corner: cube whose top (0,1) corner is pulled down to the floor (7 faces)",
    4: "hip corner pyramid: apex above corner (1,0), full square base",
    5: "inverted wedge: full top, underside slopes from the +x floor edge up to the -x top edge",
    6: "cube with the top (0,1) corner sliced off by one triangle (7 faces)",
    7: "tetrahedron on corner (1,0)",
    8: "floor plate (bottom face only; legacy ground cell)",
    9: "ramp from full height (+x) down to half height (-x)",
    10: "half-height ramp: half height at +x down to 0 at -x",
    11: "valley corner down to half height (7 faces)",
    12: "half-height valley corner (7 faces)",
    13: "pyramid corner (apex above (1,0)) on a half-height base (7 faces)",
    14: "half-height pyramid corner (apex at half height above (1,0))",
    15: "prop cell (cube geometry, drawn with the prop sprite of face slot rot+1)",
}


@dataclass
class ShapeFace:
    code: int
    verts: tuple
    uvs: tuple


def _parse_shapes():
    shapes = []
    for hx in _SHAPE_HEX:
        b = bytes.fromhex(hx)
        faces = []
        for k in range(8):
            it = b[9 * k:9 * k + 9]
            if it[0] == 0xFF:
                break
            nv = 4 if it[4] != 0xFF else 3
            faces.append(ShapeFace(it[0], tuple(it[1:1 + nv]), tuple(it[5:5 + nv])))
        draw = [[f for f in b[0x48 + 6 * r:0x48 + 6 * r + 6] if f != 0xFF] for r in range(4)]
        shapes.append((faces, draw))
    return shapes


SHAPES = _parse_shapes()

# Neighbour directions (SIMBABLD 0x120795E0, filled by 0x12011B53): (dx,dy,dz), vertex mask of my side, and the
# neighbour-vertex -> my-vertex map (0x12077A8C, 31 = not on the shared plane).
DIRS = [((0, 0, -1), 0x0F), ((0, 0, 1), 0xF0), ((0, 1, 0), 0x33), ((0, -1, 0), 0xCC), ((-1, 0, 0), 0x66),
        ((1, 0, 0), 0x99)]
NMAP = [
    [31, 31, 31, 31, 0, 1, 2, 3, 31, 31, 31, 31],
    [4, 5, 6, 7, 31, 31, 31, 31, 31, 31, 31, 31],
    [31, 31, 1, 0, 31, 31, 5, 4, 31, 31, 8, 9],
    [3, 2, 31, 31, 7, 6, 31, 31, 11, 10, 31, 31],
    [1, 31, 31, 2, 5, 31, 31, 6, 9, 31, 31, 10],
    [31, 0, 3, 31, 31, 4, 7, 31, 31, 8, 11, 31],
]
# Cube (shape 0, rotation 0) face slots
FACE_TOP, FACE_NX, FACE_NY, FACE_PX, FACE_PY, FACE_BOTTOM = range(6)
FACE_NAMES = ["top(+z)", "-x", "-y", "+x", "+y", "bottom(-z)"]


# ---------------------------------------------------------------------------------------------- model data
@dataclass
class Face:
    """4 bytes per face slot (record +8 + 4*slot); slot = index in the shape's face list.
    paint/detail = index into the model texture table (0 = none). *_uv = (u << 4) | v: which 16x16 cell of the
    texture this block face shows (u = column from the left, v = row from the top, both modulo the texture size
    in cells). For prop cells (shape 15) the four side slots hold the prop's view bitmaps and the uv bytes are
    signed sprite offsets."""
    paint: int = 0
    paint_uv: int = 0
    detail: int = 0
    detail_uv: int = 0

    def pack(self):
        return bytes((self.paint, self.paint_uv, self.detail, self.detail_uv))


@dataclass
class Block:
    x: int
    y: int
    z: int
    shape: int = 0
    rot: int = 0
    mask: int = 0                          # visible-face bitmask (bit = face slot); 0x100 = hidden marker
    faces: list = field(default_factory=lambda: [Face() for _ in range(6)])

    def d0(self, nxt):
        return (nxt & 0x1FFFF) | (self.z & 0x1FF) << 17 | (self.shape & 15) << 26 | (self.rot & 3) << 30

    def pack(self, nxt):
        return struct.pack("<II", self.d0(nxt), self.mask) + b"".join(f.pack() for f in self.faces)


def unpack_record(rec: bytes):
    d0, d1 = struct.unpack_from("<II", rec)
    faces = [Face(*rec[8 + 4 * k:12 + 4 * k]) for k in range(6)]
    return d0 & 0x1FFFF, (d0 >> 17) & 0x1FF, (d0 >> 26) & 15, d0 >> 30, d1, faces


@dataclass
class Model:
    """0xE3F87B0C, version 8 (reader 0x1200975B case 8 at 0x12009848, writer 0x1200A849):

      u8  version = 8
      u8  view_rot      (model+0x84, BAT view rotation 0..3. Rotating the view rotates the DATA: every column
                         moves (x,y) -> (g-1-y, x) per quarter turn and every block's rot += 1; cubes and prop
                         cells always carry rot == view_rot (all 17 samples). Thumbnails show the canonical
                         orientation = data rotated back by view_rot (rotate_blocks(-view_rot)). New files: 0.)
      u8  grid          (model+0x5C, cells per lot edge = 8 * lot; reader clamps to 0x30)
      u8  lot           (model+0x0C, tiles per edge; model init derives it as grid >> 3)
      u8  0xEA          (pad, ignored)
      u16 height        (model+0x60, z capacity in blocks; z < height)
      u16 0xEAEA        (ignored)
      u32 used          (model+0x68 = free-list head = 1 + number of blocks; record 0 is the null record)
      u32 0xEAEAEAEA, u32 4, u32 32, u32 0xEAEAEAEA, u32 grid*grid*4   (all ignored by the reader)
      grid x grid u32   column heads, x-major: head[x][y] = index of the lowest block of column (x, y), 0 = empty
      u32 0xEAEAEAEA
      u32 n, n bytes    compressed block: u32 n + RefPack of the first pool_bound(used) bytes of the record pool
      u32 0xEAEAEAEA
      u32 count, count x {str32 name, u32 uid}   texture table; index 0 unused; uid ignored by the reader
      u32 0xEAEAEAEA

    Record (32 bytes): u32 d0 = next(17) | z(9) << 17 | shape(4) << 26 | rot(2) << 30; u32 visible-face mask;
    6 x Face. Columns are singly linked lists sorted by strictly increasing z."""
    version: int = 8
    view_rot: int = 0
    grid: int = 8
    lot: int = 1
    height: int = 28
    used: int = 1
    heads: list = field(default_factory=list)      # heads[x][y]
    pool: bytes = b""                               # decompressed record pool (pool_bound(used) bytes)
    textures: list = field(default_factory=lambda: [("", 0)])
    pads: dict = field(default_factory=dict)        # raw pad/ignored fields for byte-exact round trip
    blob_raw: bytes | None = None
    _pool_raw: bytes | None = None

    # -- parse / serialize
    @classmethod
    def parse(cls, b: bytes) -> "Model":
        r = R(b)
        ver = r.u8()
        if ver != 8:
            raise NotImplementedError("model version %d (only 8 is handled; the loader also reads 4..7)" % ver)
        m = cls()
        m.version = ver
        m.view_rot, m.grid, m.lot = r.u8(), r.u8(), r.u8()
        m.pads["b4"] = r.u8()
        m.height = r.u16()
        m.pads["w7"] = r.u16()
        m.used = r.u32()
        m.pads["hdr5"] = tuple(r.u32() for _ in range(5))
        g = m.grid
        m.heads = [list(struct.unpack_from("<%dI" % g, b, r.o + 4 * g * x)) for x in range(g)]
        r.o += 4 * g * g
        m.pads["p_grid"] = r.u32()
        n = r.u32()
        m.blob_raw = r.raw(n)
        m.pool = decompress_block(m.blob_raw)
        m._pool_raw = m.pool
        m.pads["p_blob"] = r.u32()
        cnt = r.u32()
        m.textures = []
        for _ in range(cnt):
            name = r.str32()
            m.textures.append((name, r.u32()))
        m.pads["p_tex"] = r.u32()
        m.pads["tail"] = r.rest()
        return m

    def to_bytes(self) -> bytes:
        g = self.grid
        if len(self.heads) != g or any(len(c) != g for c in self.heads):
            raise ValueError("heads must be grid x grid")
        b = bytearray(struct.pack("<BBBBBHHI", self.version, self.view_rot, g, self.lot, self.pads.get("b4", PAD8),
                                  self.height, self.pads.get("w7", PAD16), self.used))
        b += struct.pack("<5I", *self.pads.get("hdr5", (PAD32, 4, 32, PAD32, g * g * 4)))
        for x in range(g):
            b += struct.pack("<%dI" % g, *self.heads[x])
        b += struct.pack("<I", self.pads.get("p_grid", PAD32))
        if self.blob_raw is not None and self.pool == self._pool_raw:
            blob = self.blob_raw
        else:
            blob = compress_block(self.pool)
        b += struct.pack("<I", len(blob)) + blob
        b += struct.pack("<II", self.pads.get("p_blob", PAD32), len(self.textures))
        for name, uid in self.textures:
            b += s32(name) + struct.pack("<I", uid)
        b += struct.pack("<I", self.pads.get("p_tex", PAD32)) + self.pads.get("tail", b"")
        return bytes(b)

    # -- blocks
    def record(self, k: int) -> bytes:
        return self.pool[32 * k:32 * k + 32]

    def blocks(self):
        """All blocks (column order x, y, z ascending) with their pool index."""
        out = []
        for x in range(self.grid):
            for y in range(self.grid):
                k = self.heads[x][y]
                seen = 0
                while k:
                    nxt, z, shape, rot, mask, faces = unpack_record(self.record(k))
                    blk = Block(x, y, z, shape, rot, mask, faces)
                    blk.index = k
                    out.append(blk)
                    k = nxt
                    seen += 1
                    if seen > 0x200:
                        raise ValueError("column loop at %d,%d" % (x, y))
        return out

    def set_blocks(self, blocks, textures=None):
        """Rebuild heads + pool from a block list, exactly like the BAT's compaction (0x1200D86E): records
        numbered in x, y, z order from 1, used = N + 1, free list used -> used+1 -> ... (z = 0x1FF), pool saved up to
        pool_bound(used) bytes."""
        if textures is not None:
            self.textures = list(textures)
        g = self.grid
        cols = {}
        for blk in blocks:
            if not (0 <= blk.x < g and 0 <= blk.y < g and 0 <= blk.z < self.height):
                raise ValueError("block out of bounds: %r" % ((blk.x, blk.y, blk.z),))
            cols.setdefault((blk.x, blk.y), []).append(blk)
        heads = [[0] * g for _ in range(g)]
        pool = bytearray(32)
        k = 1
        for x in range(g):
            for y in range(g):
                col = sorted(cols.get((x, y), []), key=lambda b_: b_.z)
                if len({b_.z for b_ in col}) != len(col):
                    raise ValueError("two blocks in one cell at %d,%d" % (x, y))
                if col:
                    heads[x][y] = k
                for j, blk in enumerate(col):
                    nxt = k + 1 if j + 1 < len(col) else 0
                    pool += blk.pack(nxt)
                    k += 1
        used = k
        if used > MAX_POOL:
            raise ValueError("too many blocks")
        bound = pool_bound(used)
        i = used
        while len(pool) < bound:
            pool += struct.pack("<II", (i + 1) & 0x1FFFF | 0x1FF << 17, 0) + b"\0" * 24
            i += 1
        self.heads, self.used, self.pool = heads, used, bytes(pool[:bound])

    def texture_index(self, name: str) -> int:
        """Index of a texture name in the table, appending it if needed (max 255 entries + the null slot)."""
        name = name.lower()                 # the loader lowercases names (0x12009AE7 -> _strlwr) before lookup
        for k, (n, _) in enumerate(self.textures):
            if k and n == name:
                return k
        if len(self.textures) >= 256:
            raise ValueError("texture table full (255)")
        self.textures.append((name, 0))
        return len(self.textures) - 1


# ------------------------------------------------------------------------------------- visibility masks
def face_bits(shape, rot, f):
    return sum(1 << ROT[rot][v] for v in SHAPES[shape][0][f].verts)


def compute_masks(blocks, grid, height, ground_v2=True, same_prop=None):
    """Recompute every block's visible-face mask the way SIMBABLD 0x12011C4A does: a face lying on a cell side
    is hidden when the neighbour block on that side has a face on the shared plane whose corner set contains it
    (blocks of different kind - prop vs non-prop - never hide each other; two prop cells only when same_prop()
    says they belong to one prop). With ground_v2 (flags byte 0 >= 2) the non-top faces of z=0 cubes that face out
    of the lot volume are hidden. The BAT updates masks incrementally while editing; in v1 files that leaves some
    harmless extra bits (e.g. bottom faces of the ground layer), so sample masks are not always reproduced."""
    at = {(b.x, b.y, b.z): b for b in blocks}
    for b in blocks:
        faces = SHAPES[b.shape][0]
        mask = 0
        for f in range(len(faces)):
            bits = face_bits(b.shape, b.rot, f)
            vis = True
            for d, ((dx, dy, dz), dmask) in enumerate(DIRS):
                if bits & dmask != bits:
                    continue
                q = (b.x + dx, b.y + dy, b.z + dz)
                if not (0 <= q[0] < grid and 0 <= q[1] < grid and 0 <= q[2] < height):
                    if ground_v2 and b.z == 0 and f != 0 and b.shape == 0:
                        vis = False
                    continue
                n = at.get(q)
                if n is None:
                    continue
                if (b.shape == 15) != (n.shape == 15):
                    continue
                if b.shape == 15 and not (same_prop and same_prop(b, n)):
                    continue
                for g_ in range(len(SHAPES[n.shape][0])):
                    nb = 0
                    for v in SHAPES[n.shape][0][g_].verts:
                        mv = NMAP[d][ROT[n.rot][v]]
                        if mv == 31:
                            nb = -1
                            break
                        nb |= 1 << mv
                    if nb >= 0 and nb & bits == bits:
                        vis = False
                        break
                if not vis:
                    break
            if vis:
                mask |= 1 << f
        b.mask = mask
    return blocks


def rotate_blocks(blocks, grid, k):
    """Rotate a block list by k quarter turns counter-clockwise (x right, y up), as the BAT's view rotation does:
    (x, y) -> (grid-1-y, x), rot += 1. Prop cells keep their 4 per-view offsets (the renderer picks slot rot+1)."""
    for b in blocks:
        for _ in range(k % 4):
            b.x, b.y = grid - 1 - b.y, b.x
        b.rot = (b.rot + k) & 3
    return blocks


# ------------------------------------------------------------------------------------------------- props
def prop_offsets(dx, dy, dz, rot=0):
    """Per-view sprite offsets of a prop cell relative to the prop's reference cell (derived from all prop cells of
    the samples, e.g. The Joneses' 3x3x4 tree): slot 1 = BAT view 0 (camera on +x,+y), slots 2..4 = the model
    turned 90/180/270 degrees CCW. u = screen x in half-cell units, v = screen y (down) with one z level = 2.
    (dx, dy) is the delta in the stored frame; cells carrying rot r (= view_rot) are first turned back by r."""
    for _ in range(rot & 3):
        dx, dy = dy, -dx
    return [(dy - dx, dx + dy - 2 * dz), (dx + dy, dx - dy - 2 * dz), (dx - dy, -dx - dy - 2 * dz),
            (-dx - dy, dy - dx - 2 * dz)]


def same_prop(a, b):
    """True when two adjacent prop cells (shape 15) belong to one placed prop: same 4 view bitmaps and offsets
    that differ exactly by the cell delta (two identical props side by side do not hide each other)."""
    if [f.paint for f in a.faces[1:5]] != [f.paint for f in b.faces[1:5]]:
        return False
    exp = prop_offsets(b.x - a.x, b.y - a.y, b.z - a.z, a.rot)
    for s in range(4):
        fa, fb = a.faces[1 + s], b.faces[1 + s]
        du = ((fb.paint_uv ^ 0x80) - 0x80) - ((fa.paint_uv ^ 0x80) - 0x80)
        dv = ((fb.detail_uv ^ 0x80) - 0x80) - ((fa.detail_uv ^ 0x80) - 0x80)
        if (du, dv) != exp[s]:
            return False
    return True


def read_met_files():
    """All prop definitions: {bitmap stem: [(sx, sy, sz, [v0, v1, v2, v3]) per orientation]} from
    Res\\BA\\PROPS\\*\\*.MET and BACustom\\Props\\*.met. A MET line is  x,y,z:"v0.bmp","v1.bmp","v2.bmp","v3.bmp"
    (size in blocks for that orientation, then the bitmaps seen from views 0..3); lines come in orientation order."""
    import re
    out = {}
    roots = [os.path.join(APPS, "Res", "BA", "PROPS"), os.path.join(APPS, "BACustom", "Props")]
    for root in roots:
        for dp, _, fs in os.walk(root):
            for f in fs:
                if not f.lower().endswith(".met"):
                    continue
                for line in open(os.path.join(dp, f), encoding="latin-1").read().splitlines():
                    mo = re.match(r"\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*:\s*(.*)", line)
                    if not mo:
                        continue
                    views = re.findall(r'"([^"]+)"', mo.group(4))
                    if len(views) != 4:
                        continue
                    stem = views[0].rsplit(" ", 1)[0].rsplit(".", 1)[0].lower()
                    out.setdefault(stem, []).append((int(mo.group(1)), int(mo.group(2)), int(mo.group(3)),
                                                     [v.lower() for v in views]))
    return out


def place_prop(bld, met_line, cx, cy, z0=1, rot=None):
    """Place one prop (one MET line = one orientation) with its footprint centred on cell (cx, cy) and its bottom at
    z0, like the BAT's prop tool: one shape-15 cell per block of the x*y*z volume (clipped to the lot / height),
    faces 1..4 = the 4 view bitmaps, uv bytes = signed offsets of the cell from the reference cell
    (cx, cy, z0 + (sz-1)//2) per view. Reference/clipping rule from the samples (LIKELY); NOT tested in the BAT."""
    sx, sy, sz, views = met_line
    m = bld.model
    rot = m.view_rot if rot is None else rot
    tex = [m.texture_index(v) for v in views]
    x0, y0 = cx - (sx - 1) // 2, cy - (sy - 1) // 2
    rz = z0 + (sz - 1) // 2
    cells = []
    for x in range(x0, x0 + sx):
        for y in range(y0, y0 + sy):
            for z in range(z0, z0 + sz):
                if not (0 <= x < m.grid and 0 <= y < m.grid and 0 < z < m.height):
                    continue
                blk = bld.add_block(x, y, z, shape=15, rot=rot)
                for s, (u, v) in enumerate(prop_offsets(x - cx, y - cy, z - rz, rot)):
                    blk.faces[1 + s] = Face(tex[s], u & 0xFF, 0, v & 0xFF)
                cells.append(blk)
    return cells


# --------------------------------------------------------------------------------------------- building
@dataclass
class Building:
    entries: list                          # IXF entries in file order (data kept for unknown types)
    slots: int = IXF_SLOTS
    model: Model | None = None
    info: Info | None = None
    description: str | None = None
    building_type: int | None = None
    b9ec: int | None = None
    flags: bytes | None = None
    registration: tuple | None = None      # (str, u32)
    thumbnail: Image | None = None
    tex_meta: dict = field(default_factory=dict)
    tex_image: dict = field(default_factory=dict)
    prop_met: dict = field(default_factory=dict)
    path: str | None = None

    @classmethod
    def load(cls, path) -> "Building":
        bld = cls.parse(open(path, "rb").read())
        bld.path = path
        return bld

    @classmethod
    def parse(cls, blob: bytes) -> "Building":
        entries, slots = read_ixf(blob)
        b = cls(entries, slots)
        for e in entries:
            if e.group != GROUP:
                continue
            t, d = e.type, e.data
            if t == T_MODEL:
                b.model = Model.parse(d)
            elif t == T_INFO:
                b.info = Info.parse(d)
            elif t == T_DESC:
                b.description = R(d).str8()
                e.extra = d[1 + d[0]:] if d else b""
            elif t == T_BTYPE:
                b.building_type = struct.unpack_from("<I", d)[0]
            elif t == T_B9EC:
                b.b9ec = struct.unpack_from("<I", d)[0]
            elif t == T_FLAGS:
                b.flags = bytes(d)
            elif t == T_REG:
                r = R(d)
                b.registration = (r.str32(), r.u32())
            elif t == T_THUMB:
                b.thumbnail = Image.parse(d)
            elif t == T_TEXMETA:
                b.tex_meta[e.instance] = TexMeta.parse(d)
            elif t == T_TEXIMG:
                b.tex_image[e.instance] = Image.parse(d)
            elif t == T_PROPMET:
                b.prop_met[e.instance] = PropMet.parse(d)
        return b

    def to_bytes(self) -> bytes:
        out = []
        for e in self.entries:
            t, d = e.type, e.data
            if e.group == GROUP:
                if t == T_MODEL and self.model:
                    d = self.model.to_bytes()
                elif t == T_INFO and self.info:
                    d = self.info.to_bytes()
                elif t == T_DESC and self.description is not None:
                    d = s8(self.description) + getattr(e, "extra", b"")
                elif t == T_BTYPE and self.building_type is not None:
                    d = struct.pack("<I", self.building_type) + d[4:]
                elif t == T_B9EC and self.b9ec is not None:
                    d = struct.pack("<I", self.b9ec) + d[4:]
                elif t == T_FLAGS and self.flags is not None:
                    d = self.flags
                elif t == T_REG and self.registration is not None:
                    d = s32(self.registration[0]) + struct.pack("<I", self.registration[1])
                elif t == T_THUMB and self.thumbnail:
                    d = self.thumbnail.to_bytes()
                elif t == T_TEXMETA and e.instance in self.tex_meta:
                    d = self.tex_meta[e.instance].to_bytes()
                elif t == T_TEXIMG and e.instance in self.tex_image:
                    d = self.tex_image[e.instance].to_bytes()
                elif t == T_PROPMET and e.instance in self.prop_met:
                    d = self.prop_met[e.instance].to_bytes()
            out.append(Entry(e.group, e.instance, t, d))
        return write_ixf(out, self.slots)

    def save(self, path):
        open(path, "wb").write(self.to_bytes())

    # -- construction
    @classmethod
    def new(cls, name="New Building", architect="Maxis", lot=1, description="", building_type=0x208,
            height=None, ground="grass.tga", view_rot=0):
        """A fresh project like the BAT's 'New Building': ground layer of cubes at z = 0 (top painted with the
        landscape texture), flags = 02 00 1C 00 (the newer ground mode, as in Longview Park)."""
        if lot not in (1, 2, 3, 4, 5):
            raise ValueError("lot must be 1..4 (5 = BAT Plus 5x5)")
        g = GRID_PER_TILE * lot
        m = Model(view_rot=view_rot, grid=g, lot=lot, height=height or DEFAULT_HEIGHT[lot])
        b = cls(entries=[], model=m, info=Info(lot, name, architect), description=description,
                building_type=building_type, b9ec=1, flags=bytes((2, 0, 0x1C, 0)))
        b._blocks = []
        gi = m.texture_index(ground) if ground else 0
        for x in range(g):
            for y in range(g):
                blk = Block(x, y, 0)
                if gi:
                    blk.faces[FACE_TOP] = Face(gi, top_uv(x, y, ground_size(ground)))
                b._blocks.append(blk)
        return b

    def blocks(self):
        if getattr(self, "_blocks", None) is None:
            self._blocks = self.model.blocks()
        return self._blocks

    def block_at(self, x, y, z):
        for blk in self.blocks():
            if (blk.x, blk.y, blk.z) == (x, y, z):
                return blk
        return None

    def add_block(self, x, y, z, shape=0, rot=0):
        old = self.block_at(x, y, z)
        if old:
            self._blocks.remove(old)
        blk = Block(x, y, z, shape, rot)
        self._blocks.append(blk)
        return blk

    def finalize(self, thumbnail=True):
        """Recompute masks, rebuild the pool, (re)build the resource list in the BAT's order, render a thumbnail."""
        m = self.model
        ground_v2 = bool(self.flags and self.flags[0] >= 2)
        compute_masks(self.blocks(), m.grid, m.height, ground_v2, same_prop)
        m.set_blocks(self.blocks())
        m.blob_raw = None
        if thumbnail:
            self.thumbnail = render_thumbnail(self)
        e = [Entry(GROUP, I_MODEL, T_MODEL, b"")]
        for k in sorted(self.tex_meta):
            e.append(Entry(GROUP, k, T_TEXMETA, b""))
            e.append(Entry(GROUP, k, T_TEXIMG, b""))
            if k in self.prop_met:
                e.append(Entry(GROUP, k, T_PROPMET, b""))
        e += [Entry(GROUP, I_INFO, T_INFO, b""), Entry(GROUP, I_DESC, T_DESC, b"\0"),
              Entry(GROUP, I_BTYPE, T_BTYPE, b"\0" * 4), Entry(GROUP, I_B9EC, T_B9EC, b"\0" * 4),
              Entry(GROUP, I_FLAGS, T_FLAGS, b"\0" * 4)]
        if self.registration is not None:
            e.append(Entry(GROUP, I_REG, T_REG, b""))
        if self.thumbnail:
            e.append(Entry(GROUP, I_THUMB, T_THUMB, b""))
        self.entries = e
        return self

    def props(self, mets=None):
        """Group prop cells into placed props: views (4 bitmaps = one MET line), reference cell (x, y, z) in the
        stored frame (the cell whose 4 offsets are all 0; may lie outside the lot when the prop was clipped),
        the matching MET line index (orientation) when the bitmaps are found in a .MET, and the cells."""
        cells = [b_ for b_ in self.blocks() if b_.shape == 15]
        names = [n for n, _ in self.model.textures]
        groups = []
        for c in cells:
            u1, v1 = (c.faces[1].paint_uv ^ 0x80) - 0x80, (c.faces[1].detail_uv ^ 0x80) - 0x80
            u2 = (c.faces[2].paint_uv ^ 0x80) - 0x80
            dx, dy = (u2 - u1) // 2, (u1 + u2) // 2          # canonical delta from the reference cell
            dz = (dx + dy - v1) // 2
            for _ in range(c.rot & 3):                        # back to the stored frame
                dx, dy = -dy, dx
            views = [names[f.paint] for f in c.faces[1:5]]
            key = (tuple(views), c.x - dx, c.y - dy, c.z - dz)
            for g_ in groups:
                if g_["key"] == key:
                    g_["cells"].append(c)
                    break
            else:
                groups.append({"key": key, "views": views, "ref": key[1:], "cells": [c], "met_line": None})
        if groups:
            mets = mets if mets is not None else read_met_files()
            for g_ in groups:
                stem = g_["views"][0].rsplit(" ", 1)[0].rsplit(".", 1)[0].lower()
                for k, line in enumerate(mets.get(stem, [])):
                    if line[3] == [v.lower() for v in g_["views"]]:
                        g_["met_line"] = (k, line[:3])
                        break
        return groups

    # -- summary
    def summary(self) -> dict:
        m = self.model
        blocks = m.blocks()
        shapes = {}
        levels = {}
        for blk in blocks:
            shapes[blk.shape] = shapes.get(blk.shape, 0) + 1
            levels[blk.z] = levels.get(blk.z, 0) + 1
        above = [b_ for b_ in blocks if b_.z > 0]
        bbox = None
        if above:
            bbox = [min(b_.x for b_ in above), min(b_.y for b_ in above), 1,
                    max(b_.x for b_ in above), max(b_.y for b_ in above), max(b_.z for b_ in above)]
        used = {}
        for blk in blocks:
            for f in blk.faces:
                for t in (f.paint, f.detail):
                    if t:
                        used[t] = used.get(t, 0) + 1
        names = [n for n, _ in m.textures]
        paints, details = {}, {}
        for blk in blocks:
            if blk.shape == 15:
                continue
            for f in blk.faces:
                if f.paint:
                    paints[names[f.paint]] = paints.get(names[f.paint], 0) + 1
                if f.detail:
                    details[names[f.detail]] = details.get(names[f.detail], 0) + 1
        props = self.props()
        return {
            "name": self.info.name if self.info else None,
            "architect": self.info.architect if self.info else None,
            "lot": self.info.lot if self.info else None,
            "description": self.description,
            "building_type": (hex(self.building_type), BUILDING_TYPES.get(self.building_type))
            if self.building_type is not None else None,
            "b9ec8f72": self.b9ec, "flags": self.flags.hex() if self.flags else None,
            "info_extra": self.info.extra.hex() if self.info and self.info.extra else "",
            "model": {"view_rot": m.view_rot, "grid": m.grid, "lot": m.lot, "height": m.height,
                      "used": m.used, "blocks": len(blocks), "pool_bytes": len(m.pool),
                      "pool_bound_ok": len(m.pool) == pool_bound(m.used),
                      "shapes": dict(sorted(shapes.items())), "max_z": max(levels) if levels else None,
                      "bbox_above_ground": bbox, "prop_cells": sum(len(p["cells"]) for p in props),
                      "textures": len(m.textures) - 1, "textures_used": len(used)},
            "top_paints": sorted(paints.items(), key=lambda kv: -kv[1])[:8],
            "top_details": sorted(details.items(), key=lambda kv: -kv[1])[:8],
            "props": [{"views": p["views"], "ref": p["ref"], "met_line": p["met_line"], "cells": len(p["cells"])}
                      for p in props],
            "embedded_textures": {k: (v.name, v.category, self.tex_image[k].width if k in self.tex_image else None)
                                  for k, v in self.tex_meta.items()},
            "embedded_props": {k: (v.views, v.size) for k, v in self.prop_met.items()},
            "thumbnail": (self.thumbnail.width, self.thumbnail.height, hex(self.thumbnail.kind))
            if self.thumbnail else None,
            "resources": [(hex(e.type), TYPE_NAMES.get(e.type, "?"), hex(e.instance), len(e.data))
                          for e in self.entries],
        }


# --------------------------------------------------------------------------------- built-in colour paints
# 220 solid colours the BAT registers at start-up as 16x16 textures named "color R,G,B" (SIMBABLD 0x1200301B loop
# over the u16 R,G,B table at 0x12069504, sprintf "color %d,%d,%d" at 0x120761A0; Baapp copy: table 0x480670).
# Only these exact names resolve; any other "color ..." name has no texture.
_COLOR_HEX = (
    "e8dcf4a2a1c960965cd2e1c0e1a8c08d998ff6f7f8ececa6f4f2fed6fd789ca2c2707296416f3a9cad88bf87a4687567adadb79b9d6898a0b2"
    "94af46576e944346671c421362774c6e5f804b5847515266484b274c5b725d6b1afcdfd9f3f4f8fdbac585bae294b46bf8cc3894b0f9f5bc7f"
    "f3deccd8a18dd29d93b0b1b2b78ba36190b960854abf7d26677ab5d6a2818d83849d796ba75b4b646462725d823d6793265126872f153d4575"
    "b3878328293c605249000000996565cc8787ffa8a8993232cc4343ff5454990000cc0000ff0000111111997865cca187ffc9a8995932cc7743"
    "ff9750993900cc4c00ff6000222222998c65ccbb87ffe9a8997f32ccaa43ffd454997300cc9900ffbf00333333929965c3cc87f4ffa88c9932"
    "bbcc43eaff54869900b2cc00dfff004444447f9965a9cc87d4ffa866993288cc43aaff544c990066cc0080ff005555556b99658fcc87b3ffa8"
    "3f993254cc436aff541399001acc0020ff0066666665997287cc98a8ffbe32994c43cc6554ff7f00992600cc3300ff4077777765998587ccb2"
    "a8ffde32997343cc9954ffbf00996000cc8000ff9f88888865999987cccca8ffff32999943cccc54ffff00999900cccc00ffff999999658599"
    "87b2cca8deff3273994399cc54bfff0060990080cc009fffaaaaaa6572998798cca8beff324c994365cc547fff0026990033cc0040ffbbbbbb"
    "6b65998f87ccb3a8ff3f32995443cc6a54ff1300991a00cc2000ffcccccc7f6599a987ccd4a8ff6632998843ccaa54ff4c00996600cc8000ff"
    "dddddd926599c387ccf4a8ff8c3299bb43ccea54ff860099b200ccdf00ffeeeeee99658ccc87bbffa8e999327fcc43aaff54d4990073cc0099"
    "ff00bfffffff996578cc87a1ffa8c9993259cc4377ff5494990039cc004cff0060")
COLOR_PAINTS = [tuple(bytes.fromhex(_COLOR_HEX[i:i + 6])) for i in range(0, len(_COLOR_HEX), 6)]


def color_paint(r, g, b):
    """Name of the built-in colour paint nearest to (r, g, b), e.g. 'color 204,0,0'."""
    c = min(COLOR_PAINTS, key=lambda q: (q[0] - r) ** 2 + (q[1] - g) ** 2 + (q[2] - b) ** 2)
    return "color %d,%d,%d" % c


# ------------------------------------------------------------------------------------- texture helpers
_TEX_CACHE: dict = {}


def find_texture_file(name):
    """Locate a texture/prop bitmap by file name the way the BAT's folders are laid out (Res\\BA\\PAINTS\\*,
    Res\\BA\\DETAILS\\**, Res\\BA\\PROPS\\**, BACustom\\**). Case-insensitive."""
    if not _TEX_CACHE:
        for root in (os.path.join(APPS, "Res", "BA"), os.path.join(APPS, "BACustom")):
            for dp, _, fs in os.walk(root):
                for f in fs:
                    if f.lower().endswith((".tga", ".bmp")):
                        _TEX_CACHE.setdefault(f.lower(), os.path.join(dp, f))
    return _TEX_CACHE.get(name.lower())


def texture_size(name):
    p = find_texture_file(name)
    if not p:
        return None
    try:
        from PIL import Image as PImage
        return PImage.open(p).size
    except Exception:
        return None


def ground_size(name):
    s = texture_size(name) if name else None
    return s or (128, 128)


def top_uv(x, y, size, x0=0, y0=0):
    """Paint-tool rule for top faces at view rotation 0 (SIMBABLD 0x1203A29C): u = (y0 - y - 1) mod W cells,
    v = (x0 - x) mod H cells (x0, y0 = where the paint stroke started)."""
    wc, hc = max(1, size[0] // 16), max(1, size[1] // 16)
    return (((y0 - y - 1) % wc) & 15) << 4 | (((x0 - x) % hc) & 15)


def wall_uv(along, z, size, z_top):
    """Side faces: u = cell index to the viewer's right along the wall, v = rows from the top
    (paint tool 0x12039F42: v = (z0 - z - 1) mod H cells)."""
    wc, hc = max(1, size[0] // 16), max(1, size[1] // 16)
    return ((along % wc) & 15) << 4 | (((z_top - z) % hc) & 15)


# ------------------------------------------------------------------------------------------ rendering
def _avg_color(name):
    if name and name.startswith("color "):
        try:
            return tuple(int(v) for v in name[6:].split(","))
        except ValueError:
            return None
    p = find_texture_file(name) if name else None
    if not p:
        return None
    try:
        from PIL import Image as PImage
        im = PImage.open(p).convert("RGBA")
        raw = im.tobytes()
        px = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
        px = [c for c in px if c[3] > 0 and c[:3] != (255, 0, 255)]
        if not px:
            return None
        return tuple(sum(c[i] for c in px) // len(px) for i in range(3))
    except Exception:
        return None


def render_iso(bld: Building, scale=4.0, size=None, bg=(219, 220, 226)):
    """Flat-shaded isometric preview (camera on the +x,+y side like the BAT's view 0: cube faces top, +x, +y are
    visible). Colours = average texel of each face's paint (detail if no paint), grey if unpainted."""
    from PIL import Image as PImage, ImageDraw
    m = bld.model
    blocks = bld.blocks()
    cols = {}
    names = [n for n, _ in m.textures]

    def col(k):
        if k not in cols:
            cols[k] = _avg_color(names[k]) if 0 < k < len(names) and names[k] else None
        return cols[k]

    light = {0x10: 1.0, 0x30: 0.4, 0x38: 0.4}

    def proj(px, py, pz):
        return ((py - px) * scale * 0.866, (px + py) * scale * 0.5 - pz * scale)

    g = m.grid
    zmax = max([b_.z for b_ in blocks] + [1]) + 1
    corners = [proj(cx, cy, cz) for cx in (0, g) for cy in (0, g) for cz in (0, zmax)]
    xs = [min(c[0] for c in corners), max(c[0] for c in corners)]
    ys = [min(c[1] for c in corners), max(c[1] for c in corners)]
    w, h = int(xs[1] - xs[0]) + 1, int(ys[1] - ys[0]) + 1
    W, H = size or (w + 8, h + 8)
    ox, oy = (W - w) / 2 - xs[0], (H - h) / 2 - ys[0]
    img = PImage.new("RGB", (W, H), bg)
    dr = ImageDraw.Draw(img)
    for blk in sorted(blocks, key=lambda b_: (b_.x + b_.y, b_.z)):
        faces, draw = SHAPES[blk.shape]
        for f in draw[blk.rot]:
            if not (blk.mask >> f) & 1 and blk.mask:
                continue
            sf = faces[f]
            fc = blk.faces[f] if f < 6 else Face()
            if blk.shape == 15:
                fc = blk.faces[(blk.rot & 3) + 1]
            c = col(fc.paint) or col(fc.detail) or ((150, 150, 150) if blk.shape != 15 else (90, 140, 70))
            pts = []
            for v in sf.verts:
                vx, vy, vz = VERTS[ROT[blk.rot][v]]
                sx, sy = proj(blk.x + vx, blk.y + vy, blk.z + vz)
                pts.append((sx + ox, sy + oy))
            code = sf.code
            k = light.get(code, None)
            if k is None:
                k = 0.85 if code in (0x03, 0x05) else 0.65 if code in (0x07, 0x01) else 0.8
                if code & 0x20 or code & 0x10:
                    k = 0.9
            dr.polygon(pts, fill=tuple(int(cc * k) for cc in c))
    return img


def render_thumbnail(bld: Building) -> Image:
    img = render_iso(bld, scale=24.0, bg=(255, 0, 255))
    from PIL import Image as PImage
    w, h = img.size
    s = min(190 / w, 190 / h)
    img = img.resize((max(1, int(w * s)), max(1, int(h * s))), PImage.NEAREST)
    canvas = PImage.new("RGB", (200, 200), (255, 0, 255))     # samples use magenta (RGB565 F81F) as background
    canvas.paste(img, ((200 - img.size[0]) // 2, (200 - img.size[1]) // 2))
    return Image.from_rgb565(200, 200, canvas.tobytes())


# ------------------------------------------------------------------------------------- minimal example
def example(path=None):
    """1x1 lot, grass ground, a 4x4-cell footprint, 2 blocks tall box with brick walls and a flat roof.
    NOT TESTED in the BAT or the game."""
    b = Building.new("Agent Box", "sc3k-mcp", lot=1, description="2-storey brick box", building_type=0x208)
    m = b.model
    brick, roof = "brick 04.tga", "flatr 01.tga"
    bi, ri = m.texture_index(brick), m.texture_index(roof)
    bsz, rsz = texture_size(brick) or (128, 128), texture_size(roof) or (128, 128)
    x0, x1, y0, y1 = 2, 5, 2, 5               # inclusive footprint (cells)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in (1, 2):
                blk = b.add_block(x, y, z)
                if x == x0:
                    blk.faces[FACE_NX] = Face(bi, wall_uv(y1 - y, z, bsz, 2))   # viewer's right = -y
                if x == x1:
                    blk.faces[FACE_PX] = Face(bi, wall_uv(y - y0, z, bsz, 2))   # viewer's right = +y
                if y == y0:
                    blk.faces[FACE_NY] = Face(bi, wall_uv(x - x0, z, bsz, 2))   # viewer's right = +x
                if y == y1:
                    blk.faces[FACE_PY] = Face(bi, wall_uv(x1 - x, z, bsz, 2))   # viewer's right = -x
                if z == 2:
                    blk.faces[FACE_TOP] = Face(ri, top_uv(x, y, rsz))
    b.finalize()
    if path:
        b.save(path)
    return b


# ---------------------------------------------------------------------------------------------- CLI
def _files(args):
    return args or sorted(glob.glob(os.path.join(BUILDINGS, "*.bld")))


def _print_summary(path):
    import json
    b = Building.load(path)
    s = b.summary()
    print("=" * 100)
    print(os.path.basename(path))
    print(json.dumps(s, indent=1, default=str))


def _roundtrip(path):
    orig = open(path, "rb").read()
    b = Building.parse(orig)
    same = b.to_bytes() == orig
    # re-encode the model from its block list and compare decoded geometry + texture table
    m = b.model
    blocks = m.blocks()
    m2 = Model(view_rot=m.view_rot, grid=m.grid, lot=m.lot, height=m.height, textures=list(m.textures),
               pads=dict(m.pads))
    m2.set_blocks(blocks)
    enc = m2.to_bytes()
    m3 = Model.parse(enc)
    geo_same = [(x.x, x.y, x.z, x.shape, x.rot, x.mask, [f.pack() for f in x.faces]) for x in m3.blocks()] == \
               [(x.x, x.y, x.z, x.shape, x.rot, x.mask, [f.pack() for f in x.faces]) for x in blocks]
    pool_same = m2.pool[:32 * m2.used] == m.pool[:32 * m.used]
    print("%-32s bytes %-6s re-encoded geometry %-5s pool[:used] identical %-5s (orig blob %d, recompressed %d)" % (
        os.path.basename(path), same, geo_same, pool_same, len(m.blob_raw), len(compress_block(m2.pool))))
    return same and geo_same


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "summary":
        for p in _files(args):
            _print_summary(p)
    elif cmd == "roundtrip":
        ok = all([_roundtrip(p) for p in _files(args)])
        print("ALL OK" if ok else "MISMATCH")
        return 0 if ok else 1
    elif cmd == "thumbs":
        out = args[0]
        os.makedirs(out, exist_ok=True)
        for p in _files(args[1:]):
            b = Building.load(p)
            base = os.path.splitext(os.path.basename(p))[0]
            if b.thumbnail:
                b.thumbnail.save_png(os.path.join(out, base + ".thumb.png"))
            for k, im in b.tex_image.items():
                im.save_png(os.path.join(out, "%s.tex%d.%s.png" % (base, k, b.tex_meta[k].name)))
    elif cmd == "render":
        render_iso(Building.load(args[0]), scale=float(args[2]) if len(args) > 2 else 12.0).save(args[1])
    elif cmd == "example":
        b = example(args[0])
        print("wrote", args[0], "blocks", len(b.blocks()), "used", b.model.used)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
