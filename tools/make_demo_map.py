"""Build a clean, connected demo network for the README screenshots.

Writes ``web/testmaps/demo.json`` (the editor's JSON map format). The layout is a
multi-loop network: an outer ring, two horizontal spines, a vertical spine, three
connectors, a diamond crossing (marked level-free), a single slip, a double slip,
dead-end spurs, and city/station markers.

Edges are added symmetrically (``link`` adds both directions) and the result is
validated for reciprocity + Flatland validity, so every track connects and every
cell is a real ``RailEnvTransitions`` value.
"""
from __future__ import annotations

import json
from pathlib import Path

from railenv_editor.core import transitions as T

OUT = Path(__file__).resolve().parents[1] / "web" / "testmaps" / "demo.json"

W, H = 24, 14

# N=0, E=1, S=2, W=3
DELTA = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
OPP = {0: 2, 2: 0, 1: 3, 3: 1}

cells: dict[tuple[int, int], set[int]] = {}


def add_dir(x: int, y: int, d: int) -> None:
    cells.setdefault((x, y), set()).add(d)


def link(x1: int, y1: int, x2: int, y2: int) -> None:
    """Add a track between adjacent cells (both directions)."""
    dx, dy = x2 - x1, y2 - y1
    d = next(k for k, v in DELTA.items() if v == (dx, dy))
    add_dir(x1, y1, d)
    add_dir(x2, y2, OPP[d])


def ring(x0: int, y0: int, x1: int, y1: int) -> None:
    for x in range(x0, x1):
        link(x, y0, x + 1, y0)
        link(x, y1, x + 1, y1)
    for y in range(y0, y1):
        link(x0, y, x0, y + 1)
        link(x1, y, x1, y + 1)


def line_h(y: int, x0: int, x1: int) -> None:
    for x in range(x0, x1):
        link(x, y, x + 1, y)


def line_v(x: int, y0: int, y1: int) -> None:
    for y in range(y0, y1):
        link(x, y, x, y + 1)


# --- layout -----------------------------------------------------------------
ring(2, 2, 21, 11)        # outer loop
line_h(6, 2, 21)          # upper horizontal spine
line_h(8, 2, 21)          # lower horizontal spine
line_v(11, 2, 11)         # central vertical spine
line_v(6, 2, 6)           # upper-left connector
line_v(17, 6, 11)         # right connector (spans both spines)
link(8, 2, 8, 1)          # dead-end spur (up)
link(8, 1, 8, 0)
link(15, 11, 15, 12)      # dead-end spur (down)
link(15, 12, 15, 13)

# preferred tile value per physical-edge set (turn / straight / simple switch / diamond)
PICK = {
    frozenset([0]): 128,
    frozenset([2]): 8192,
    frozenset([0, 1]): 72,
    frozenset([0, 2]): 32800,
    frozenset([0, 3]): 2064,
    frozenset([1, 2]): 16386,
    frozenset([1, 3]): 1025,
    frozenset([2, 3]): 4608,
    frozenset([0, 1, 2]): 49186,      # switch NR
    frozenset([0, 1, 3]): 3089,       # switch EL
    frozenset([0, 2, 3]): 37408,      # switch NL
    frozenset([1, 2, 3]): 17411,      # switch WL
    frozenset([0, 1, 2, 3]): 33825,   # diamond crossing
}

# hand-picked 4-way tiles to show off slips
OVERRIDE = {
    (11, 6): 33825,   # diamond crossing (rendered level-free below)
    (11, 8): 52275,   # double slip
    (17, 8): 38433,   # single slip
}

# --- validate reciprocity ---------------------------------------------------
for (x, y), dirs in cells.items():
    for d in dirs:
        nx, ny = x + DELTA[d][0], y + DELTA[d][1]
        assert OPP[d] in cells.get((nx, ny), set()), f"dangling track at {(x, y)} dir {d}"

# --- build grid -------------------------------------------------------------
grid = [[0] * W for _ in range(H)]
for (x, y), dirs in cells.items():
    v = OVERRIDE.get((x, y), PICK[frozenset(dirs)])
    assert T.is_valid(v), f"invalid tile {v} at {(x, y)}"
    grid[y][x] = v

map_obj = {
    "width": W,
    "height": H,
    "origin": [0, 0],
    "grid": grid,
    "cities": [[4, 2, 3], [18, 2, 7], [4, 11, 11], [18, 11, 15]],
    "stations": [[11, 4], [11, 10]],
    "level_free": [[11, 6, 0]],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(map_obj, indent=2), encoding="utf-8")
print("wrote", OUT, f"({W}x{H}, {sum(1 for row in grid for v in row if v)} rail cells)")
