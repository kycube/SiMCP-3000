"""Images of buildings read from files, no screenshots (re/agents/batrender/REPORT.md, decoders verified on all 15
rendered buildings and all 17 sample projects).

- Rendered buildings (Apps\\BARender\\BAT.DAT or any render output DAT): IXF container; per building (group
  0xBA1DBF1E) a 0x856CD19A record (lot size, sprite-family key, name, architect...), a "BIN\\r" sprite family (type
  0x6300: 20 frames = 5 zooms x 4 rotations; zoom 5 = zoom 4 doubled) and the images (type 0: RefPack-packed RGB565
  rows with 0xF81F as transparent) with their anchors (type 1). These are exactly the pictures the game draws.
- Projects (*.bld): the same container (group 0xC3F8D4A9): header (lot size, name, architect, building id) and a
  200x200 RGB565 thumbnail = the Architect's own preview of the building.
"""

from __future__ import annotations

import os
import struct

from PIL import Image

IXF_MAGIC = 0x80C381D7
KEY = 0xF81F
T_BLD, T_FAM, T_IMG, T_ANC = 0x856CD19A, 0x6300, 0x0, 0x1
T_HDR, T_THUMB, T_MODEL = 0xE3F87B0F, 0xE3F87B0E, 0xE3F87B0C
PIXELS_PER_TILE = {1: 8, 2: 16, 3: 32, 4: 64, 5: 128}


def refpack(src: bytes) -> bytes:
    """RefPack / QFS decompression (header 10 FB)."""
    flags = src[0] << 8 | src[1]
    i = 2
    if flags & 0x0100:
        i += 3
    size = src[i] << 16 | src[i + 1] << 8 | src[i + 2]
    i += 3
    out = bytearray()
    while i < len(src):
        b0 = src[i]
        if b0 < 0x80:
            b1 = src[i + 1]
            i += 2
            plain, cnt, off = b0 & 3, ((b0 >> 2) & 7) + 3, ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            b1, b2 = src[i + 1], src[i + 2]
            i += 3
            plain, cnt, off = b1 >> 6, (b0 & 0x3F) + 4, ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:
            b1, b2, b3 = src[i + 1], src[i + 2], src[i + 3]
            i += 4
            plain, cnt, off = b0 & 3, ((b0 & 0x0C) << 6) + b3 + 5, ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            i += 1
            plain, cnt, off = ((b0 & 0x1F) << 2) + 4, 0, 0
        else:
            i += 1
            plain = b0 & 3
            out += src[i:i + plain]
            break
        out += src[i:i + plain]
        i += plain
        for _ in range(cnt):
            out.append(out[-off])
    return bytes(out[:size])


def ixf_records(blob: bytes) -> dict[tuple[int, int, int], bytes]:
    """{(type, group, instance): data} of an IXF file (index entries {group, instance, type, offset, size})."""
    if struct.unpack_from("<I", blob, 0)[0] != IXF_MAGIC:
        raise ValueError("not an IXF file")
    recs, o = {}, 4
    while o + 20 <= len(blob):
        g, i, t, off, sz = struct.unpack_from("<5I", blob, o)
        o += 20
        if g == 0 and i == 0 and t == 0:
            break
        if t != 0xFFFFFFFF:
            recs[(t, g, i)] = blob[off:off + sz]
    return recs


def _rgb565_to_rgba(px: bytes, n: int) -> bytearray:
    out = bytearray(n * 4)
    for k in range(n):
        v = px[2 * k] | px[2 * k + 1] << 8
        if v == KEY:
            continue
        r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
        out[4 * k:4 * k + 4] = bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2), 255))
    return out


