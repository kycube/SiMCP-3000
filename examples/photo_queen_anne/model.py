"""The Haas-Lilienthal House (San Francisco, 1886) as a photo-built model for the buildingarchitect server's photo
tools (no Building Architect needed). Lengths in metres on a 2x2 lot (32 x 32 m); the street front faces +x (the
lit, left side in the game's default view); seen from the street the turret is on the left (-y end) and the porch
on the right (+y end).

Photo: "Haas-Lilienthal House exterior 2025.jpg" by Ppienovagem, Wikimedia Commons, CC BY 4.0
(https://commons.wikimedia.org/wiki/File:Haas-Lilienthal_House_exterior_2025.jpg), added as photo "haas" with
crop [820, 280, 2396, 2990] and scale 0.5 (build.py does this): every photo coordinate below is in that picture.
How it was made, and the lessons: notes/PHOTO_TO_BUILDING.md.
"""
import json, math, os

R_T = 2.2                                  # turret radius
SKY = "#3c8ee0"                            # the sky behind the turret and gable in the photo
WALL = "#7d8f7b"                           # the clapboard colour sampled from the photo
MODEL = {
    "name": "MCP Haas-Lilienthal House",
    "architect": "SiMCP 3000 example (photo build)",
    "description": "Queen Anne Victorian, San Francisco 1886, built from a photograph (CC BY 4.0 Ppienovagem)",
    "lot": 2,
    "materials": {
        "front": {"photo": "haas", "quad": [[60, 345], [562, 345], [600, 870], [25, 870]], "fit": True, "brightness": 1.3},
        "gable": {"photo": "haas", "quad": [[115, 195], [410, 195], [410, 348], [115, 348]], "fit": True, "brightness": 1.3,
                  "remove_color": SKY, "tolerance": 85},
        # round surfaces: unrolled from the photo (silhouette edges per part), only on the street side
        "bay_photo": {"photo": "haas", "cylinder": {"left": [[93, 350], [62, 866]], "right": [[212, 350], [212, 866]],
                                                    "span_deg": 160}, "brightness": 0.95, "tint": "#dde6da"},
        "turret_photo": {"photo": "haas", "cylinder": {"left": [[71, 216], [72, 344]], "right": [[251, 216], [250, 344]],
                                                       "span_deg": 150}, "brightness": 0.8, "tint": "#dde6da",
                         "remove_color": SKY, "tolerance": 85},
        "turret_back": {"pattern": "clapboard", "color": WALL, "size_m": [1.0, 1.0]},
        "turret_back_top": {"pattern": "fishscale", "color": WALL, "size_m": [1.0, 1.0]},
        "pediment": {"photo": "haas", "quad": [[305, 478], [600, 478], [600, 600], [305, 600]], "fit": True, "brightness": 1.3,
                     "remove_color": SKY, "tolerance": 85},
        "side": {"pattern": "clapboard_window", "color": WALL, "color2": "#d6d2c2", "size_m": [2.6, 4.0]},
        "basement": {"photo": "haas", "quad": [[70, 880], [230, 880], [230, 985], [70, 985]], "size_m": [3.0, 2.0]},
        "roof": {"pattern": "roof_shingle", "color": "#4a4e58", "size_m": [1.5, 1.5]},
        # weathered grey-brown shingles (photo sample 129,125,122 on the upper cone), a little darker for the warm light
        "cone": {"pattern": "roof_shingle", "color": "#6a5c58", "color2": "#4a3f3b", "size_m": [1.0, 0.8]},
        "dormer": {"photo": "haas", "quad": [[130, 210], [196, 210], [196, 292], [130, 292]], "fit": True,
                   "brightness": 1.1, "remove_color": SKY, "tolerance": 80},
        "turret_top": {"photo": "haas", "quad": [[90, 215], [236, 215], [236, 345], [85, 345]],
                       "size_m": [math.pi * R_T, 3.5], "brightness": 0.72, "tint": "#d4e0d0", "remove_color": SKY,
                       "tolerance": 85},
        "finial_body": {"color": "#62706a"},
        "trim": {"color": "#6f7f70"},
        "stone": {"pattern": "stone", "color": "#b9bcb8", "size_m": [2, 1]},
        "lawn": {"texture": "grass", "size_m": [16, 16]},
        "path": {"texture": "walkway", "size_m": [8, 8]},
        "finial": {"color": "#3c4246"},
    },
    "parts": [
        {"type": "ground", "mat": "lawn"},
        {"type": "patch", "x": 26, "y": 18.5, "w": 6, "d": 2.0, "mat": "path"},
        # raised basement and the three storeys
        {"type": "box", "x": 10, "y": 9, "z": 0, "w": 16, "d": 13, "h": 2, "mat": "basement"},
        {"type": "box", "x": 10, "y": 9, "z": 2, "w": 16, "d": 13, "h": 12, "mat": "side", "faces": {"+x": "front"}},
        # roofs: main hip roof crossed by the front gable (ridge along x, gable end on the front)
        {"type": "roof", "x": 10, "y": 9, "w": 16, "d": 13, "z": 14, "style": "hip", "pitch": 40, "overhang": 0.5,
         "mat": "roof"},
        {"type": "roof", "x": 17, "y": 11.0, "w": 9, "d": 6.6, "z": 14, "style": "gable_x", "pitch": 47,
         "overhang": 0.5, "mat": "roof", "gable": "gable"},
        # corner turret: a round tower with a cone and a finial
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 0, "r": 1.75, "h": 2, "mat": "basement"},
        # tower: the bay storeys (photo of the lower turret), the shingled top band with its frieze, eave ring
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 2, "r": 1.75, "h": 10.8, "mat": "turret_back",
         "photo": {"mat": "bay_photo", "toward_deg": 0}, "faces": {"top": "trim"}},
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 12.8, "r": R_T, "h": 3.2, "mat": "turret_back_top",
         "photo": {"mat": "turret_photo", "toward_deg": 0}, "faces": {"top": "trim"}},
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 16.0, "r": R_T + 0.45, "h": 0.3, "mat": "trim"},
        # blunt shingle cone (about 3.2 m on a 5 m base, as in the photo), truncated by the finial's collar
        {"type": "cone", "cx": 25.6, "cy": 9.4, "z": 16.3, "r": R_T + 0.3, "h": 4.2, "mat": "cone"},
        # turned finial: collar, bell, two dark knobs, spike (about 3 m)
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 19.5, "r": 0.75, "h": 0.25, "mat": "finial_body"},
        {"type": "cone", "cx": 25.6, "cy": 9.4, "z": 19.75, "r": 0.75, "h": 0.8, "mat": "finial_body"},
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 20.2, "r": 0.3, "h": 0.35, "mat": "finial"},
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 20.55, "r": 0.13, "h": 0.3, "mat": "finial"},
        {"type": "cylinder", "cx": 25.6, "cy": 9.4, "z": 20.85, "r": 0.24, "h": 0.3, "mat": "finial"},
        {"type": "cone", "cx": 25.6, "cy": 9.4, "z": 21.15, "r": 0.11, "h": 1.3, "mat": "finial"},
        # gabled dormer window on the street side of the cone
        {"type": "box", "x": 26.6, "y": 8.75, "z": 14.9, "w": 1.9, "d": 1.3, "h": 1.7, "mat": "trim",
         "faces": {"+x": "dormer"}},
        {"type": "roof", "x": 26.6, "y": 8.75, "w": 1.9, "d": 1.3, "z": 16.6, "style": "gable_x", "pitch": 50,
         "overhang": 0.15, "mat": "trim", "gable": "trim"},
        # porch: floor, two columns, pediment roof (gable end facing the street)
        {"type": "box", "x": 26, "y": 17, "z": 0, "w": 2.6, "d": 5, "h": 2, "mat": "stone"},
        {"type": "cylinder", "cx": 28.3, "cy": 17.3, "z": 2, "r": 0.22, "h": 4.2, "sides": 8, "mat": "trim"},
        {"type": "cylinder", "cx": 28.3, "cy": 21.7, "z": 2, "r": 0.22, "h": 4.2, "sides": 8, "mat": "trim"},
        {"type": "roof", "x": 26, "y": 17, "w": 2.6, "d": 5, "z": 6.2, "style": "gable_x", "pitch": 40,
         "overhang": 0.3, "mat": "roof", "gable": "pediment"},
        # front steps down to the street, a low garden wall
        {"type": "box", "x": 28.6, "y": 18.6, "z": 0, "w": 0.7, "d": 1.8, "h": 1.6, "mat": "stone"},
        {"type": "box", "x": 29.3, "y": 18.6, "z": 0, "w": 0.7, "d": 1.8, "h": 1.1, "mat": "stone"},
        {"type": "box", "x": 30.0, "y": 18.6, "z": 0, "w": 0.7, "d": 1.8, "h": 0.6, "mat": "stone"},
        {"type": "box", "x": 31.3, "y": 0.5, "z": 0, "w": 0.5, "d": 18.0, "h": 0.8, "mat": "stone"},
        {"type": "box", "x": 31.3, "y": 20.5, "z": 0, "w": 0.5, "d": 11.0, "h": 0.8, "mat": "stone"},
        # garden
        {"type": "prop", "name": "sm shrub1", "x": 29.5, "y": 12, "z": 0},
        {"type": "prop", "name": "floweringbush1", "x": 29.5, "y": 14.5, "z": 0},
        {"type": "prop", "name": "sm shrub2", "x": 29.5, "y": 23.5, "z": 0},
        {"type": "prop", "name": "sm decid1", "x": 5, "y": 27, "z": 0},
        {"type": "prop", "name": "med decid1", "x": 5, "y": 5, "z": 0},
    ],
}

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haas_model.json")
    json.dump(MODEL, open(out, "w"), indent=1)
    print(out)
