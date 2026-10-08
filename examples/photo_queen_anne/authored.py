"""The Haas-Lilienthal House recreated in authored pixels: the photograph is the reference for every position and
proportion (measured with photo_view), but nothing is pasted from it - every wall is drawn element by element
(facade materials) and the building is lit by the renderer like the game's own buildings.

Measuring (photo crop 788 x 1355 px): the camera is level (verticals stay vertical), so the facade plane has one
scale, about 58 px per metre (the double door is 115 px wide, the parked car 4.8 m = 415 px a few metres nearer).
The tower axis is the origin of the front (photo x 130); porch floor at photo y 990 = z 2.

Lot 2x2 (32 x 32 m); the street front faces +x (the lit left side in the default view); seen from the street the
tower is on the left (-y end) and the porch on the right (+y end). A narrow, deep house: the body is 10.5 m wide
(y 9.5..20) and 17.5 m deep (x 8..25.5); raised basement z 0..2, storeys z 2-6.6, 6.6-10.2, 10.2-12.4 and the
attic in the roof. Faces: u = metres from the left edge seen from outside, v = metres down from the top.

    python examples/photo_queen_anne/authored.py          -> authored.json (the model)
"""
import json
import math
import os

# the photo's scheme: a mid grey-green body, LIGHTER sage trim (frames, bands, columns, bargeboards) and dark
# recesses (sampled in its shade: body #374342, trim #9daba3 - #a0aca4, recesses #262c2a)
PALETTE = {"body": "#76897a", "trim": "#a6b2a3", "dark": "#2f3833", "light": "#d6d2be", "glass": "#232c37",
           "sky": "#58708a", "sash": "#3a4540", "accent": "#b08c48", "door": "#4c3a2e", "curtain": "#d9cfb6"}
CLAP = {"pattern": "clapboard", "color": "body", "size_m": [1.0, 1.0]}
FX = 25.5                                             # the front wall
Y0, Y1 = 9.5, 20.0                                    # the body's sides
ZE = 12.4                                             # eaves


def win(u, v, w=0.9, h=2.0, **kw):
    return {"type": "window", "u": u, "v": v, "w": w, "h": h, **kw}


def facade(w, h, elements, base=CLAP):
    return {"facade": {"size_m": [w, h], "palette": PALETTE, "base": base, "elements": elements}}


def bands():
    """Floor-line bands of the body (v from the eaves, z 12.4)."""
    return [{"type": "band", "v": 0.0, "h": 0.4, "style": "brackets", "spacing": 0.9},
            {"type": "band", "v": 2.2, "h": 0.3, "style": "dentil"},
            {"type": "band", "v": 5.75, "h": 0.3, "style": "molding"}]


