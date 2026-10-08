"""Offline tests of the photo-to-building route: authored facades, the model builder and the software renderer in
the game's projection (patterns and colours only, so no game files are needed)."""
import math

import numpy as np
import pytest
from PIL import Image

from bat_mcp import facade, photomodel, render3d, roofs
from sc3k_mcp.game import GameError


def test_facade_draws_and_cuts_out():
    im = facade.draw({"size_m": [4, 2], "base": {"color": "clear"}, "elements": [
        {"type": "railing", "u": 0, "v": 0.6, "w": 4, "h": 1.0, "style": "iron", "color": "#202020"},
        {"type": "arch", "u": 0.5, "v": 0, "w": 1.5, "h": 0.6, "rise": 0.3, "color": "#555555"},
        {"type": "band", "u": 2.5, "w": 1.2, "v": 0.1, "h": 0.3, "style": "brackets", "spacing": 0.3}]})
    a = np.asarray(im)
    assert im.mode == "RGBA" and im.size == (160, 80)
    assert 0.3 < (a[:, :, 3] == 0).mean() < 0.9                       # see-through between the bars
    wall = facade.draw({"size_m": [4, 3], "base": {"pattern": "clapboard", "color": "body"}, "elements": [
        {"type": "window", "u": 1, "v": 0.5, "w": 1, "h": 1.6, "hood": True, "transom": True, "curtain": "curtain"},
        {"type": "door", "u": 2.5, "v": 1.0, "w": 1.2, "h": 2.0},
        {"type": "repeat", "n": 3, "du": 1.0, "element": {"type": "ornament", "u": 0.2, "v": 0.1, "w": 0.6,
                                                          "h": 0.3, "style": "rosette"}}]})
    assert (np.asarray(wall)[:, :, 3] == 255).all()                   # an opaque wall stays opaque


def test_facade_errors():
    with pytest.raises(GameError):
        facade.draw({"size_m": [2, 2], "elements": [{"type": "gargoyle"}]})
    with pytest.raises(GameError):
        facade.draw({"elements": []})


MATS = {"wall": {"pattern": "clapboard", "color": "#7d8f7b"}, "roof": {"pattern": "slate", "color": "#3e434f"},
        "trim": {"color": "#c8ccc0"}, "lawn": {"color": "#4f7a3c"},
        "fence": {"facade": {"size_m": [4, 0.9], "base": {"color": "clear"}, "elements": [
            {"type": "railing", "u": 0, "v": 0, "w": 4, "h": 0.9, "style": "iron", "color": "#202020"}]}}}


def _house(lot=1):
    return {"name": "Test", "lot": lot, "materials": MATS, "parts": [
        {"type": "ground", "mat": "lawn"},
        {"type": "box", "x": 3, "y": 3, "z": 0, "w": 8, "d": 7, "h": 6, "mat": "wall"},
        {"type": "roof", "x": 3, "y": 3, "w": 8, "d": 7, "z": 6, "style": "hip", "pitch": 40, "mat": "roof",
         "ridge_cap": {"mat": "trim"}},
        {"type": "roof", "x": 6, "y": 4, "w": 5.5, "d": 4, "z": 6, "style": "gable_x", "pitch": 40, "mat": "roof",
         "ends": ["+x"], "bargeboard": {"mat": "trim"}, "finial": {"mat": "trim"}},
        {"type": "cylinder", "cx": 11, "cy": 12, "z": 0, "r": 1.6, "h": 8, "mat": "wall"},
        {"type": "cone", "cx": 11, "cy": 12, "z": 8, "r": 1.9, "h": 3, "mat": "roof"},
        {"type": "extrude", "points": [[1, 1], [3, 1], [2, 2.5]], "z": 0, "h": 2, "mat": "wall"},
        {"type": "beam", "from": [11, 3, 3], "to": [12, 3, 2.5], "mat": "trim"},
        {"type": "panel", "from": [15.5, 1], "to": [15.5, 15], "z": 0, "h": 0.9, "mat": "fence"},
        {"type": "patch", "x": 12, "y": 1, "w": 2, "d": 2, "mat": "trim"}]}


def test_render_sizes_and_coverage():
    mesh, mats = photomodel.Builder(_house()).build()
    r = render3d.Renderer(mesh, mats, 1, shadows=True, lights="game")
    for rot in range(4):
        im = render3d.crop_top(render3d.downsample(r.render(rot, 32, 2), 2))
        assert im.width == 32                                         # one tile = 32 px at zoom 3
        assert np.asarray(im)[:, :, 3].mean() > 60                    # something was drawn
    assert {m.name: m.cutout for m in mats}["fence"] is True


def test_sprite_set_frames():
    mesh, mats = photomodel.Builder(_house()).build()
    frames = render3d.sprite_set(render3d.Renderer(mesh, mats, 1), ss=1)
    assert sorted(frames) == [(z, r) for z in range(1, 6) for r in range(4)]
    assert [frames[(z, 0)].width for z in range(1, 6)] == [8, 16, 32, 64, 128]


def test_gable_end_meets_the_ridge():
    m = {"lot": 1, "materials": {"r": {"color": "#555555"}, "g": {"color": "#999999"}}, "parts": [
        {"type": "roof", "x": 2, "y": 2, "w": 8, "d": 6, "z": 5, "style": "gable_x", "pitch": 45, "overhang": 0.5,
         "mat": "r", "gable": "g"}]}
    mesh, mats = photomodel.Builder(m).build()
    gi = [x.name for x in mats].index("g")
    gable_top = max(max(q[2] for q in t) for t, k in zip(mesh.p, mesh.mat) if k == gi)
    ridge = max(max(q[2] for q in t) for t in mesh.p)
    assert math.isclose(gable_top, ridge) and math.isclose(ridge, 5 + 3 * math.tan(math.radians(45)))


@pytest.mark.parametrize("part, msg", [
    ({"type": "blob"}, "type one of"),
    ({"type": "roof", "x": 0, "y": 0, "w": 4, "d": 4, "z": 3, "style": "gable_x", "ends": ["+y"],
      "bargeboard": {"w": 0.1}}, "roof ends"),
    ({"type": "beam", "from": [1, 1, 1], "to": [1, 1, 1]}, "same point"),
])
def test_builder_errors(part, msg):
    with pytest.raises(GameError, match=msg):
        photomodel.Builder({"lot": 1, "materials": {}, "parts": [part]}).build()


def test_texture_lookup_wraps_at_the_edge():
    mat = render3d.Material("t", Image.new("RGB", (64, 64), (10, 20, 30)), size_m=(1, 1))
    u = np.array([-1e-9, 0.0, 0.9999999, 1.0, 7.25], np.float32)    # float modulo can round up to the width
    out = mat.sample(u, u)
    assert out.shape == (5, 4)


def test_roof_blocks_hip():
    blocks = roofs.roof_blocks([{"x0": 0, "y0": 0, "x1": 3, "y1": 5, "style": "hip"}], z=4)
    assert blocks and all(b["z"] >= 4 for b in blocks)
    assert {(b["x"], b["y"]) for b in blocks if b["z"] == 4} == {(x, y) for x in range(4) for y in range(6)}
