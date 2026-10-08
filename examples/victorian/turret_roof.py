"""The turret's conical roof as a 3 x 3 x 5 prop: a shingled cone (with a band at the eave) and a turned finial,
ray-cast on prop_template's grid (2:1 isometric, cell 32 px wide, storey 16 px, middle cell centred) so it sits
exactly on the turret below. Rotationally symmetric, so all four views are the same picture; the light comes from
the left like the Architect's renderer (the +x wall, on the left, is the lit one)."""
import math
import os

from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turret")
W, D, H = 3, 3, 5
S = 128
RX, RY, RZ = (W - 1) // 2 + 0.5, (D - 1) // 2 + 0.5, (H - 1) // 2 + 0.5
CX, CY = 1.5, 1.5                 # cone axis (cell units, prop-local)
R0, Z0, ZT = 1.62, 0.0, 3.6       # base radius (slight overhang), base height, apex height of the cone
FIN = [(3.6, 0.20), (3.85, 0.13), (4.0, 0.20), (4.15, 0.10), (4.6, 0.07), (4.75, 0.12), (4.9, 0.04)]  # finial profile


def radius(z):
    """Solid of revolution: cone + eave band + finial knobs; radius at height z (cell units), None above."""
    if z < Z0:
        return None
    if z <= 0.25:
        return R0 + 0.05                                   # eave band
    if z <= ZT:
        return R0 * (ZT - z) / (ZT - 0.25) + 0.02
    for (za, ra), (zb, rb) in zip(FIN, FIN[1:]):
        if za <= z <= zb:
            return ra + (rb - ra) * (z - za) / (zb - za)
    return None


def colour(z, nx, ny, nz):
    # light from the upper left of the picture: towards +x, a little -y, up
    lx, ly, lz = 0.55, -0.25, 0.8
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
    d = max(0.0, (nx * lx + ny * ly + nz * lz) / n)
    if z <= 0.25:
        base = (96, 106, 94)                               # trim band
    elif z <= ZT:
        row = int((z - 0.25) * 8)                          # shingle courses
        base = (150, 98, 82) if row % 2 else (136, 88, 74)
        if (row % 2 == 0) and ((math.atan2(ny, nx) * 12) % 2 < 0.25):
            base = (112, 72, 62)                           # shingle joints
    else:
        base = (60, 66, 70)                                # metal finial
    k = 0.45 + 0.75 * d
    return tuple(min(255, int(c * k)) for c in base) + (255,)


def draw() -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    px = im.load()
    cen = S / 2
    for py in range(S):
        for pxx in range(S):
            u = (pxx + 0.5 - cen) / 16.0            # = (y - RY) - (x - RX)
            v = (py + 0.5 - cen)                    # = 8 ((x - RX) + (y - RY)) - 16 (z - RZ)
            # march from the viewer (large x + y) backwards
            hit = None
            for k in range(240):
                t = 6.0 - k * 0.025                 # t = (x - RX) + (y - RY)
                z = (8 * t - v) / 16.0 + RZ
                x = (t - u) / 2 + RX
                y = (t + u) / 2 + RY
                r = radius(z)
                if r is not None and math.hypot(x - CX, y - CY) <= r:
                    hit = (x, y, z, r)
                    break
            if hit:
                x, y, z, r = hit
                dx, dy = x - CX, y - CY
                slope = R0 / (ZT - 0.25) if 0.25 < z <= ZT else 0.0
                rr = math.hypot(dx, dy) or 1
                px[pxx, py] = colour(z, dx / rr, dy / rr, slope)
    return im


def write() -> list[str]:
    os.makedirs(OUT, exist_ok=True)
    im = draw()
    paths = []
    for k in range(4):
        p = os.path.join(OUT, f"turret_roof_view{k}.png")
        im.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    print(write())
