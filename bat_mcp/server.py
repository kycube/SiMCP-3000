"""MCP server for the SimCity 3000 Unlimited Building Architect (Baapp.exe): create buildings for the game.

Same conventions as the game's server (sc3k_mcp): every tool is registered through sc3k_mcp.registry (docstring Args
become the JSON-schema parameter descriptions, kinds set the MCP annotations, {"error": ...} results are MCP tool
errors), so any MCP client can use it.
"""

from __future__ import annotations

import io
import json
import os
import re
import struct

import numpy  # noqa: F401  - import on the main thread: a first numpy import inside a tool (a worker thread) hangs
from mcp.server.fastmcp import FastMCP, Image

from sc3k_mcp.game import GameError
from sc3k_mcp.registry import tool as _register

from . import bldfile
from . import render as render_mod
from . import sprites
from .app import BUILDINGS_DIR, RENDER_DAT, BatApp
from .model import BUILDING_TYPES, CATEGORIES, MODES, Architect

mcp = FastMCP(
    "buildingarchitect",
    instructions=(
        "Makes buildings for SimCity 3000 Unlimited. (1) Drives the game's Building Architect: create and edit "
        "buildings (blocks, roofs, paints, details, props), see them as images read from the program and its rendered "
        "output (no screenshots), render them for the game - start with bat_launch. (2) Photo to building, no "
        "Architect needed: photo_add, photo_view (measure the photo), then a model of 3D parts whose walls are drawn "
        "as authored facades, rendered by photo_model_render and written into the game's format by "
        "photo_model_export (higher quality); photo_buildings / photo_building_remove manage what is installed. "
        "Call guide() first (guide(topic='photo') for the photo route and its best practices)."
    ),
)
app = BatApp()
arch = Architect(app)


def tool(kind: str, **kw):
    return _register(mcp, kind, **kw)


def _guard(fn, *a, _attach: bool = True, **kw):
    try:
        if _attach and (not app.proc or not app.proc.alive() or not app.bridge):
            app.attach(launch=False)
        return fn(*a, **kw)
    except (GameError, KeyError, ValueError) as e:
        return {"error": e.args[0] if isinstance(e, KeyError) and e.args else str(e)}
    except Exception as e:
        out = {"error": f"{type(e).__name__}: {e}"}
        if os.environ.get("BAT_MCP_TRACE"):
            import traceback
            out["trace"] = traceback.format_exc()[-1500:]
        if app.proc and not app.proc.alive():
            out["hint"] = "the Building Architect is no longer running: bat_launch starts it again"
        return out


_GUIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guide.md")


@tool("read", structured_output=False)
def guide(topic: str = "") -> str:
    """How to use this server (markdown): what the Building Architect is, building with blocks, roofs, paints,
    details and props, your own textures and props, coordinates, seeing the building as images, best practices
    learned from complete builds (scale, colours through the renderer, roofs, houses, towers), saving and rendering
    for SimCity. Read it first.

    Args:
        topic: A section title or part of it (e.g. "best practices", "lot", "paint", "your own"); empty for all.
    """
    text = open(_GUIDE, encoding="utf-8").read() if os.path.exists(_GUIDE) else "(guide not written yet)"
    if not topic:
        return text
    parts = text.split("\n## ")
    hits = ["## " + p for p in parts[1:] if topic.lower() in p.split("\n", 1)[0].lower()]
    return "\n\n".join(hits) if hits else {"error": f"no section matches {topic!r}"}


@tool("set")
def bat_launch() -> dict:
    """Start the Building Architect (windowed 1024x768) and attach to it, or attach to the copy already running."""
    return _guard(app.attach, launch=True, _attach=False)


@tool("read")
def bat_status() -> dict:
    """Whether the Building Architect runs, its window, and the folders it uses (projects, rendered output)."""
    def run():
        st = app.status()
        st["projects_folder"] = BUILDINGS_DIR
        st["rendered_output"] = RENDER_DAT
        return st
    return _guard(run, _attach=False)


def _png(img) -> Image:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return Image(data=buf.getvalue(), format="png")


def _project_path(name: str) -> str:
    p = name if os.path.isabs(name) else os.path.join(BUILDINGS_DIR, name)
    if not p.lower().endswith(".bld"):
        p += ".bld"
    if not os.path.exists(p):
        raise GameError(f"no project {name!r} in {BUILDINGS_DIR} (see projects)")
    return p


@tool("read")
def projects() -> dict:
    """The Building Architect projects (*.bld) in the game's Buildings folder: file, building name, architect, lot
    size (tiles a side) and building id, read from each file."""
    def run():
        out = []
        for f in sorted(os.listdir(BUILDINGS_DIR)) if os.path.isdir(BUILDINGS_DIR) else []:
            if f.lower().endswith(".bld"):
                try:
                    info = sprites.project_info(os.path.join(BUILDINGS_DIR, f))
                except (ValueError, struct.error) as e:
                    info = {"error": str(e)}
                info["file"] = f
                out.append(info)
        return {"folder": BUILDINGS_DIR, "projects": out}
    return _guard(run, _attach=False)


@tool("read", structured_output=False)
def project_image(name: str) -> Image:
    """The preview picture a project file carries (200x200, the Architect's own render of the building, saved with
    it), as a PNG. Read from the file: no screenshot.

    Args:
        name: Project file name in the Buildings folder (with or without .bld), or a full path.
    """
    return _guard(lambda: _png(sprites.project_thumbnail(_project_path(name))), _attach=False)


@tool("read")
def rendered_buildings(dat_path: str = "") -> dict:
    """The buildings rendered for SimCity 3000 (the game reads them from Apps\\BARender\\BAT.DAT): name, architect,
    lot size and id. These are the user-made buildings the game can show (see the game server's
    building_replacements).

    Args:
        dat_path: Another render output file to read instead (e.g. one made by render_building); empty for the game's.
    """
    def run():
        rs = sprites.RenderedSet(dat_path or RENDER_DAT)
        return {"file": rs.path, "buildings": [{k: v for k, v in b.items() if k not in ("frames", "group")}
                                                for b in rs.buildings]}
    return _guard(run, _attach=False)


@tool("read", structured_output=False)
def rendered_image(name: str, zoom: int = 4, rotation: int = -1, dat_path: str = "") -> Image:
    """A rendered building exactly as SimCity 3000 draws it (decoded from the render output, transparent background,
    no screenshot): one view, or all four rotations side by side.

    Args:
        name: Building name or id (rendered_buildings).
        zoom: 1 (farthest, 8 px per tile) .. 5 (closest, 128 px per tile); 4 = 64 px per tile.
        rotation: 0..3 for one view; -1 for the four rotations side by side.
        dat_path: Another render output file (e.g. from render_building); empty for the game's BAT.DAT.
    """
    def run():
        rs = sprites.RenderedSet(dat_path or RENDER_DAT)
        b = rs.find(name)
        if not 1 <= zoom <= 5:
            raise GameError("zoom must be 1..5")
        if rotation == -1:
            return _png(sprites.sheet([rs.image(b, zoom, r) for r in range(4)]))
        if rotation not in (0, 1, 2, 3):
            raise GameError("rotation must be 0..3 or -1")
        return _png(rs.image(b, zoom, rotation))
    return _guard(run, _attach=False)


