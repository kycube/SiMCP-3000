"""STATIC: extract Apps/Sys/SYS.PAK to re/out/syspak/ (raw) and re/out/syspak_txt/ (readable .txt).

PAK: u32 count; per file: u32 namelen, name, u32 offset. Each INI: u32 line count, then per line
u32 length + text.
"""
import os
import struct

from pe import APPS

HERE = os.path.dirname(os.path.abspath(__file__))


def entries(data):
    n = struct.unpack_from("<I", data, 0)[0]
    pos, out = 4, []
    for _ in range(n):
        ln = struct.unpack_from("<I", data, pos)[0]
        name = data[pos + 4:pos + 4 + ln].decode("latin-1")
        off = struct.unpack_from("<I", data, pos + 4 + ln)[0]
        out.append((name, off))
        pos += 8 + ln
    return out


def decode_ini(blob):
    n = struct.unpack_from("<I", blob, 0)[0]
    pos, lines = 4, []
    for _ in range(n):
        if pos + 4 > len(blob):
            break
        ln = struct.unpack_from("<I", blob, pos)[0]
        lines.append(blob[pos + 4:pos + 4 + ln].decode("latin-1"))
        pos += 4 + ln
    return lines


def main():
    data = open(os.path.join(APPS, "Sys", "SYS.PAK"), "rb").read()
    raw_dir = os.path.join(HERE, "out", "syspak")
    txt_dir = os.path.join(HERE, "out", "syspak_txt")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(txt_dir, exist_ok=True)
    ents = entries(data)
    for i, (name, off) in enumerate(ents):
        end = ents[i + 1][1] if i + 1 < len(ents) else len(data)
        blob = data[off:end]
        with open(os.path.join(raw_dir, name), "wb") as f:
            f.write(blob)
        with open(os.path.join(txt_dir, name + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(decode_ini(blob)) + "\n")
        print(f"{end - off:7d} {name}")


if __name__ == "__main__":
    main()
