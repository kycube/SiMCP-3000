"""Version 1 (built from the photo and Wikipedia only, before looking at the game's own landmark). Replay with
    python live/mcp_run.py bat examples/empire_state/build_v1.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import textures, geometry, spire

spire.write()

X0, Y0, _, X1, Y1, TOP = geometry.bbox()
T = {t[0]: t for t in geometry.TIERS}
_t85 = T["t85"]
DECK = [{"prop": "blstrd1", "x": x, "y": y, "z": 86} for x in range(_t85[1], _t85[3] + 1) for y in (_t85[2], _t85[4])]
SPIRE = [os.path.join(HERE, "spire", f"spire_view{k}.png") for k in range(4)]

STEPS = [
    ("bat_launch", {}),
    ("new_building", {"size": 4, "name": "MCP Empire State", "architect": "SiMCP 3000 example",
                      "building_type": "commercial",
                      "description": "Empire State Building, New York (1931), recreated over MCP from photographs"}),
    *textures.steps(),
    ("create_prop", {"name": "esb spire", "width": 1, "depth": 1, "height": 15, "view_paths": SPIRE,
                     "overwrite": True}),
    *geometry.fill_steps(),
    *geometry.chamfer_steps(),
    *geometry.recess_steps(),
    ("paint_box", {"x0": X0, "y0": Y0, "z0": 1, "x1": X1, "y1": Y1, "z1": TOP, "walls": "esb facade",
                   "roof": "esb roof"}),
    ("paint_box", {"x0": 8, "y0": 0, "z0": 2, "x1": 22, "y1": 30, "z1": 5, "walls": "esb base"}),
    ("paint_box", {"x0": 8, "y0": 0, "z0": 1, "x1": 22, "y1": 30, "z1": 1, "walls": "esb storefront"}),
    ("paint_box", {"x0": 13, "y0": 13, "z0": 87, "x1": 17, "y1": 17, "z1": TOP, "walls": "esb mast",
                   "roof": "esb mast"}),
    ("place_detail", {"x": 16, "y": 30, "z": 3, "face": "+y", "detail": "esb entrance"}),
    ("fill_paint", {"x": 0, "y": 0, "z": 0, "face": "top", "texture": "clean concrete"}),
    ("place_props", {"props": [{"prop": "esb spire", "x": 15, "y": 15, "z": TOP + 1}] + DECK}),
    ("building_info", {}),
    ("view_image", {"mode": "paint", "zoom": 0, "all_sides": True}),
    ("save_building", {"name": "MCP Empire State", "overwrite": True}),
    ("render_building", {"zoom": 5}),
]
