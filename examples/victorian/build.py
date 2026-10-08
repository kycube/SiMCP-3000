"""Queen Anne Victorian house (after the Haas-Lilienthal House, San Francisco, 1886) on a 2x2 lot, built with the
buildingarchitect MCP server; every step is a plain MCP tool call:

    python live/mcp_run.py bat examples/victorian/build.py

Scale: 2 cells per storey (the stock "silver spoons" windows are 1 x 2 faces = one storey); z 1 raised stone
basement, storeys at z 2-3, 4-5, 6-7, hip roof z 8-10. The street front is the +y side (on the right in the default
view); seen from the street the turret is on the left (+x) corner and the porch on the right.
Roofs come from the roof tool (a hip roof with a deck crossed by the front gable; it places the valleys); the turret's
round roof is a custom prop drawn by turret_roof.py. Write-up: notes/BAT_E2E_VICTORIAN.md.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import textures, turret_roof

ROOF_VIEWS = turret_roof.write()

# main body
BX0, BX1, BY0, BY1 = 3, 12, 2, 10           # front wall at y = 10


def box(x0, y0, z0, x1, y1, z1, **kw):
    return {"x0": x0, "y0": y0, "z0": z0, "x1": x1, "y1": y1, "z1": z1, **kw}


# turret: 3 x 3 octagon on the front-left corner (seen from the street), up to z 9; diagonal half-cubes (shape 1)
# keep the inner half: rotation 0 at (-x,+y), 2 at (+x,-y), 3 at (+x,+y)
TURRET = [{"x": x, "y": y, "z": z} for z in range(1, 10) for x in range(11, 14) for y in range(9, 12)
          if (x, y) not in ((13, 9), (13, 11), (11, 11))] + \
    [{"x": x, "y": y, "z": z, "shape": 1, "rotation": r} for z in range(1, 10)
     for x, y, r in ((13, 9, 2), (13, 11, 3), (11, 11, 0))]
BAY = [{"x": 9, "y": 11, "z": z} for z in range(1, 6)] + \
    [{"x": x, "y": 11, "z": z, "shape": 1, "rotation": r} for z in range(1, 6) for x, r in ((8, 0), (10, 3))]
STEPS_BLOCKS = [{"x": x, "y": 13, "z": 1, "shape": 2, "rotation": 3} for x in (4, 5)]
CHIMNEY = [{"x": 4, "y": 4, "z": z} for z in range(8, 13)]
LOGGIA = [{"x": x, "y": BY1, "z": z} for x in (7, 8) for z in (6, 7)]


# windows ("silver spoons 15", 1 x 2 faces = one storey): top cell v 0, bottom v 1
def window(x, y, z_top, face, name="silver spoons 15"):
    return [{"x": x, "y": y, "z": z_top, "face": face, "texture": name, "u": 0, "v": 0},
            {"x": x, "y": y, "z": z_top - 1, "face": face, "texture": name, "u": 0, "v": 1}]


WINDOWS = []
for zt in (3, 5, 7):
    for y in (3, 5, 7):                                        # side walls
        WINDOWS += window(BX0, y, zt, "-x") + window(BX1, y, zt, "+x")
    for x in (4, 6, 8, 10):                                    # back wall
        WINDOWS += window(x, BY0, zt, "-y")
    for face, x, y in (("+x", 13, 10), ("+y", 12, 11), ("+x+y", 13, 11), ("-x+y", 11, 11)):   # turret
        WINDOWS += window(x, y, zt, face)
for zt in (3, 5):                                              # bay window
    WINDOWS += window(9, 11, zt, "+y") + window(10, 11, zt, "+x+y") + window(8, 11, zt, "-x+y")
WINDOWS += window(7, BY1, 3, "+y") + window(6, BY1, 5, "+y") + window(4, BY1, 5, "+y")
WINDOWS += window(5, BY1, 7, "+y") + window(4, BY1, 7, "+y") + window(10, BY1, 7, "+y") + window(9, BY1, 7, "+y")
CORNICE = [{"x": x, "y": y, "z": 7, "face": f, "texture": "silver spoons 32"}
           for f, cells in (("+y", [(x, BY1) for x in range(BX0, 11)]), ("-y", [(x, BY0) for x in range(BX0, BX1 + 1)]),
                            ("-x", [(BX0, y) for y in range(BY0, BY1 + 1)]), ("+x", [(BX1, y) for y in range(BY0, 9)]))
           for x, y in cells]
TURRET_BAND = [{"x": x, "y": y, "z": 9, "face": f, "texture": "silver spoons 32"}
               for f, x, y in (("+x", 13, 10), ("+y", 12, 11), ("+x+y", 13, 11), ("-x+y", 11, 11), ("+x-y", 13, 9))]
GABLE_END = [{"x": x, "y": BY1, "z": z, "face": "+y", "texture": "vic shingle"}
             for z, xs in ((8, range(5, 11)), (9, range(6, 10)), (10, range(7, 9))) for x in xs]
PEDIMENT = [{"x": x, "y": 12, "z": z, "face": "+y", "texture": "vic shingle"}
            for z, xs in ((4, range(3, 7)), (5, range(4, 6))) for x in xs]
LOGGIA_BACK = [{"x": x, "y": BY1 - 1, "z": z, "face": "+y", "texture": "vic trim"} for x in (7, 8) for z in (6, 7)] + \
    [{"x": 6, "y": BY1, "z": z, "face": "-x", "texture": "vic trim"} for z in (6, 7)] + \
    [{"x": 9, "y": BY1, "z": z, "face": "+x", "texture": "vic trim"} for z in (6, 7)]

PROPS = [{"prop": "blstrd1", "x": x, "y": BY1, "z": 6} for x in (7, 8)] + \
    [{"prop": "column4", "x": x, "y": 12, "z": 2} for x in (3, 6)] + \
    [{"prop": "vic turret roof", "x": 12, "y": 10, "z": 10}] + \
    [{"prop": "sm decid1", "x": 1, "y": 13}, {"prop": "med decid1", "x": 14, "y": 4}] + \
    [{"prop": p, "x": x, "y": 14} for p, x in (("sm shrub1", 7), ("floweringbush1", 8), ("sm shrub2", 9),
                                               ("floweringbush1", 10), ("sm shrub1", 11), ("sm shrub2", 12))] + \
    [{"prop": "wall1d", "x": x, "y": 15} for x in list(range(0, 4)) + list(range(6, 16))]

CORNICE = [c for c in CORNICE if not (c["y"] == BY1 and c["x"] in (7, 8))]       # not over the loggia opening

STEPS = [
    ("bat_launch", {}),
    ("new_building", {"size": 2, "name": "MCP Queen Anne", "architect": "SiMCP 3000 example",
                      "building_type": "residential",
                      "description": "Queen Anne Victorian house after the Haas-Lilienthal House, San Francisco (1886)"}),
    *textures.steps(),
    ("create_prop", {"name": "vic turret roof", "width": 3, "depth": 3, "height": 5, "view_paths": ROOF_VIEWS,
                     "overwrite": True}),
    # 1. walls: body, bay, porch floor, steps, loggia opening - and their paint
    ("fill_box", box(BX0, BY0, 1, BX1, BY1, 7)),
    ("place_blocks", {"blocks": BAY + STEPS_BLOCKS}),
    ("fill_box", box(3, 11, 1, 6, 12, 1)),
    ("remove_blocks", {"cells": LOGGIA}),
    ("paint_box", box(0, 0, 1, 15, 15, 7, walls="vic siding", roof="vic roof")),
    ("paint_box", box(0, 0, 1, 15, 15, 1, walls="vic foundation", roof="vic foundation")),
    # 2. roofs: main hip roof with a deck, crossed by the front gable (valleys come from the roof tool); porch
    ("roof", {"parts": [{"x0": BX0, "y0": BY0, "x1": BX1, "y1": BY1, "style": "hip", "max_height": 3},
                        {"x0": 5, "y0": 6, "x1": 10, "y1": BY1, "style": "gable_y"}],
              "z": 8, "roof_texture": "vic roof", "gable_texture": "vic shingle"}),
    ("roof", {"parts": [{"x0": 3, "y0": 11, "x1": 6, "y1": 12, "style": "gable_y"}], "z": 4,
              "roof_texture": "vic roof", "gable_texture": "vic shingle"}),
    # 3. turret (after the roof: it rises through the roof's corner), chimney
    ("place_blocks", {"blocks": TURRET}),
    ("paint_box", box(11, 9, 1, 13, 11, 9, walls="vic siding", roof="vic trim")),
    ("paint_box", box(11, 9, 6, 13, 11, 9, walls="vic shingle")),
    ("paint_box", box(11, 9, 1, 13, 11, 1, walls="vic foundation")),
    ("place_blocks", {"blocks": CHIMNEY}),
    ("paint_box", box(4, 4, 8, 4, 4, 12, walls="brick 03", roof="vic trim")),
    # 4. small paint, ground
    ("paint_faces", {"faces": LOGGIA_BACK}),
    ("paint_faces", {"faces": [{"x": x, "y": 13, "z": 1, "face": "slope", "texture": "zsteps"} for x in (4, 5)]}),
    ("fill_paint", {"x": 0, "y": 0, "z": 0, "face": "top", "texture": "grass"}),
    ("paint_faces", {"faces": [{"x": x, "y": y, "z": 0, "face": "top", "texture": "walkway"}
                               for x in (4, 5) for y in (14, 15)]}),
    # 5. details: cornices first, windows over them, the door
    ("detail_faces", {"faces": CORNICE + TURRET_BAND}),
    ("detail_faces", {"faces": WINDOWS}),
    ("place_detail", {"x": 5, "y": BY1, "z": 3, "face": "+y", "detail": "silver spoons 20"}),
    # rake trim along the gable edges (seen from the street the left edge rises "/", the right edge falls "\\")
    ("detail_faces", {"faces": [{"x": x, "y": BY1, "z": z, "face": "+y", "texture": t}
                                for x, z, t in ((10, 8, "silver spoons 91"), (9, 9, "silver spoons 91"),
                                                (8, 10, "silver spoons 91"), (5, 8, "silver spoons 92"),
                                                (6, 9, "silver spoons 92"), (7, 10, "silver spoons 92"))] +
                               [{"x": x, "y": 12, "z": z, "face": "+y", "texture": t}
                                for x, z, t in ((6, 4, "silver spoons 91"), (5, 5, "silver spoons 91"),
                                                (3, 4, "silver spoons 92"), (4, 5, "silver spoons 92"))]}),
    # 6. props
    ("place_props", {"props": PROPS}),
    ("building_info", {}),
    ("view_image", {"mode": "paint", "zoom": 5, "all_sides": True}),
    ("save_building", {"name": "MCP Queen Anne", "overwrite": True}),
    ("render_building", {"zoom": 5}),
]