def decode_sprite(d: bytes) -> Image.Image:
    """A rendered building image (type 0 record) -> RGBA (transparent outside the building)."""
    _fmt, _x2, w0, h0, _packed = struct.unpack_from("<5I", d)
    px = refpack(d[20:])
    _size, w, h, _a, pf, key = struct.unpack_from("<IHHHHI", px)
    if (w, h) != (w0, h0) or pf != 7 or key != KEY:
        raise ValueError(f"unexpected image format {w}x{h} pf {pf} key {key:#x}")
    base = 16 + 8 * h
    rgba = bytearray(w * h * 4)
    for y in range(h):
        off, left, cnt = struct.unpack_from("<IHH", px, 16 + 8 * y)
        cnt &= 0x7FFF
        row = _rgb565_to_rgba(px[base + 2 * off:base + 2 * (off + cnt)], cnt)
        k = (y * w + left) * 4
        rgba[k:k + 4 * cnt] = row
    return Image.frombytes("RGBA", (w, h), bytes(rgba))


def _strings(d: bytes, o: int, n: int, wide_len: bool) -> tuple[list[str], int]:
    out = []
    for _ in range(n):
        if wide_len:
            ln = struct.unpack_from("<I", d, o)[0]
            o += 4
        else:
            ln = d[o]
            o += 1
        out.append(d[o:o + ln].decode("latin-1"))
        o += ln
    return out, o


class RenderedSet:
    """The buildings in a render output DAT (default the game's Apps\\BARender\\BAT.DAT)."""

    def __init__(self, path: str):
        self.path = path
        self.recs = ixf_records(open(path, "rb").read())
        self.buildings = []
        for (t, g, i), d in sorted(self.recs.items(), key=lambda kv: kv[0][2]):
            if t != T_BLD:
                continue
            strs, o = _strings(d, 13, 4, True)
            fam_key = struct.unpack_from("<3I", d, 1)
            fam = self.recs.get(fam_key)
            frames = []
            if fam and fam[:4] == b"BIN\r":
                rots, nf = fam[13], struct.unpack_from("<H", fam, 22)[0]
                for k in range(nf):
                    idx, fg, fi, scale, _dx, _dy = struct.unpack_from("<HIIBhh", fam, 24 + 15 * k)
                    zoom, rot = divmod(idx, rots)
                    frames.append({"zoom": zoom + 1, "rotation": rot, "group": fg, "instance": fi, "scale": scale})
            self.buildings.append({"name": strs[0], "architect": strs[1], "description": strs[2] if len(strs) > 2
                                   else "", "size": d[0], "id": i, "group": g, "frames": frames})

    def find(self, name_or_id) -> dict:
        s = str(name_or_id).lower()
        for b in self.buildings:
            if b["name"].lower() == s or f"{b['id']:#x}" == s or str(b["id"]) == s:
                return b
        raise KeyError(f"no rendered building {name_or_id!r}; have {[b['name'] for b in self.buildings]}")

    def image(self, b: dict, zoom: int, rotation: int) -> Image.Image:
        fr = next((f for f in b["frames"] if f["zoom"] == zoom and f["rotation"] == rotation), None)
        if fr is None:
            raise KeyError(f"no frame zoom {zoom} rotation {rotation}")
        img = decode_sprite(self.recs[(T_IMG, fr["group"], fr["instance"])])
        if fr["scale"] > 1:
            img = img.resize((img.width * fr["scale"], img.height * fr["scale"]), Image.NEAREST)
        return img

    def anchor(self, b: dict, zoom: int, rotation: int):
        fr = next(f for f in b["frames"] if f["zoom"] == zoom and f["rotation"] == rotation)
        a = self.recs.get((T_ANC, fr["group"], fr["instance"]))
        return list(struct.unpack("<4h", a)) if a else None


def sheet(images: list[Image.Image], gap: int = 8, background=(0, 0, 0, 0)) -> Image.Image:
    """Images side by side, bottom-aligned."""
    W = sum(i.width for i in images) + gap * (len(images) - 1)
    H = max(i.height for i in images)
    out = Image.new("RGBA", (W, H), background)
    x = 0
    for im in images:
        out.alpha_composite(im, (x, H - im.height))
        x += im.width + gap
    return out


