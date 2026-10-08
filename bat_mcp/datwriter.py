"""Write user-made buildings for SimCity 3000 directly (no Building Architect): the same IXF database the Architect's
render writes and the game loads from Apps\\BARender\\*.DAT (re/agents/batrender/REPORT.md, re/agents/replace/REPORT.md;
byte layout checked against Architect renders).

Per building (all records in one group):
- 0x856CD19A building record: u8 lot size, sprite-family key {0x6300, group, inst}, four strings (u32 length + bytes:
  name, architect, description, ""), u32 building id (= inst).
- 0x6300 "BIN\\r" sprite family: header (version 1, 0x7300, 5 zooms, 4 rotations, 4 zoom sets, 20 anim sets, 1 frame,
  0 reg rects, layer flags 0, 20 frames) and 20 frames {u16 index = zoom * 4 + rot, u32 group, u32 instance, s8 scale,
  s16 dx, s16 dy}. The Architect points zoom 5 at the zoom-4 images with scale 2; here zoom 5 can also have its own
  full-size images (scale 0).
- type 0 image per frame: u32 0x107, u32 0x80000, u32 w, u32 h, u32 packed size, RefPack data of: u32 size, u16 w,
  u16 h, u16 4, u16 7 (RGB565), u32 key 0xF81F, h rows {u32 first pixel, u16 left, u16 count | 0x8000 when the row
  has no key pixel}, then the RGB565 pixels of every row's span. Transparent = outside the span or 0xF81F.
- type 1 anchor (same instance as its image): s16 {0, h - w / 4, w, w / 4}: the lot diamond's left corner.
"""

from __future__ import annotations

import os
import struct
import time
import zlib

from PIL import Image

from sc3k_mcp.game import GameError

IXF_MAGIC = 0x80C381D7
T_BLD, T_FAM, T_IMG, T_ANC = 0x856CD19A, 0x6300, 0x0, 0x1
GROUP = 0xBA1DBF1E                     # the group the Architect's BAT.DAT uses for every user building
KEY565 = 0xF81F
INDEX_SLOTS = 1024                     # the Architect reserves 1024 index entries; kept for compatibility


