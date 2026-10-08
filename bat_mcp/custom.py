"""User-made textures, details and props for the Building Architect: files in Apps\\BACustom, in the formats its
readmes describe (Apps\\BACustom\\{Paints,Details,Props}\\Readme*.txt):

- paints: .bmp or .tga, sides a multiple of 16 px (16 px = one block face); written here as 24-bit BMP.
- details: .bmp (pink 255,0,255 = transparent) or 32-bit .tga with an alpha channel; written here as 32-bit TGA.
- props: .bmp views (128 x 128, pink background) plus a .met file with one line per orientation
  `W,D,H:"v0.bmp","v1.bmp","v2.bmp","v3.bmp"` (footprint and height in cells, then the views for the four camera
  rotations; the samples list the four orientations as the views rotated one step each, and W / D swapped on the
  odd ones).
"""

from __future__ import annotations

import base64
import io
import os
import re

from PIL import Image

from sc3k_mcp.game import GameError

from .app import APPS

CUSTOM = os.path.join(APPS, "BACustom")
DIRS = {"paint": os.path.join(CUSTOM, "Paints"), "detail": os.path.join(CUSTOM, "Details"),
        "prop": os.path.join(CUSTOM, "Props")}
PINK = (255, 0, 255)
PROP_SIZES = (32, 64, 128, 256)     # the stock props' view bitmaps are squares of these sizes, all at one scale


def prop_box(w: int, d: int, h: int) -> tuple[float, float, float, float]:
    """The prop's box in a bitmap of size 0 (centre at 0, 0): left, top, right, bottom (2:1 isometric, a cell 32 px
    wide and 16 px deep, one storey 16 px high, the middle cell (index (n-1)//2 on each axis) centred; verified on
    the stock props of every size, e.g. radiotower1 1x1x13 in 256 px, column4 1x1x2 in 64 px)."""
    rx, ry, rz = (w - 1) // 2 + 0.5, (d - 1) // 2 + 0.5, (h - 1) // 2 + 0.5
    return (-16 * (w + d) / 2, 8 * (-rx - ry) - 16 * (h - rz), 16 * (w + d) / 2, 8 * (w - rx + d - ry) + 16 * rz)


def prop_bitmap_size(w: int, d: int, h: int) -> int:
    """The smallest stock bitmap size the prop's box fits in (as the stock props use)."""
    boxes = [prop_box(w, d, h), prop_box(d, w, h)]
    for S in PROP_SIZES:
        if all(-S / 2 <= l and r <= S / 2 and -S / 2 <= t and b <= S / 2 for l, t, r, b in boxes):
            return S
    raise GameError(f"a {w}x{d}x{h} prop does not fit the largest prop bitmap (256 px): footprint + height too big")


def check_name(name: str) -> str:
    n = name.strip()
    if n.lower().endswith((".bmp", ".tga", ".met")):
        n = n[:-4]
    if not n or not re.fullmatch(r"[A-Za-z0-9 _\-]{1,40}", n):
        raise GameError("name: 1..40 letters, digits, spaces, '-' or '_'")
    return n


def parse_color(v) -> tuple | None:
    """'#rrggbb', 'r,g,b', [r, g, b] or 'transparent' / 'none'."""
    if isinstance(v, (list, tuple)) and len(v) in (3, 4):
        return tuple(int(c) for c in v[:3]) + (255,)
    s = str(v).strip().lower()
    if s in ("transparent", "none", "clear", ""):
        return (0, 0, 0, 0)
    if s.startswith("#") and len(s) == 7:
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    parts = [p for p in re.split(r"[ ,]+", s) if p]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return tuple(min(255, int(p)) for p in parts) + (255,)
    raise GameError(f"colour {v!r}: use '#rrggbb', 'r,g,b' or 'transparent'")