def project_info(path: str) -> dict:
    """Header of a .bld project: lot size, name, architect, building id; whether it has a thumbnail / model."""
    recs = ixf_records(open(path, "rb").read())
    by_type = {t: d for (t, _g, _i), d in recs.items()}
    out = {"file": path}
    if T_HDR in by_type:
        d = by_type[T_HDR]
        strs, o = _strings(d, 1, 2, False)
        # the building id is only there once the project has been rendered (a new project's header ends here)
        bid = struct.unpack_from("<II", d, o)[1] if len(d) >= o + 8 else None
        out.update({"size": d[0], "name": strs[0], "architect": strs[1], "building_id": bid})
    out["has_thumbnail"] = T_THUMB in by_type
    out["has_model"] = T_MODEL in by_type
    return out


def project_thumbnail(path: str) -> Image.Image:
    """The 200x200 preview the Architect stores in a .bld (its own render of the building)."""
    recs = ixf_records(open(path, "rb").read())
    d = next((d for (t, _g, _i), d in recs.items() if t == T_THUMB), None)
    if d is None:
        raise KeyError("this project has no thumbnail (saved before it was previewed?)")
    _fmt, w, h, _n = struct.unpack_from("<HHHI", d)
    px = refpack(d[10:])
    return Image.frombytes("RGBA", (w, h), bytes(_rgb565_to_rgba(px, w * h)))


# ------------------------------------------------------------------------------------------ the game's own sprites
# Apps\Res\Sprites\*.DAT hold the game's building sprites (North American set); BuildingSets\<id>\*.dat the European
# (e523f3fb) and Asian (6523f3d5) replacements. Same IXF / RefPack format as BAT.DAT. A sprite's instance is
# occupant_id << 16 | frame; frames 0..15 = zoom 1..4 x rotation 0..3 (zoom 5 is zoom 4 drawn twice as large).
GAME_SPRITE_SETS = {"north_american": "", "european": os.path.join("BuildingSets", "e523f3fb"),
                    "asian": os.path.join("BuildingSets", "6523f3d5")}
_GAME_INDEX: dict[str, dict[int, list]] = {}


def _ixf_index(path: str) -> list[tuple[int, int, int, int, int]]:
    """(type, group, instance, offset, size) of every record, reading only the index."""
    out = []
    with open(path, "rb") as f:
        if struct.unpack("<I", f.read(4))[0] != IXF_MAGIC:
            return out
        while True:
            e = f.read(20)
            if len(e) < 20:
                break
            g, i, t, off, sz = struct.unpack("<5I", e)
            if g == 0 and i == 0 and t == 0:
                break
            if t != 0xFFFFFFFF:
                out.append((t, g, i, off, sz))
    return out


def game_sprite_index(style: str = "north_american") -> dict[int, list]:
    """{occupant id: [(path, instance, offset, size) of its images]} for one building style."""
    if style not in GAME_SPRITE_SETS:
        raise ValueError(f"style: one of {list(GAME_SPRITE_SETS)}")
    if style not in _GAME_INDEX:
        from .app import APPS
        root = os.path.join(APPS, "Res", "Sprites", GAME_SPRITE_SETS[style])
        idx: dict[int, list] = {}
        for fn in sorted(os.listdir(root)):
            p = os.path.join(root, fn)
            if not fn.lower().endswith(".dat") or not os.path.isfile(p):
                continue
            for t, g, i, off, sz in _ixf_index(p):
                if t == T_IMG:
                    idx.setdefault(i >> 16, []).append((p, i, off, sz))
        _GAME_INDEX[style] = idx
    return _GAME_INDEX[style]


def game_sprite(entry) -> Image.Image:
    p, _i, off, sz = entry
    with open(p, "rb") as f:
        f.seek(off)
        return decode_sprite(f.read(sz))


def game_building_frames(occupant: int, style: str = "north_american") -> dict[tuple[int, int], tuple]:
    """{(zoom 1..4, rotation 0..3): index entry} of a game building's sprites."""
    out = {}
    for e in game_sprite_index(style).get(occupant, []):
        k = e[1] & 0xFFFF
        if k < 16:
            out[(k // 4 + 1, k % 4)] = e
    return out