# ================================================================ the building being edited
def _box(x0, y0, z0, x1, y1, z1):
    return [{"x": x, "y": y, "z": z} for x in range(min(x0, x1), max(x0, x1) + 1)
            for y in range(min(y0, y1), max(y0, y1) + 1) for z in range(min(z0, z1), max(z0, z1) + 1)]


@tool("read", structured_output=False)
def game_building_image(name: str, zoom: int = 5, rotation: int = -1):
    """One of SimCity 3000's own buildings or landmarks as the game draws it, decoded from the game's sprite files
    (no screenshot) - the reference for scale, level of detail and style when designing a building: compare it
    with render_building at the same zoom. Returns its lot size and a picture of the chosen rotation (or all four).
    Covers the default (North American) building style.

    Args:
        name: The building's name as the game calls it (e.g. "Empire State Building", "Hospital", "Mayor's House"),
            a unique part of it, or its occupant id (e.g. "0x252C").
        zoom: 1 (smallest) .. 5 (largest; the game draws zoom 5 as zoom 4 doubled, as it does for user buildings).
        rotation: 0..3, or -1 for all four side by side.
    """
    def run():
        from PIL import Image as PImage
        from sc3k_mcp import catalog
        idx = sprites.game_sprite_index()
        occ = {k: v for k, v in catalog.OCCUPANTS.items() if k in idx}
        key = name.strip()
        try:
            hits = [int(key, 0)] if int(key, 0) in occ else []
        except ValueError:
            hits = ([k for k, v in occ.items() if v["name"].lower() == key.lower()] or
                    [k for k, v in occ.items() if key.lower() in v["name"].lower()])
        if not hits:
            raise GameError(f"no game building named {name!r}")
        if len(hits) > 1:
            raise GameError(f"{name!r} matches {len(hits)} buildings: "
                            f"{sorted({occ[k]['name'] for k in hits})[:15]} - give the full name")
        k = hits[0]
        frames = sprites.game_building_frames(k)
        z = max(1, min(5, zoom))
        rots = range(4) if rotation < 0 else [rotation % 4]
        ims = []
        for r in rots:
            e = frames.get((min(z, 4), r))
            if not e:
                raise GameError(f"{occ[k]['name']} has no sprite for zoom {z} rotation {r}")
            im = sprites.game_sprite(e)
            if z == 5:
                im = im.resize((im.width * 2, im.height * 2), PImage.NEAREST)
            ims.append(im)
        size = occ[k].get("size") or [None, None, None]
        info = {"name": occ[k]["name"], "occupant": hex(k), "lot_tiles": [size[0], size[2]],
                "zoom": z, "pixels": [list(i.size) for i in ims],
                "note": "a lot of N tiles is 128 * N px wide at zoom 5 (64 at zoom 4); compare with render_building"}
        return [json.dumps(info), _png(sprites.sheet(ims))]
    return _guard(run, _attach=False)


@tool("destructive")
def new_building(size: int = 1, name: str = "New Building", architect: str = "", description: str = "",
                 building_type: str = "residential") -> dict:
    """Start a new building in the Building Architect (its New Building button and Tile Size dialog). The building
    being edited is replaced; unsaved changes to it are lost (save_building first). The new lot has a ground layer
    at z = 0; build from z = 1 up.

    Args:
        size: Lot size in city tiles a side: 1..5 (1x1 = 8 x 8 cells and 28 cells high; 2x2 16 x 16 x 64;
            3x3 24 x 24 x 108; 4x4 32 x 32 x 144; 5x5 40 x 40 x 80).
        name: Building name (shown in SimCity's Query).
        architect: Architect name.
        description: Description text.
        building_type: residential | commercial | industrial | police_station | jail | fire_station | hospital |
            school | college | library | museum | historic_statue | mayors_house | city_hall |
            performing_arts_center | other.
    """
    def run():
        arch.new_building(size)
        return arch.set_properties(name=name, architect=architect or None, description=description or None,
                                   building_type=building_type)
    return _guard(run)


@tool("destructive")
def open_building(name: str) -> dict:
    """Open a project (.bld) in the Building Architect for editing, as its Load Building does. The building being
    edited is replaced (unsaved changes are lost).

    Args:
        name: Project file name in the Buildings folder (with or without .bld) or a full path.
    """
    def run():
        arch.open_building(_project_path(name))
        return arch.properties()
    return _guard(run)


@tool("act")
def save_building(name: str = "", overwrite: bool = False) -> dict:
    """Save the building being edited as a project file (.bld) with the Building Architect's own save, including its
    preview picture. The game's Buildings folder is used unless a full path is given.

    Args:
        name: File name (without .bld) or full path; empty = save to the file it was opened from / last saved to.
        overwrite: Replace an existing file of that name.
    """
    def run():
        path = name
        if not path:
            path = arch.current_path()
            if not path:
                raise GameError("this building has no file yet: give a name")
        else:
            path = path if os.path.isabs(path) else os.path.join(BUILDINGS_DIR, path)
            if not path.lower().endswith(".bld"):
                path += ".bld"
            if os.path.exists(path) and not overwrite and os.path.normcase(path) != os.path.normcase(
                    arch.current_path() or ""):
                raise GameError(f"{path} exists; pass overwrite=true to replace it")
        if os.path.basename(path).lower() in _SHIPPED_PROJECTS and os.path.exists(path):
            raise GameError(f"{os.path.basename(path)} is one of the game's own sample projects; save under a new name")
        arch.save_building(path)
        return {"saved": path, "bytes": os.path.getsize(path), **arch.properties()}
    return _guard(run)


_SHIPPED_PROJECTS = {f.lower() for f in ("Den Burg Bruges.bld", "Dupont House.bld", "Garvey Plaza.bld",
                                         "GuestHouse Building.bld", "Headquarters.bld", "HiTech Lab.bld",
                                         "Hotel Splash.bld", "Kankakee Jr. High School.bld", "Longview Park.bld",
                                         "Maxis Towers.bld", "North Shore Cannery.bld", "Northeast Nonwovens.bld",
                                         "Proton Building.bld", "The Joneses.bld", "Trash & Burn.bld",
                                         "Tutorial House.bld", "Zweikky Unpainted.bld")}


@tool("read")
def building_info() -> dict:
    """The building being edited: name, architect, description, type, lot size, building volume in cells, block
    count, which textures it uses, unsaved changes, its file, the view mode and zoom."""
    def run():
        info = arch.properties()
        blocks = arch.blocks()
        used = {}
        for b in blocks:
            for f in b.get("faces", {}).values():
                for k in ("paint", "detail"):
                    if k in f:
                        used[f[k]] = used.get(f[k], 0) + 1
        info.update({"building_blocks": len(blocks), "props_cells": sum(b["shape"] == 15 for b in blocks),
                     "props": len(arch.placed_props()), "rotation": arch.view_rotation(),
                     "top_z": max((b["z"] for b in blocks), default=0), "textures_used": used,
                     "view_mode": arch.mode(), "zoom": arch.zoom()})
        return info
    return _guard(run)


@tool("set")
def set_building_properties(name: str | None = None, architect: str | None = None, description: str | None = None,
                            building_type: str | None = None) -> dict:
    """Change the building's name, architect, description or type (saved with save_building).

    Args:
        name: Building name; omit to keep.
        architect: Architect name; omit to keep.
        description: Description; omit to keep.
        building_type: As new_building's building_type; omit to keep.
    """
    return _guard(arch.set_properties, name=name, architect=architect, description=description,
                  building_type=building_type)


