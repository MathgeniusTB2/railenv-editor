"""Cache PILSVG-rendered pixmaps for every palette tile (and the city building)."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtGui import QPixmap, QTransform

from ..core.transitions import CITY, EMPTY, TILE_DEDUP, value_to_tile

TARGET_CELL = 56

_pixmaps: dict[str, QPixmap] | None = None
_rotated: dict[tuple[str, int], QPixmap] = {}
_value_icons: dict[int, QPixmap] = {}


def _need(c: int) -> float:
    return (TARGET_CELL * (c + 5) + c + 10) / c


def _renderer_scale(cols: int, rows: int) -> int:
    return int(max(_need(cols), _need(rows))) + 1


def _sheet_pix(values: list[int]) -> list[QPixmap]:
    from .canvas import PilsvgRenderer

    n = len(values)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    renderer = PilsvgRenderer(_renderer_scale(cols, rows))
    grid = np.zeros((rows, cols), dtype=np.uint16)
    for i, v in enumerate(values):
        grid[i // cols, i % cols] = v
    img, cell = renderer.render(grid)
    out = []
    for i in range(n):
        r, c = divmod(i, cols)
        out.append(QPixmap.fromImage(img.copy(c * cell, r * cell, cell, cell)))
    return out


def _single_pix(value: int, city: bool) -> QPixmap:
    from .canvas import PilsvgRenderer

    renderer = PilsvgRenderer(_renderer_scale(1, 1))
    grid = np.zeros((1, 1), dtype=np.uint16)
    grid[0, 0] = value
    img, cell = renderer.render(grid, {(0, 0)} if city else None)
    return QPixmap.fromImage(img.copy(0, 0, cell, cell))


def pixmaps() -> dict[str, QPixmap]:
    """Return {tile name -> native PILSVG pixmap}, cached on first use."""
    global _pixmaps
    if _pixmaps is not None:
        return _pixmaps
    rail = [(name, value) for name, value in TILE_DEDUP if name not in (CITY, EMPTY)]
    rail_pix = _sheet_pix([v for _, v in rail])
    out = {name: pm for (name, _v), pm in zip(rail, rail_pix, strict=True)}
    out[CITY] = _single_pix(0, True)
    out[EMPTY] = _single_pix(0, False)
    _pixmaps = out
    return out


def icon(name: str, rotation: int = 0) -> QPixmap:
    """Return the tile pixmap rotated by ``rotation`` (0/90/180/270), cached."""
    rotation %= 360
    base = pixmaps()[name]
    if rotation == 0:
        return base
    key = (name, rotation)
    if key not in _rotated:
        _rotated[key] = base.transformed(QTransform().rotate(rotation))
    return _rotated[key]


def value_icon(value: int) -> QPixmap | None:
    """Return a pilsvg pixmap for a raw cell value (cached by value)."""
    value = int(value)
    if value == 0:
        return None
    if value in _value_icons:
        return _value_icons[value]
    hit = value_to_tile(value)
    if hit is None:
        return None
    name, rotation = hit
    pm = icon(name, rotation)
    _value_icons[value] = pm
    return pm