# ------------------------------------------------------------------------------------------ RefPack
def refpack_compress(data: bytes) -> bytes:
    """RefPack / QFS compression (header 10 FB + 3-byte size): greedy LZ77 with a hash of 3-byte prefixes, using the
    four command forms the decoder (sprites.refpack) reads."""
    n = len(data)
    if n >= 1 << 24:
        raise ValueError("RefPack: data too large")
    out = bytearray(b"\x10\xfb" + n.to_bytes(3, "big"))
    heads: dict[bytes, list[int]] = {}
    i = lit = 0

    def flush_literals(upto: int, keep: int):
        """Emit literals data[lit:upto] in 4-byte multiples (0xE0 commands), leaving keep (0..3) for the next copy."""
        nonlocal lit, out
        while upto - lit - keep >= 4:
            k = min(112, ((upto - lit - keep) // 4) * 4)
            out.append(0xE0 + (k // 4 - 1))
            out += data[lit:lit + k]
            lit += k

    while i < n:
        best_len, best_off = 0, 0
        if i + 3 <= n:
            key = data[i:i + 3]
            cands = heads.get(key)
            if cands:
                for j in reversed(cands[-24:]):
                    off = i - j
                    if off > 131072:
                        break
                    m = 3
                    lim = min(1028, n - i)
                    while m + 16 <= lim and data[j + m:j + m + 16] == data[i + m:i + m + 16]:
                        m += 16
                    while m < lim and data[j + m] == data[i + m]:
                        m += 1
                    if m > best_len:
                        best_len, best_off = m, off
                        if m >= lim:
                            break
            heads.setdefault(key, []).append(i)
        # usable copy?
        ok = False
        if best_len >= 3 and best_off <= 1024 and best_len <= 10:
            ok = True
        elif best_len >= 4 and best_off <= 16384 and best_len <= 67:
            ok = True
        elif best_len >= 5 and best_off <= 131072:
            ok = True
        if not ok:
            i += 1
            continue
        flush_literals(i, (i - lit) % 4)
        plain = i - lit
        ln, off = best_len, best_off - 1
        if ln <= 10 and off < 1024:
            out += bytes((((off >> 3) & 0x60) | ((ln - 3) << 2) | plain, off & 0xFF))
        elif ln <= 67 and off < 16384:
            out += bytes((0x80 | (ln - 4), (plain << 6) | (off >> 8), off & 0xFF))
        else:
            ln = min(ln, 1028)
            out += bytes((0xC0 | ((off >> 12) & 0x10) | (((ln - 5) >> 6) & 0x0C) | plain, (off >> 8) & 0xFF, off & 0xFF,
                          (ln - 5) & 0xFF))
        out += data[lit:i]
        for k in range(i + 1, min(i + ln, n - 2)):
            heads.setdefault(data[k:k + 3], []).append(k)
        i += ln
        lit = i
    flush_literals(n, (n - lit) % 4)
    out.append(0xFC + (n - lit))
    out += data[lit:n]
    return bytes(out)


# ------------------------------------------------------------------------------------------ sprites
def encode_image(im: Image.Image) -> tuple[bytes, bytes]:
    """RGBA image (alpha >= 128 = opaque, else transparent) -> (image record, anchor record)."""
    import numpy as np
    a = np.asarray(im.convert("RGBA"), dtype=np.uint16)
    h, w = a.shape[:2]
    opaque = a[:, :, 3] >= 128
    v = ((a[:, :, 0] >> 3) << 11) | ((a[:, :, 1] >> 2) << 5) | (a[:, :, 2] >> 3)
    v[v == KEY565] = 0xF81E                       # never the key colour by accident
    v[~opaque] = KEY565
    rows, chunks, pos = [], [], 0
    for y in range(h):
        xs = np.flatnonzero(opaque[y])
        if xs.size == 0:
            rows.append((pos, w, 0x8000))              # empty row: left = width, as the Architect writes it
            continue
        left, right = int(xs[0]), int(xs[-1]) + 1
        span = v[y, left:right]
        has_key = bool((~opaque[y, left:right]).any())
        rows.append((pos, left, (right - left) | (0 if has_key else 0x8000)))
        chunks.append(span.astype("<u2").tobytes())
        pos += right - left
    body = struct.pack("<HHHHI", w, h, 4, 7, KEY565)
    body += b"".join(struct.pack("<IHH", s_, l_, c_) for s_, l_, c_ in rows) + b"".join(chunks)
    raw = struct.pack("<I", len(body) + 4) + body
    packed = refpack_compress(raw)
    rec = struct.pack("<5I", 0x107, 0x80000, w, h, len(packed)) + packed
    anchor = struct.pack("<4h", 0, h - w // 4, w, w // 4)
    return rec, anchor


def building_id(name: str) -> int:
    """A stable 32-bit instance id for a building name (never 0)."""
    return (zlib.crc32(("sc3k-mcp photo building:" + name).encode("utf-8")) & 0x7FFFFFFF) | 0x10000000


def _string(s: str) -> bytes:
    b = s.encode("cp1252", "replace")
    return struct.pack("<I", len(b)) + b


def building_records(name: str, architect: str, description: str, lot: int,
                     frames: dict[tuple[int, int], Image.Image], native_zoom5: bool = True,
                     inst: int | None = None) -> dict[tuple[int, int, int], bytes]:
    """All records of one building. frames: {(zoom 1..5, rotation 0..3): RGBA image}; zoom 5 optional (without it,
    or with native_zoom5 False, zoom 5 shows zoom 4 at scale 2 as the Architect does)."""
    if not 1 <= lot <= 5:
        raise GameError("lot size 1..5 tiles")
    inst = inst or building_id(name)
    img_base = (inst * 32) & 0xFFFFFFE0 or 0x20
    recs = {}
    fam_frames = []
    for z in range(1, 6):
        for r in range(4):
            idx = (z - 1) * 4 + r
            if z == 5 and (not native_zoom5 or (5, r) not in frames):
                fam_frames.append(struct.pack("<HIIbhh", idx, GROUP, img_base + 12 + r, 2, 0, 0))
                continue
            im = frames[(z, r)]
            rec, anc = encode_image(im)
            ii = img_base + idx
            recs[(T_IMG, GROUP, ii)] = rec
            recs[(T_ANC, GROUP, ii)] = anc
            fam_frames.append(struct.pack("<HIIbhh", idx, GROUP, ii, 0, 0, 0))
    fam = b"BIN\r" + struct.pack("<II", 1, 0x7300) + bytes((5, 4, 4, 20, 1, 0)) + struct.pack("<IH", 0, 20)
    recs[(T_FAM, GROUP, inst)] = fam + b"".join(fam_frames)
    recs[(T_BLD, GROUP, inst)] = (bytes((lot,)) + struct.pack("<3I", T_FAM, GROUP, inst) + _string(name) +
                                  _string(architect) + _string(description) + _string("") + struct.pack("<I", inst))
    return recs


def write_ixf(path: str, recs: dict[tuple[int, int, int], bytes]) -> None:
    """An IXF database: magic, index entries {group, instance, type, offset, size} (reserved to at least
    INDEX_SLOTS entries, ending with zeros), then the records."""
    items = sorted(recs.items(), key=lambda kv: (kv[0][0] != T_FAM, kv[0][0] == T_BLD, kv[0][2], kv[0][0]))
    slots = max(INDEX_SLOTS, len(items) + 1)
    off = 4 + 20 * slots
    index, blob = bytearray(), bytearray()
    for (t, g, i), d in items:
        index += struct.pack("<5I", g, i, t, off + len(blob), len(d))
        blob += d
    index += bytes(20 * slots - len(index))
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<I", IXF_MAGIC) + bytes(index) + bytes(blob))
    os.replace(tmp, path)


def read_ixf(path: str) -> dict[tuple[int, int, int], bytes]:
    from .sprites import ixf_records
    return ixf_records(open(path, "rb").read())


def _without(old: dict, insts: set) -> dict:
    """The records of a DAT minus the buildings with these instance ids (their building record, sprite family,
    images and anchors)."""
    img_bases = {((i * 32) & 0xFFFFFFE0 or 0x20) for i in insts}
    keep = {}
    for k, d in old.items():
        t, g, i = k
        if (t in (T_BLD, T_FAM) and i in insts) or (t in (T_IMG, T_ANC) and (i & 0xFFFFFFE0) in img_bases):
            continue
        keep[k] = d
    return keep


def _backup(dat_path: str) -> str:
    bak = dat_path + time.strftime(".%Y%m%d-%H%M%S.bak")
    with open(dat_path, "rb") as a, open(bak, "wb") as b:
        b.write(a.read())
    return bak


def install(recs: dict[tuple[int, int, int], bytes], dat_path: str) -> dict:
    """Add (or replace) a building's records in our own DAT in Apps\\BARender (the game loads every *.DAT there),
    keeping the other buildings in that file; a previous file is backed up first."""
    new_insts = {i for (t, g, i) in recs if t == T_BLD}
    keep = {}
    if os.path.exists(dat_path):
        old = read_ixf(dat_path)
        keep = _without(old, {i for (t, g, i) in old if t == T_BLD and i in new_insts})
        bak = _backup(dat_path)
    else:
        bak = None
    keep.update(recs)
    write_ixf(dat_path, keep)
    return {"file": dat_path, "backup": bak, "buildings": sorted(i for (t, g, i) in keep if t == T_BLD)}


def uninstall(insts: set, dat_path: str) -> dict:
    """Take buildings (instance ids) out of our DAT, keeping the others; the previous file is backed up first.
    An emptied file is removed (after its backup) so the game has nothing to load."""
    old = read_ixf(dat_path)
    keep = _without(old, set(insts))
    bak = _backup(dat_path)
    if any(t == T_BLD for (t, g, i) in keep):
        write_ixf(dat_path, keep)
    else:
        os.remove(dat_path)
    return {"file": dat_path, "backup": bak, "buildings": sorted(i for (t, g, i) in keep if t == T_BLD)}
