"""LIVE p1: the photo-to-building tools over MCP stdio (no Building Architect, no game needed), with a synthetic photo:
a facade drawn in perspective and a striped round tower; then the exported DAT is read back as the game reads it,
and the DAT encoder is checked byte-for-byte against the Architect's own BAT.DAT.

    python live/p1_photo.py [OUTDIR]
"""
import asyncio
import base64
import json
import math
import os
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "sc3k-mcp", "p1")


def synthetic_photo(path: str) -> dict:
    """A 'photo': sky, a facade (8 windows) warped into perspective, and a tower with 12 vertical stripes as a
    cylinder seen from the front (stripe x = centre + r sin(angle))."""
    W, H = 900, 700
    im = Image.new("RGB", (W, H), (70, 140, 220))
    flat = Image.new("RGB", (400, 300), (120, 140, 118))
    d = ImageDraw.Draw(flat)
    for i in range(4):
        for j in range(2):
            d.rectangle([30 + i * 95, 40 + j * 130, 90 + i * 95, 140 + j * 130], fill=(40, 48, 60))
    quad = [(470, 180), (860, 210), (850, 640), (480, 620)]           # where the facade's corners land in the photo
    from bat_mcp.photomodel import _homography
    coeffs = _homography([(0, 0), (400, 0), (400, 300), (0, 300)], quad)
    warped = flat.transform((W, H), Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(quad, fill=255)
    im.paste(warped, (0, 0), mask)
    cx, r, top, bot = 220, 120, 150, 640
    px = im.load()
    for y in range(top, bot):
        for x in range(cx - r, cx + r):
            a = math.asin(max(-1, min(1, (x - cx) / r)))
            stripe = int((a + math.pi / 2) / math.pi * 12) % 2
            px[x, y] = (200, 190, 170) if stripe else (90, 70, 60)
    im.save(path)
    return {"facade_quad": [list(p) for p in quad], "tower": {"left": [[cx - r, top], [cx - r, bot]],
                                                             "right": [[cx + r, top], [cx + r, bot]]}}


async def main():
    os.makedirs(OUT, exist_ok=True)
    photo = os.path.join(OUT, "synthetic_photo.png")
    geo = synthetic_photo(photo)
    model = {"name": "MCP Photo Test", "lot": 1, "materials": {
        "front": {"photo": "p1", "quad": geo["facade_quad"], "fit": True},
        "tower": {"photo": "p1", "cylinder": dict(geo["tower"], span_deg=160)},
        "wall": {"pattern": "clapboard_window", "color": "#7d8f7b", "size_m": [2.5, 3.5]},
        "roof": {"pattern": "roof_shingle", "color": "#4e5260"}, "lawn": {"texture": "grass", "size_m": [16, 16]},
        "sky": {"color": "#46a0e0"},
        "authored": {"facade": {"size_m": [7.0, 6.0], "base": {"pattern": "clapboard", "color": "body"}, "elements": [
            {"type": "band", "v": 0, "h": 0.4, "style": "dentil"}, {"type": "band", "v": 2.9, "h": 0.3, "style": "frieze"},
            {"type": "repeat", "n": 3, "du": 2.2, "element": {"type": "window", "u": 0.8, "v": 0.8, "w": 0.9, "h": 1.8,
                                                              "hood": True, "transom": True}},
            {"type": "door", "u": 2.6, "v": 3.4, "w": 1.6, "h": 2.5}, {"type": "railing", "u": 0.3, "v": 4.8, "w": 2.0, "h": 0.9},
            {"type": "ornament", "u": 5.0, "v": 3.6, "w": 1.4, "h": 0.8, "style": "sunburst"},
            {"type": "band", "u": 1.0, "w": 3.0, "v": 5.5, "h": 0.3, "style": "brackets", "spacing": 0.4},
            {"type": "arch", "u": 4.0, "v": 4.5, "w": 1.5, "h": 1.2, "rise": 0.5, "color": "clear"}]}},
        "fence": {"facade": {"size_m": [4.0, 0.9], "base": {"color": "clear"}, "elements": [
            {"type": "railing", "u": 0, "v": 0, "w": 4.0, "h": 0.9, "style": "iron", "color": "#202020"}]}},
        "trim": {"color": "#c8ccc0"}},
        "parts": [{"type": "ground", "mat": "lawn"},
                  {"type": "box", "x": 3, "y": 3, "z": 0, "w": 8, "d": 7, "h": 6, "mat": "wall",
                   "faces": {"+x": "front", "+y": "authored"}},
                  {"type": "roof", "x": 3, "y": 3, "w": 8, "d": 7, "z": 6, "style": "hip", "pitch": 40, "mat": "roof",
                   "ridge_cap": {"mat": "trim"}},
                  {"type": "roof", "x": 6, "y": 3.5, "w": 5.5, "d": 4, "z": 6, "style": "gable_x", "pitch": 45,
                   "mat": "roof", "gable": "authored", "ends": ["+x"], "bargeboard": {"mat": "trim"},
                   "finial": {"mat": "trim"}, "ridge_cap": {"mat": "trim"}},
                  {"type": "beam", "from": [11, 3, 3], "to": [12, 3, 2.5], "w": 0.15, "h": 0.25, "mat": "trim"},
                  {"type": "panel", "from": [15.5, 1], "to": [15.5, 15], "z": 0, "h": 0.9, "mat": "fence"},
                  {"type": "cylinder", "cx": 11, "cy": 12, "z": 0, "r": 1.6, "h": 8, "mat": "wall",
                   "photo": {"mat": "tower", "toward_deg": 0}},
                  {"type": "cone", "cx": 11, "cy": 12, "z": 8, "r": 1.9, "h": 3, "mat": "roof"},
                  {"type": "prop", "name": "sm decid1", "x": 3, "y": 13}]}
    steps = [
        ("photo_add", {"name": "p1", "image_path": photo}),
        ("photo_add", {"name": "p1 crop", "image_path": photo, "crop": [400, 100, 900, 700], "scale": 0.5}),
        ("photo_view", {"name": "p1", "grid": 100}),
        ("photo_rectify", {"name": "p1", "quad": geo["facade_quad"], "width_m": 8, "height_m": 6}),
        ("photo_model_render", {"model": model}),
        ("photo_model_render", {"model": dict(model, lighting="architect"), "rotation": 1, "zoom": 3}),
        ("photo_model_export", {"model": model}),
        ("photo_model_render", {"model": dict(model, parts=[{"type": "blob"}]), "_expect_error": True}),
        ("photo_model_render", {"model": dict(model, parts=[{"type": "roof", "x": 3, "y": 3, "w": 8, "d": 7, "z": 6,
                                                             "style": "gable_x", "ends": ["+y"],
                                                             "bargeboard": {"w": 0.1}}]), "_expect_error": True}),
        ("photo_buildings", {}),
        ("photo_view", {"name": "no such photo", "_expect_error": True}),
    ]
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(command=sys.executable, args=["-m", "bat_mcp"], env=env)
    errors = unexpected = 0
    exported = None
    async with stdio_client(params, errlog=open(os.devnull, "w")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for k, (tool, args) in enumerate(steps):
                args = dict(args)
                expect = args.pop("_expect_error", False)
                res = await s.call_tool(tool, args)
                texts = [c.text for c in res.content if c.type == "text"]
                for c in res.content:
                    if c.type == "image":
                        p = os.path.join(OUT, f"{k:02d}_{tool}.png")
                        open(p, "wb").write(base64.b64decode(c.data))
                        texts.append(f"[image {p}]")
                errors += res.isError
                unexpected += res.isError and not expect
                if tool == "photo_model_export" and not res.isError:
                    exported = json.loads(texts[0])
                print(f"{'ERR' if res.isError else 'ok '} {tool}: {' '.join(texts)[:200]}")
    # the exported file, read the way the game reads it
    from bat_mcp import sprites, datwriter
    rs = sprites.RenderedSet(exported["temp_file"])
    b = rs.buildings[0]
    z5 = [f for f in b["frames"] if f["zoom"] == 5]
    sizes = {(f["zoom"], f["rotation"]): rs.image(b, f["zoom"], f["rotation"]).size for f in b["frames"]}
    ok = (len(b["frames"]) == 20 and all(f["scale"] == 0 for f in z5) and b["size"] == 1
          and all(sizes[(z, 0)][0] == 8 * 2 ** (z - 1) for z in range(1, 6)))
    print(f"exported: {b['name']} size {b['size']}, {len(b['frames'])} frames, native zoom 5: "
          f"{all(f['scale'] == 0 for f in z5)}, widths {[sizes[(z, 0)][0] for z in range(1, 6)]} -> {'ok' if ok else 'BAD'}")
    unexpected += not ok
    # see-through facades: the fence material is a cut-out; the gable triangle meets the ridge
    from bat_mcp import photomodel
    mesh, mats = photomodel.Builder(model).build()
    cut = {m.name: m.cutout for m in mats}
    g = photomodel.Builder({"lot": 1, "materials": {"r": {"color": "#555555"}, "g": {"color": "#999999"}}, "parts": [
        {"type": "roof", "x": 2, "y": 2, "w": 8, "d": 6, "z": 5, "style": "gable_x", "pitch": 45, "overhang": 0.5,
         "mat": "r", "gable": "g"}]})
    gm, gmats = g.build()
    gi = [m.name for m in gmats].index("g")
    tops = [max(q[2] for q in tri) for tri, k in zip(gm.p, gm.mat) if k == gi]
    ridge = max(max(q[2] for q in tri) for tri in gm.p)
    print(f"gable end apex {max(tops):.2f} m, ridge {ridge:.2f} m -> {'ok' if abs(max(tops) - ridge) < 1e-6 else 'BAD'}")
    unexpected += abs(max(tops) - ridge) > 1e-6
    print(f"cut-out materials: fence {cut.get('fence')}, wall {cut.get('wall')} -> "
          f"{'ok' if cut.get('fence') and not cut.get('wall') else 'BAD'}")
    unexpected += not (cut.get("fence") and not cut.get("wall"))
    # the encoder against the Architect's own BAT.DAT
    from bat_mcp.app import RENDER_DAT
    if os.path.exists(RENDER_DAT):
        recs = sprites.ixf_records(open(RENDER_DAT, "rb").read())
        imgs = [(k, d) for k, d in recs.items() if k[0] == 0]
        bad = sum(1 for k, d in imgs if sprites.refpack(d[20:]) !=
                  sprites.refpack(datwriter.encode_image(sprites.decode_sprite(d))[0][20:]))
        print(f"encoder vs BAT.DAT: {len(imgs)} images, {bad} differ")
        unexpected += bad > 0
    print(f"{errors} errors (3 expected), {unexpected} unexpected")
    return unexpected


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