@tool("read")
def shapes() -> dict:
    """The 16 block shapes (id, description, and what each face slot is at rotation 0: top, bottom, a side
    direction, or a sloped face and the way it faces) and the conventions: cells are (x, y, z) with z up, 8 cells
    per city tile; a shape's rotation 0..3 turns it 90 degrees counter-clockwise (x right, y up). A cube's slots
    are 0 top, 1 -x, 2 -y, 3 +x, 4 +y, 5 bottom (at rotation 0). The default camera looks from the +x, +y side, so
    top, +x and +y faces face the viewer. Paint tools accept direction names, so slot numbers are rarely needed."""
    from .model import slot_info, slot_label
    return {"shapes": [{"id": k, "description": v, "slots_at_rotation_0": [slot_label(i) for i in slot_info(k, 0)]}
                       for k, v in bldfile.SHAPE_NAMES.items()],
            "rotation": "each quarter turn (counter-clockwise seen from above) turns every side / slope direction: "
                        "+x -> +y -> -x -> -y",
            "faces": {"0": "top", "1": "-x side", "2": "-y side", "3": "+x side", "4": "+y side", "5": "bottom"},
            "notes": "shape 15 is used by props (place_props); 8 is a legacy floor plate"}


@tool("read")
def blocks(z_min: int = 1, z_max: int = 1000, include_ground: bool = False) -> dict:
    """The blocks of the building being edited: position (x, y, z), shape, rotation and the paint / detail of each
    painted face slot; for shapes other than cubes also "slots": what each slot is (top, a side direction, a sloped
    face...).

    Args:
        z_min: Lowest z to list.
        z_max: Highest z to list.
        include_ground: Also list the ground layer (z = 0).
    """
    def run():
        bl = [b for b in arch.blocks(include_ground=include_ground)
              if (include_ground and b["z"] == 0) or z_min <= b["z"] <= z_max]
        return {"count": len(bl), "blocks": bl}
    return _guard(run)


@tool("act")
def place_blocks(blocks: list[dict]) -> dict:
    """Place blocks with the Building Architect's own SetBlock (replacing what is in those cells), each
    {"x": .., "y": .., "z": .., "shape": 0..15 (default 0 = cube), "rotation": 0..3}. z starts at 1 (0 is the
    ground). Returns the building's block count.

    Args:
        blocks: The blocks to place.
    """
    return _guard(lambda: {"blocks": arch.set_blocks(blocks)})


@tool("act")
def fill_box(x0: int, y0: int, z0: int, x1: int, y1: int, z1: int, shape: int = 0, rotation: int = 0) -> dict:
    """Fill a box of cells (both corners included) with one block shape, e.g. the body of a building.

    Args:
        x0: First corner x.
        y0: First corner y.
        z0: First corner z (1 = on the ground).
        x1: Opposite corner x.
        y1: Opposite corner y.
        z1: Opposite corner z.
        shape: Block shape 0..15 (shapes lists them; 0 = cube).
        rotation: 0..3.
    """
    return _guard(lambda: {"blocks": arch.set_blocks([dict(c, shape=shape, rotation=rotation)
                                                      for c in _box(x0, y0, z0, x1, y1, z1)])})


@tool("act")
def roof(parts: list[dict], z: int, pitch: float = 1.0, roof_texture: str = "", gable_texture: str = "") -> dict:
    """Build a roof from one or more rectangles, with the right block shape in every cell: slopes, hip corners,
    ridges and the valleys where roofs meet (the parts are combined by taking the highest surface, so a front gable
    crossing a hip roof gets proper valleys). Each part {"x0", "y0", "x1", "y1", "style", optional "pitch", "z",
    "max_height"}: style hip (slopes on all four sides), pyramid, gable_y (ridge along y, gable ends facing +y and
    -y), gable_x (ridge along x), shed_+x / shed_-x / shed_+y / shed_-y (one slope rising towards that side) or
    flat; max_height cuts the roof off flat at that many cells (a roof deck). Even widths give a sharp ridge; odd
    widths a flat ridge one cell wide. Optionally paints it: roof_texture on the slopes and tops, gable_texture on
    the vertical gable ends.

    Args:
        parts: The roof rectangles (cells, both corners included), e.g. [{"x0": 3, "y0": 2, "x1": 12, "y1": 10,
            "style": "hip", "max_height": 3}, {"x0": 5, "y0": 6, "x1": 10, "y1": 10, "style": "gable_y"}].
        z: Level of the lowest roof cells (the cell level just above the top of the walls).
        pitch: 1 = 45 degrees (one cell up per cell in), 0.5 = 26.6 degrees; a part's own "pitch" overrides it.
        roof_texture: Paint for the slopes and flat tops (library kind=roofs or any paint); empty to leave them.
        gable_texture: Paint for the vertical gable-end faces (walls, shingles...); empty to leave them.
    """
    def run():
        from . import roofs
        blocks_ = roofs.roof_blocks(parts, z, pitch)
        if not blocks_:
            raise GameError("those parts make no roof")
        n = arch.set_blocks(blocks_)
        out = {"roof_cells": len(blocks_), "top_z": max(b["z"] for b in blocks_), "blocks": n}
        if roof_texture or gable_texture:
            xs = [b["x"] for b in blocks_]
            ys = [b["y"] for b in blocks_]
            zs = [b["z"] for b in blocks_]
            faces = arch.exterior_faces((min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)))
            cells = {(b["x"], b["y"], b["z"]) for b in blocks_}
            faces = [f for f in faces if (f["x"], f["y"], f["z"]) in cells]
            if roof_texture:
                out["roof_painted"] = arch.paint_mapped([{k: v for k, v in f.items() if k != "kind"} | {"texture": roof_texture}
                                                         for f in faces if f["kind"] != "side"])
            if gable_texture:
                out["gables_painted"] = arch.paint_mapped([{k: v for k, v in f.items() if k != "kind"} | {"texture": gable_texture}
                                                           for f in faces if f["kind"] == "side"])
        return out
    return _guard(run)


@tool("act")
def remove_blocks(cells: list[dict] | None = None, x0: int | None = None, y0: int | None = None,
                  z0: int | None = None, x1: int | None = None, y1: int | None = None,
                  z1: int | None = None) -> dict:
    """Remove blocks (including prop cells) by cell list or by box. Only existing blocks are removed.

    Args:
        cells: Cells {"x", "y", "z"} to clear; or give a box with x0..z1 instead.
        x0: Box corner x.
        y0: Box corner y.
        z0: Box corner z.
        x1: Opposite corner x.
        y1: Opposite corner y.
        z1: Opposite corner z.
    """
    def run():
        want = cells or (_box(x0, y0, z0, x1, y1, z1) if None not in (x0, y0, z0, x1, y1, z1) else None)
        if not want:
            raise GameError("give cells or a full box x0, y0, z0, x1, y1, z1")
        have = {(b["x"], b["y"], b["z"]) for b in arch.blocks()}
        todo = [c for c in want if (int(c["x"]), int(c["y"]), int(c["z"])) in have]
        return {"removed": len(todo), "blocks": arch.remove_blocks(todo) if todo else arch.properties()["blocks"]}
    return _guard(run)


