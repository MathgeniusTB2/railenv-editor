"""In-memory rail environment model: an origin-based grid + cities.

The grid is a numpy ``uint16`` array of shape ``(height, width)`` equal to
Flatland's ``RailGridTransitionMap.grid``. Absolute cell coordinates ``(x, y)``
are mapped to the local array via ``origin`` (the absolute coordinate of the
local cell ``(0, 0)``). This lets the grid grow in all four directions
(including negative coordinates) while the local array stays a normal 0-based
grid for Flatland. ``cities`` is a set of absolute city-marker cells (drawn as
buildings) that are mutually exclusive with rail.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class GridModel:
    width: int = 20
    height: int = 20
    cells: np.ndarray = field(default=None, repr=False)
    origin: tuple[int, int] = (0, 0)  # absolute (x, y) of local cell (0,0)
    cities: set[tuple[int, int]] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.cells is None:
            self.cells = np.zeros((self.height, self.width), dtype=np.uint16)
        else:
            self.cells = np.asarray(self.cells, dtype=np.uint16)
        self.origin = (int(self.origin[0]), int(self.origin[1]))

    # ------------------------------------------------------------------ coords
    def _local(self, x: int, y: int) -> tuple[int, int]:
        return (y - self.origin[1], x - self.origin[0])

    def home(self, local: tuple[int, int]) -> tuple[int, int]:
        """Local (row, col) -> absolute (x, y)."""
        row, col = local
        return (self.origin[0] + col, self.origin[1] + row)

    def in_bounds(self, x: int, y: int) -> bool:
        r, c = self._local(x, y)
        return 0 <= c < self.width and 0 <= r < self.height

    def get(self, x: int, y: int) -> int:
        r, c = self._local(x, y)
        return int(self.cells[r, c])

    def set(self, x: int, y: int, value: int) -> None:
        r, c = self._local(x, y)
        self.cells[r, c] = int(value)
        if int(value) != 0:
            self.cities.discard((int(x), int(y)))

    def clear_cell(self, x: int, y: int) -> None:
        self.set(x, y, 0)

    def for_each_cell(self) -> Iterator[tuple[int, int, int]]:
        for r in range(self.height):
            for c in range(self.width):
                yield self.home((r, c)) + (int(self.cells[r, c]),)

    # ------------------------------------------------------------------ growth
    def grow_to_include(self, points: Iterable[tuple[int, int]]) -> bool:
        """Grow (in any direction) until every absolute point is inside the grid.

        Returns True if the grid changed.
        """
        pts = [(int(p[0]), int(p[1])) for p in points]
        if not pts or all(self.in_bounds(x, y) for x, y in pts):
            return False
        minx = min(self.origin[0], min(x for x, _ in pts))
        miny = min(self.origin[1], min(y for _, y in pts))
        maxx = max(self.origin[0] + self.width - 1, max(x for x, _ in pts))
        maxy = max(self.origin[1] + self.height - 1, max(y for _, y in pts))
        return self._set_region(minx, miny, maxx, maxy)

    def _set_region(self, minx: int, miny: int, maxx: int, maxy: int) -> bool:
        w = int(maxx - minx + 1)
        h = int(maxy - miny + 1)
        if w <= 0 or h <= 0:
            return False
        if (minx == self.origin[0] and miny == self.origin[1] and w == self.width and h == self.height):
            return False
        new = np.zeros((h, w), dtype=np.uint16)
        # absolute overlap of old and new regions
        ax0 = max(minx, self.origin[0])
        ax1 = min(maxx, self.origin[0] + self.width - 1)
        ay0 = max(miny, self.origin[1])
        ay1 = min(maxy, self.origin[1] + self.height - 1)
        if ax0 <= ax1 and ay0 <= ay1:
            sr0 = ay0 - self.origin[1]
            sr1 = ay1 - self.origin[1]
            sc0 = ax0 - self.origin[0]
            sc1 = ax1 - self.origin[0]
            dr0 = ay0 - miny
            dr1 = ay1 - miny
            dc0 = ax0 - minx
            dc1 = ax1 - minx
            new[dr0:dr1 + 1, dc0:dc1 + 1] = self.cells[sr0:sr1 + 1, sc0:sc1 + 1]
        self.cells = new
        self.origin = (minx, miny)
        self.width = w
        self.height = h
        return True

    def content_bbox(self) -> tuple[int, int, int, int] | None:
        """Absolute bounding box (minx, miny, maxx, maxy) of drawn content."""
        xs, ys = [], []
        for (x, y, v) in self.for_each_cell():
            if v != 0:
                xs.append(x)
                ys.append(y)
        for (x, y) in self.cities:
            xs.append(x)
            ys.append(y)
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def shrink_to_content(self) -> bool:
        """Crop the grid to the bounding box of drawn content."""
        bbox = self.content_bbox()
        if bbox is None:
            return False
        return self._set_region(bbox[0], bbox[1], bbox[2], bbox[3])

    def resize(self, width: int, height: int) -> None:
        """Set explicit size, anchored at the current origin (top-left)."""
        new = np.zeros((height, width), dtype=np.uint16)
        h = min(height, self.height)
        w = min(width, self.width)
        new[:h, :w] = self.cells[:h, :w]
        self.cells = new
        self.width = width
        self.height = height

    # ------------------------------------------------- cities / rail exclusivity
    def set_city(self, x: int, y: int, value: bool) -> None:
        if value:
            self.cells[self._local(x, y)] = 0  # city clears rail
            self.cities.add((int(x), int(y)))
        else:
            self.cities.discard((int(x), int(y)))

    # ------------------------------------------------------------------ IO
    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "origin": list(self.origin),
            "grid": np.asarray(self.cells, dtype=int).tolist(),
            "cities": [list(c) for c in sorted(self.cities)],
        }

    @classmethod
    def from_dict(cls, data: dict) -> GridModel:
        cells = np.asarray(data["grid"], dtype=np.uint16)
        model = cls(
            width=data["width"],
            height=data["height"],
            cells=cells,
            origin=tuple(data.get("origin", (0, 0))),
        )
        model.cities = {tuple(int(v) for v in c) for c in data.get("cities", [])}
        return model

    def save(self, path: Path) -> None:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> GridModel:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
