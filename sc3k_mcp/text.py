"""The game's text tables (Apps\\Res\\Text\\ENGLISH\\*.IXF), loaded once on first use.

IXF: magic D7 81 C3 80, then 20-byte records {table id, index, type 0x2026960B, offset, size} until a zero record;
the data at offset is a u32 length + Latin-1 text.
"""

from __future__ import annotations

import glob
import os
import struct

from .game import APPS

TEXT_DIR = os.path.join(APPS, "Res", "Text", "ENGLISH")
_TABLE: dict[tuple[int, int], str] | None = None

# petitioner tables (re/agents/events/REPORT.md)
PETITION = {"heading": 0xC26DD29B, "name": 0x826DD2D0, "message": 0xC26DD2AB, "button1": 0xA26DD23B,
            "button2": 0xE26DD247, "reaction1": 0xE26DD2FA, "reaction2": 0x226DD30B, "advice": 0xE26DD125}
ADVISOR = {"heading": 0x825ADC5A, "message": 0x225ADC6B, "ticker": 0xC25B11C3}


def _load() -> dict[tuple[int, int], str]:
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    table: dict[tuple[int, int], str] = {}
    for path in glob.glob(os.path.join(TEXT_DIR, "*.IXF")) + glob.glob(os.path.join(TEXT_DIR, "*.ixf")):
        try:
            d = open(path, "rb").read()
        except OSError:
            continue
        if d[:4] != b"\xd7\x81\xc3\x80":
            continue
        o = 4
        while o + 20 <= len(d):
            t, idx, typ, off, size = struct.unpack_from("<5I", d, o)
            o += 20
            if t == 0 and idx == 0 and typ == 0:
                break
            if off + 4 > len(d):
                continue
            n = struct.unpack_from("<I", d, off)[0]
            table.setdefault((t, idx), d[off + 4: off + 4 + n].decode("latin-1", "replace"))
    _TABLE = table
    return table


def text(table: int, index: int) -> str | None:
    return _load().get((table, index))


def petition_text(pid: int) -> dict:
    out = {k: text(t, pid) for k, t in PETITION.items()}
    return {k: v for k, v in out.items() if v}
