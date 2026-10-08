"""Draw the ESB spire (102nd-floor drum, cone, broadcast antenna) as a 1 x 1 x 15 prop on prop_template's grid:
256 px bitmap, cell 32 px wide, storey 16 px, middle cell (z index 7) centred -> ground (z = 0) centre at
y = 128 + 16 * 7.5 = 248, each storey 16 px up. Rotationally symmetric, so all four views are the same."""
import os
import sys
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spire")
S, H = 256, 15
CX = 128
Y0 = 128 + 16 * 7.5          # y of the prop's ground level at the cell centre (diamond centre)


def zy(z):                   # height in storeys -> bitmap y (cell centre column)
    return Y0 - 16 * z


def shade(t):                # t 0 (left, lit) .. 1 (right, shadow): aluminium
    a, b = (232, 232, 228), (128, 130, 134)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def draw() -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    px = im.load()
    dr = ImageDraw.Draw(im)

    def cylinder(z0, z1, r0, r1, windows=False):
        y0, y1 = int(zy(z1)), int(zy(z0))
        for y in range(y0, y1 + 1):
            f = (y - y0) / max(1, (y1 - y0))           # 0 at top .. 1 at bottom
            r = r1 + (r0 - r1) * f
            for x in range(int(CX - r), int(CX + r) + 1):
                t = (x - (CX - r)) / max(1, 2 * r)
                c = shade(t)
                if windows and int(x - CX + 64) % 4 == 0 and (y - y0) % 8 < 6:
                    c = (60, 66, 76, 255)
                px[x, y] = c
        # elliptical top (lit)
        r = r1
        dr.ellipse([CX - r, zy(z1) - r / 2, CX + r, zy(z1) + r / 2], fill=(240, 240, 236, 255))

    cylinder(0.0, 2.0, 11, 11, windows=True)      # the 102nd-floor drum (with its windows)
    cylinder(2.0, 2.4, 13, 13)                    # balcony ring
    cylinder(2.4, 4.0, 10, 3)                     # cone
    cylinder(4.0, 5.0, 3, 3)                      # antenna base
    for z in (6.0, 8.5, 10.5):                    # antenna platforms
        cylinder(z - 0.25, z, 4, 4)
    cylinder(5.0, 13.5, 2, 1)                     # antenna mast
    cylinder(13.5, 14.8, 1, 0.5)                  # lightning rod
    return im


def write() -> list[str]:
    """Draw the four views (identical: the spire is round) into spire/ and return their paths."""
    os.makedirs(OUT, exist_ok=True)
    im = draw()
    paths = []
    for k in range(4):
        p = os.path.join(OUT, f"spire_view{k}.png")
        im.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    print(write())
