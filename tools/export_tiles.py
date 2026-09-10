"""Export Flatland's authoritative rail-transition catalogue for the comparison page.

Writes ``web/testmaps/tiles.json`` (a list of ``{value, name}`` from
``RailEnvTransitionsEnum``) so ``web/compare.html`` can show every valid tile
next to the editor's sprite and check it against the generated every-tile map.

Run:  uv run --all-extras python tools/export_tiles.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "web" / "testmaps" / "tiles.json"


def main() -> None:
    from flatland.envs.grid.rail_env_grid import RailEnvTransitionsEnum

    tiles = sorted((int(t), t.name) for t in RailEnvTransitionsEnum)
    OUT.write_text(json.dumps([{"value": v, "name": n} for v, n in tiles], indent=2) + "\n",
                   encoding="utf-8")
    print("wrote", OUT, "|", len(tiles), "tiles")


if __name__ == "__main__":
    main()
