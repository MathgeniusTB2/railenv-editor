"""Capture README screenshots of the web editor with a headless browser.

Serves ``web/`` locally, loads a map through the editor's own Open path, and
writes PNGs into ``docs/``. Uses the installed Google Chrome via Playwright's
``chrome`` channel, so no Chromium download is required.

Run:  uv run --extra dev python tools/screenshot_web.py
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DOCS = ROOT / "docs"


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = int(httpd.server_address[1])
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def _fit_view(page, margin: float = 0.92) -> None:
    """Zoom so the loaded grid fills the canvas area, then centre it."""
    page.evaluate(
        """(m) => {
            const cv = document.getElementById('cv');
            const z = Math.min(cv.clientWidth / (W * CELL), cv.clientHeight / (H * CELL)) * m;
            zoom = Math.max(0.1, Math.min(20, z));
            centerView();
        }""",
        margin,
    )


def main() -> None:
    from playwright.sync_api import sync_playwright

    DOCS.mkdir(exist_ok=True)
    httpd, port = _serve(WEB)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
            page.goto(f"http://127.0.0.1:{port}/index.html")
            page.wait_for_function(
                "document.getElementById('status') && "
                "document.getElementById('status').textContent.includes('Grid')"
            )

            # clean hero: the whole app with the demo network loaded
            page.set_input_files("#file", str(WEB / "testmaps" / "demo.json"))
            page.wait_for_timeout(500)
            _fit_view(page)
            page.wait_for_timeout(300)
            page.locator("#wrap").screenshot(path=str(DOCS / "hero.png"))

            # every-tile detail: the raw canvas (all 29 transitions), trimmed
            page.set_input_files("#file", str(WEB / "testmaps" / "every_tile.json"))
            page.wait_for_timeout(500)
            page.locator("#cv").screenshot(path=str(DOCS / "every-tile.png"))
            _trim(DOCS / "every-tile.png")

            browser.close()
    finally:
        httpd.shutdown()
    print("wrote", DOCS / "hero.png")
    print("wrote", DOCS / "every-tile.png")


def _trim(path: Path, pad: int = 8) -> None:
    """Crop the uniform background border (the canvas AIR margin)."""
    from PIL import Image, ImageChops

    img = Image.open(path).convert("RGBA")
    bg = img.getpixel((0, 0))
    diff = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, bg[:3]))
    bbox = diff.getbbox()
    if bbox is None:
        return
    x0, y0, x1, y1 = bbox
    img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))).save(path)


if __name__ == "__main__":
    main()
