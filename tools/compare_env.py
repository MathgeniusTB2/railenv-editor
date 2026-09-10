"""Render the every-tile environment with Flatland's PILSVG and with the editor,
then write a side-by-side comparison (two PNGs + a pixel-diff metric) for the
browser page ``web/compare.html``.

Run:  uv run --all-extras python tools/compare_env.py
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
MAP = OUT / "every_tile.json"


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, int(httpd.server_address[1])


def flatland_render(cells: np.ndarray, scale: int = 200) -> np.ndarray:
    """Flatland's own PILSVG render of ``cells`` as an RGBA uint8 array."""
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

    env = RailEnv(width=cols, height=rows, rail_generator=rail_from_grid_transition_map(rm),
                  line_generator=line_gen, timetable_generator=timetable, number_of_agents=0)
    rt = RenderTool(env, gl="PILSVG", screen_width=cols * scale, screen_height=rows * scale)
    env.reset()
    arr = rt.render_env(show=False, show_agents=False, show_observations=False, return_image=True)
    rt.close_window()
    return np.asarray(arr)


def editor_render() -> None:
    """Screenshot the editor's canvas with the every-tile map loaded."""
    from playwright.sync_api import sync_playwright

    httpd, port = _serve(WEB)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
            page.goto(f"http://127.0.0.1:{port}/index.html?map=testmaps/every_tile.json")
            page.wait_for_function(
                "document.getElementById('status') && "
                "document.getElementById('status').textContent.includes('Grid')"
            )
            page.wait_for_timeout(600)
            page.locator("#cv").screenshot(path=str(OUT / "every_tile_editor.png"))
            browser.close()
    finally:
        httpd.shutdown()
    _trim(OUT / "every_tile_editor.png")


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

    grid = json.loads(MAP.read_text())["grid"]

    flat = Image.fromarray(flatland_render(np.asarray(grid))).convert("RGBA")
    flat.save(OUT / "every_tile_flatland.png")
    _trim(OUT / "every_tile_flatland.png")
    flat = Image.open(OUT / "every_tile_flatland.png").convert("RGBA")

    editor_render()
    ed = Image.open(OUT / "every_tile_editor.png").convert("RGBA")

    # compare on a common size
    size = ed.size
    flat_r = flat.resize(size)
    a = np.asarray(ed.convert("RGB"), dtype=int)
    b = np.asarray(flat_r.convert("RGB"), dtype=int)
    mae = float(np.abs(a - b).mean())
    # rail-only rows (all but the last grid row, which the editor fills with stations)
    rows = len(grid)
    cut = int(round(a.shape[0] * (rows - 1) / rows))
    mae_rail = float(np.abs(a[:cut] - b[:cut]).mean())

    (OUT / "compare_env.json").write_text(json.dumps({
        "editor": "testmaps/every_tile_editor.png",
        "flatland": "testmaps/every_tile_flatland.png",
        "editor_size": list(ed.size),
        "flatland_size": list(flat.size),
        "mae": round(mae, 2),
        "mae_rail_rows": round(mae_rail, 2),
        "note": "Bottom row differs: the editor draws 4 station markers (editor-only); "
                "Flatland's 0-agent render has none.",
    }, indent=2) + "\n")
    print("wrote", OUT / "every_tile_flatland.png", flat.size)
    print("wrote", OUT / "every_tile_editor.png", ed.size)
    print("mean abs pixel diff (editor vs flatland):", round(mae, 2))
    print("mean abs pixel diff (rail rows only):     ", round(mae_rail, 2))


if __name__ == "__main__":
    main()
