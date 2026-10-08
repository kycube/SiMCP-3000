"""The building being edited in the Building Architect, through the program's own functions
(re/agents/baapp/REPORT.md; verified live 2026-10-08: new 1x1 building via the New Building dialog, 64 cube blocks
via SetBlock, brick / roof paint via the model's paint function, saved as a .bld, view pixels read from memory).

Grid: 8 cells per tile; a 1x1 lot is 8 x 8 cells and 28 high (2x2 16 x 64, 3x3 24 x 108, 4x4 32 x 144, 5x5 40 x 80).
z = 0 is the ground layer the program creates; buildings start at z = 1. A block = shape (0..15) + rotation (0..3);
faces 0 top, 1..4 sides, 5 bottom.
"""

from __future__ import annotations

import os
import struct
import time

from PIL import Image

from sc3k_mcp.game import GameError

M_GLOBAL = 0x4954E0              # BA manager
WM_GLOBAL = 0x497124             # GZ window manager (cached service)
FN_CURRENT_MODEL = 0x40F6AD      # cdecl -> model
FN_DEFAULT_BLOCK = 0x409FD9      # this = 32-byte block buffer
FN_FIND_BLOCK = 0x40B977         # model: (pos*, incl15, 0) -> index
FN_SET_BLOCK = 0x40BA33          # model: (pos*, block*)
FN_REMOVE_BLOCK = 0x40C5FF       # model: (pos*)
FN_PAINT = 0x40DFD8              # model: (block*, face, item*)
FN_DECAL = 0x40E0B4              # model: (block*, face, item*)
FN_UNDO, FN_REDO = 0x40F5DD, 0x40F622
FN_BBOX = 0x40F336               # model: (model+0x6C)
FN_REDRAW = 0x43628E             # view: (1)
FN_STR_APPEND = 0x44F39B         # BaString: append char*
FN_ROTATE = 0x43A8E5             # view: (+1 / -1, 1) = the Rotate button / Space: turns the building on its lot
FN_PAINT_UV = 0x40E042           # model: (block*, face, item*, uv)
FN_DECAL_UV = 0x40E11E           # model: (block*, face, item*, uv)
REPLAYING = 0x1B0                # model byte: set while the program replays its undo log (edits are not logged)
# library L = *(M+0x1C) (re/agents/batlib/REPORT.md)
FN_LOAD_CATEGORY = 0x419A77      # L: (cat) load every item of a category (what opening its palette tab does; idempotent)
FN_ADD_FILE = 0x41926E           # L: (cat, BaString* path) add one .bmp / .tga file (the folder scan's per-file call)
FN_PARSE_MET = 0x41885D          # L: (cat, BaString* met) read a prop definition file
FN_FIND_ID = 0x418705            # L: (id, Item**)
FN_REGISTER = 0x419697           # L: (BaString* name) load an item's image and register its id
FN_SET_IMAGE = 0x4178D8          # item: (image | 0)
FN_FIND_PROP = 0x4187B5          # L: (view0 id, PropRec**) (AddRefs)
FN_PROP_RELEASE = 0x40B8D7       # PropRec: ()
FN_STR_CTOR = 0x402C4C           # BaString: (char*)
FN_STR_DTOR = 0x450A28           # BaString: ()
CUSTOM_CATEGORY = {"paint": 6, "detail": 7, "prop": 16}
MSG_NEW = 0x63CC6994
MSG_EDITED = 0x63CC69AD
MSG_VIEW = 0x63CC69B7            # {3, 0x63CC69A6, mode} = set mode as the tabs do
MODE_SETMODE = 0x63CC69A6
SIZE_RADIO = 0xA2FBB0B6          # New Building Tile Size dialog: radio group; items 0x75C408C9 + (size - 1)
SIZE_ITEM0 = 0x75C408C9
RESULT_OK, RESULT_CANCEL = 0x05C3F90C, 0x05C3F90D   # that dialog's DoModal results
BTN_NO = 0x53018149              # message box "No"
MODES = {"construct": 0, "paint": 1, "detail": 2, "props": 3, "file": 4}
CATEGORIES = {0: "ground", 1: "roofs", 2: "walls", 3: "colors", 4: "details_contemporary",
              5: "details_traditional", 6: "custom_paints", 7: "custom_details", 8: "props_architecture",
              9: "props_building_decoration", 10: "props_plaza_and_street", 11: "props_yard_objects",
              12: "props_flora", 13: "props_industrial", 14: "props_rooftops", 15: "props_vehicles",
              16: "custom_props"}
PAINT_CATEGORIES = {0, 1, 2, 3, 6}
DETAIL_CATEGORIES = {4, 5, 7}
BUILDING_TYPES = ["residential", "commercial", "industrial", "police_station", "jail", "fire_station", "hospital",
                  "school", "college", "library", "museum", "historic_statue", "mayors_house", "city_hall",
                  "performing_arts_center", "other"]
FOOTPRINT = {1: 8, 2: 16, 3: 24, 4: 32, 5: 40}
SCRATCH = 0x8000                 # offset in the bridge scratch buffer used here (0x8000..0xFFFF)


# A shape's face slots carry a direction code (bldfile.SHAPES; the Fill tool 0x43BC71 compares them): 16 top,
# 48 bottom, 0..7 a vertical side, +8 a steep (45 degree) slope, +32 a shallow (half-height) slope; the low 3 bits are
# the direction (odd = along an axis, even = diagonal) and a block's rotation adds 2 per quarter turn.
DIR_NAMES = {7: "+x", 1: "+y", 3: "-x", 5: "-y", 0: "+x+y", 2: "-x+y", 4: "-x-y", 6: "+x-y"}
CUBE_FACE = {"+x": 3, "-x": 1, "+y": 4, "-y": 2}          # cube slot of each axis direction
NO_PAINT_SHAPES = (8, 15)                                 # floor plate, prop cell


def slot_info(shape: int, rot: int) -> list[dict]:
    """The face slots of a shape at a rotation: kind (top / bottom / side / slope), world direction and the
    rotated direction code."""
    from . import bldfile
    out = []
    for slot, sf in enumerate(bldfile.SHAPES[shape][0]):
        c = sf.code
        if c == 16 or c == 48:
            out.append({"slot": slot, "kind": "top" if c == 16 else "bottom", "dir": None, "code": c})
        else:
            d = ((c & 7) + 2 * rot) & 7
            out.append({"slot": slot, "kind": "side" if c < 8 else "slope", "dir": DIR_NAMES[d],
                        "code": (c & ~7) | d})
    return out