def side_facade(width):
    """A side wall: hooded windows on three storeys at a steady rhythm."""
    n = int((width - 1.0) // 2.4)
    u0 = (width - (n - 1) * 2.4 - 0.9) / 2
    els = bands()
    for v, h in ((0.55, 1.5), (3.0, 2.3), (6.7, 2.7)):
        els.append({"type": "repeat", "n": n, "du": 2.4,
                    "element": win(u0, v, 0.9, h, hood=True, curtain="curtain" if v > 2 else None)})
    return facade(width, ZE - 2, els)


# the main front (+x, y 9.5..20, z 2..12.4); the tower hides u < 2.5, the porch stands in front of u 4.4..10.5
FRONT = facade(10.5, ZE - 2, bands() + [
    win(7.0, 0.55, 0.85, 1.5, hood=True), win(9.0, 0.55, 0.85, 1.5, hood=True),            # third floor
    win(8.7, 2.9, 0.85, 2.3, pediment=True, curtain="curtain"),                              # second floor
    win(4.75, 7.0, 0.7, 2.6, hood=True),                                                    # behind the porch
    {"type": "door", "u": 6.2, "v": 7.3, "w": 1.9, "h": 3.1},
    win(8.75, 7.0, 0.95, 2.6, hood=True, curtain="curtain")])

# the third floor under the front gable stands 0.5 m proud (y 10.4..16.2): the open loggia behind the balcony
LOGGIA = facade(5.8, 2.2, [
    {"type": "band", "v": 0.0, "h": 0.3, "style": "brackets", "spacing": 0.45},
    {"type": "arch", "u": 1.75, "v": 0.35, "w": 2.25, "h": 1.85, "rise": 0.35, "color": "#232a27"},
    {"type": "railing", "u": 1.75, "v": 0.5, "w": 2.25, "h": 0.28, "spindle": 0.12},
    win(4.3, 0.45, 0.9, 1.5, hood=True)])

# the front gable: 5.8 m at 47 degrees, its end 2.9 tan 47 = 3.11 m high: fish-scale skirt, a bracketed collar,
# a sunburst panel in the apex and the king post hanging from it
GABLE_W, GABLE_PITCH = 5.8, 47
GABLE_H = GABLE_W / 2 * math.tan(math.radians(GABLE_PITCH))
GABLE = facade(GABLE_W, GABLE_H, [
    {"type": "field", "u": 0, "v": GABLE_H - 0.95, "w": GABLE_W, "h": 0.95, "pattern": "fishscale", "color": "body",
     "size_m": [0.5, 0.5]},
    {"type": "band", "v": GABLE_H - 1.25, "h": 0.3, "style": "brackets", "spacing": 0.4},
    {"type": "ornament", "u": GABLE_W / 2 - 0.8, "v": 0.85, "w": 1.6, "h": 0.8, "style": "sunburst"},
    {"type": "rect", "u": GABLE_W / 2 - 0.06, "v": 0.2, "w": 0.12, "h": GABLE_H - 1.0, "color": "light"},
    {"type": "ornament", "u": GABLE_W / 2 - 0.15, "v": GABLE_H - 0.95, "w": 0.3, "h": 0.3, "style": "diamond",
     "color": "light"}], base={"color": "body"})

# the second-floor bay (y 14.35..17.5) projecting 0.7 m: garland frieze, sunburst panels over the narrow lights
BAY_W = 3.15
BAYBOX = facade(BAY_W, 3.25, [
    {"type": "band", "v": 0.0, "h": 0.35, "style": "frieze"},
    {"type": "ornament", "u": 0.2, "v": 0.45, "w": 0.65, "h": 0.4, "style": "sunburst"},
    {"type": "ornament", "u": 2.3, "v": 0.45, "w": 0.65, "h": 0.4, "style": "sunburst"},
    win(0.25, 0.95, 0.55, 2.0), win(0.95, 0.6, 1.25, 2.35, transom=True, curtain="curtain"), win(2.35, 0.95, 0.55, 2.0),
    {"type": "band", "v": 3.0, "h": 0.25, "style": "molding"}])
BAYSIDE = facade(0.7, 3.25, [{"type": "band", "v": 0.0, "h": 0.35, "style": "frieze"}, win(0.12, 0.95, 0.46, 2.0),
                             {"type": "band", "v": 3.0, "h": 0.25, "style": "molding"}])

# porch: pediment 6.1 m at 32 degrees; the front and sides are open arches (a see-through fascia)
PORCH_W, PORCH_PITCH = 6.1, 32
PEDIMENT = facade(PORCH_W, PORCH_W / 2 * math.tan(math.radians(PORCH_PITCH)), [
    {"type": "ornament", "u": PORCH_W / 2 - 0.9, "v": 0.55, "w": 1.8, "h": 0.9, "style": "fan"},
    {"type": "railing", "u": 0.9, "v": 1.45, "w": PORCH_W - 1.8, "h": 0.35, "spindle": 0.16, "color": "light"},
    {"type": "band", "v": 1.65, "h": 0.25, "style": "dentil"}], base={"color": "body"})


def porch_fascia(w):
    return facade(w, 1.6, [
        {"type": "band", "v": 0.0, "h": 0.45, "style": "dentil"},
        {"type": "arch", "u": 0.35, "v": 0.6, "w": w - 0.7, "h": 1.0, "rise": 0.45, "color": "clear"}],
        base={"color": "body"})


BALUSTRADE = facade(2.0, 0.95, [{"type": "railing", "u": 0, "v": 0, "w": 2.0, "h": 0.95, "spindle": 0.17,
                                 "color": "light"}], base={"color": "clear"})
IRON = facade(4.0, 0.85, [{"type": "railing", "u": 0, "v": 0, "w": 4.0, "h": 0.85, "spindle": 0.13,
                           "style": "iron", "color": "#1d2120"}], base={"color": "clear"})

# round tower: the prisms start their u at "angle" -180 (the back), so the street side (+x) is at half the
# circumference; windows at -60, 0, +60 degrees from the street
R_BAY, R_TUR = 1.6, 1.95
C = (25.3, 10.4)                                      # tower axis


def tower_windows(r, v, w, h, angles=(-60, 0, 60), **kw):
    mid = math.pi * r
    return [win(mid + r * math.radians(a) - w / 2, v, w, h, **kw) for a in angles]


BAY = facade(2 * math.pi * R_BAY, 10.2, [                         # z 2..12.2
    {"type": "band", "v": 0.0, "h": 0.3, "style": "molding"},
    {"type": "band", "v": 2.0, "h": 0.3, "style": "dentil"},
    {"type": "band", "v": 5.6, "h": 0.3, "style": "molding"},
    {"type": "band", "v": 9.35, "h": 0.4, "style": "frieze"},
    *tower_windows(R_BAY, 0.45, 0.7, 1.35, hood=True),
    *tower_windows(R_BAY, 2.6, 0.8, 2.5, transom=True, curtain="curtain"),
    *tower_windows(R_BAY, 6.2, 0.8, 2.9, hood=True, curtain="curtain")])

TURRET = facade(2 * math.pi * R_TUR, 3.1, [                      # z 12.3..15.4
    {"type": "field", "u": 0, "v": 1.35, "w": 2 * math.pi * R_TUR, "h": 1.45, "pattern": "fishscale",
     "color": "body", "size_m": [0.5, 0.5]},
    {"type": "band", "v": 0.0, "h": 0.3, "style": "brackets", "spacing": 0.5},
    {"type": "band", "v": 0.4, "h": 0.55, "style": "frieze", "color": "trim"},
    {"type": "band", "v": 2.8, "h": 0.3, "style": "brackets", "spacing": 0.5},
    *tower_windows(R_TUR, 0.35, 0.75, 1.15, angles=(-70, 70), pediment=True)], base={"color": "body"})

# the wall dormer on the turret's street side: a window rising through the eave under its own small gable
DORMER = facade(1.2, 2.3, [{"type": "band", "v": 0.0, "h": 0.2, "style": "plain"},
                           win(0.2, 0.35, 0.8, 1.5, transom=True), {"type": "band", "v": 2.0, "h": 0.3,
                                                                     "style": "brackets", "spacing": 0.3}])
DORMER_GABLE = facade(1.2, 0.6 * math.tan(math.radians(55)), [
    {"type": "ornament", "u": 0.3, "v": 0.35, "w": 0.6, "h": 0.4, "style": "sunburst"}], base={"color": "body"})

BASEMENT = facade(10.5, 2.0, [
    {"type": "repeat", "n": 3, "du": 2.6, "element": {"type": "rect", "u": 3.0, "v": 0.6, "w": 0.7, "h": 0.6,
                                                      "color": "#2a302e"}},
    {"type": "band", "v": 0.0, "h": 0.18, "style": "plain", "color": "#9a9e98"}],
    base={"pattern": "stone", "color": "#b9bcb8", "size_m": [2.0, 1.0]})

# the cross gable on the garden side (+y): a two-storey bay 5 m wide under its own gable
SIDE_BAY = facade(5.0, ZE - 2, bands() + [
    {"type": "repeat", "n": 2, "du": 2.3, "element": win(1.0, 0.55, 0.85, 1.5, hood=True)},
    {"type": "repeat", "n": 2, "du": 2.3, "element": win(1.0, 3.0, 0.85, 2.3, transom=True, curtain="curtain")},
    {"type": "repeat", "n": 3, "du": 1.5, "element": win(0.85, 6.7, 0.8, 2.7, hood=True, curtain="curtain")}])
SIDE_GABLE = facade(5.0, 2.5 * math.tan(math.radians(GABLE_PITCH)), [
    {"type": "field", "u": 0, "v": 1.2, "w": 5.0, "h": 1.5, "pattern": "fishscale", "color": "body",
     "size_m": [0.5, 0.5]},
    win(2.1, 0.75, 0.8, 1.0, arch=True)], base={"color": "body"})

# the slanted side bay: a trapezoid on the +y wall, x 21..24.8, 1 m deep (edges 0, 1, 2 = the three glazed sides)
SBAY = [[24.8, Y1], [24.2, Y1 + 1.0], [21.6, Y1 + 1.0], [21.0, Y1]]
# and one on the tower side (-y), further back (listed so that its edges 1, 2, 3 are the glazed sides)
SBAY2 = [[17.8, Y0], [14.0, Y0], [14.6, Y0 - 1.0], [17.2, Y0 - 1.0]]
SBAY_FRONT = facade(2.6, 8.2, [{"type": "band", "v": 0.0, "h": 0.35, "style": "brackets", "spacing": 0.5},
                               win(0.75, 0.7, 1.1, 2.3, pediment=True, curtain="curtain"),
                               {"type": "band", "v": 3.55, "h": 0.25, "style": "dentil"},
                               win(0.7, 4.6, 1.2, 2.9, transom=True, curtain="curtain"),
                               {"type": "band", "v": 7.8, "h": 0.4, "style": "frieze"}])
SBAY_SIDE = facade(1.17, 8.2, [{"type": "band", "v": 0.0, "h": 0.35, "style": "brackets", "spacing": 0.5},
                               win(0.3, 0.9, 0.57, 2.1), {"type": "band", "v": 3.55, "h": 0.25, "style": "dentil"},
                               win(0.3, 4.8, 0.57, 2.7), {"type": "band", "v": 7.8, "h": 0.4, "style": "frieze"}])

ROOF = {"type": "roof", "mat": "roof", "ridge_cap": {"mat": "ridge"}}
BARGE = {"mat": "barge", "w": 0.16, "h": 0.38}
MODEL = {
    "name": "MCP Haas-Lilienthal House",
    "architect": "SiMCP 3000 example (authored from a photo)",
    "description": "Queen Anne Victorian, San Francisco 1886 - recreated in drawn pixels from a photograph "
                   "(reference: Ppienovagem, CC BY 4.0)",
    "lot": 2, "lighting": "game",
    "materials": {
        "front": FRONT, "loggia": LOGGIA, "gable": GABLE, "bay_box": BAYBOX, "bay_side": BAYSIDE,
        "pediment": PEDIMENT, "fascia_front": porch_fascia(PORCH_W), "fascia_side": porch_fascia(2.8),
        "balustrade": BALUSTRADE, "iron": IRON, "bay": BAY, "turret": TURRET, "dormer": DORMER,
        "dormer_gable": DORMER_GABLE, "sbay_front": SBAY_FRONT, "sbay_side": SBAY_SIDE, "basement_front": BASEMENT, "side_bay": SIDE_BAY, "side_gable": SIDE_GABLE,
        "side_y": side_facade(FX - 8), "side_x": side_facade(Y1 - Y0),
        "stone": {"pattern": "stone", "color": "#b9bcb8", "size_m": [2.0, 1.0]},
        "roof": {"pattern": "slate", "color": "#3e434f", "size_m": [1.2, 1.2]}, "ridge": {"color": "#7c8390"},
        "cone": {"pattern": "shingle", "color": "#6a645d", "color2": "#46403b", "size_m": [0.8, 0.6]},
        "trim": {"color": "#97a396"}, "light": {"color": "#dcd8c4"}, "barge": {"color": "#b3bdaf"},
        "finial": {"color": "#353d3a"}, "finial_body": {"color": "#6b7a72"}, "body": {"color": "#76897a"},
        "brick": {"pattern": "brick", "color": "#7b5d52", "color2": "#4b3a33", "size_m": [1.0, 1.0]},
        "lawn": {"texture": "grass", "size_m": [16, 16]}, "path": {"texture": "walkway", "size_m": [8, 8]},
    },
    "parts": [
        {"type": "ground", "mat": "lawn"},
        {"type": "patch", "x": 28.3, "y": 15.6, "w": 3.7, "d": 2.0, "mat": "path"},
        # basement, body, floor ledges and cornice
        {"type": "box", "x": 8, "y": Y0, "z": 0, "w": FX - 8, "d": Y1 - Y0, "h": 2, "mat": "stone",
         "faces": {"+x": "basement_front"}},
        {"type": "box", "x": 8, "y": Y0, "z": 2, "w": FX - 8, "d": Y1 - Y0, "h": ZE - 2, "mat": "side_x",
         "faces": {"+x": "front", "+y": "side_y", "-y": "side_y"}},
        {"type": "box", "x": 7.9, "y": Y0 - 0.1, "z": 1.85, "w": FX - 7.8, "d": Y1 - Y0 + 0.2, "h": 0.2, "mat": "trim"},
        {"type": "box", "x": 7.92, "y": Y0 - 0.08, "z": 6.45, "w": FX - 7.84, "d": Y1 - Y0 + 0.16, "h": 0.18,
         "mat": "trim"},
        {"type": "box", "x": 7.92, "y": Y0 - 0.08, "z": 10.05, "w": FX - 7.84, "d": Y1 - Y0 + 0.16, "h": 0.15,
         "mat": "trim"},
        {"type": "box", "x": 7.8, "y": Y0 - 0.2, "z": ZE - 0.3, "w": FX - 7.6, "d": Y1 - Y0 + 0.4, "h": 0.3,
         "mat": "trim"},
        # main hip roof
        dict(ROOF, x=8, y=Y0, w=FX - 8, d=Y1 - Y0, z=ZE, style="hip", pitch=40, overhang=0.5),
        # the second-floor bay, the balcony slab running over it, the loggia storey and the front gable
        {"type": "box", "x": FX, "y": 14.35, "z": 6.6, "w": 0.7, "d": BAY_W, "h": 3.25, "mat": "bay_side",
         "faces": {"+x": "bay_box", "top": "trim"}},
        {"type": "box", "x": FX, "y": 11.9, "z": 9.85, "w": 1.1, "d": 5.6, "h": 0.3, "mat": "trim",
         "faces": {"top": "body"}},
        {"type": "box", "x": FX, "y": 10.4, "z": 10.15, "w": 0.5, "d": GABLE_W, "h": ZE - 10.15, "mat": "body",
         "faces": {"+x": "loggia"}},
        {"type": "panel", "from": [26.5, 12.0], "to": [26.5, 14.4], "z": 10.15, "h": 0.95, "mat": "balustrade"},
        {"type": "box", "x": 26.0, "y": 10.4, "z": ZE - 0.2, "w": 0.55, "d": GABLE_W, "h": 0.2, "mat": "trim"},
        dict(ROOF, x=18, y=10.4, w=8.0, d=GABLE_W, z=ZE, style="gable_x", pitch=GABLE_PITCH, overhang=0.5,
             gable="gable", ends=["+x"], bargeboard=BARGE, finial={"mat": "barge", "h": 1.0, "r": 0.09}),
        # the cross gable on the garden side
        {"type": "box", "x": 13, "y": Y1, "z": 0, "w": 5, "d": 1.0, "h": 2, "mat": "stone"},
        {"type": "box", "x": 13, "y": Y1, "z": 2, "w": 5, "d": 1.0, "h": ZE - 2, "mat": "body",
         "faces": {"+y": "side_bay"}},
        {"type": "box", "x": 12.9, "y": Y1, "z": ZE - 0.3, "w": 5.2, "d": 1.1, "h": 0.3, "mat": "trim"},
        dict(ROOF, x=13, y=14, w=5, d=7.0, z=ZE, style="gable_y", pitch=GABLE_PITCH, overhang=0.5,
             gable="side_gable", ends=["+y"], bargeboard=BARGE, finial={"mat": "barge", "h": 0.8, "r": 0.08}),
        # the slanted bay on the garden side near the front (two storeys, its own hip roof)
        {"type": "extrude", "points": SBAY, "z": 0, "h": 2, "mat": "stone"},
        {"type": "extrude", "points": SBAY, "z": 2, "h": 8.2, "mat": "body",
         "faces": {"0": "sbay_side", "1": "sbay_front", "2": "sbay_side", "top": "trim"}},
        {"type": "extrude", "points": [[x, y + (0.08 if y > Y1 else 0)] for x, y in SBAY], "z": 10.2, "h": 0.25,
         "mat": "trim"},
        dict(ROOF, x=21.2, y=Y1, w=3.4, d=0.95, z=10.45, style="hip", pitch=40, overhang=0.25),
        {"type": "extrude", "points": SBAY2, "z": 0, "h": 2, "mat": "stone"},
        {"type": "extrude", "points": SBAY2, "z": 2, "h": 8.2, "mat": "body",
         "faces": {"1": "sbay_side", "2": "sbay_front", "3": "sbay_side", "top": "trim"}},
        {"type": "extrude", "points": [[x, y - (0.08 if y < Y0 else 0)] for x, y in SBAY2], "z": 10.2, "h": 0.25,
         "mat": "trim"},
        dict(ROOF, x=14.2, y=Y0 - 0.95, w=3.4, d=0.95, z=10.45, style="hip", pitch=40, overhang=0.25),
        # chimneys
        {"type": "box", "x": 11.5, "y": 17.8, "z": ZE, "w": 1.0, "d": 1.0, "h": 6.6, "mat": "brick"},
        {"type": "box", "x": 11.35, "y": 17.65, "z": ZE + 6.6, "w": 1.3, "d": 1.3, "h": 0.25, "mat": "trim"},
        {"type": "box", "x": 19.0, "y": 9.9, "z": ZE, "w": 1.0, "d": 0.9, "h": 5.8, "mat": "brick"},
        {"type": "box", "x": 18.85, "y": 9.75, "z": ZE + 5.8, "w": 1.3, "d": 1.2, "h": 0.25, "mat": "trim"},
        # the corner tower: rounded bay (three tiers of windows), rings, turret band, wall dormer, cone, finial
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 0, "r": R_BAY, "h": 2, "mat": "stone"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 2, "r": R_BAY, "h": 10.2, "angle": -180, "mat": "bay"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 6.45, "r": R_BAY + 0.1, "h": 0.18, "mat": "trim"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 10.05, "r": R_BAY + 0.1, "h": 0.15, "mat": "trim"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 12.05, "r": R_TUR + 0.1, "h": 0.25, "mat": "trim"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 12.3, "r": R_TUR, "h": 3.1, "angle": -180,
         "mat": "turret"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 15.4, "r": R_TUR + 0.35, "h": 0.3, "mat": "trim"},
        {"type": "cone", "cx": C[0], "cy": C[1], "z": 15.7, "r": R_TUR + 0.25, "h": 3.4, "mat": "cone"},
        {"type": "box", "x": C[0] + 1.55, "y": C[1] - 0.6, "z": 13.6, "w": 0.7, "d": 1.2, "h": 2.3, "mat": "body",
         "faces": {"+x": "dormer"}},
        dict(ROOF, x=C[0] + 0.6, y=C[1] - 0.6, w=1.65, d=1.2, z=15.9, style="gable_x", pitch=55, overhang=0.15,
             gable="dormer_gable", ends=["+x"], bargeboard={"mat": "barge", "w": 0.1, "h": 0.2},
             finial={"mat": "barge", "h": 0.5, "r": 0.05}),
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 18.3, "r": 0.55, "h": 0.2, "mat": "finial_body"},
        {"type": "cone", "cx": C[0], "cy": C[1], "z": 18.5, "r": 0.55, "h": 0.6, "mat": "finial_body"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 18.85, "r": 0.25, "h": 0.3, "mat": "finial"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 19.15, "r": 0.11, "h": 0.25, "mat": "finial"},
        {"type": "cylinder", "cx": C[0], "cy": C[1], "z": 19.4, "r": 0.2, "h": 0.25, "mat": "finial"},
        {"type": "cone", "cx": C[0], "cy": C[1], "z": 19.65, "r": 0.09, "h": 1.1, "mat": "finial"},
        # porch: stone floor, columns, open arched fascia, balustrades, pediment with bargeboards and a finial
        {"type": "box", "x": FX, "y": 13.9, "z": 0, "w": 2.8, "d": PORCH_W, "h": 2, "mat": "stone"},
        {"type": "box", "x": FX, "y": 13.85, "z": 1.9, "w": 2.85, "d": PORCH_W + 0.1, "h": 0.12, "mat": "trim"},
        *[{"type": "cylinder", "cx": 28.0, "cy": cy, "z": 2, "r": 0.18, "h": 3.0, "sides": 8, "mat": "barge"}
          for cy in (14.2, 15.55, 17.65, 19.7)],
        *[{"type": "box", "x": 27.78, "y": cy - 0.22, "z": 2, "w": 0.44, "d": 0.44, "h": 0.3, "mat": "trim"}
          for cy in (14.2, 15.55, 17.65, 19.7)],
        {"type": "panel", "from": [28.3, 13.9], "to": [28.3, 20.0], "z": 5.0, "h": 1.6, "mat": "fascia_front"},
        {"type": "panel", "from": [FX, 20.0], "to": [28.3, 20.0], "z": 5.0, "h": 1.6, "mat": "fascia_side"},
        {"type": "panel", "from": [28.3, 13.9], "to": [FX, 13.9], "z": 5.0, "h": 1.6, "mat": "fascia_side"},
        {"type": "box", "x": FX, "y": 13.85, "z": 6.6, "w": 2.85, "d": PORCH_W + 0.1, "h": 0.12, "mat": "trim"},
        {"type": "panel", "from": [28.0, 14.4], "to": [28.0, 15.35], "z": 2.02, "h": 0.95, "mat": "balustrade"},
        {"type": "panel", "from": [28.0, 17.85], "to": [28.0, 19.5], "z": 2.02, "h": 0.95, "mat": "balustrade"},
        dict(ROOF, x=FX, y=13.9, w=2.8, d=PORCH_W, z=6.72, style="gable_x", pitch=PORCH_PITCH, overhang=0.3,
             gable="pediment", ends=["+x"], bargeboard={"mat": "barge", "w": 0.14, "h": 0.3},
             finial={"mat": "barge", "h": 0.8, "r": 0.08}),
        # steps up to the porch, the garden wall with its iron fence
        {"type": "box", "x": 28.3, "y": 15.65, "z": 0, "w": 0.8, "d": 1.9, "h": 1.5, "mat": "stone"},
        {"type": "box", "x": 29.1, "y": 15.65, "z": 0, "w": 0.8, "d": 1.9, "h": 1.0, "mat": "stone"},
        {"type": "box", "x": 29.9, "y": 15.65, "z": 0, "w": 0.8, "d": 1.9, "h": 0.5, "mat": "stone"},
        {"type": "box", "x": 31.2, "y": 0.5, "z": 0, "w": 0.5, "d": 15.0, "h": 0.9, "mat": "stone"},
        {"type": "box", "x": 31.2, "y": 17.7, "z": 0, "w": 0.5, "d": 13.8, "h": 0.9, "mat": "stone"},
        {"type": "panel", "from": [31.45, 0.5], "to": [31.45, 15.5], "z": 0.9, "h": 0.85, "mat": "iron"},
        {"type": "panel", "from": [31.45, 17.7], "to": [31.45, 31.5], "z": 0.9, "h": 0.85, "mat": "iron"},
        # garden
        {"type": "prop", "name": "sm shrub1", "x": 29.6, "y": 12.5, "z": 0},
        {"type": "prop", "name": "floweringbush1", "x": 29.8, "y": 14.4, "z": 0},
        {"type": "prop", "name": "sm shrub2", "x": 29.8, "y": 19.2, "z": 0},
        {"type": "prop", "name": "floweringbush1", "x": 29.6, "y": 21.5, "z": 0},
        {"type": "prop", "name": "sm decid1", "x": 15, "y": 28, "z": 0},
        {"type": "prop", "name": "med decid1", "x": 4, "y": 26, "z": 0},
        {"type": "prop", "name": "med decid1", "x": 4, "y": 5, "z": 0},
    ],
}

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authored.json")
    json.dump(MODEL, open(out, "w"), indent=1)
    print(out)
