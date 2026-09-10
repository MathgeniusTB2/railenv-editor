"""Flatland rail transition-map catalogue shared by the web editor's tooling.

Each grid cell is a raw 16-bit bitmap (the value Flatland reads directly from
``GridTransitionMap.grid``). This module exposes the catalogue of valid cell
values and a membership check used by the tests and tools.

All values are taken directly from ``flatland.envs.grid.rail_env_grid`` so the
generated grids are guaranteed valid for ``RailEnv``. No Flatland import is
required at runtime.
"""

from __future__ import annotations

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


def is_valid(value: int) -> bool:
    """True if ``value`` is a recognized rail transition bitmap."""
    return value in VALUE_TO_NAME
