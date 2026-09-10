"""Compare a real, Flatland-generated environment in the editor and in Flatland.

Generates a network with Flatland's ``sparse_rail_generator`` (cities, agents and
level-free crossings), saves it as ``.mpk``, derives an editor JSON with the same
grid + targets-as-stations + level-free + agent markers, then renders the whole
environment both ways and writes a side-by-side comparison for ``web/compare.html``.

Run:  uv run --all-extras python tools/compare_real_env.py
"""
from __future__ import annotations

import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = WEB / "testmaps"
SEED = 1
AGENTS = 3


def make_env():
    from flatland.envs.line_generators import sparse_line_generator
    from flatland.envs.observations import GlobalObsForRailEnv
    from flatland.envs.rail_env import RailEnv
    from flatland.envs.rail_generators import sparse_rail_generator

    env = RailEnv(
        width=30, height=30, number_of_agents=AGENTS,
        rail_generator=sparse_rail_generator(
            max_num_cities=3, max_rails_between_cities=2, max_rail_pairs_in_city=2, p_level_free=0.5),
        line_generator=sparse_line_generator(),
        obs_builder_object=GlobalObsForRailEnv(),
    )
    env.reset(random_seed=SEED)
    return env


def flatland_render(env, scale: int = 40) -> np.ndarray:
    from flatland.utils.rendertools import RenderTool

    rows, cols = env.rail.grid.shape
    rt = RenderTool(env, gl="PILSVG", screen_width=cols * scale, screen_height=rows * scale)
    arr = rt.render_env(show=False, show_agents=True, show_observations=False, return_image=True)
    rt.close_window()
    return np.asarray(arr)


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, int(httpd.server_address[1])


def editor_render(map_url: str) -> None:
    from playwright.sync_api import sync_playwright

    httpd, port = _serve(WEB)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=2)
            page.goto(f"http://127.0.0.1:{port}/index.html?map={map_url}")
            page.wait_for_function(
                "document.getElementById('status') && "
                "document.getElementById('status').textContent.includes('Grid')"
            )
            page.wait_for_timeout(700)
            page.evaluate(
                """() => {
                    const cv = document.getElementById('cv');
                    zoom = Math.max(0.05, Math.min(cv.clientWidth / (W * CELL),
                                                   cv.clientHeight / (H * CELL)) * 0.96);
                    centerView();
                }"""
            )
            page.wait_for_timeout(200)
            page.locator("#cv").screenshot(path=str(OUT / "real_env_editor.png"))
            browser.close()
    finally:
        httpd.shutdown()
    _trim(OUT / "real_env_editor.png")


def _trim(path: Path, pad: int = 0) -> None:
    from PIL import Image, ImageChops

    img = Image.open(path).convert("RGBA")
    bg = img.getpixel((0, 0))
    diff = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, bg[:3]))
    bbox = diff.getbbox()
    if bbox is None:
        return
    x0, y0, x1, y1 = bbox
    img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))).save(path)


def main() -> None:
    from PIL import Image

    env = make_env()
    env.reset(random_seed=SEED)
    grid = env.rail.grid.tolist()
    rows, cols = env.rail.grid.shape

    targets: set[tuple[int, int]] = set()
    agents = []
    for a in env.agents:
        (sr, sc), sd = a.initial_configuration
        (tr, tc) = a.waypoints[-1][-1].position
        targets.add((int(tc), int(tr)))          # editor uses (x=col, y=row)
        agents.append([int(sc), int(sr), int(sd)])   # editor uses (x=col, y=row, dir)
    level_free = [[int(c), int(r), 0] for (r, c) in sorted(env.resource_map.level_free_positions)]

    editor_map = {
        "width": cols, "height": rows, "origin": [0, 0],
        "grid": grid,
        "stations": [list(t) for t in sorted(targets)],
        "level_free": level_free,
        "agents": agents,
    }
    (OUT / "real_env.json").write_text(json.dumps(editor_map, indent=2) + "\n")

    flat = Image.fromarray(flatland_render(env)).convert("RGBA")
    flat.save(OUT / "real_env_flatland.png")
    _trim(OUT / "real_env_flatland.png")
    flat = Image.open(OUT / "real_env_flatland.png").convert("RGBA")

    editor_render("testmaps/real_env.json")
    ed = Image.open(OUT / "real_env_editor.png").convert("RGBA")

    a = np.asarray(ed.resize(flat.size).convert("RGB"), dtype=int)
    b = np.asarray(flat.convert("RGB"), dtype=int)
    mae = float(np.abs(a - b).mean())

    (OUT / "compare_real.json").write_text(json.dumps({
        "editor": "testmaps/real_env_editor.png",
        "flatland": "testmaps/real_env_flatland.png",
        "grid": [cols, rows],
        "agents": len(env.agents),
        "level_free": len(env.resource_map.level_free_positions),
        "mae": round(mae, 2),
    }, indent=2) + "\n")
    print(f"real env: {cols}x{rows}, {len(env.agents)} agents, "
          f"{len(env.resource_map.level_free_positions)} level-free")
    print("wrote", OUT / "real_env.json", "+ real_env_{flatland,editor}.png + compare_real.json")
    print("mean abs pixel diff (editor vs flatland):", round(mae, 2))


if __name__ == "__main__":
    main()