@tool("read")
def library(kind: str = "walls", search: str = "") -> dict:
    """The textures, details and props the Building Architect offers (its palettes), by name. Use the names in
    paint_faces / paint_box (paints), detail_faces (details) and place_props (props).

    Args:
        kind: walls | roofs | ground | colors | details | props | custom (user-added paints, details, props) | all.
        search: Only names (or prop categories / detail sets) containing this text, e.g. "flora", "brick".
    """
    return _guard(_library_data, kind, search)


def _library_data(kind: str, search: str) -> dict:
    from . import bldfile as B
    groups = {"walls": {2}, "roofs": {1}, "ground": {0}, "colors": {3}, "details": {4, 5, 7},
              "props": set(range(8, 17)), "custom": {6, 7, 16}, "all": set(CATEGORIES)}
    if kind not in groups:
        raise GameError(f"kind: one of {list(groups)}")
    if kind == "props":
        mets = B.read_met_files()
        folder = {}
        for i in arch.library():
            if i["_cat"] >= 8:
                folder.setdefault(i["name"].rsplit(" ", 1)[0].rsplit(".", 1)[0].lower(), i["category"])
        out = [{"prop": k, "category": folder.get(k, "").replace("props_", ""), "size_cells": list(v[0][:3]),
                "orientations": len(v)} for k, v in sorted(mets.items())
               if search.lower() in k or search.lower() in folder.get(k, "")]
        return {"kind": kind, "count": len(out), "props": out,
                "note": "size_cells = x, y, z blocks; texture_image('<prop> 0.bmp') shows its first view"}
    items = [i for i in arch.library() if i["_cat"] in groups[kind] and (
        search.lower() in i["name"].lower() or search.lower() in app.rz_string(i["_item"] + 0x5C, 1024).lower())]
    out = []
    for i in items:
        d = {"name": i["name"], "category": i["category"]}
        if i["_cat"] in (4, 5, 7):          # detail sets: the folder the detail comes from
            d["set"] = os.path.basename(os.path.dirname(app.rz_string(i["_item"] + 0x5C, 1024))) or ""
        if i["_cat"] != 3:
            sz = B.texture_size(i["name"])
            if sz:
                d["pixels"] = list(sz)
                d["block_faces"] = [sz[0] // 16, sz[1] // 16]
        out.append(d)
    return {"kind": kind, "count": len(out), "items": out}


@tool("read", structured_output=False)
def texture_image(name: str) -> Image:
    """A texture, detail or prop bitmap as a PNG (read from the Architect's files; 16 px = one block face).

    Args:
        name: Its name as library lists it (e.g. "brick 03.tga", "sm decid1 0.bmp").
    """
    def run():
        from PIL import Image as PImage
        from . import bldfile as B
        path = B.find_texture_file(name if "." in name else name + ".tga") or B.find_texture_file(name + ".bmp")
        if not path:
            raise GameError(f"no texture file {name!r}")
        im = PImage.open(path).convert("RGBA")
        if im.width < 64:
            im = im.resize((im.width * 4, im.height * 4), PImage.NEAREST)
        return _png(im)
    return _guard(run, _attach=False)


@tool("read", structured_output=False)
def texture_sheet(kind: str = "details", search: str = "", page: int = 1) -> Image:
    """Many textures, details or props at once: a labelled contact sheet (up to 40 per page, each scaled to fit
    a 96 px box, name underneath; transparent parts on grey), so a set can be browsed in one call instead of one
    texture_image per item.

    Args:
        kind: walls | roofs | ground | details | props | custom | all (as library).
        search: Only names (or prop categories / detail sets) containing this text, e.g. "deco", "flora".
        page: Page number when more than 40 match.
    """
    def run():
        from PIL import Image as PImage, ImageDraw
        from . import bldfile as B
        lib = _library_data(kind, search)
        names = ([f"{p['prop']} 0.bmp" for p in lib["props"]] if kind == "props"
                 else [i["name"] for i in lib["items"] if i.get("category") != "colors"])
        pages = max(1, (len(names) + 39) // 40)
        names = names[(page - 1) * 40:page * 40]
        if not names:
            raise GameError(f"nothing on page {page} (pages 1..{pages})")
        cols, W, H = 8, 104, 118
        out = PImage.new("RGB", (cols * W, ((len(names) + cols - 1) // cols) * H), (40, 40, 40))
        dr = ImageDraw.Draw(out)
        for k, n in enumerate(names):
            x, y = (k % cols) * W, (k // cols) * H
            path = B.find_texture_file(n)
            cell = PImage.new("RGBA", (96, 96), (128, 128, 128, 255))
            if path:
                im = PImage.open(path).convert("RGBA")
                if path.lower().endswith(".bmp"):
                    px = [(0, 0, 0, 0) if c[:3] == (255, 0, 255) else c for c in im.getdata()]
                    im.putdata(px)
                f = 96 / max(im.size)
                im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), PImage.NEAREST)
                cell.alpha_composite(im, ((96 - im.width) // 2, (96 - im.height) // 2))
            out.paste(cell.convert("RGB"), (x + 4, y + 2))
            dr.text((x + 4, y + 100), os.path.splitext(n)[0][:16], fill=(255, 230, 120))
        return _png(out)
    return _guard(run)


@tool("act")
def create_texture(name: str, kind: str = "paint", image_path: str = "", image_base64: str = "",
                   rows: list[str] | None = None, palette: dict | None = None, scale: int = 1,
                   overwrite: bool = False) -> dict:
    """Make a new paint texture or detail (decal) of your own and add it to the Architect's library, as its
    Apps\\BACustom folders allow: a paint is saved as BACustom\\Paints\\<name>.bmp, a detail as
    BACustom\\Details\\<name>.tga (transparent parts let the paint show through). Each side must be a multiple of
    16 px (16 px = one block face; up to 256). Give the picture as a file, as base64, or as pixel rows: one string
    per row, one palette character per pixel, e.g. rows ["aab", "abb"] with palette {"a": "#8a3b2a", "b": "200,200,200",
    ".": "transparent"}, enlarged by scale. Then use the name in paint_faces / fill_paint / detail_faces.

    Args:
        name: Name for the new texture (letters, digits, spaces, - and _), used as its library name.
        kind: paint | detail.
        image_path: A picture file (PNG, BMP, TGA, JPG...).
        image_base64: A picture as base64 (or a data: URL).
        rows: Pixel rows (all the same length) using palette characters.
        palette: For rows: character -> colour ("#rrggbb", "r,g,b" or "transparent").
        scale: Enlarge rows / the picture this many times (1..16), e.g. 16 x 16 rows with scale 2 -> 32 x 32 px.
        overwrite: Replace a texture of that name made earlier in BACustom.
    """
    def run():
        from . import custom
        im = custom.load_image(image_path, image_base64, rows, palette, scale)
        path = custom.write_texture(kind, name, im, overwrite=overwrite)
        out = {"file": path, "pixels": list(im.size), "block_faces": [im.width // 16, im.height // 16]}
        out.update(arch.load_custom(path, kind))
        return out
    return _guard(run)


@tool("read", structured_output=False)
def prop_template(width: int, depth: int, height: int) -> Image:
    """Drawing guide for a new prop's four views (create_prop): four square bitmaps side by side (views 0..3), each
    showing the prop's box of cells exactly where the Architect places a prop picture - 2:1 isometric, one cell
    32 px wide and 16 px deep, one storey 16 px high, the middle cell (index (n-1)//2 on each axis) centred, pink
    (255, 0, 255) = empty. The bitmap is the smallest of 32, 64, 128 or 256 px that fits, as the stock props use
    (a 1x1x1 prop is 32 px, a 1x1x13 antenna 256 px). Views 1 and 3 see the footprint turned. Draw the prop inside
    the box in each view, at this size.

    Args:
        width: Cells along x (1..7).
        depth: Cells along y (1..7).
        height: Cells high (1..14; it must fit a 256 px bitmap).
    """
    def run():
        from PIL import Image as PImage
        from . import custom
        ims = [custom.prop_template(width, depth, height, v) for v in range(4)]
        S = ims[0].width
        out = PImage.new("RGB", (4 * S + 3 * 4, S), (255, 255, 255))
        for k, im in enumerate(ims):
            out.paste(im, (k * (S + 4), 0))
        return _png(out)
    return _guard(run, _attach=False)


@tool("act")
def create_prop(name: str, width: int, depth: int, height: int, views: list[str] | None = None,
                view_paths: list[str] | None = None, view_rows: list[list[str]] | None = None,
                palette: dict | None = None, scale: int = 1, overwrite: bool = False) -> dict:
    """Make a new prop of your own (as the Architect's BACustom\\Props folder allows): four square view pictures
    (one per camera rotation, at the size and layout prop_template shows - 32, 64, 128 or 256 px; transparent or
    pink = empty) saved as BMPs with the .met file that tells the Architect the prop's size. Then place it with
    place_props(prop=name).

    Args:
        name: Prop name (letters, digits, spaces, - and _).
        width: Cells along x (1..7).
        depth: Cells along y (1..7).
        height: Cells high (1..28).
        views: The four views as base64 pictures (or data: URLs), view 0 first.
        view_paths: Or the four views as picture files.
        view_rows: Or the four views as pixel rows with palette (each size / scale rows of size / scale characters).
        palette: For view_rows: character -> colour ("#rrggbb", "r,g,b" or "transparent").
        scale: Enlarge view_rows this many times (1..16).
        overwrite: Replace a prop of that name made earlier in BACustom.
    """
    def run():
        from . import custom
        given = [x for x in (views, view_paths, view_rows) if x]
        if len(given) != 1 or len(given[0]) != 4:
            raise GameError("give the four views once: views (base64), view_paths or view_rows (+ palette)")
        if views:
            ims = [custom.load_image(image_base64=v) for v in views]
        elif view_paths:
            ims = [custom.load_image(image_path=v) for v in view_paths]
        else:
            ims = [custom.load_image(rows=r, palette=palette, scale=scale) for r in view_rows]
        out = custom.write_prop(name, (width, depth, height), ims, overwrite=overwrite)
        out.update(arch.load_custom(out["met"], "prop"))
        return out
    return _guard(run)


@tool("act")
def paint_faces(faces: list[dict]) -> dict:
    """Paint block faces with textures, laid out continuously as the Architect's Paintbrush does (each 16x16
    pixel cell of a texture covers one block face). Each face: {"x", "y", "z", "face", "texture": name from library
    (walls, roofs, ground, colors such as "color 162,161,201", custom), optional "u" / "v" to pick the texture
    cell yourself}; "texture": "" clears the paint. "face" is a direction name - "top", "bottom", "+x", "-x",
    "+y", "-y", a diagonal such as "-x+y", "slope" or "slope -x" - or a slot number as blocks lists it (for a
    cube: 0 top, 1 -x, 2 -y, 3 +x, 4 +y, 5 bottom; other shapes have their own slots, see blocks / shapes). The
    ground (z = 0) can be painted too.

    Args:
        faces: The faces to paint.
    """
    return _guard(lambda: {"painted": arch.paint_mapped(faces)})


@tool("act")
def detail_faces(faces: list[dict]) -> dict:
    """Put details (decals: windows, doors, signs...) on block faces, over their paint, laid out like paint_faces.
    Each: {"x", "y", "z", "face" (a direction name such as "+x" or a slot number, as paint_faces), "texture": a
    detail name from library(kind="details"), optional "u" / "v"}; "texture": "" removes the detail. To put a
    whole multi-face detail (e.g. 48 x 48 px = 3 x 3 faces) in one go use place_detail.

    Args:
        faces: The faces to decorate.
    """
    return _guard(lambda: {"detailed": arch.paint_mapped(faces, detail=True)})


@tool("act")
def place_detail(x: int, y: int, z: int, face: str, detail: str) -> dict:
    """Put a whole detail picture on a wall (or a roof) in one go, as the Architect's Apply Decal tool does: a
    detail W x H px covers W/16 x H/16 faces; the given face is its top-left corner as seen from outside, and it
    extends to the right along the wall and downwards (on a top face: towards -y and -x). E.g. a 48 x 48 px door
    on the +y wall with its top-left face at (16, 30, 3) covers x 16..14, z 3..1.

    Args:
        x: Cell x of the top-left face.
        y: Cell y.
        z: Cell z.
        face: Wall direction "+x", "-x", "+y", "-y", or "top".
        detail: Detail name (library kind=details, or one made with create_texture kind=detail).
    """
    def run():
        from . import bldfile as B
        path = B.find_texture_file(detail if "." in detail else detail + ".tga") or B.find_texture_file(detail + ".bmp")
        size = B.texture_size(os.path.basename(path)) if path else None
        if not size:
            raise GameError(f"no detail {detail!r} (library kind=details lists them)")
        wc, hc = max(1, size[0] // 16), max(1, size[1] // 16)
        right = {"+x": (0, 1), "-x": (0, -1), "+y": (-1, 0), "-y": (1, 0)}
        faces = []
        for i in range(wc):
            for j in range(hc):
                if face == "top":
                    c = (x - j, y - i, z)
                elif face in right:
                    c = (x + right[face][0] * i, y + right[face][1] * i, z - j)
                else:
                    raise GameError('face: "+x", "-x", "+y", "-y" or "top"')
                faces.append({"x": c[0], "y": c[1], "z": c[2], "face": face, "texture": detail, "u": i, "v": j})
        return {"detailed": arch.paint_mapped(faces, detail=True), "faces": [wc, hc],
                "cells": [[f["x"], f["y"], f["z"]] for f in faces]}
    return _guard(run)


@tool("act")
def paint_box(x0: int, y0: int, z0: int, x1: int, y1: int, z1: int, walls: str = "", roof: str = "",
              wall_detail: str = "") -> dict:
    """Paint the outside of the blocks in a box: every visible vertical face (diagonal ones too) gets the wall
    texture (and optionally a detail such as windows), every visible top and sloped roof face the roof texture -
    for any block shape, using the Architect's own visible-face bits.

    Args:
        x0: Box corner x.
        y0: Box corner y.
        z0: Box corner z.
        x1: Opposite corner x.
        y1: Opposite corner y.
        z1: Opposite corner z.
        walls: Wall texture name (library kind=walls / colors / custom); empty to leave walls as they are.
        roof: Roof texture name (library kind=roofs); empty to leave tops as they are.
        wall_detail: Detail to put on the walls (library kind=details); empty for none.
    """
    def run():
        faces = arch.exterior_faces((x0, y0, z0, x1, y1, z1))
        out = {"walls": 0, "roof": 0, "details": 0}
        sides = [{k: v for k, v in f.items() if k != "kind"} for f in faces if f["kind"] == "side"]
        tops = [{k: v for k, v in f.items() if k != "kind"} for f in faces if f["kind"] != "side"]
        if walls:
            out["walls"] = arch.paint_mapped([dict(f, texture=walls) for f in sides])
        if roof:
            out["roof"] = arch.paint_mapped([dict(f, texture=roof) for f in tops])
        if wall_detail:
            out["details"] = arch.paint_mapped([dict(f, texture=wall_detail) for f in sides], detail=True)
        return out
    return _guard(run)


@tool("act")
def place_props(props: list[dict]) -> dict:
    """Place props (trees, cars, benches, signs, rooftop units...) as the Architect's prop tool does: each
    {"prop": name from library(kind="props"), "x", "y" (the cell the prop is centred on), "z" (its bottom, default
    1), "orientation": 0..3}. A prop fills its size in cells, which must be empty; placed_props lists the props
    on the building and remove_props takes them away.

    Args:
        props: The props to place.
    """
    return _guard(lambda: {"placed": arch.place_props(props)})


@tool("read")
def placed_props() -> dict:
    """The props on the building being edited: prop name (as in library kind=props), orientation, the box of
    cells it fills (x0..x1, y0..y1, z0..z1) and its cell count."""
    def run():
        props = [{k: v for k, v in p.items() if k != "_cells"} for p in arch.placed_props()]
        return {"count": len(props), "props": props}
    return _guard(run)


@tool("act")
def remove_props(at: list[dict]) -> dict:
    """Remove whole props: every prop that has a cell at one of the given positions (all its cells go).

    Args:
        at: Positions {"x", "y"} or {"x", "y", "z"} (z omitted = any height), e.g. a prop's x0, y0 from
            placed_props.
    """
    def run():
        hit = arch.remove_props([(int(c["x"]), int(c["y"])) + ((int(c["z"]),) if "z" in c else ()) for c in at])
        if not hit:
            raise GameError("no prop at those positions (placed_props lists them)")
        return {"removed": [{k: v for k, v in p.items() if k != "_cells"} for p in hit]}
    return _guard(run)


@tool("act")
def copy_blocks(x0: int, y0: int, z0: int, x1: int, y1: int, z1: int, dx: int = 0, dy: int = 0, dz: int = 0,
                move: bool = False, overwrite: bool = False) -> dict:
    """Copy (or move) everything in a box - blocks with their paint and details, and prop cells - by an offset,
    like the Architect's copy / cut / paste of a plane: e.g. copy floor 1 (z 1..1) up with dz=1 to add a storey,
    or repeat a bay of a facade along x. Undo takes the whole copy back.

    Args:
        x0: Box corner x.
        y0: Box corner y.
        z0: Box corner z.
        x1: Opposite corner x.
        y1: Opposite corner y.
        z1: Opposite corner z.
        dx: Offset in x.
        dy: Offset in y.
        dz: Offset in z.
        move: Remove the originals (cut and paste).
        overwrite: Replace blocks already in the target cells (otherwise the call is refused if any target cell is
            taken).
    """
    return _guard(lambda: {"copied": arch.copy_blocks((x0, y0, z0, x1, y1, z1), (dx, dy, dz), move=move,
                                                      overwrite=overwrite), "blocks": arch.properties()["blocks"]})


@tool("act")
def fill_paint(x: int, y: int, z: int, face: str, texture: str, detail: bool = False) -> dict:
    """The Architect's Fill tool: paint (or put a detail on) the given face and every face connected to it that
    points the same way (shape and rotation included), can be seen and has the same paint (or detail) as that
    face - e.g. one whole wall, a whole flat roof, one side of a sloped roof, or the whole lot ground (z = 0, face
    "top"). Textures are laid out continuously as paint_faces does.

    Args:
        x: Cell x of the starting face.
        y: Cell y.
        z: Cell z (0 = ground).
        face: Direction name ("top", "+x", "-y", "slope -x", ...) or a slot number as text ("3"), as paint_faces.
        texture: Paint name (library walls / roofs / ground / colors / custom) or, with detail=true, a detail name;
            "" clears.
        detail: Fill with a detail instead of paint.
    """
    def run():
        faces = arch.fill_faces(x, y, z, face, detail=detail)
        n = arch.paint_mapped([dict(f, texture=texture) for f in faces], detail=detail)
        return {"filled": n}
    return _guard(run)


@tool("act")
def rotate_building(turns: int = 1) -> dict:
    """Turn the building on its lot by quarter turns, as the Architect's Rotate button (Space) does. Every block
    moves with it: with N cells a side, one turn moves the block at (x, y) to (N-1-y, x), so coordinates change.
    This sets which side faces which way in SimCity. To only look at other sides use view_image(rotation=...)
    instead. Undo turns it back.

    Args:
        turns: Quarter turns, 1..3 (negative turns the other way).
    """
    return _guard(lambda: {"rotation": arch.rotate(turns)})


@tool("act")
def undo(steps: int = 1) -> dict:
    """Undo the last editing calls (place / fill / remove / paint / detail / props), one call per step, with the
    Architect's own undo records. History starts when the building is opened or created and ends at a render
    (render_building resets the Architect's undo log).

    Args:
        steps: How many calls to undo.
    """
    def run():
        done = sum(1 for _ in range(max(1, steps)) if arch.undo())
        return {"undone": done, "blocks": arch.properties()["blocks"]}
    return _guard(run)


@tool("act")
def redo(steps: int = 1) -> dict:
    """Redo calls undone with undo (until a new edit is made).

    Args:
        steps: How many calls to redo.
    """
    def run():
        done = sum(1 for _ in range(max(1, steps)) if arch.redo())
        return {"redone": done, "blocks": arch.properties()["blocks"]}
    return _guard(run)


@tool("read", structured_output=False)
def view_image(mode: str = "paint", zoom: int = -1, rotation: int = 0, all_sides: bool = False,
               crop: bool = True) -> Image:
    """The Building Architect's view of the building being edited, read from its own render buffer (no
    screenshot). construct = untextured blocks with the edit grid and side planes; paint / detail / props = the
    textured building (on the Architect's showcase lot at low zoom); file = its preview. To see other sides the
    building is turned with the Rotate button and turned back afterwards (coordinates and undo are unaffected).

    Args:
        mode: construct | paint | detail | props | file.
        zoom: View zoom 0..5 (higher = closer; the program limits the range for each lot size); -1 keeps the
            current zoom.
        rotation: Quarter turns to view the building from, 0..3 (0 = as edited: the +x, +y sides face you; 2 =
            the back).
        all_sides: Return all four sides in one picture (2 x 2: rotation 0 top left, 1 top right, 2 bottom left,
            3 bottom right).
        crop: Cut the picture down to the building (and whatever else is drawn around it).
    """
    def run():
        if mode not in MODES:
            raise GameError(f"mode: one of {list(MODES)}")
        arch.model()
        if arch.mode() != mode:
            arch.set_mode(mode)
        if zoom >= 0:
            arch.set_zoom(zoom)
        import time as _t
        _t.sleep(0.3)
        ims = arch.view_images([0, 1, 2, 3] if all_sides else [rotation % 4], crop=crop)
        return _png(ims[0] if len(ims) == 1 else _grid(ims))
    return _guard(run)


def _grid(ims, cols: int = 2, pad: int = 4):
    from PIL import Image as PImage
    w, h = max(i.width for i in ims), max(i.height for i in ims)
    rows = (len(ims) + cols - 1) // cols
    bg = ims[0].getpixel((0, 0))
    out = PImage.new("RGB", (cols * w + (cols - 1) * pad, rows * h + (rows - 1) * pad), (255, 255, 255))
    for k, im in enumerate(ims):
        cell = PImage.new("RGB", (w, h), bg)
        cell.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        out.paste(cell, ((k % cols) * (w + pad), (k // cols) * (h + pad)))
    return out


@tool("act", structured_output=False)
def render_building(name: str = "", zoom: int = 4, install: bool = False):
    """Render a project with the Architect's own renderer into the sprites SimCity 3000 uses, and return how the
    building looks in the game (the four rotations side by side, decoded from the render output, no screenshot).
    By default the render goes to a temporary file; install=true adds the building to the game's
    Apps\\BARender\\BAT.DAT (keeping every other building; the old file is backed up next to it), as the
    Architect's render for SimCity does, so the game can use it.

    Args:
        name: Project file name in the Buildings folder (with or without .bld) or a full path; empty = the
            building being edited (saved first with save_building).
        zoom: Zoom of the returned picture: 1 (8 px per tile) .. 5 (128 px per tile).
        install: Also write the building into the game's BAT.DAT (SimCity 3000 must not be running: it keeps that
            file open).
    """
    def run():
        if name:
            path = _project_path(name)
        else:
            path = arch.current_path()
            if not path or not os.path.exists(path):
                raise GameError("the building being edited has no file: save_building first")
            if arch.properties()["unsaved_changes"]:
                raise GameError("the building has unsaved changes: save_building first (the renderer reads the file)")
        # the renderer draws with the view's state: in construct mode the working plane clips the building, so
        # render from the File tab, where the Architect's Render button is, and go back afterwards
        prev = arch.mode() if arch.screen() == 2 else None
        if prev and prev != "file":
            arch.set_mode("file")
        try:
            rs = render_mod.render_to_temp(app, path)
            b = rs.buildings[0]
            info = {"rendered": b["name"], "size": b["size"], "id": b["id"], "temp_file": rs.path}
            if install:
                info["installed"] = render_mod.install(app, path)
        finally:
            arch.forget_history()                 # rendering resets the Architect's undo log
            if prev and prev != "file":
                arch.set_mode(prev)
        img = sprites.sheet([rs.image(b, max(1, min(5, zoom)), r) for r in range(4)])
        return [json.dumps(info), _png(img)]
    return _guard(run)


# ------------------------------------------------------------------------------------------ photo to building
# Buildings made straight from photographs, without the Building Architect: a model of parts in metres with photo /
# pattern / texture materials, rendered by our own renderer (render3d.py, matched to the Architect's renders) into the
# game's sprite format (datwriter.py). See guide topic "photo".
PHOTO_DAT = os.path.join(os.path.dirname(RENDER_DAT), "MCP Photo Buildings.DAT")


def _photo_model(model: dict | None, model_path: str) -> dict:
    if model_path:
        if not os.path.exists(model_path):
            raise GameError(f"no model file {model_path}")
        return json.load(open(model_path, encoding="utf-8"))
    if not model:
        raise GameError("give the model (an object) or model_path (a JSON file)")
    return model


@tool("set")
def photo_add(name: str, image_path: str = "", image_base64: str = "", crop: list[int] | None = None,
              scale: float = 1.0) -> dict:
    """Add a photograph to work from (photo-to-building, no Building Architect needed): a picture file or base64,
    optionally cropped and scaled (coordinates in later calls are in the stored picture). Later calls refer to it by
    name; photo_view shows it with a pixel grid for reading coordinates.

    Args:
        name: A short name for the photo (letters, digits, spaces, - and _).
        image_path: A picture file (JPG, PNG...).
        image_base64: Or the picture as base64 (or a data: URL).
        crop: [x0, y0, x1, y1] in the original picture's pixels to keep only the building.
        scale: Resize after cropping (e.g. 0.5); about 30 - 60 px per metre of facade is plenty.
    """
    def run():
        from PIL import Image as PImage
        from . import custom, photomodel
        im = custom.load_image(image_path, image_base64)
        if crop:
            if len(crop) != 4:
                raise GameError("crop: [x0, y0, x1, y1]")
            im = im.crop(tuple(int(v) for v in crop))
        if scale and scale != 1.0:
            if not 0.05 <= scale <= 4:
                raise GameError("scale: 0.05 .. 4")
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), PImage.LANCZOS)
        return photomodel.add_photo(name, im)
    return _guard(run, _attach=False)


@tool("read", structured_output=False)
def photo_view(name: str, x0: int = 0, y0: int = 0, x1: int = -1, y1: int = -1, grid: int = 0) -> Image:
    """A photo (or part of it) with a labelled pixel grid in the photo's own coordinates - for reading the corners
    of facades, roofs and windows to use in photo materials (quad).

    Args:
        name: The photo's name (photo_add).
        x0: Left edge of the part to show (photo pixels).
        y0: Top edge.
        x1: Right edge (-1 = the photo's width).
        y1: Bottom edge (-1 = the photo's height).
        grid: Grid spacing in photo pixels (0 = about 10 lines across the shown part).
    """
    def run():
        from PIL import ImageDraw
        from . import photomodel
        im = photomodel.load_photo(name)
        X1 = im.width if x1 < 0 else min(x1, im.width)
        Y1 = im.height if y1 < 0 else min(y1, im.height)
        crop = im.crop((max(0, x0), max(0, y0), X1, Y1))
        f = min(1.0, 1200 / max(crop.size)) if max(crop.size) > 1200 else min(4.0, 800 / max(crop.size))
        view = crop.resize((max(1, int(crop.width * f)), max(1, int(crop.height * f))), PImage.LANCZOS)
        g = grid or max(10, int(round(max(crop.size) / 10 / 10)) * 10)
        dr = ImageDraw.Draw(view)
        for gx in range((max(0, x0) // g + 1) * g, X1, g):
            X = int((gx - x0) * f)
            dr.line([(X, 0), (X, view.height)], fill=(255, 255, 0), width=1)
            dr.text((X + 2, 2), str(gx), fill=(255, 255, 0))
        for gy in range((max(0, y0) // g + 1) * g, Y1, g):
            Y = int((gy - y0) * f)
            dr.line([(0, Y), (view.width, Y)], fill=(0, 255, 255), width=1)
            dr.text((2, Y + 2), str(gy), fill=(0, 255, 255))
        return _png(view)
    from PIL import Image as PImage
    return _guard(run, _attach=False)


@tool("read", structured_output=False)
def photo_rectify(name: str, quad: list[list[float]], width_m: float = 0, height_m: float = 0) -> Image:
    """Preview a photo material: the region inside quad (four photo pixels: the facade's top-left, top-right,
    bottom-right and bottom-left corners, as photo_view shows them) with the perspective removed - what a face will
    be painted with. Give the face's real size to see it in proportion.

    Args:
        name: The photo's name.
        quad: [[x, y], [x, y], [x, y], [x, y]]: top-left, top-right, bottom-right, bottom-left.
        width_m: The face's width in metres (0 = keep the photo's proportions).
        height_m: The face's height in metres.
    """
    def run():
        import math as _m
        from . import photomodel
        im = photomodel.load_photo(name)
        wq = max(_m.dist(quad[0], quad[1]), _m.dist(quad[3], quad[2]))
        hq = max(_m.dist(quad[0], quad[3]), _m.dist(quad[1], quad[2]))
        if width_m > 0 and height_m > 0:
            hq = wq * height_m / width_m
        out = photomodel.rectify(im, quad, int(max(16, min(1600, wq))), int(max(16, min(1600, hq))))
        return _png(out)
    return _guard(run, _attach=False)


@tool("read", structured_output=False)
def photo_model_render(model: dict | None = None, model_path: str = "", rotation: int = -1, zoom: int = 5,
                       shadows: bool = True):
    """Render a photo-built building model (see guide topic "photo": parts in metres, authored facade / pattern /
    texture / photo materials) exactly as SimCity 3000 will draw it - its projection, rotations, lot and lighting
    matched to the game's own buildings - without the Building Architect. Returns facts about the model and a picture
    (four rotations side by side, or one). Iterate until it matches the photo (compare them side by side, enlarged),
    then photo_model_export.

    Args:
        model: The model object {"name", "lot", "materials": {...}, "parts": [...]}.
        model_path: Or a JSON file holding the model.
        rotation: 0..3, or -1 for all four.
        zoom: 1..5 (5 = 128 px per tile, the game's closest zoom, drawn at full resolution).
        shadows: Cast soft shadows from the key light.
    """
    def run():
        import time as _t
        from . import photomodel, render3d
        m = _photo_model(model, model_path)
        t0 = _t.time()
        mesh, mats = photomodel.Builder(m).build()
        R = render3d.Renderer(mesh, mats, int(m.get("lot", 1)), shadows=shadows, lights=m.get("lighting", "game"))
        z = max(1, min(5, zoom))
        px = 8 * 2 ** (z - 1)
        ss = 4 if z >= 4 else 8
        rots = range(4) if rotation < 0 else [rotation % 4]
        ims = [render3d.crop_top(render3d.downsample(R.render(r, px, ss), ss)) for r in rots]
        info = {"name": m.get("name", ""), "lot_tiles": R.lot, "lot_m": R.L, "triangles": int(len(R.M)),
                "materials": len(mats), "props": len(mesh.billboards), "zoom": z,
                "pixels": [list(i.size) for i in ims], "seconds": round(_t.time() - t0, 1)}
        return [json.dumps(info), _png(sprites.sheet(ims))]
    return _guard(run, _attach=False)


@tool("act", structured_output=False)
def photo_model_export(model: dict | None = None, model_path: str = "", install: bool = False,
                       native_zoom5: bool = True, architect: str = "", description: str = ""):
    """Turn a photo-built model into a SimCity 3000 building: all 20 sprites (5 zooms x 4 rotations; zoom 5 at full
    resolution unless native_zoom5 is false) in the game's own format, written to a temporary DAT file; with
    install=true also into Apps\\BARender\\MCP Photo Buildings.DAT (our own file - the Architect's BAT.DAT is not
    touched; the previous file is backed up). The game reads that folder when it starts, so restart SimCity 3000,
    then put the building in a city with the game server's replace_building (it lists user-made buildings). Returns
    the building key and the zoom-5 picture.

    Args:
        model: The model object.
        model_path: Or a JSON file holding it.
        install: Also add it to the game's user-building folder (SimCity 3000 must be restarted to see it).
        native_zoom5: Store real 128 px-per-tile zoom-5 images (sharper) instead of zoom 4 doubled as the Architect does.
        architect: Architect name stored with the building (default the model's "architect").
        description: Description (default the model's "description").
    """
    def run():
        import tempfile, time as _t
        from . import datwriter, photomodel, render3d
        m = _photo_model(model, model_path)
        name = str(m.get("name") or "").strip()
        if not name:
            raise GameError("the model needs a name")
        t0 = _t.time()
        mesh, mats = photomodel.Builder(m).build()
        lot = int(m.get("lot", 1))
        R = render3d.Renderer(mesh, mats, lot, shadows=bool(m.get("shadows", True)),
                              lights=m.get("lighting", "game"))
        frames = render3d.sprite_set(R, ss=4, native_zoom5=native_zoom5)
        recs = datwriter.building_records(name, architect or m.get("architect", "sc3k-mcp photo"),
                                          description or m.get("description", ""), lot, frames, native_zoom5)
        out_dir = os.path.join(tempfile.gettempdir(), "sc3k-mcp", "photo")
        os.makedirs(out_dir, exist_ok=True)
        tmp = os.path.join(out_dir, re.sub(r"[^A-Za-z0-9 _\-]", "_", name) + ".DAT")
        datwriter.write_ixf(tmp, recs)
        rs = sprites.RenderedSet(tmp)                    # read back with the game-format reader
        b = rs.buildings[0]
        info = {"name": name, "lot_tiles": lot, "building_key": {"type": hex(datwriter.T_BLD),
                "group": hex(datwriter.GROUP), "instance": hex(b["id"])}, "temp_file": tmp,
                "bytes": os.path.getsize(tmp), "native_zoom5": native_zoom5, "seconds": round(_t.time() - t0, 1)}
        if install:
            info["installed"] = datwriter.install(recs, PHOTO_DAT)
            info["next"] = "restart SimCity 3000, then replace_building to show it in a city"
        z5 = [rs.image(b, 5, r) for r in range(4)]
        return [json.dumps(info), _png(sprites.sheet(z5))]
    return _guard(run, _attach=False)


@tool("read")
def photo_buildings() -> dict:
    """The photo-built buildings installed for the game (Apps\\BARender\\MCP Photo Buildings.DAT): name, building id,
    lot size, architect and description - what replace_building in the game server can show in a city after a
    restart."""
    def run():
        if not os.path.exists(PHOTO_DAT):
            return {"file": PHOTO_DAT, "buildings": []}
        rs = sprites.RenderedSet(PHOTO_DAT)
        return {"file": PHOTO_DAT, "buildings": [{"name": b["name"], "id": hex(b["id"]), "lot_tiles": b["size"],
                                                  "architect": b.get("architect", ""),
                                                  "description": b.get("description", "")}
                                                 for b in rs.buildings]}
    return _guard(run, _attach=False)


@tool("destructive")
def photo_building_remove(name: str) -> dict:
    """Take an installed photo-built building out of the game's user-building file (a test building, an old
    version): its records go, the other buildings stay, the previous file is kept as a dated .bak beside it. Like
    installing, it takes effect when SimCity 3000 next starts; first undo replace_building in any city that shows it.

    Args:
        name: The building's name or id, as photo_buildings lists it.
    """
    def run():
        from . import datwriter
        if not os.path.exists(PHOTO_DAT):
            raise GameError("no photo-built buildings are installed")
        b = sprites.RenderedSet(PHOTO_DAT).find(name)
        out = datwriter.uninstall({b["id"]}, PHOTO_DAT)
        out["buildings"] = [hex(i) for i in out["buildings"]]
        out["removed"] = b["name"]
        out["next"] = "restart SimCity 3000 for the change to show"
        return out
    return _guard(run, _attach=False)


@tool("destructive")
def bat_quit() -> dict:
    """Close the Building Architect (unsaved changes are lost)."""
    return _guard(app.quit, _attach=False)


def main():
    import argparse
    ap = argparse.ArgumentParser(prog="bat-mcp", description="MCP server for the SimCity 3000 Building Architect.")
    ap.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    if a.transport != "stdio":
        mcp.settings.host, mcp.settings.port = a.host, a.port
    mcp.run(transport=a.transport)


if __name__ == "__main__":
    main()
