"""Build a clean, connected demo network for the README screenshots.

Writes ``web/testmaps/demo.json`` (the editor's JSON map format). The layout is a
rectangular loop with a diamond crossing in the middle, four simple switches, a
dead-end spur, city/station markers and one level-free crossing.
"""
from __future__ import annotations

import json
from pathlib import Path

from railenv_editor.core import transitions as T

OUT = Path(__file__).resolve().parents[1] / "web" / "testmaps" / "demo.json"

W, H = 17, 11

# desired physical connections per cell, as a set of directions (N=0,E=1,S=2,W=3)
cells: dict[tuple[int, int], set[int]] = {}


def put(x: int, y: int, dirs: list[int]) -> None:
    cells[(x, y)] = set(dirs)


# outer loop
put(2, 2, [1, 2])
put(14, 2, [2, 3])
put(14, 8, [0, 3])
put(2, 8, [0, 1])
for x in range(3, 14):
    if x not in (8, 11):
        put(x, 2, [1, 3])
for x in range(3, 14):
    if x != 8:
        put(x, 8, [1, 3])
for y in (3, 4, 6, 7):
    put(2, y, [0, 2])
    put(14, y, [0, 2])
# T-junctions on the loop
put(2, 5, [0, 1, 2])
put(14, 5, [0, 2, 3])
put(8, 2, [1, 2, 3])
put(8, 8, [0, 1, 3])
# middle cross
put(8, 5, [0, 1, 2, 3])
for y in (3, 4, 6, 7):
    put(8, y, [0, 2])
for x in list(range(3, 8)) + list(range(9, 14)):
    put(x, 5, [1, 3])
# dead-end spur
put(11, 2, [0, 1, 3])
put(11, 1, [2])

# preferred tile value per physical-edge set (turn/straight/simple switch/diamond)
PICK = {
    frozenset([0]): 128,
    frozenset([2]): 8192,
    frozenset([0, 1]): 72,
    frozenset([0, 2]): 32800,
    frozenset([0, 3]): 2064,
    frozenset([1, 2]): 16386,
    frozenset([1, 3]): 1025,
    frozenset([2, 3]): 4608,
    frozenset([0, 1, 2]): 49186,  # switch NR
    frozenset([0, 1, 3]): 3089,   # switch EL
    frozenset([0, 2, 3]): 37408,  # switch NL
    frozenset([1, 2, 3]): 17411,  # switch WL
    frozenset([0, 1, 2, 3]): 33825,  # diamond crossing
}

grid = [[0] * W for _ in range(H)]
for (x, y), dirs in cells.items():
    v = PICK[frozenset(dirs)]
    assert T.is_valid(v), v
    grid[y][x] = v

map_obj = {
    "width": W,
    "height": H,
    "origin": [0, 0],
    "grid": grid,
    "cities": [[5, 2, 3], [11, 8, 7], [2, 6, 11]],
    "stations": [[8, 2], [8, 8]],
    "level_free": [[8, 5, 0]],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(map_obj, indent=2), encoding="utf-8")
print("wrote", OUT, f"({W}x{H})")
