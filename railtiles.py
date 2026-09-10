"""Flatland rail transition-map catalogue shared by the web editor's tooling.

Each grid cell is a raw 16-bit bitmap (the value Flatland reads directly from
``GridTransitionMap.grid``). This module provides the tile palette (base cell
types + clockwise rotations) and helpers to decode a cell back into a
human-readable name. It mirrors the bit math in ``web/index.html``.

All values are taken directly from ``flatland.envs.grid.rail_env_grid`` so the
generated grids are guaranteed valid for ``RailEnv``. No Flatland import is
required at runtime.
"""

from __future__ import annotations

from enum import IntEnum

# Number of bits in a valid rail cell transition map.
RE_BITS = 16


class Direction(IntEnum):
    """Cardinal directions used for agents and for the inspector UI."""

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


# A single cell type is identified by (base_value, rotation). Rotations are
# clock-wise in degrees. The rotate table is pre-computed from Flatland's own
# fast_grid4_rotate_transition so it is exact even without Flatland installed.
# Values are kept intentionally as the *base* enum value (rotation=0).

# name -> "canonical" base value repeated up to 4x due to symmetry.
_BASE_TILES: dict[str, int] = {
    "empty": 0,
    "vertical_straight": 32800,
    "simple_switch_north_left": 37408,
    "diamond_crossing": 33825,
    "single_slip_SW": 38433,
    "double_slip_NW_SE": 52275,
    "symmetric_switch_from_south": 20994,
    "dead_end_from_south": 8192,
    "right_turn_from_south": 16386,
    "right_turn_from_west": 4608,
    "simple_switch_north_right": 49186,
}

# rotation (deg) -> index into the rotate row.
_ROT_TO_IDX = {0: 0, 90: 1, 180: 2, 270: 3}

# base value -> row of 4 rotated values in (0, 90, 180, 270) order.
_ROT_ROWS: dict[int, list[int]] = {
    0: [0, 0, 0, 0],
    32800: [32800, 1025, 32800, 1025],          # vertical / horizontal straight
    37408: [37408, 3089, 32872, 17411],          # simple switch (left variants)
    33825: [33825, 33825, 33825, 33825],         # diamond crossing
    38433: [38433, 35889, 33897, 50211],         # single slips
    52275: [52275, 38505, 52275, 38505],         # double slips
    20994: [20994, 6672, 2136, 16458],           # symmetric switch
    8192: [8192, 256, 128, 4],                   # dead ends
    16386: [16386, 4608, 2064, 72],              # right turns
    4608: [4608, 2064, 72, 16386],               # right turns (offset)
    49186: [49186, 5633, 34864, 1097],           # simple switch (right variants)
}

# All valid 16-bit values -> short name (for the inspector).
VALUE_TO_NAME: dict[int, str] = {
    0: "empty",
    32800: "straight (N-S)",
    1025: "straight (E-W)",
    37408: "switch NL",
    3089: "switch EL",
    32872: "switch SL",
    17411: "switch WL",
    33825: "diamond crossing",
    38433: "slip SW",
    35889: "slip NW",
    33897: "slip NE",
    50211: "slip SE",
    52275: "dbl slip NW-SE",
    38505: "dbl slip NE-SW",
    20994: "symmetric switch (S)",
    6672: "symmetric switch (W)",
    2136: "symmetric switch (N)",
    16458: "symmetric switch (E)",
    8192: "dead-end (S)",
    256: "dead-end (W)",
    128: "dead-end (N)",
    4: "dead-end (E)",
    16386: "right turn (S)",
    4608: "right turn (W)",
    2064: "right turn (N)",
    72: "right turn (E)",
    49186: "switch NR",
    5633: "switch ER",
    34864: "switch SR",
    1097: "switch WR",
}

Tile = tuple[str, int]  # (base name, rotation)


def rotate(value: int, rotation: int) -> int:
    """Return ``value`` rotated clock-wise by ``rotation`` degrees.

    Rotates the cell's transitions directly (no re-basing), so it is exact for
    any value, including ones shared across orientation tables.
    """
    k = (int(rotation) % 360) // 90
    value = int(value)
    if k == 0:
        return value
    nv = 0
    for f in range(4):
        for t in exit_dirs(value, f):
            nf = (f + k) % 4
            nt = (t + k) % 4
            nv |= 1 << ((3 - nf) * 4 + (3 - nt))
    return nv


def value_for(tile: Tile) -> int:
    """Compute the 16-bit value for a ``(name, rotation)`` tile."""
    name, rotation = tile
    base = _BASE_TILES[name]
    return rotate(base, rotation)


def name_for_value(value: int) -> str:
    """Human-readable name for a raw cell value."""
    return VALUE_TO_NAME.get(value, f"unknown({value})")


def is_valid(value: int) -> bool:
    """True if ``value`` is a recognized rail transition bitmap."""
    return value in VALUE_TO_NAME


def palette() -> list[Tile]:
    """The ordered tiles shown in the editor palette (base orientation)."""
    return [(name, 0) for name in _BASE_TILES]


def empty_tile() -> Tile:
    return ("empty", 0)


# Palette tile set, deduped by rotation. Every value in Flatland's catalogue
# (RailEnvTransitionsEnum) is covered by one of these orbit representatives;
# `R` rotates a tile through the other members of its orbit. Order matters:
# digits 0-9 map to the first ten entries; "empty" is last and click-only.
CITY = "city"
EMPTY = "empty"

