"""LIVE b1: build a small cottage with the Building Architect through the bat_mcp server over MCP stdio (the way
any MCP client would), save the pictures it returns, and count errors.

    python live/b1_stdio.py [OUTDIR]
"""
import asyncio
import base64
import json
import os
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "sc3k-mcp", "b1")
SAVE = os.path.join(tempfile.gettempdir(), "sc3k-mcp", "MCP Cottage.bld")

WALLS = (2, 2, 1, 5, 5, 3)
_BRICK = [r for k in range(4) for r in [("bbbbbbbmbbbbbbbm" if k % 2 == 0 else "bbbmbbbbbbbmbbbb")] * 3 + ["m" * 16]]
_WINDOW = ["".join("f" if 5.5 < ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** 0.5 <= 7 else
                   "g" if ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** 0.5 <= 5.5 else "." for x in range(16)) for y in range(16)]


def _post_views() -> list[str]:
    """Four view pictures for a 1 x 1 x 2 orange post, drawn on the prop template (written to OUT)."""
    sys.path.insert(0, ROOT)
    from bat_mcp.custom import prop_template
    out = []
    recol = {(205, 205, 205): (230, 120, 30, 255), (158, 158, 158): (170, 80, 20, 255),
             (242, 242, 242): (255, 170, 80, 255), (255, 0, 255): (0, 0, 0, 0)}
    for v in range(4):
        im = prop_template(1, 1, 2, v).convert("RGBA")
        im.putdata([recol.get(c[:3], (60, 30, 10, 255)) for c in im.getdata()])
        path = os.path.join(OUT, f"post_view{v}.png")
        im.save(path)
        out.append(path)
    return out


STEPS = [
    ("guide", {"topic": "lot"}),
    ("bat_launch", {}),
    ("new_building", {"size": 1, "name": "MCP Cottage", "architect": "bat_mcp test", "building_type": "residential",
                      "description": "A brick cottage built over MCP"}),
    ("fill_box", dict(zip(("x0", "y0", "z0", "x1", "y1", "z1"), WALLS[:5] + (1,)))),     # ground floor
    ("copy_blocks", {"x0": 2, "y0": 2, "z0": 1, "x1": 5, "y1": 5, "z1": 1, "dz": 1}),       # second storey
    ("copy_blocks", {"x0": 2, "y0": 2, "z0": 1, "x1": 5, "y1": 5, "z1": 1, "dz": 2}),       # third
    ("roof", {"parts": [{"x0": 2, "y0": 2, "x1": 5, "y1": 5, "style": "gable_y"}], "z": 4, "pitch": 0.5}),
    ("paint_box", dict(zip(("x0", "y0", "z0", "x1", "y1", "z1"), WALLS), walls="brick 01", wall_detail="ranch 02")),
    ("paint_box", {"x0": 2, "y0": 2, "z0": 4, "x1": 5, "y1": 5, "z1": 4, "walls": "brick 01",   # gable ends
                   "roof": "shingle 02"}),                                                     # + both slopes
    ("fill_paint", {"x": 0, "y": 0, "z": 0, "face": "top", "texture": "grass"}),             # the whole lot
    ("place_props", {"props": [{"prop": "sm evgn1", "x": 0, "y": 6}, {"prop": "lamp1", "x": 6, "y": 0}]}),
    ("copy_blocks", {"x0": 0, "y0": 6, "z0": 1, "x1": 0, "y1": 6, "z1": 3, "dx": 7, "dy": 1}),   # a second tree
    ("create_texture", {"name": "mcp blue brick", "rows": _BRICK, "palette": {"b": "#3a5f9a", "m": "220,220,210"},
                        "scale": 2, "overwrite": True}),
    ("create_texture", {"name": "mcp round window", "kind": "detail", "rows": _WINDOW,
                        "palette": {"f": "#f0f0f0", "g": "#203040", ".": "transparent"}, "overwrite": True}),
    ("prop_template", {"width": 1, "depth": 1, "height": 2}),
    ("create_prop", {"name": "mcp orange post", "width": 1, "depth": 1, "height": 2, "view_paths": "POST_VIEWS",
                     "overwrite": True}),
    ("fill_paint", {"x": 5, "y": 3, "z": 1, "face": "+x", "texture": "mcp blue brick"}),
    ("detail_faces", {"faces": [{"x": 5, "y": 3, "z": 2, "face": 3, "texture": "mcp round window"}]}),
    ("place_props", {"props": [{"prop": "mcp orange post", "x": 7, "y": 3}]}),
    ("placed_props", {}),
    ("place_detail", {"x": 5, "y": 5, "z": 3, "face": "+y", "detail": "ranch 02"}),       # 2 x 2 faces
    ("texture_sheet", {"kind": "details", "search": "ranch"}),
    ("game_building_image", {"name": "Mayor's House", "zoom": 4}),
    ("library", {"kind": "props", "search": "flora"}),
    ("shapes", {}),
    ("building_info", {}),
    ("blocks", {"z_min": 4, "z_max": 4}),
    ("view_image", {"mode": "paint", "zoom": 5, "all_sides": True}),
    ("view_image", {"mode": "construct"}),
    ("rotate_building", {"turns": 1}),
    ("undo", {}),                                                       # turns it back
    ("remove_props", {"at": [{"x": 6, "y": 0}]}),                       # the lamp
    ("undo", {}),                                                       # puts the lamp back
    ("redo", {}),                                                       # and removes it again
    ("save_building", {"name": SAVE, "overwrite": True}),
    ("render_building", {"zoom": 4}),
    ("project_image", {"name": SAVE}),
    ("undo", {}),                                                       # nothing: a render reset the log
    ("place_blocks", {"blocks": [{"x": 99, "y": 0, "z": 1}]}),          # expected error: outside the lot
    ("paint_faces", {"faces": [{"x": 0, "y": 0, "z": 5, "face": 0, "texture": "brick 01"}]}),   # expected: no block
    ("place_props", {"props": [{"prop": "sm decid1", "x": 3, "y": 3}]}),                       # expected: occupied
    ("create_texture", {"name": "mcp bad size", "rows": ["ab" * 10] * 20, "palette": {"a": "#000000", "b": "#ffffff"}}),
    ("paint_faces", {"faces": [{"x": 2, "y": 2, "z": 1, "face": "-x", "texture": "grass"},     # expected: all or
                               {"x": 0, "y": 7, "z": 9, "face": "top", "texture": "grass"}]}),  # nothing (no block)
]                                                                       # expected: 20 x 20 is not a multiple of 16


async def main():
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(command=sys.executable, args=["-m", "bat_mcp"], env=env)
    errors, images = 0, 0
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            tools = (await s.list_tools()).tools
            print(f"server {init.serverInfo.name}: {len(tools)} tools, "
                  f"{sum(t.annotations is not None for t in tools)} annotated")
            views = _post_views()
            for k, (tool, args) in enumerate(STEPS):
                args = {a: (views if v == "POST_VIEWS" else v) for a, v in args.items()}
                res = await s.call_tool(tool, args)
                texts = [c.text for c in res.content if c.type == "text"]
                for c in res.content:
                    if c.type == "image":
                        images += 1
                        p = os.path.join(OUT, f"{k:02d}_{tool}.png")
                        open(p, "wb").write(base64.b64decode(c.data))
                        texts.append(f"[image {p}]")
                errors += res.isError
                print(f"{'ERR' if res.isError else 'ok '} {tool} {json.dumps(args)[:80]}: {' '.join(texts)[:240]}")
    print(f"{errors} errors (5 expected), {images} images in {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
