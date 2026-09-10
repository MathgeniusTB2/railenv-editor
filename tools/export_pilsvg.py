"""Export Flatland's PILSVG sprites + manifest so a browser can reproduce the look.

Run once:  .venv/bin/python tools/export_pilsvg.py
Writes PNGs + manifest.json into web/assets/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "web" / "assets"


def main() -> None:
    from flatland.utils.graphics_pil import PILSVG

    gl = PILSVG(1, 1, screen_width=80, screen_height=80)
    cell = int(gl.nPixCell)
    OUT.mkdir(parents=True, exist_ok=True)

    def save(img, name: str) -> None:
        img.convert("RGBA").save(OUT / name)
        return name

    manifest: dict = {"cell": cell}

    # rail sprites keyed by the 16-bit transition mask (skip odd tuple keys)
    manifest["rail"] = {}
    for mask, img in gl.pil_rail.items():
        if not isinstance(mask, (int, np.integer)):
            continue
        f = save(img, f"rail_{int(mask):05d}.png")
        manifest["rail"][str(int(mask))] = f

    # decoration sprites (in flatland's load order)
    manifest["scenery"] = [save(img, f"scenery_{i}.png") for i, img in enumerate(gl.scenery)]
    manifest["scenery_d2"] = [save(img, f"scenery_d2_{i}.png") for i, img in enumerate(gl.scenery_d2)]
    manifest["scenery_d3"] = [save(img, f"scenery_d3_{i}.png") for i, img in enumerate(gl.scenery_d3)]
    manifest["scenery_water"] = [save(img, f"scenery_water_{i}.png") for i, img in enumerate(gl.scenery_water)]
    manifest["buildings"] = [save(img, f"building_{i}.png") for i, img in enumerate(gl.lBuildings)]
    if gl.station_colors:
        manifest["station"] = save(gl.station_colors[4], "station.png")

    with open(OUT / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)

    # report sprite sizes so the browser can scale
    examples = list(gl.pil_rail.items())[:2]
    print("cell px:", cell, "| rail sprites:", len(gl.pil_rail),
          "| scenery:", len(gl.scenery), "| buildings:", len(gl.lBuildings))
    for mask, img in examples:
        print("  rail", mask, img.size)


if __name__ == "__main__":
    main()