def slot_label(info: dict) -> str:
    return info["kind"] if info["dir"] is None else (info["dir"] if info["kind"] == "side" else f"slope {info['dir']}")


def uv_face(info: dict) -> int:
    """The cube face whose texture layout a slot follows: tops and slopes like a top, axis sides like that side,
    diagonal sides like their x side."""
    if info["kind"] in ("top", "slope"):
        return 0
    if info["kind"] == "bottom":
        return 5
    d = info["dir"]
    return CUBE_FACE.get(d) or CUBE_FACE[d[:2]]


def resolve_slot(face, info: list[dict]) -> int:
    """A face given as a slot number or a name: top, bottom, +x, -x, +y, -y, a diagonal such as -x+y, slope (any
    sloped face) or slope -x."""
    if isinstance(face, int) or (isinstance(face, str) and face.strip().lstrip("-").isdigit()):
        k = int(face)
        if not 0 <= k < len(info):
            raise GameError(f"face {k}: this shape has slots 0..{len(info) - 1} "
                            f"({', '.join(slot_label(i) for i in info)})")
        return k
    name = str(face).strip().lower().replace("slope", "slope ").replace("  ", " ").strip()
    for i in info:
        lab = slot_label(i)
        if name == lab or (name == "slope" and i["kind"] == "slope"):
            return i["slot"]
    raise GameError(f"face {face!r}: this block's faces are {', '.join(slot_label(i) for i in info)}")


def raw_visible(raw: bytes, face: int) -> bool:
    """A block record's visible-face bit (kept up to date by SetBlock: set when no neighbour covers the face)."""
    return bool(struct.unpack_from("<I", raw, 4)[0] >> face & 1)


