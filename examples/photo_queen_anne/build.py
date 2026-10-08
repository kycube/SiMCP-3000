r"""Build the photo-based Haas-Lilienthal House with the buildingarchitect server's photo tools:

    set PHOTO=path\to\Haas-Lilienthal_House_exterior_2025.jpg   (the Wikimedia Commons file, CC BY 4.0)
    python live/mcp_run.py bat examples/photo_queen_anne/build.py
    (set INSTALL=1 to also add it to the game's Apps\BARender folder; restart SimCity 3000 afterwards)
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model import MODEL

PHOTO = os.environ.get("PHOTO", "")
MODEL_FILE = os.path.join(HERE, "model.json")
json.dump(MODEL, open(MODEL_FILE, "w"), indent=1)

STEPS = ([("photo_add", {"name": "haas", "image_path": PHOTO, "crop": [820, 280, 2396, 2990], "scale": 0.5})]
         if PHOTO else []) + [
    ("photo_view", {"name": "haas", "grid": 50}),
    ("photo_model_render", {"model_path": MODEL_FILE}),
    ("photo_model_export", {"model_path": MODEL_FILE, "install": os.environ.get("INSTALL") == "1"}),
]
