"""Offline tests of the game file formats: RefPack, the RGB565 sprite records and the IXF database (no game
needed). Tests that compare against the local game install skip when it is not there."""
import os
import random

import numpy as np
import pytest
from PIL import Image

from bat_mcp import bldfile, datwriter, sprites


def _sample_bytes(n: int, seed: int = 1) -> bytes:
    rnd = random.Random(seed)
    words = [bytes(rnd.randrange(256) for _ in range(rnd.randrange(2, 12))) for _ in range(40)]
    out = bytearray()
    while len(out) < n:
        out += rnd.choice(words) if rnd.random() < 0.8 else bytes([rnd.randrange(256)])
    return bytes(out[:n])


@pytest.mark.parametrize("n", [1, 3, 17, 1000, 70000])
def test_refpack_round_trip(n):
    data = _sample_bytes(n, seed=n)
    assert sprites.refpack(datwriter.refpack_compress(data)) == data
    assert bldfile.refpack_decompress(bldfile.refpack_compress(data)) == data


def test_refpack_compresses_repetition():
    data = b"SimCity 3000 " * 500
    assert len(datwriter.refpack_compress(data)) < len(data) // 10


def _test_sprite() -> Image.Image:
    im = Image.new("RGBA", (64, 40), (0, 0, 0, 0))
    px = im.load()
    for y in range(40):
        for x in range(64):
            if abs(x - 32) < y or (x + y) % 7 == 0:                   # a triangle and some loose pixels (holes)
                px[x, y] = ((x * 4) & 0xF8, (y * 6) & 0xFC, ((x + y) * 3) & 0xF8, 255)
    return im


def test_sprite_round_trip():
    im = _test_sprite()
    rec, anchor = datwriter.encode_image(im)
    back = np.asarray(sprites.decode_sprite(rec).convert("RGBA"))
    a = np.asarray(im)
    assert back.shape == a.shape
    opaque = a[:, :, 3] >= 128
    assert ((back[:, :, 3] >= 128) == opaque).all()
    # the same RGB565 colours (the decoder widens 5/6-bit channels to 8 bits)
    shift = np.array([3, 2, 3])
    assert ((back[opaque][:, :3] >> shift) == (a[opaque][:, :3] >> shift)).all()
    assert len(anchor) == 8


def test_ixf_round_trip(tmp_path):
    im = _test_sprite()
    frames = {(z, r): im.resize((8 * 2 ** (z - 1) * 2, max(1, 5 * 2 ** (z - 1))))
              for z in range(1, 6) for r in range(4)}
    recs = datwriter.building_records("Test House", "tester", "a test", 2, frames, True)
    path = tmp_path / "test.DAT"
    datwriter.write_ixf(str(path), recs)
    assert datwriter.read_ixf(str(path)) == recs
    rs = sprites.RenderedSet(str(path))
    assert [b["name"] for b in rs.buildings] == ["Test House"]
    b = rs.buildings[0]
    assert b["size"] == 2 and b["architect"] == "tester" and b["description"] == "a test"
    assert len(b["frames"]) == 20
    assert all(f["scale"] == 0 for f in b["frames"] if f["zoom"] == 5)
    assert rs.image(b, 3, 1).size == frames[(3, 1)].size


def test_install_and_uninstall(tmp_path):
    dat = str(tmp_path / "MCP Photo Buildings.DAT")
    im = _test_sprite()
    frames = {(z, r): im for z in range(1, 6) for r in range(4)}
    a = datwriter.building_records("House A", "x", "", 1, frames, True)
    b = datwriter.building_records("House B", "x", "", 1, frames, True)
    datwriter.install(a, dat)
    out = datwriter.install(b, dat)
    assert out["backup"] and os.path.exists(out["backup"])
    assert sorted(x["name"] for x in sprites.RenderedSet(dat).buildings) == ["House A", "House B"]
    datwriter.install(a, dat)                                         # the same name replaces, not duplicates
    assert sorted(x["name"] for x in sprites.RenderedSet(dat).buildings) == ["House A", "House B"]
    ida = sprites.RenderedSet(dat).find("House A")["id"]
    datwriter.uninstall({ida}, dat)
    rs = sprites.RenderedSet(dat)
    assert [x["name"] for x in rs.buildings] == ["House B"]
    assert rs.image(rs.buildings[0], 5, 0).size == im.size                # the other building's images are kept


SAMPLES = os.path.join(bldfile.GAME, "Buildings")


@pytest.mark.skipif(not os.path.isdir(SAMPLES), reason="no SimCity 3000 install (SC3K_GAME_DIR)")
def test_bld_round_trip_on_game_samples():
    files = [f for f in os.listdir(SAMPLES) if f.lower().endswith(".bld") and not f.lower().startswith("mcp")]
    assert files
    for f in files:
        blob = open(os.path.join(SAMPLES, f), "rb").read()
        assert bldfile.Building.parse(blob).to_bytes() == blob, f