def load_image(image_path: str = "", image_base64: str = "", rows: list[str] | None = None,
               palette: dict | None = None, scale: int = 1) -> Image.Image:
    """An RGBA image from a file, base64 data, or pixel rows (one string per row, one palette character per
    pixel), enlarged scale times (nearest neighbour)."""
    given = [bool(image_path), bool(image_base64), bool(rows)]
    if sum(given) != 1:
        raise GameError("give exactly one of image_path, image_base64 or rows (+ palette)")
    if image_path:
        if not os.path.isfile(image_path):
            raise GameError(f"no file {image_path}")
        im = Image.open(image_path)
    elif image_base64:
        data = image_base64.split(",", 1)[1] if image_base64.startswith("data:") else image_base64
        try:
            im = Image.open(io.BytesIO(base64.b64decode(data)))
        except Exception as e:
            raise GameError(f"image_base64 is not an image: {e}")
    else:
        if not palette:
            raise GameError("rows need a palette: {character: colour}")
        cols = {str(k)[:1]: parse_color(v) for k, v in palette.items()}
        w = len(rows[0])
        if not w or any(len(r) != w for r in rows):
            raise GameError("rows must all have the same length")
        im = Image.new("RGBA", (w, len(rows)))
        px = im.load()
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if ch not in cols:
                    raise GameError(f"row {y}: character {ch!r} is not in the palette")
                px[x, y] = cols[ch]
    im = im.convert("RGBA")
    scale = int(scale)
    if not 1 <= scale <= 16:
        raise GameError("scale: 1..16")
    if scale > 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    return im


def existing(name: str) -> str | None:
    """A texture / prop file with this name anywhere in the Architect's folders."""
    from . import bldfile
    for ext in (".bmp", ".tga"):
        p = bldfile.find_texture_file(name + ext)
        if p:
            return p
    return None


def _target(kind: str, name: str, ext: str, overwrite: bool) -> str:
    path = os.path.join(DIRS[kind], name + ext)
    other = existing(name)
    if other and os.path.normcase(other) != os.path.normcase(path):
        raise GameError(f"the Architect already has a texture or prop named {name!r} ({other}): pick another name")
    if os.path.exists(path) and not overwrite:
        raise GameError(f"{path} exists: overwrite=true replaces it")
    return path


def write_texture(kind: str, name: str, im: Image.Image, overwrite: bool = False) -> str:
    """Write a custom paint (24-bit BMP) or detail (32-bit TGA with alpha) into BACustom."""
    if kind not in ("paint", "detail"):
        raise GameError("kind: paint or detail")
    name = check_name(name)
    w, h = im.size
    if w % 16 or h % 16 or not (16 <= w <= 256 and 16 <= h <= 256):
        raise GameError(f"the image is {w}x{h}: each side must be a multiple of 16 px (one block face), 16..256")
    if kind == "paint":
        if im.getextrema()[3][0] < 255:
            raise GameError("paints cannot be transparent (use kind=detail for a decal with see-through parts)")
        path = _target(kind, name, ".bmp", overwrite)
        im.convert("RGB").save(path, "BMP")
    else:
        path = _target(kind, name, ".tga", overwrite)
        im.save(path, "TGA")
    _forget_cache()
    return path


