"""Rendering projects for SimCity with the Architect's own renderer (re/agents/batrender/REPORT.md section 2).

The BAT manager M = *(Baapp 0x4954E0) has the render entries M vt[0x10] = Baapp 0x40446B and vt[0x18] = 0x404488 (the
one the Render button uses with a building open)
(cIGZString* datPath, int nBld, cIGZString*** bldArray, int nKeep, Key* keepKeys): it loads each .bld, renders the
four rotations at 128 px per tile, scales them to the zoom levels, and writes the game's sprites and the building
record into datPath. An existing datPath is first moved to Apps\\Res\\BA\\RenderedBuildingsBackup.IXF; buildings whose
keys are in keepKeys are copied over from it (that is how the Architect adds buildings to the game's BAT.DAT).
Verified live: Tutorial House.bld -> a temp DAT with 20 frames, decoded by sprites.RenderedSet.
"""

from __future__ import annotations

import os
import shutil
import struct
import tempfile
import time

from sc3k_mcp.game import GameError

from . import sprites
from .app import APPS, RENDER_DAT, BatApp

BAT_MANAGER = 0x4954E0          # Baapp global: the BAT manager M
RENDER_FN = 0x404488            # M vt[0x18]: as the Render button (0x401C73) calls it - with an open building
FN_ADDREF, FN_RELEASE = 0x40A8C6, 0x40A8D9
RZSTRING_VT = 0x480344          # Baapp cRZString vtable (vt[0x14] = c_str = *(this+4))
BACKUP = os.path.join(APPS, "Res", "BA", "RenderedBuildingsBackup.IXF")
TEMP_DIR = os.path.join(tempfile.gettempdir(), "sc3k-mcp", "renders")


def _rz(app: BatApp, at: int, text: str) -> int:
    """A cRZString {vtable, begin, end, end, refcount} at `at` with its text right after it."""
    data = text.encode("cp1252")
    p = at + 0x20
    app.proc.write(p, data + b"\0")
    app.proc.write(at, struct.pack("<5I", RZSTRING_VT, p, p + len(data), p + len(data), 100))
    return at


def render(app: BatApp, bld_paths: list[str], dat_path: str, keep_keys: list[tuple[int, int, int]] = ()) -> dict:
    """Render .bld files into dat_path (created anew), keeping the given buildings of an existing dat_path."""
    if not bld_paths:
        raise GameError("nothing to render")
    for p in bld_paths:
        if not os.path.exists(p):
            raise GameError(f"no project file {p}")
    if os.path.exists(BACKUP):
        raise GameError(f"a stale render backup exists ({BACKUP}); the Architect's last render did not finish")
    M = app.u32(BAT_MANAGER)
    if not M:
        raise GameError("the Architect's BAT manager is not available")
    buf = app.scratch() + 0x2000                        # 0x2000..0x5FFF: strings, arrays, keys
    if len(bld_paths) > 8 or len(keep_keys) > 200:
        raise GameError("at most 8 projects per render and 200 kept buildings")
    dat_s = _rz(app, buf, dat_path)
    arr = buf + 0x2400
    ptrs = []
    for k, p in enumerate(bld_paths):
        ptrs.append(_rz(app, buf + 0x200 + 0x200 * k, p))
    app.proc.write(arr, struct.pack(f"<{len(ptrs)}I", *ptrs))
    parr = arr + 0x40
    app.proc.write(parr, struct.pack("<I", arr))
    keys = buf + 0x2500
    if keep_keys:
        app.proc.write(keys, b"".join(struct.pack("<3I", *k) for k in keep_keys))
    t = time.time()
    # as the Render button does: keep the open building, render (the renderer replaces the current building),
    # then make it current again
    cur = app.call(app.vfn(M, 0x20 // 4), [], this=M)
    if cur:
        app.call(FN_ADDREF, [], this=cur)
    try:
        app._check(app.bridge.call_function(RENDER_FN, [dat_s, len(ptrs), parr, len(keep_keys),
                                                        keys if keep_keys else 0], M))
    finally:
        if cur:
            app.call(app.vfn(M, 0x30 // 4), [cur, 0], this=M)
            app.call(FN_RELEASE, [], this=cur)
    if not os.path.exists(dat_path):
        raise GameError("the renderer wrote no output")
    return {"file": dat_path, "seconds": round(time.time() - t, 2)}


def render_to_temp(app: BatApp, bld_path: str) -> sprites.RenderedSet:
    os.makedirs(TEMP_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(bld_path))[0]
    for old in os.listdir(TEMP_DIR):                     # tidy earlier renders (skip any still open)
        try:
            os.remove(os.path.join(TEMP_DIR, old))
        except OSError:
            pass
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in base)
    dat = os.path.join(TEMP_DIR, f"{safe}-{int(time.time() * 1000)}.dat")
    render(app, [bld_path], dat)
    return sprites.RenderedSet(dat)


def install(app: BatApp, bld_path: str) -> dict:
    """Add (or update) a building in the game's BAT.DAT, keeping every other rendered building, as the Architect's
    render-for-SimCity does. BAT.DAT is copied to a timestamped backup next to it first."""
    info = sprites.project_info(bld_path)
    current = sprites.RenderedSet(RENDER_DAT) if os.path.exists(RENDER_DAT) else None
    keep = [(sprites.T_BLD, b["group"], b["id"]) for b in (current.buildings if current else [])
            if b["id"] != info.get("building_id")]
    backup = None
    if os.path.exists(RENDER_DAT):
        backup = RENDER_DAT + time.strftime(".%Y%m%d-%H%M%S.bak")
        shutil.copy2(RENDER_DAT, backup)
    r = render(app, [bld_path], RENDER_DAT, keep)
    after = sprites.RenderedSet(RENDER_DAT)
    names = [b["name"] for b in after.buildings]
    lost = [b["name"] for b in (current.buildings if current else []) if b["name"] not in names]
    if lost:
        raise GameError(f"buildings missing after the render: {lost}; the previous file is at {backup}")
    return {**r, "backup": backup, "buildings": names, "note": "a running game sees the new building after it "
            "reloads its user-made buildings (the game server's building_replacements lists them)"}