# Palette tile set (deduped by rotation/handedness). Digits: 0 = empty (last),
# 1..9 = the rail tiles in order, then city. `R` rotates 90°; `F` mirrors (flips
# the handedness of turns/switches). Both stay within Flatland's valid set.
TILE_DEDUP: list[tuple[str, int]] = [
    ("vertical_straight", 32800),          # 1 straight
    ("right_turn_from_south", 16386),      # 2 simple turn (F flips handedness)
    ("simple_switch_north_left", 37408),   # 3 simple switch (F flips handedness)
    ("symmetric_switch_from_south", 20994),# 4 symmetrical switch
    ("single_slip_SW", 38433),             # 5 single slip
    ("double_slip_NW_SE", 52275),          # 6 double slip
    ("diamond_crossing", 33825),           # 7 diamond crossing
    ("dead_end_from_south", 8192),         # 8 dead-end
    (CITY, 0),                             # 9 city (building)
    (EMPTY, 0),                            # 0 empty (last)
]

# Names that are rotatable (i.e. more than one meaningful orientation).
TILE_ROTATABLE: set[str] = {name for name, _ in TILE_DEDUP if name not in (CITY, EMPTY)}

# Human-readable label for a tile name.
TILE_LABELS = {
    "vertical_straight": "Straight",
    "right_turn_from_south": "Simple turn",
    "simple_switch_north_left": "Simple switch",
    "symmetric_switch_from_south": "Symmetrical switch",
    "single_slip_SW": "Single slip",
    "double_slip_NW_SE": "Double slip",
    "diamond_crossing": "Diamond crossing",
    "dead_end_from_south": "Dead-end",
    CITY: "City",
    EMPTY: "Empty",
}


def is_rotatable(name: str) -> bool:
    return name in TILE_ROTATABLE


def is_city(name: str) -> bool:
    return name == CITY


def tile_value_by_name() -> dict[str, int]:
    return {name: value for name, value in TILE_DEDUP}


# Hotkey digits: 0 = empty (displayed last), 1..9 = the first nine rail tiles.
def _hotkeys() -> dict[int, tuple[str, int]]:
    keys: dict[int, tuple[str, int]] = {0: (EMPTY, 0)}
    for i, (name, value) in enumerate(TILE_DEDUP):
        if i < 9:
            keys[i + 1] = (name, value)
    return keys


HOTKEY_TO_TILE: dict[int, tuple[str, int]] = _hotkeys()
TILE_HOTKEY: dict[str, str] = {name: str(digit) for digit, (name, _v) in HOTKEY_TO_TILE.items()}


def value_to_tile(value: int) -> tuple[str, int] | None:
    """Map a 16-bit cell value to its palette (tile name, rotation)."""
    value = int(value)
    if value == 0:
        return None
    for name, base in TILE_DEDUP:
        if name in (CITY, EMPTY):
            continue
        for rot in (0, 90, 180, 270):
            if rotate(base, rot) == value:
                return (name, rot)
    return None


def flip_value(value: int, axis: str = "ew") -> int:
    """Mirror a cell's transitions (default E<->W): toggles turn/switch handedness.

    Closed on Flatland's valid catalogue, so the result always renders in pilsvg.
    ``axis`` may be "ew" (swap E/W) or "ns" (swap N/S).
    """
    value = int(value)
    swap = {1: 3, 3: 1} if axis == "ew" else {0: 2, 2: 0}
    nv = 0
    for f in range(4):
        for t in exit_dirs(value, f):
            ff = swap.get(f, f)
            tt = swap.get(t, t)
            nv |= 1 << ((3 - ff) * 4 + (3 - tt))
    return nv


def rotation_orbits(values: list[int]) -> list[set[int]]:
    """Group a list of values into rotation-orbits (each closed under rotate())."""
    orbits: list[set[int]] = []
    covered: set[int] = set()
    for v in values:
        if v in covered:
            continue
        orbit = {rotate(v, r) for r in (0, 90, 180, 270)}
        covered |= orbit
        orbits.append(orbit)
    return orbits


# --- connection helpers (validated against flatland's get_transition) ------
# 16-bit layout: 4 blocks of 4 bits for facing {N,E,S,W}. Each block holds the
# allowed movements in [N,E,S,W] order, N being the block's MSB.

# group offset (facing) -> bit offset of the block's MSB.
_BLOCK = {Direction.NORTH: 12, Direction.EAST: 8, Direction.SOUTH: 4, Direction.WEST: 0}


def _bit(value: int, facing: int, moving: int) -> bool:
    return bool(value & (1 << (_BLOCK[Direction(facing)] + (3 - Direction(moving)))))


def mirror(direction: int) -> int:
    """Return the opposite direction (incoming == outgoing reversed)."""
    return (Direction(direction) + 2) % 4


def exit_dirs(value: int, incoming: int) -> list[int]:
    """Directions a train can continue in after entering a cell from `incoming`.

    Verified to match ``flatland.envs.grid.rail_env_grid`` for every transition.
    """
    if value == 0:
        return []
    return [d for d in range(4) if _bit(value, incoming, d)]


# (x, y) grid delta per direction.
DIR_DELTA = {
    Direction.NORTH: (0, -1),
    Direction.EAST: (1, 0),
    Direction.SOUTH: (0, 1),
    Direction.WEST: (-1, 0),
}


def neighbor(cell: tuple[int, int], direction: int) -> tuple[int, int]:
    dx, dy = DIR_DELTA[Direction(direction)]
    return (cell[0] + dx, cell[1] + dy)