def write_prop(name: str, size: tuple, views: list[Image.Image], overwrite: bool = False) -> dict:
    """Write a custom prop: four square view bitmaps (32, 64, 128 or 256 px, at least the size prop_template
    gives; transparent / pink background) and its .met file."""
    name = check_name(name)
    w, d, h = (int(v) for v in size)
    if not (1 <= w <= 7 and 1 <= d <= 7 and 1 <= h <= 28):
        raise GameError("size: footprint 1..7 x 1..7 cells, height 1..28 cells")
    if len(views) != 4:
        raise GameError("a prop needs four views (camera rotations 0..3)")
    files = [f"{name} {k}.bmp" for k in range(4)]
    met = os.path.join(DIRS["prop"], name + ".met")
    other = existing(f"{name} 0")
    if other and os.path.normcase(os.path.dirname(other)) != os.path.normcase(DIRS["prop"]):
        raise GameError(f"the Architect already has a prop named {name!r}: pick another name")
    if (os.path.exists(met) or any(os.path.exists(os.path.join(DIRS["prop"], f)) for f in files)) and not overwrite:
        raise GameError(f"prop {name!r} exists in BACustom\\Props: overwrite=true replaces it")
    need = prop_bitmap_size(w, d, h)
    S = views[0].size[0]
    for k, im in enumerate(views):
        if im.size != (S, S) or S not in PROP_SIZES:
            raise GameError(f"view {k} is {im.size[0]}x{im.size[1]}: prop views are squares of 32, 64, 128 or 256 px, "
                            "all four the same size (prop_template gives the size and layout)")
    if S < need:
        raise GameError(f"a {w}x{d}x{h} prop needs {need} x {need} px views (see prop_template)")
    for k, im in enumerate(views):
        bg = Image.new("RGB", (S, S), PINK)
        rgb = im.convert("RGB")
        px = rgb.load()                      # opaque pixels that happen to be pink would turn transparent: nudge them
        for y in range(S):
            for x in range(S):
                if px[x, y] == PINK:
                    px[x, y] = (254, 0, 254)
        bg.paste(rgb, (0, 0), im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
        bg.save(os.path.join(DIRS["prop"], files[k]), "BMP")
    lines = []
    for o in range(4):
        sx, sy = (w, d) if o % 2 == 0 else (d, w)
        vs = files[o:] + files[:o]
        lines.append(f"{sx},{sy},{h}:" + ",".join(f'"{v}"' for v in vs))
    open(met, "w", encoding="latin-1", newline="").write("\r\n".join(lines) + "\r\n")
    _forget_cache()
    return {"met": met, "views": [os.path.join(DIRS["prop"], f) for f in files], "size": [w, d, h], "pixels": S}


def _forget_cache() -> None:
    from . import bldfile
    bldfile._TEX_CACHE.clear()


def prop_template(w: int, d: int, h: int, view: int = 0, size: int = 0) -> Image.Image:
    """The drawing guide for one view of a W x D x H prop, as the Architect's sample templates
    (BACustom\\Props\\1X1X5.BMP etc.) draw it: 2:1 isometric, a cell 32 px wide and 16 px deep, one storey 16 px
    high, the middle cell (x (W-1)//2, y (D-1)//2, z (H-1)//2) centred in the bitmap; views 1 and 3 see the
    footprint turned (W and D swapped). size = bitmap side (32 / 64 / 128 / 256; 0 = the smallest that fits).
    Pink background; visible faces lightly shaded with the cell grid drawn (left face 205, right face 158, top 242
    grey)."""
    from PIL import ImageDraw
    S = size or prop_bitmap_size(w, d, h)
    if view % 2:
        w, d = d, w
    rx, ry, rz = (w - 1) // 2 + 0.5, (d - 1) // 2 + 0.5, (h - 1) // 2 + 0.5
    cen = S / 2

    def P(x, y, z):                       # cell-space point -> bitmap pixel (prop_offsets: u = y - x, v = x + y - 2z)
        return (cen + 16 * ((y - ry) - (x - rx)), cen + 8 * ((x - rx) + (y - ry)) - 16 * (z - rz))

    im = Image.new("RGB", (S, S), PINK)
    dr = ImageDraw.Draw(im)
    top = [P(0, 0, h), P(w, 0, h), P(w, d, h), P(0, d, h)]
    left = [P(w, 0, 0), P(w, d, 0), P(w, d, h), P(w, 0, h)]      # +x side (faces the viewer, left)
    right = [P(0, d, 0), P(w, d, 0), P(w, d, h), P(0, d, h)]     # +y side (right)
    for poly, c in ((left, (205, 205, 205)), (right, (158, 158, 158)), (top, (242, 242, 242))):
        dr.polygon(poly, fill=c)
    line = (110, 110, 110)
    for k in range(w + 1):
        dr.line([P(k, d, 0), P(k, d, h)], fill=line)
        dr.line([P(k, 0, h), P(k, d, h)], fill=line)
    for k in range(d + 1):
        dr.line([P(w, k, 0), P(w, k, h)], fill=line)
        dr.line([P(0, k, h), P(w, k, h)], fill=line)
    for z in range(h + 1):
        dr.line([P(w, 0, z), P(w, d, z), P(0, d, z)], fill=line)
    return im
