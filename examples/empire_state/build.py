"""Empire State Building for SimCity 3000, built with the buildingarchitect MCP server - every step is a plain MCP
tool call, so any MCP client can replay it:

    python live/mcp_run.py bat examples/empire_state/build.py

Version 2 (after comparing version 1 with the game's own landmark, see notes/BAT_E2E_EMPIRE_STATE.md): the v1
massing plus the recessed centre bays of the shaft, cooler anti-aliased textures (textures2.py), street trees.
The spire is a custom prop whose four views spire.py draws (1 x 1 x 15 cells, 256 px, on prop_template's grid).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import textures, textures2, geometry, spire

SPIRE = spire.write()

X0, Y0, _, X1, Y1, TOP = geometry.bbox()
T = {t[0]: t for t in geometry.TIERS}
_t85 = T["t85"]
DECK = [{"prop": "blstrd1", "x": x, "y": y, "z": 86} for x in range(_t85[1], _t85[3] + 1) for y in (_t85[2], _t85[4])]

# full-height recessed centre bays (one cell deep) on every face of the shaft and the 72nd-floor tier
BAYS = []
for name, (ya, yb), (xa, xb) in (("shaft", (13, 17), (14, 16)), ("t72", (13, 17), (14, 16))):
    _, x0, y0, x1, y1, z0, z1, _n = T[name]
    for z in range(z0, z1 + 1):
        BAYS += [{"x": x, "y": y, "z": z} for x in (x0, x1) for y in range(ya, yb + 1)]
        BAYS += [{"x": x, "y": y, "z": z} for y in (y0, y1) for x in range(xa, xb + 1)]

TREES = [{"prop": "sm decid1", "x": x, "y": y} for x in (5, 25) for y in (3, 9, 15, 21, 27)]

STEPS = [
    ("bat_launch", {}),
    ("new_building", {"size": 4, "name": "MCP Empire State", "architect": "SiMCP 3000 example",
                      "building_type": "commercial",
                      "description": "Empire State Building, New York (1931), recreated over MCP from photographs"}),
    *textures2.steps(),
    *[st for st in textures.steps() if st[1]["name"] in ("esb storefront", "esb entrance")],
    ("create_prop", {"name": "esb spire", "width": 1, "depth": 1, "height": 15, "view_paths": SPIRE,
                     "overwrite": True}),
    *geometry.fill_steps(),
    *geometry.chamfer_steps(),
    *geometry.recess_steps(),
    ("remove_blocks", {"cells": BAYS}),
    ("paint_box", {"x0": X0, "y0": Y0, "z0": 1, "x1": X1, "y1": Y1, "z1": TOP, "walls": "esb2 facade",
                   "roof": "esb2 roof"}),
    ("paint_box", {"x0": X0, "y0": Y0, "z0": 72, "x1": X1, "y1": Y1, "z1": 86, "walls": "esb2 crown"}),
    ("paint_box", {"x0": 8, "y0": 0, "z0": 2, "x1": 22, "y1": 30, "z1": 5, "walls": "esb2 base"}),
    ("paint_box", {"x0": 8, "y0": 0, "z0": 1, "x1": 22, "y1": 30, "z1": 1, "walls": "esb storefront"}),
    ("paint_box", {"x0": 13, "y0": 13, "z0": 87, "x1": 17, "y1": 17, "z1": TOP, "walls": "esb2 mast",
                   "roof": "esb2 mast"}),
    ("place_detail", {"x": 16, "y": 30, "z": 3, "face": "+y", "detail": "esb entrance"}),
    ("fill_paint", {"x": 0, "y": 0, "z": 0, "face": "top", "texture": "clean concrete"}),
    ("place_props", {"props": [{"prop": "esb spire", "x": 15, "y": 15, "z": TOP + 1}] + DECK + TREES}),
    ("building_info", {}),
    ("save_building", {"name": "MCP Empire State", "overwrite": True}),
    ("render_building", {"zoom": 5}),
    ("view_image", {"mode": "paint", "zoom": 0, "all_sides": True}),
    ("game_building_image", {"name": "Empire State Building", "zoom": 5, "rotation": 0}),   # the game's own
]
