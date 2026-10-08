"""IXF record files (saved cities .sc3, scenarios .SNR, text tables .IXF, the Architect's .DAT): magic D7 81 C3 80,
an index of 20-byte entries {group, instance, type, offset, size} ended by a zero entry, then the record data.
Entries of type 0xFFFFFFFF are free slots."""

from __future__ import annotations

import os
import struct

MAGIC = 0x80C381D7


def read(blob: bytes) -> list[tuple[int, int, int, bytes]]:
    """The records in index order: [(type, group, instance, data)]."""
    if len(blob) < 4 or struct.unpack_from("<I", blob, 0)[0] != MAGIC:
        raise ValueError("not an IXF file")
    out, o = [], 4
    while o + 20 <= len(blob):
        g, i, t, off, sz = struct.unpack_from("<5I", blob, o)
        o += 20
        if g == 0 and i == 0 and t == 0:
            break
        if t != 0xFFFFFFFF:
            out.append((t, g, i, blob[off:off + sz]))
    return out


def build(records: list[tuple[int, int, int, bytes]], spare_slots: int = 0) -> bytes:
    """An IXF file holding these records in this order (index first, then the data)."""
    n = len(records) + 1 + spare_slots
    off = 4 + 20 * n
    index, data = bytearray(), bytearray()
    for t, g, i, d in records:
        index += struct.pack("<5I", g, i, t, off + len(data), len(d))
        data += d
    index += bytes(20 * n - len(index))
    return struct.pack("<I", MAGIC) + bytes(index) + bytes(data)


def write(path: str, records: list[tuple[int, int, int, bytes]]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(build(records))
    os.replace(tmp, path)
