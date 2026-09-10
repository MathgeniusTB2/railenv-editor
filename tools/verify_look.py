"""Verify the transcribed placement + exported sprites reproduce flatland's pilsvg.

Renders a sample grid two ways and reports the pixel difference:
  1. real = flatland's PilsvgRenderer output
  2. repro = PIL draw using web/assets sprites + the transcribed set_rail_at logic
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from railenv_editor.editor.canvas import PilsvgRenderer

ROOT = Path(__file__).resolve().parents[1]


def sample(N):
    g = np.zeros((N, N), dtype=np.uint16)
    for x in range(N):
        g[5, x] = 1025
    for y in range(2, 5):
        g[y, 5] = 32800
    g[2, 5] = 33825
    g[6, 6] = 16386
    g[7, 6] = 49186
    g[8, 8] = 8192
    return g


def repro(g, cities):
    m = json.load(open(ROOT / "web/assets/manifest.json"))
    cell = 30
    W = g.shape[1]
    H = g.shape[0]
    img = Image.new("RGBA", (W * cell, H * cell), (233, 238, 233, 255))
    rail = {int(k): Image.open(ROOT / "web/assets" / v).convert("RGBA") for k, v in m["rail"].items()}
    scenery = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["scenery"]]
    sc2 = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["scenery_d2"]]
    water = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["scenery_water"]]
    buildings = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["buildings"]]
    station = Image.open(ROOT / "web/assets" / "station.png").convert("RGBA")
    bg = math.ceil(math.sqrt(W * W + H * H))

    def put(im, c, r):
        im = im.resize((cell, cell))
        img.paste(im, (c * cell, r * cell), im)

    for r in range(H):
        for c in range(W):
            v = int(g[r, c])
            pt = None
            if v == 0:
                s1 = bg <= 4 + math.ceil(((c * r + c) % 10) / 1)
                if s1:
                    a = bg % len(buildings)
                    if (c + r + c * r) % 13 > 11:
                        pt = scenery[a % len(scenery)]
                    else:
                        if (c + r + c * r) % 3 == 0:
                            a = (a + (c + r + c * r)) % len(buildings)
                        pt = buildings[a]
                elif bg > 5 + ((c * r + c) % 3) or ((c ** 3 + r ** 2 + c * r) % 10 == 0):
                    a = bg - 4
                    a2 = a + (c + r + c * r + c ** 3 + r ** 4)
                    if a2 % 64 > 11:
                        a = a2
                    a_l = a % len(scenery)
                    pt = water[0] if a2 % 50 == 49 else scenery[a_l]
                    if a2 % 11 > 3 and a_l == len(scenery) - 1:
                        if c > 1 and r % 7 == 1 and int(g[r, c - 1]) == 0:
                            put(sc2[0], c - 1, r)
                            pt = sc2[1]
                else:
                    pt = rail.get(0)
                if pt is not None:
                    put(pt, c, r)
                if (c, r) in cities:
                    put(station, c, r)
            else:
                spr = rail.get(v)
                if spr is not None:
                    put(spr, c, r)
    return img


cities = {(6, 7)}
N = 16
grid = sample(N)
real = PilsvgRenderer(40).render(grid, cities)
# real is QImage
from PySide6.QtCore import QBuffer  # noqa

def qimg_to_png(qimg):
    arr = np.array(qimg.constBits()).reshape(qimg.height(), qimg.width(), 4)
    return Image.fromarray(arr).convert("RGBA")

real_pil = qimg_to_png(real[0].copy())
real_pil.save("/tmp/real.png")
repro_pil = repro(grid, cities)
repro_pil.save("/tmp/repro.png")
# compare: resize real to repro cell coords (real cell = real[1])
cellr = real[1]
real_resized = real_pil.resize((N * 30, N * 30))
a = np.asarray(real_resized.convert("RGB"), dtype=int)
b = np.asarray(repro_pil.convert("RGB"), dtype=int)
mae = np.abs(a - b).mean()
print("saved /tmp/real.png /tmp/repro.png")
print("real cell px:", cellr, "| mean abs pixel diff (vector vs pilsvg):", round(float(mae), 2))
