"""Verify the web renderer reproduces Flatland's PILSVG look.

Renders a sample grid two ways and reports the pixel difference:
  1. real  = Flatland's ``RenderTool(gl="PILSVG")`` output
  2. repro = PIL draw using ``web/assets`` sprites + the transcribed ``set_rail_at`` logic
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

SCALE = 40
REPRO_CELL = 30


def sample(n: int) -> np.ndarray:
    g = np.zeros((n, n), dtype=np.uint16)
    for x in range(n):
        g[5, x] = 1025
    for y in range(2, 5):
        g[y, 5] = 32800
    g[2, 5] = 33825
    g[6, 6] = 16386
    g[7, 6] = 49186
    g[8, 8] = 8192
    return g


def flatland_render(cells: np.ndarray) -> np.ndarray:
    """Flatland's own PILSVG render as a uint8 RGBA array (no Qt objects)."""
    from flatland.envs.grid.rail_env_grid import RailEnvTransitions
    from flatland.envs.line_generators import Line
    from flatland.envs.rail_env import RailEnv
    from flatland.envs.rail_generators import rail_from_grid_transition_map
    from flatland.envs.rail_grid_transition_map import RailGridTransitionMap
    from flatland.utils.rendertools import RenderTool

    g = np.asarray(cells, dtype=np.uint16)
    rows, cols = g.shape
    rm = RailGridTransitionMap(width=cols, height=rows, transitions=RailEnvTransitions(), grid=g)

    def line_gen(rail, num_agents, hints, num_resets, np_random):
        return Line(agent_waypoints={}, agent_speeds=[])

    def timetable(agents, distance_map, hints, np_random):
        class T:
            pass

        t = T()
        t.max_episode_steps = 1
        t.earliest_departures = []
        t.latest_arrivals = []
        return t

    env = RailEnv(
        width=cols,
        height=rows,
        rail_generator=rail_from_grid_transition_map(rm),
        line_generator=line_gen,
        timetable_generator=timetable,
        number_of_agents=0,
    )
    rt = RenderTool(env, gl="PILSVG", screen_width=cols * SCALE, screen_height=rows * SCALE)
    env.reset()
    arr = rt.render_env(show=False, show_agents=False, show_observations=False, return_image=True)
    rt.close_window()
    return np.asarray(arr)


def repro(g: np.ndarray, cities: set[tuple[int, int]]) -> Image.Image:
    m = json.load(open(ROOT / "web/assets/manifest.json"))
    cell = REPRO_CELL
    w, h = g.shape[1], g.shape[0]
    img = Image.new("RGBA", (w * cell, h * cell), (233, 238, 233, 255))
    rail = {int(k): Image.open(ROOT / "web/assets" / v).convert("RGBA") for k, v in m["rail"].items()}
    scenery = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["scenery"]]
    sc2 = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["scenery_d2"]]
    water = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["scenery_water"]]
    buildings = [Image.open(ROOT / "web/assets" / v).convert("RGBA") for v in m["buildings"]]
    station = Image.open(ROOT / "web/assets" / "station.png").convert("RGBA")
    bg = math.ceil(math.sqrt(w * w + h * h))

    def put(im: Image.Image, c: int, r: int) -> None:
        im = im.resize((cell, cell))
        img.paste(im, (c * cell, r * cell), im)

    for r in range(h):
        for c in range(w):
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


def main() -> None:
    cities = {(6, 7)}
    n = 16
    grid = sample(n)

    real = Image.fromarray(flatland_render(grid)).convert("RGBA")
    real = real.resize((n * REPRO_CELL, n * REPRO_CELL))
    repro_pil = repro(grid, cities)

    real.save("/tmp/real.png")
    repro_pil.save("/tmp/repro.png")

    a = np.asarray(real.convert("RGB"), dtype=int)
    b = np.asarray(repro_pil.convert("RGB"), dtype=int)
    mae = np.abs(a - b).mean()
    print("saved /tmp/real.png /tmp/repro.png")
    print("mean abs pixel diff (vector vs pilsvg):", round(float(mae), 2))


if __name__ == "__main__":
    main()
