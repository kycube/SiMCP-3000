"""The game's Photo Album on disk: <game>\\Albums\\<city>--<id>\\ holds, per snapshot,
- <name>.jpg   the picture (take_snapshot / the game's Take Snapshot),
- <name>.info  text lines XOR 0x7B: "SanityCheck", the Windows user, city, mayor, game date as a Julian day number,
               population, funds, "", four view numbers, "",
- <name>.txt   the description typed in the album's text box (plain cp1252; written when the album window closes).
The album's Delete button removes all three at once. Verified in the game 2026-10-08 (notes/LIVE_FACTS.md round 8).
These functions work on the files and need no running game.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes as wt

from .game import GameError, jdn_to_date


def root() -> str:
    from .bridge import GAME_DIR
    return os.path.join(GAME_DIR, "Albums")


def _info(path_jpg: str) -> dict:
    p = path_jpg[:-4] + ".info"
    if not os.path.exists(p):
        return {}
    lines = bytes(b ^ 0x7B for b in open(p, "rb").read()).decode("cp1252", "replace").split("\n")
    if not lines or lines[0] != "SanityCheck" or len(lines) < 7:
        return {}
    out = {"city": lines[2], "mayor": lines[3]}
    try:
        out["date"] = str(jdn_to_date(int(lines[4])))
        out["population"] = int(lines[5])
        out["funds"] = int(lines[6])
    except ValueError:
        pass
    return out


def caption(path_jpg: str) -> str:
    p = path_jpg[:-4] + ".txt"
    return open(p, "rb").read().decode("cp1252", "replace") if os.path.exists(p) else ""


def snapshots(album: str | None = None) -> list[dict]:
    out = []
    base = root()
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if album and album.lower() not in (d.lower(), d.split("--")[0].lower()):
            continue
        for f in sorted(os.listdir(os.path.join(base, d))):
            if f.lower().endswith(".jpg"):
                p = os.path.join(base, d, f)
                out.append({"album": d, "file": f, "path": p, "bytes": os.path.getsize(p),
                            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))),
                            **_info(p), "caption": caption(p)})
    return out


def find(file: str, album: str | None = None) -> str:
    name = file if file.lower().endswith(".jpg") else file + ".jpg"
    hits = [s for s in snapshots(album) if s["file"].lower() == name.lower()]
    if not hits:
        raise GameError(f"no snapshot {file!r}{' in album ' + repr(album) if album else ''} (snapshots lists them)")
    if len(hits) > 1:
        raise GameError(f"{file!r} is in several albums {[h['album'] for h in hits]}: give the album")
    return hits[0]["path"]


def set_caption(file: str, text: str, album: str | None = None) -> dict:
    p = find(file, album)
    t = p[:-4] + ".txt"
    data = text.replace("\r\n", "\n").encode("cp1252", "replace")
    if data:
        open(t, "wb").write(data)
    elif os.path.exists(t):
        os.remove(t)                                       # no description = no .txt, as in the album
    return {"file": os.path.basename(p), "album": os.path.basename(os.path.dirname(p)), "caption": caption(p)}


def _recycle(paths: list[str]) -> None:
    """Move files to the Recycle Bin (SHFileOperationW, FOF_ALLOWUNDO) so a deletion can be undone."""
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wt.HWND), ("wFunc", wt.UINT), ("pFrom", wt.LPCWSTR), ("pTo", wt.LPCWSTR),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wt.BOOL), ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", wt.LPCWSTR)]
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(None, FO_DELETE, "\0".join(paths) + "\0\0", None,
                         FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI, False, None, None)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc or op.fAnyOperationsAborted:
        raise GameError(f"could not move the snapshot to the Recycle Bin (error {rc:#x})")


def delete(file: str, album: str | None = None) -> dict:
    p = find(file, album)
    files = [x for x in (p, p[:-4] + ".info", p[:-4] + ".txt") if os.path.exists(x)]
    _recycle(files)
    return {"deleted": [os.path.basename(x) for x in files], "album": os.path.basename(os.path.dirname(p)),
            "recycle_bin": True}