class Architect:
    def __init__(self, app):
        self.a = app
        # per-call undo: the model's undo log (entries 0x14 bytes at +0x1B4, position +0xA01A0) has no step markers
        # for programmatic edits, so each edit call records its (start, end) log positions here
        self._actions: list[tuple[int, int, int]] = []     # (model, start, end)
        self._redo: list[tuple[int, int, int]] = []
        self._loaded: set[tuple[int, int]] = set()          # (library, category) loaded this session

    # ------------------------------------------------------------ objects
    def manager(self) -> int:
        M = self.a.u32(M_GLOBAL)
        if not M:
            raise GameError("the Building Architect is not ready")
        return M

    def view(self) -> int:
        return self.a.u32(self.a.u32(self.manager() + 0x2C) + 0xA4)

    def screen(self) -> int:
        return self.a.i32(self.a.u32(self.manager() + 0x2C) + 0xCC)

    def model(self, need: bool = True) -> int:
        m = self.a.call(FN_CURRENT_MODEL)
        if need and (not m or self.screen() != 2):
            raise GameError("no building is open: new_building or open_building first")
        return m

    def wm(self) -> int:
        return self.a.u32(WM_GLOBAL)

    def modal(self) -> int:
        wm = self.wm()
        return self.a.u32(wm + 0x30) if self.a.i32(wm + 0x194) > 0 else 0

    def end_modal(self, result: int) -> None:
        wm = self.wm()
        self.a.call(self.a.vfn(wm, 0x44 // 4), [0xD, self.modal(), result], this=wm)

    def _wait(self, cond, timeout: float = 10.0, what: str = "the Building Architect") -> None:
        t = time.time()
        while not cond():
            if time.time() - t > timeout:
                raise GameError(f"timed out waiting for {what}")
            time.sleep(0.1)

    # ------------------------------------------------------------ strings
    def _set_string(self, at: int, text: str) -> None:
        """Replace a BaString's text: truncate (end = begin) then the program's own append."""
        buf = self.a.scratch() + SCRATCH
        self.a.proc.write(at + 8, struct.pack("<I", self.a.u32(at + 4)))
        self.a.proc.write(buf, text.encode("cp1252", "replace") + b"\0")
        self.a.call(FN_STR_APPEND, [buf], this=at)

    # ------------------------------------------------------------ new / open / save
    def new_building(self, size: int) -> None:
        """As the New Building button: the program's own New Building message and Tile Size dialog (an unsaved
        current building is discarded: its "save?" question is answered No)."""
        if size not in FOOTPRINT:
            raise GameError("size must be 1..5 (tiles a side)")
        if self.modal():
            raise GameError("a dialog is open in the Building Architect")
        from sc3k_mcp.lifecycle import Lifecycle
        L = Lifecycle(self.a)
        self.a.post_message(MSG_NEW)
        self._wait(lambda: self.modal(), what="the New Building dialog")
        win = self.modal()
        if any("save" in w["text"].lower() for w in L.widgets(win)):
            self.end_modal(BTN_NO)
            self._wait(lambda: self.modal() and self.modal() != win, what="the Tile Size dialog")
            win = self.modal()
        grp = next((w for w in L.widgets(win) if w["id"] == SIZE_RADIO), None)
        if not grp:
            self.end_modal(RESULT_CANCEL)
            raise GameError("unexpected dialog instead of the Tile Size dialog")
        iface = grp["window"] + 0xA4
        self.a.call(self.a.vfn(iface, 0x34 // 4), [SIZE_ITEM0 + size - 1], this=iface)
        old = self.a.call(FN_CURRENT_MODEL)
        self.end_modal(RESULT_OK)
        self._wait(lambda: not self.modal() and self.screen() == 2 and self.a.call(FN_CURRENT_MODEL) != old
                   and self.a.i32(self.a.call(FN_CURRENT_MODEL) + 0x5C) == FOOTPRINT[size], what="the new building")

    def open_building(self, path: str) -> None:
        """M vt[0x34](path, &model) (the Load dialog's own load), make it current, show the toolkit."""
        if self.modal():
            raise GameError("a dialog is open in the Building Architect")
        M = self.manager()
        buf = self.a.scratch() + SCRATCH
        self.a.proc.write(buf, struct.pack("<I", 0))
        self.a.proc.write(buf + 0x10, path.encode("cp1252") + b"\0")
        if not self.a.call(self.a.vfn(M, 0x34 // 4), [buf + 0x10, buf], this=M) & 0xFF:
            raise GameError(f"the Building Architect could not load {path}")
        m = self.a.u32(buf)
        self.a.call(self.a.vfn(M, 0x30 // 4), [m, 0], this=M)
        self.a.call(0x40A8D9, [], this=m)
        self.a.post_message(0x63CC69B9, 1)
        self.a.post_message(0x63CC699D)
        self._wait(lambda: self.screen() == 2 and self.a.call(FN_CURRENT_MODEL) == m, what="the building to open")

    def save_building(self, path: str) -> None:
        M, m = self.manager(), self.model()
        buf = self.a.scratch() + SCRATCH
        self.a.proc.write(buf, path.encode("cp1252") + b"\0")
        self.a.call(self.a.vfn(M, 0x38 // 4), [m, buf], this=M)
        if not os.path.exists(path):
            raise GameError(f"the Building Architect did not write {path}")

    def current_path(self) -> str:
        return self.a.rz_string(self.manager() + 0x34, 1024)

    # ------------------------------------------------------------ properties
    def properties(self) -> dict:
        a, m = self.a, self.model()
        t = a.i32(m + 0x4C)
        return {"name": a.rz_string(m + 0x24), "architect": a.rz_string(m + 0x10),
                "description": a.rz_string(m + 0x38, 4096),
                "type": BUILDING_TYPES[t - 0x208] if 0x208 <= t <= 0x217 else "other",
                "lot_tiles": a.i32(m + 0x5C) // 8, "footprint_cells": a.i32(m + 0x5C),
                "max_height_cells": a.i32(m + 0x60), "blocks": a.i32(m + 0x68),
                "unsaved_changes": bool(a.proc.read(m + 0x190, 1)[0]), "file": self.current_path()}

    def set_properties(self, name=None, architect=None, description=None, building_type=None) -> dict:
        m = self.model()
        for off, v in ((0x24, name), (0x10, architect), (0x38, description)):
            if v is not None:
                self._set_string(m + off, v)
        if building_type is not None:
            if building_type not in BUILDING_TYPES:
                raise GameError(f"building_type: one of {BUILDING_TYPES}")
            self.a.proc.write(m + 0x4C, struct.pack("<i", 0x208 + BUILDING_TYPES.index(building_type)))
        self.a.proc.write(m + 0x190, b"\x01")
        return self.properties()

    # ------------------------------------------------------------ blocks
    def cells(self, include_ground: bool = False) -> dict[tuple, bytes]:
        """{(x, y, z): the block's 32-byte record} read from the model's column lists (d0 bits 0-16 next, 17-25 z,
        26-29 shape, 30-31 rotation; d1 bit f = face f visible; then 6 faces {paint slot, paint uv, detail slot,
        detail uv}; slots index the model's texture table)."""
        a, m = self.a, self.model()
        n = a.i32(m + 0x5C)
        pool = a.u32(m + 0x8C)
        cols = struct.unpack(f"<{n}I", a.proc.read(a.u32(m + 0x90), 4 * n))
        out = {}
        for x, col in enumerate(cols):
            heads = struct.unpack(f"<{n}I", a.proc.read(col, 4 * n))
            for y, idx in enumerate(heads):
                k = 0
                while idx and k < 512:
                    raw = a.proc.read(pool + 32 * idx, 32)
                    bits = struct.unpack_from("<I", raw)[0]
                    z = (bits >> 17) & 0x1FF
                    if z or include_ground:
                        out[(x, y, z)] = raw
                    idx, k = bits & 0x1FFFF, k + 1
        return out

    def blocks(self, include_ground: bool = False) -> list[dict]:
        names = self._texture_names(self.model())
        out = []
        for (x, y, z), raw in self.cells(include_ground).items():
            bits = struct.unpack_from("<I", raw)[0]
            faces = {}
            for f in range(6):
                ps, pp, ds, dp = raw[8 + 4 * f:12 + 4 * f]
                if ps or ds:
                    faces[f] = {k2: v for k2, v in (("paint", names.get(ps) if ps else None),
                                                   ("detail", names.get(ds) if ds else None)) if v}
            shape, rot = (bits >> 26) & 0xF, bits >> 30
            extra = {}
            if shape not in (0,) + NO_PAINT_SHAPES:
                extra["slots"] = [slot_label(i) for i in slot_info(shape, rot)]
            out.append({"x": x, "y": y, "z": z, "shape": shape, "rotation": rot, **extra,
                        **({"faces": faces} if faces else {})})
        return out

    def _texture_items(self, m: int) -> dict[int, int]:
        """Texture-table slot -> library item pointer."""
        raw = self.a.proc.read(self.a.u32(m + 0x1AC), 8 * 256)
        return {s: struct.unpack_from("<I", raw, 8 * s + 4)[0] for s in range(1, 256)
                if struct.unpack_from("<I", raw, 8 * s + 4)[0]}

    def _texture_names(self, m: int) -> dict[int, str]:
        tab = self.a.u32(m + 0x1AC)
        raw = self.a.proc.read(tab, 8 * 256)
        out = {}
        for s in range(1, 256):
            ref, item = struct.unpack_from("<II", raw, 8 * s)
            if item:
                out[s] = self.a.rz_string(item + 0x48)
        return out

    def _check_pos(self, m: int, x: int, y: int, z: int) -> None:
        n, h = self.a.i32(m + 0x5C), self.a.i32(m + 0x60)
        if not (0 <= x < n and 0 <= y < n and 1 <= z < h):
            raise GameError(f"cell ({x}, {y}, {z}) is outside the building volume: x, y 0..{n - 1}, z 1..{h - 1}")

    def set_blocks(self, blocks: list[dict]) -> int:
        """Place blocks {x, y, z, shape (0..15, default cube 0), rotation (0..3)} with the model's SetBlock."""
        _mark = self.begin()
        try:
            a, m = self.a, self.model()
            base = a.scratch() + SCRATCH + 0x100
            for i in range(0, len(blocks), 12):
                chunk = blocks[i:i + 12]
                calls = []
                for k, b in enumerate(chunk):
                    x, y, z = int(b["x"]), int(b["y"]), int(b["z"])
                    self._check_pos(m, x, y, z)
                    shape, rot = int(b.get("shape", 0)), int(b.get("rotation", 0))
                    if not (0 <= shape <= 15 and 0 <= rot <= 3):
                        raise GameError("shape 0..15, rotation 0..3")
                    blk, pos = base + 0x40 * k, base + 0x40 * k + 0x20
                    a.proc.write(blk, struct.pack("<II", (rot << 30) | (shape << 26) | (z << 17), 0xFF) + b"\0" * 24)
                    a.proc.write(pos, struct.pack("<3i", x, y, z))
                    calls.append((FN_SET_BLOCK, m, [pos, blk]))
                a.call_seq(calls)
            self.refresh()
            return a.i32(m + 0x68)

        finally:
            self.end(_mark)

    def remove_blocks(self, cells: list[dict]) -> int:
        """Remove the blocks in these cells with the model's RemoveBlock."""
        _mark = self.begin()
        try:
            a, m = self.a, self.model()
            base = a.scratch() + SCRATCH + 0x100
            for i in range(0, len(cells), 12):
                calls = []
                for k, c in enumerate(cells[i:i + 12]):
                    x, y, z = int(c["x"]), int(c["y"]), int(c["z"])
                    self._check_pos(m, x, y, z)
                    a.proc.write(base + 0x10 * k, struct.pack("<3i", x, y, z))
                    calls.append((FN_REMOVE_BLOCK, m, [base + 0x10 * k]))
                a.call_seq(calls)
            self.refresh()
            return a.i32(m + 0x68)
        finally:
            self.end(_mark)

    def library(self) -> list[dict]:
        a = self.a
        L = a.u32(self.manager() + 0x1C)
        b, e = a.u32(L + 0x3C), a.u32(L + 0x40)
        out = []
        for p in struct.unpack(f"<{(e - b) // 4}I", a.proc.read(b, e - b)) if e > b else ():
            cat = a.proc.read(p + 0xC, 1)[0]
            out.append({"name": a.rz_string(p + 0x48), "category": CATEGORIES.get(cat, str(cat)), "_cat": cat,
                        "_item": p})
        return out

    def find_item(self, name: str, kinds: set[int]) -> int:
        """The library item with this name (the newest one, as the program's own name lookup), its category loaded
        first: stock items get their image, id and texture only when their category is loaded (opening the palette
        tab does it), and an unloaded item draws as a grey untextured face."""
        s = name.lower()
        hits = [i for i in self.library() if i["_cat"] in kinds and
                (i["name"].lower() == s or os.path.splitext(i["name"])[0].lower() == s)]
        if not hits:
            raise GameError(f"no texture {name!r} (library lists them)")
        self.load_category(hits[-1]["_cat"])
        return hits[-1]["_item"]

    def library_object(self) -> int:
        L = self.a.u32(self.manager() + 0x1C)
        if not L:
            raise GameError("the Building Architect's library is not ready")
        return L

    def load_category(self, cat: int) -> None:
        L = self.library_object()
        if (L, cat) not in self._loaded:
            self.a.call(FN_LOAD_CATEGORY, [cat], this=L)
            self._loaded.add((L, cat))

    def _bastring(self, text: str, at: int) -> int:
        """Construct a BaString at scratch offset `at` holding text (destroy with FN_STR_DTOR)."""
        a = self.a
        obj, buf = a.scratch() + at, a.scratch() + at + 0x20
        a.proc.write(obj, bytes(0x14))
        a.proc.write(buf, text.encode("cp1252") + b"\0")
        a.call(FN_STR_CTOR, [buf], this=obj)
        return obj

    def _add_file(self, cat: int, path: str) -> dict:
        """Add one custom file to the running library with the folder scan's own per-file call (it loads the image
        and registers its id at once for the custom categories); a file added before is reloaded in place."""
        a, L = self.a, self.library_object()
        want = os.path.normcase(os.path.abspath(path))
        old = [i for i in self.library() if i["_cat"] == cat and
               os.path.normcase(a.rz_string(i["_item"] + 0x5C, 1024)) == want]
        if old:
            item = old[-1]["_item"]
            a.call(FN_SET_IMAGE, [0], this=item)
            a.call(FN_REGISTER, [item + 0x48], this=L)
            how = "reloaded"
        else:
            s = self._bastring(path, SCRATCH + 0x400)
            try:
                ok = a.call(FN_ADD_FILE, [cat, s], this=L) & 0xFF
            finally:
                a.call(FN_STR_DTOR, [], this=s)
            if not ok:
                raise GameError(f"the Building Architect did not accept {path}")
            item = a.u32(a.u32(L + 0x40) - 4)
            how = "added"
        name = a.rz_string(item + 0x48)
        tex, iid = a.u32(item + 8), a.u32(item + 0x10)
        if a.proc.read(item + 0xC, 1)[0] != cat or not tex or not iid:
            raise GameError(f"{path} was added but its picture did not load")
        buf = a.scratch() + SCRATCH + 0x700
        a.proc.write(buf, bytes(4))
        a.call(FN_FIND_ID, [iid, buf], this=L)
        same = a.u32(buf)
        out = {"name": name, how: True, "id": iid}
        if same and same != item:
            out["note"] = f"the picture is identical to {a.rz_string(same + 0x48)!r}"
        return out

    def load_custom(self, path: str, kind: str) -> dict:
        """Make a new BACustom file usable in the running Architect (re/agents/batlib/REPORT.md section 5): paints /
        details are added as one item; a prop adds its four view bitmaps, then reads its .met and registers it."""
        cat = CUSTOM_CATEGORY[kind]
        if kind != "prop":
            return {"library": self._add_file(cat, path)}
        from . import bldfile
        folder = os.path.dirname(path)
        lines = [ln for ln in open(path, encoding="latin-1").read().splitlines() if ln.strip()]
        views = []
        for ln in lines:
            for v in ln.split(":", 1)[1].split(","):
                v = v.strip().strip('"')
                if v and v not in views:
                    views.append(v)
        items = [self._add_file(cat, os.path.join(folder, v)) for v in views]
        for it in items:
            it.pop("note", None)                     # identical views are normal for a symmetric prop
        a, L = self.a, self.library_object()
        s = self._bastring(path, SCRATCH + 0x400)
        try:
            a.call(FN_PARSE_MET, [cat, s], this=L)
        finally:
            a.call(FN_STR_DTOR, [], this=s)
        a.call(FN_LOAD_CATEGORY, [cat], this=L)
        self._loaded.add((L, cat))
        buf = a.scratch() + SCRATCH + 0x700
        a.proc.write(buf, bytes(4))
        a.call(FN_FIND_PROP, [items[0]["id"], buf], this=L)
        rec = a.u32(buf)
        if not rec:
            raise GameError(f"the Building Architect did not register the prop in {path}")
        size = [a.i32(rec + 0x18), a.i32(rec + 0x1C), a.i32(rec + 0x20)]
        a.call(FN_PROP_RELEASE, [], this=rec)
        bldfile._TEX_CACHE.clear()
        return {"library": items, "prop_registered": True, "prop_size": size}

    def paint(self, faces: list[dict], detail: bool = False) -> int:
        """Paint (or put a detail / decal on) block faces {x, y, z, face (0 top, 1..4 sides, 5 bottom), texture}:
        the model's own paint function on a copy of the block, committed with SetBlock (as the Paintbrush)."""
        _mark = self.begin()
        try:
            a, m = self.a, self.model()
            fn = FN_DECAL if detail else FN_PAINT
            kinds = DETAIL_CATEGORIES if detail else PAINT_CATEGORIES
            items: dict[str, int] = {}
            pool = a.u32(m + 0x8C)
            base = a.scratch() + SCRATCH + 0x100
            done = 0
            by_cell: dict[tuple, list] = {}
            for f in faces:
                by_cell.setdefault((int(f["x"]), int(f["y"]), int(f["z"])), []).append(f)
            for (x, y, z), fl in by_cell.items():
                a.proc.write(base, struct.pack("<3i", x, y, z))
                idx = a.call(FN_FIND_BLOCK, [base, 1, 0], this=m)
                if not idx:
                    raise GameError(f"no block at ({x}, {y}, {z}) to paint")
                blk = base + 0x20
                a.proc.write(blk, a.proc.read(pool + 32 * idx, 32))
                calls = []
                for f in fl:
                    face = int(f.get("face", 0))
                    if not 0 <= face <= 5:
                        raise GameError("face: 0 top, 1..4 sides, 5 bottom")
                    t = f.get("texture")
                    if t:
                        if t not in items:
                            items[t] = self.find_item(t, kinds)
                        item = items[t]
                    else:
                        item = 0
                    calls.append((fn, m, [blk, face, item]))
                calls.append((FN_SET_BLOCK, m, [base, blk]))
                for i in range(0, len(calls), 14):
                    a.call_seq(calls[i:i + 14])
                done += len(fl)
            self.refresh()
            return done
        finally:
            self.end(_mark)

    # ------------------------------------------------------------ texture-mapped painting and props
    # side face slots: 1 -x, 2 -y, 3 +x, 4 +y (bldfile: geometry tables + renders matching the thumbnails)
    SIDE_DIRS = {1: (-1, 0), 2: (0, -1), 3: (1, 0), 4: (0, 1)}

    def _along(self, face: int, x: int, y: int, g: int) -> int:
        """Cell index to the viewer's right along the wall seen from outside (the paint tool's u rule)."""
        return {3: y, 1: g - 1 - y, 4: g - 1 - x, 2: x}[face]

    def _check_faces(self, faces: list[dict], kinds: set[int]) -> None:
        """Check a whole paint / detail request before anything changes (all or nothing): every cell has a block,
        every face name exists on that block, every texture exists. Lists all problems at once."""
        cells = self.cells(include_ground=True)
        missing, bad, names = [], [], set()
        for f in faces:
            c = (int(f["x"]), int(f["y"]), int(f["z"]))
            raw = cells.get(c)
            if raw is None:
                missing.append(c)
                continue
            bits = struct.unpack_from("<I", raw)[0]
            try:
                resolve_slot(f.get("face", 0), slot_info((bits >> 26) & 0xF, bits >> 30))
            except GameError as e:
                bad.append(f"{c}: {e}")
            if f.get("texture"):
                names.add(f["texture"])
        unknown = []
        lib = [i for i in self.library() if i["_cat"] in kinds]
        for t in names:
            s = t.lower()
            if not any(i["name"].lower() == s or os.path.splitext(i["name"])[0].lower() == s for i in lib):
                unknown.append(t)
        if missing or bad or unknown:
            parts = []
            if missing:
                parts.append(f"{len(missing)} cells have no block, e.g. {sorted(set(missing))[:6]}")
            if bad:
                parts.append(f"{len(bad)} faces do not exist: {bad[:3]}")
            if unknown:
                parts.append(f"unknown textures {sorted(unknown)} (library lists them)")
            raise GameError("nothing was changed: " + "; ".join(parts))

    def paint_mapped(self, faces: list[dict], detail: bool = False) -> int:
        """Paint faces {x, y, z, face, texture[, u, v]} with the texture laid out continuously the way the
        Architect's Paintbrush does (each 16x16 cell of a texture covers one block face): u = position along the
        wall (to the viewer's right), v = rows down from the top of the painted area; top faces by x / y. The
        model's own paint-with-offset function (0x40E042; details 0x40E11E) on a copy of each block, committed
        with SetBlock."""
        self._check_faces(faces, DETAIL_CATEGORIES if detail else PAINT_CATEGORIES)
        _mark = self.begin()
        try:
            from . import bldfile
            a, m = self.a, self.model()
            g = a.i32(m + 0x5C)
            fn = 0x40E11E if detail else 0x40E042
            kinds = DETAIL_CATEGORIES if detail else PAINT_CATEGORIES
            items: dict[str, int] = {}
            sizes: dict[str, tuple] = {}
            ztop: dict[str, int] = {}
            for f in faces:
                t = f.get("texture")
                if t and str(f.get("face", 0)) not in ("0", "top", "5", "bottom") and "slope" not in str(f.get("face")):
                    ztop[t] = max(ztop.get(t, 0), int(f["z"]))
            pool = a.u32(m + 0x8C)
            base = a.scratch() + SCRATCH + 0x100
            by_cell: dict[tuple, list] = {}
            for f in faces:
                by_cell.setdefault((int(f["x"]), int(f["y"]), int(f["z"])), []).append(f)
            n = 0
            for (x, y, z), fl in by_cell.items():
                a.proc.write(base, struct.pack("<3i", x, y, z))
                idx = a.call(FN_FIND_BLOCK, [base, 1, 0], this=m)
                if not idx:
                    raise GameError(f"no block at ({x}, {y}, {z}) to paint")
                blk = base + 0x20
                raw = a.proc.read(pool + 32 * idx, 32)
                a.proc.write(blk, raw)
                bits = struct.unpack_from("<I", raw)[0]
                info = slot_info((bits >> 26) & 0xF, bits >> 30)
                calls = []
                for f in fl:
                    face = resolve_slot(f.get("face", 0), info)
                    uvf = uv_face(info[face])
                    t = f.get("texture")
                    if not t:
                        calls.append((FN_DECAL if detail else FN_PAINT, m, [blk, face, 0]))
                        continue
                    if t not in items:
                        items[t] = self.find_item(t, kinds)
                        sizes[t] = bldfile.texture_size(a.rz_string(items[t] + 0x48)) or (16, 16)
                    wc, hc = max(1, sizes[t][0] // 16), max(1, sizes[t][1] // 16)
                    if "u" in f or "v" in f:
                        uv = ((int(f.get("u", 0)) % wc) & 15) << 4 | ((int(f.get("v", 0)) % hc) & 15)
                    elif uvf == 0:
                        uv = bldfile.top_uv(x, y, sizes[t])
                    elif uvf == 5:
                        uv = 0
                    else:
                        uv = bldfile.wall_uv(self._along(uvf, x, y, g), z, sizes[t], ztop.get(t, z))
                    calls.append((fn, m, [blk, face, items[t], uv]))
                calls.append((FN_SET_BLOCK, m, [base, blk]))
                for i in range(0, len(calls), 14):
                    a.call_seq(calls[i:i + 14])
                n += len(fl)
            self.refresh()
            return n

        finally:
            self.end(_mark)

    def exterior_faces(self, box: tuple, sides: bool = True, tops: bool = True) -> list[dict]:
        """Faces of the blocks inside box (x0, y0, z0, x1, y1, z1) that can be seen (the visible-face bits SetBlock
        keeps), for any shape: vertical sides (including diagonal ones) as kind "side", tops and sloped roof faces
        as "top" / "slope". Prop cells and the ground layer are left out."""
        x0, y0, z0, x1, y1, z1 = box
        out = []
        for (x, y, z), raw in sorted(self.cells().items()):
            if not (min(x0, x1) <= x <= max(x0, x1) and min(y0, y1) <= y <= max(y0, y1)
                    and min(z0, z1) <= z <= max(z0, z1)):
                continue
            bits = struct.unpack_from("<I", raw)[0]
            shape = (bits >> 26) & 0xF
            if shape in NO_PAINT_SHAPES:
                continue
            for i in slot_info(shape, bits >> 30):
                if not raw_visible(raw, i["slot"]):
                    continue
                if (sides and i["kind"] == "side") or (tops and i["kind"] in ("top", "slope")):
                    out.append({"x": x, "y": y, "z": z, "face": i["slot"], "kind": i["kind"]})
        return out

    def view_rotation(self) -> int:
        return self.a.proc.read(self.model() + 0x84, 1)[0] & 3

    def place_props(self, props: list[dict]) -> list[dict]:
        """Place props {prop, x, y, z (bottom, default 1), orientation (0..3)} as the prop tool stores them: the
        prop's x*y*z volume (from its .MET line) filled with prop cells (shape 15) whose four side slots hold the
        prop's four view bitmaps and whose offset bytes say where in the sprite each cell sits."""
        _mark = self.begin()
        try:
            from . import bldfile
            a, m = self.a, self.model()
            g, h = a.i32(m + 0x5C), a.i32(m + 0x60)
            mets = bldfile.read_met_files()
            rot = self.view_rotation()
            base = a.scratch() + SCRATCH + 0x100
            placed = []
            for p in props:
                stem = str(p["prop"]).lower().rsplit(".", 1)[0]
                if stem not in mets and stem.rsplit(" ", 1)[0] in mets:
                    stem = stem.rsplit(" ", 1)[0]
                if stem not in mets:
                    raise GameError(f"no prop {p['prop']!r} (library kind=props lists them)")
                lines = mets[stem]
                o = int(p.get("orientation", 0)) % len(lines)
                sx, sy, sz, views = lines[o]
                items = [self.find_item(v, set(range(8, 17))) for v in views]
                cx, cy, z0 = int(p["x"]), int(p["y"]), int(p.get("z", 1))
                x0, y0 = cx - (sx - 1) // 2, cy - (sy - 1) // 2
                rz = z0 + (sz - 1) // 2
                occ = self.cells()
                busy = [(x, y, z) for x in range(x0, x0 + sx) for y in range(y0, y0 + sy)
                        for z in range(z0, z0 + sz) if (x, y, z) in occ]
                if busy:
                    raise GameError(f"prop {stem!r} ({sx}x{sy}x{sz} cells) at ({cx}, {cy}, {z0}) overlaps blocks at "
                                    f"{busy[:4]}: a prop needs empty cells")
                cells = 0
                for x in range(x0, x0 + sx):
                    for y in range(y0, y0 + sy):
                        for z in range(z0, z0 + sz):
                            if not (0 <= x < g and 0 <= y < g and 0 < z < h):
                                continue
                            blk = base + 0x20
                            a.proc.write(base, struct.pack("<3i", x, y, z))
                            a.proc.write(blk, struct.pack("<II", (rot << 30) | (15 << 26) | (z << 17), 0xFF)
                                         + bytes(24))
                            offs = bldfile.prop_offsets(x - cx, y - cy, z - rz, rot)
                            a.call_seq([(0x40E042, m, [blk, 1 + k, items[k], offs[k][0] & 0xFF]) for k in range(4)])
                            for k in range(4):              # the second offset sits in the (unused) detail uv byte
                                a.proc.write(blk + 8 + 4 * (1 + k) + 3, bytes((offs[k][1] & 0xFF,)))
                            a.call(FN_SET_BLOCK, [base, blk], this=m)
                            cells += 1
                placed.append({"prop": stem, "x": cx, "y": cy, "z": z0, "orientation": o, "size": [sx, sy, sz],
                               "cells": cells})
            self.refresh()
            return placed

        finally:
            self.end(_mark)

    def copy_blocks(self, box: tuple, offset: tuple, move: bool = False, overwrite: bool = False) -> int:
        """Copy (or move) every block in box (x0, y0, z0, x1, y1, z1) by offset (dx, dy, dz) with its paint, details
        and prop cells, as the Architect's copy / paste: each copy is a new block painted with the model's own
        paint functions (so the texture table's use counts stay right) and placed with SetBlock. Cells already
        holding a block are refused unless overwrite (then that block is removed first; the program never puts a
        prop cell over a block)."""
        _mark = self.begin()
        try:
            a, m = self.a, self.model()
            x0, y0, z0, x1, y1, z1 = box
            dx, dy, dz = offset
            allc = self.cells()
            src = {k: v for k, v in allc.items()
                   if min(x0, x1) <= k[0] <= max(x0, x1) and min(y0, y1) <= k[1] <= max(y0, y1)
                   and min(z0, z1) <= k[2] <= max(z0, z1)}
            if not src:
                raise GameError("no blocks in that box")
            dest = {(x + dx, y + dy, z + dz) for (x, y, z) in src}
            for c in dest:
                self._check_pos(m, *c)
            busy = sorted(c for c in dest if c in allc and not (move and c in src))
            if busy and not overwrite:
                raise GameError(f"{len(busy)} target cells already hold blocks, e.g. {busy[:4]}: "
                                "use overwrite=true to replace them")
            items = self._texture_items(m)
            base = a.scratch() + SCRATCH + 0x100
            for (x, y, z) in sorted(set(src) | set(busy) if move else busy):
                a.proc.write(base, struct.pack("<3i", x, y, z))
                a.call(FN_REMOVE_BLOCK, [base], this=m)
            for (x, y, z), raw in sorted(src.items(), key=lambda kv: kv[0][2]):
                bits = struct.unpack_from("<I", raw)[0]
                nz = z + dz
                blk = base + 0x20
                a.proc.write(base, struct.pack("<3i", x + dx, y + dy, nz))
                a.proc.write(blk, struct.pack("<II", (bits & 0xFC000000) | (nz << 17), 0xFF) + bytes(24))
                calls, raw_dv = [], []
                for f in range(6):
                    ps, pp, ds, dp = raw[8 + 4 * f:12 + 4 * f]
                    if ps and ps in items:
                        calls.append((FN_PAINT_UV, m, [blk, f, items[ps], pp]))
                    if ds and ds in items:
                        calls.append((FN_DECAL_UV, m, [blk, f, items[ds], dp]))
                    elif dp:
                        raw_dv.append((f, dp))           # prop cells keep their second sprite offset here
                for i in range(0, len(calls), 14):
                    a.call_seq(calls[i:i + 14])
                for f, dp in raw_dv:
                    a.proc.write(blk + 8 + 4 * f + 3, bytes((dp,)))
                a.call(FN_SET_BLOCK, [base, blk], this=m)
            self.refresh()
            return len(src)
        finally:
            self.end(_mark)

    def fill_faces(self, x: int, y: int, z: int, face, detail: bool = False) -> list[dict]:
        """The faces the Fill tool covers from one face (as the program's Fill, 0x43BC71): that face plus every
        connected face that points the same way (same direction code, rotation included), can be seen (visible bit)
        and carries the same paint (or detail) as the starting face. Walls spread sideways and up / down, tops and
        slopes across x / y."""
        cells = self.cells(include_ground=True)
        start = cells.get((x, y, z))
        if start is None:
            raise GameError(f"no block at ({x}, {y}, {z})")
        k = 10 if detail else 8

        def info_of(raw):
            b = struct.unpack_from("<I", raw)[0]
            return slot_info((b >> 26) & 0xF, b >> 30)

        sinfo = info_of(start)
        slot = resolve_slot(face, sinfo)
        if not raw_visible(start, slot):
            raise GameError(f"face {slot_label(sinfo[slot])} of ({x}, {y}, {z}) is hidden by a neighbouring block")
        code, want = sinfo[slot]["code"], start[k + 4 * slot]
        kind, d = sinfo[slot]["kind"], sinfo[slot]["dir"]
        if kind in ("top", "bottom", "slope"):
            steps = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]
        elif d in ("+x", "-x"):
            steps = [(0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        elif d in ("+y", "-y"):
            steps = [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]
        else:
            steps = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        seen = {(x, y, z): slot}
        todo = [(x, y, z)]
        while todo:
            c = todo.pop()
            for dx, dy, dz in steps:
                n = (c[0] + dx, c[1] + dy, c[2] + dz)
                raw = cells.get(n)
                if n in seen or raw is None:
                    continue
                hit = next((i["slot"] for i in info_of(raw) if i["code"] == code and raw_visible(raw, i["slot"])
                            and raw[k + 4 * i["slot"]] == want), None)
                if hit is not None:
                    seen[n] = hit
                    todo.append(n)
        return [{"x": c[0], "y": c[1], "z": c[2], "face": f} for c, f in sorted(seen.items())]

    def placed_props(self) -> list[dict]:
        """Props on the building: connected prop cells (shape 15) with the same four view bitmaps, named after the
        prop definition (.MET) that uses those bitmaps."""
        from . import bldfile
        m = self.model()
        names = self._texture_names(m)
        cells = {k: v for k, v in self.cells().items() if (struct.unpack_from("<I", v)[0] >> 26) & 0xF == 15}
        views = {k: tuple((names.get(v[8 + 4 * f]) or "").lower() for f in range(1, 5)) for k, v in cells.items()}
        mets = bldfile.read_met_files()
        out, seen = [], set()
        for c in sorted(cells):
            if c in seen:
                continue
            group, todo = {c}, [c]
            while todo:
                q = todo.pop()
                for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    n = (q[0] + d[0], q[1] + d[1], q[2] + d[2])
                    if n in cells and n not in group and views[n] == views[c]:
                        group.add(n)
                        todo.append(n)
            seen |= group
            xs, ys, zs = zip(*group)
            v = views[c]
            name, orient = None, None
            for stem, lines in mets.items():
                for o, (_sx, _sy, _sz, vs) in enumerate(lines):
                    if tuple(x.lower() for x in vs) == v:
                        name, orient = stem, o
                        break
                if name:
                    break
            if name is None:
                name = os.path.splitext(v[0])[0]
            out.append({"prop": name, "orientation": orient, "x0": min(xs), "y0": min(ys), "z0": min(zs),
                        "x1": max(xs), "y1": max(ys), "z1": max(zs), "cells": len(group),
                        "_cells": sorted(group)})
        return out

    def remove_props(self, at: list[tuple]) -> list[dict]:
        """Remove whole props: every placed prop with a cell at one of these (x, y[, z]) positions."""
        props = self.placed_props()
        hit = [p for p in props if any(c[:2] == t[:2] and (len(t) < 3 or c[2] == t[2]) for t in at
                                       for c in p["_cells"])]
        if hit:
            self.remove_blocks([{"x": c[0], "y": c[1], "z": c[2]} for p in hit for c in p["_cells"]])
        return hit

    def rotate(self, turns: int, log: bool = True) -> int:
        """Turn the building on its lot with the view's own Rotate (the toolbar button / Space): every block moves
        to its turned cell. log=False turns it the way the program's undo replays a rotation (no undo entry)."""
        a, m, V = self.a, self.model(), self.view()
        turns = int(turns) % 4
        if not turns:
            return self.view_rotation()
        step, n = (1, turns) if turns <= 2 else (-1, 4 - turns)
        if log:
            _mark = self.begin()
            try:
                for _ in range(n):
                    a.call(FN_ROTATE, [step, 1], this=V)
            finally:
                self.end(_mark)
        else:
            old = a.proc.read(m + REPLAYING, 1)
            a.proc.write(m + REPLAYING, b"\x01")
            try:
                for _ in range(n):
                    a.call(FN_ROTATE, [step, 1], this=V)
            finally:
                a.proc.write(m + REPLAYING, old)
        self.refresh(edited=log)
        return self.view_rotation()

    def zoom(self) -> int:
        return self.a.i32(self.view() + 0x778)

    def set_zoom(self, level: int) -> int:
        """Zoom in / out one step at a time with the view's own Zoom (0x43AC76(+-1)) until the level is reached or
        the program's limit for this lot is hit; returns the zoom reached."""
        level = max(0, min(5, int(level)))
        V = self.view()
        for _ in range(6):
            cur = self.zoom()
            if cur == level:
                break
            self.a.call(0x43AC76, [1 if level > cur else -1], this=V)
            if self.zoom() == cur:
                break                                  # at the program's limit
        return self.zoom()

    UNDO_POS = 0xA01A0
    FN_APPLY_LOG = 0x40F4B2            # model: apply one log entry's op (the undo / redo loops call it)

    def _pos(self, m: int) -> int:
        return self.a.i32(m + self.UNDO_POS)

    def begin(self) -> tuple[int, int]:
        m = self.model()
        return m, self._pos(m)

    def end(self, mark: tuple[int, int]) -> None:
        m, start = mark
        endp = self._pos(m)
        if endp != start:
            self._actions.append((m, start, endp))
            self._redo.clear()

    def undo(self) -> bool:
        """Undo the last edit call: the model's own per-entry undo (0x40F4B2 with the entry's undo op) for exactly
        the log entries that call recorded."""
        a, m = self.a, self.model()
        while self._actions and self._actions[-1][0] != m:
            self._actions.pop()
        if not self._actions:
            return False
        if self._pos(m) != self._actions[-1][2]:          # the program reset its undo log (e.g. a render): stale
            self._actions.clear()
            self._redo.clear()
            return False
        _m, start, endp = self._actions.pop()
        while self._pos(m) > start:
            k = self._pos(m) - 1
            a.proc.write(m + self.UNDO_POS, struct.pack("<i", k))
            a.call(self.FN_APPLY_LOG, [a.proc.read(m + 0x1B4 + 0x14 * k, 1)[0]], this=m)
        self._redo.append((m, start, endp))
        self.refresh()
        return True

    def forget_history(self) -> None:
        self._actions.clear()
        self._redo.clear()

    def redo(self) -> bool:
        a, m = self.a, self.model()
        while self._redo and self._redo[-1][0] != m:
            self._redo.pop()
        if not self._redo or self._pos(m) != self._redo[-1][1]:
            return False
        _m, start, endp = self._redo.pop()
        while self._pos(m) < endp:
            k = self._pos(m)
            a.call(self.FN_APPLY_LOG, [a.proc.read(m + 0x1B4 + 0x14 * k + 1, 1)[0]], this=m)
            a.proc.write(m + self.UNDO_POS, struct.pack("<i", k + 1))
        self._actions.append((m, start, endp))
        self.refresh()
        return True

    def refresh(self, edited: bool = True) -> None:
        m, V = self.model(), self.view()
        self.a.call(FN_BBOX, [m + 0x6C], this=m)
        self.a.call(FN_REDRAW, [1], this=V)
        if edited:
            self.a.post_message(MSG_EDITED)

    # ------------------------------------------------------------ view
    def mode(self) -> str:
        v = self.a.i32(self.view() + 0x6AC)
        return next((k for k, i in MODES.items() if i == v), str(v))

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise GameError(f"mode: one of {list(MODES)}")
        self.a.post_message(MSG_VIEW, 3, MODE_SETMODE, MODES[mode])
        self._wait(lambda: self.a.i32(self.view() + 0x6AC) == MODES[mode], what=f"{mode} mode")

    def view_images(self, turns: list[int], crop: bool = True) -> list[Image.Image]:
        """The view with the building turned by each number of quarter turns (Rotate without an undo entry; it is
        turned back afterwards, so coordinates do not change)."""
        out, cur = [], 0
        try:
            for t in turns:
                if (t - cur) % 4:
                    self.rotate(t - cur, log=False)
                    cur = t
                time.sleep(0.25)
                out.append(self.view_image())
        finally:
            if cur % 4:
                self.rotate(-cur, log=False)
        return [crop_view(im) for im in out] if crop else out

    def view_image(self) -> Image.Image:
        """The Architect's view as it is drawn, read from its render surface (V+0x678, an RGB565 system-memory
        DirectDraw surface; locked through the GZ surface's own Lock / Unlock): no screenshot."""
        a, V = self.a, self.view()
        S = a.u32(V + 0x678)
        w, h = a.i32(S + 0x24), a.i32(S + 0x28)
        D = a.u32(S + 0x44)
        if not (S and D and w and h):
            raise GameError("the Building Architect's view has no picture yet (open a building)")
        if not a.call(a.vfn(S, 0x1C // 4), [0x40], this=S) & 0xFF:
            raise GameError("could not lock the view surface")
        try:
            p, pitch = a.u32(D + 0xF0), a.i32(D + 0xF4)
            raw = a.proc.read(p, pitch * h)
        finally:
            a.call(a.vfn(S, 0x20 // 4), [0x40], this=S)
        fmt = a.i32(S + 0xC)
        mode = {7: "BGR;16", 5: "BGR;15"}.get(fmt)
        if fmt in (0xD, 0xE):
            return Image.frombuffer("RGB", (w, h), raw, "raw", "BGRX", pitch, 1)
        if not mode:
            raise GameError(f"unsupported view pixel format {fmt}")
        return Image.frombuffer("RGB", (w, h), raw, "raw", mode, pitch, 1)


def crop_view(im: Image.Image, margin: int = 12) -> Image.Image:
    """Crop a view to what differs from its background colour (the top-left pixel), plus a margin."""
    from PIL import ImageChops
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im.convert("RGB"), bg).convert("L").point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if not box:
        return im
    l, t, r, b = box
    return im.crop((max(0, l - margin), max(0, t - margin), min(im.width, r + margin), min(im.height, b + margin)))
