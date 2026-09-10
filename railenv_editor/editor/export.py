"""Export/import a GridModel as a Flatland environment.

The single interchange format is Flatland's native MessagePack ``.mpk`` env dict
(what ``RailEnvPersister.save(env, "*.mpk")`` writes). Editor-only state that
Flatland does not model (``origin``, city markers) rides along under a top-level
``"railenv_editor"`` key; ``RailEnvPersister.set_full_state`` reads only known
keys, so the same file stays loadable as a stock ``RailEnv``.

``to_pickled_env`` is kept for legacy consumers on old Flatland versions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..core.grid_model import GridModel

EDITOR_META_KEY = "railenv_editor"
EDITOR_META_VERSION = 1


def _editor_meta(model: GridModel) -> dict:
    """Editor-only state that a stock Flatland env dict does not carry."""
    return {
        "version": EDITOR_META_VERSION,
        "origin": [int(model.origin[0]), int(model.origin[1])],
        # Desktop has no per-city building sprite, so index 0 is the default.
        "cities": [[int(x), int(y), 0] for (x, y) in sorted(model.cities)],
        "stations": [],
    }


def _build_env(model: GridModel):
    """Build a live RailEnv from the model's grid (no agents)."""
    import flatland  # noqa: F401  (ensures flatland is importable)
    from flatland.envs.grid.rail_env_grid import RailEnvTransitions
    from flatland.envs.line_generators import Line
    from flatland.envs.rail_env import RailEnv
    from flatland.envs.rail_generators import RailFromGridGen, RailGridTransitionMap

    grid = np.asarray(model.cells, dtype=np.uint16)
    rail_map = RailGridTransitionMap(width=model.width, height=model.height, transitions=RailEnvTransitions())
    rail_map.grid = grid

    def line_gen(rail, num_agents, hints, num_resets, np_random):
        return Line(agent_waypoints={}, agent_speeds=[])

    def timetable(agents, distance_map, hints, np_random):
        class TT:
            pass

        t = TT()
        t.max_episode_steps = 500
        t.earliest_departures = []
        t.latest_arrivals = []
        return t

    env = RailEnv(
        width=model.width,
        height=model.height,
        number_of_agents=0,
        rail_generator=RailFromGridGen(rail_map),
        line_generator=line_gen,
        timetable_generator=timetable,
    )
    env.reset()
    return env


def _msgpack_safe(obj):
    """Recursively replace ``set``/``frozenset`` with lists (msgpack can't pack sets).

    ``RailEnvPersister.get_full_state`` returns an empty ``level_free_positions``
    set, which makes Flatland's own ``msgpack.packb`` raise; lists load back fine
    because ``GridResourceMap`` only does membership tests.
    """
    if isinstance(obj, dict):
        return {k: _msgpack_safe(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        return [_msgpack_safe(v) for v in sorted(obj, key=repr)]
    if isinstance(obj, list):
        return [_msgpack_safe(v) for v in obj]
    return obj


# Env-dict keys that survive a msgpack round-trip and that RailEnvPersister can
# rebuild via load_new. Flatland's get_full_state also emits a `malfunction`
# namedtuple, which msgpack turns into a bare tuple and then breaks load_new
# (FileMalfunctionGen reads `.malfunction_rate`); the editor has no malfunction,
# so keep only this portable, web-compatible subset.
_MPK_KEYS = (
    "grid",
    "agents",
    "max_episode_steps",
    "elapsed_steps",
    "random_seed",
    "seed_history",
    "dev_pred_dict",
    "dev_obs_dict",
    "dones",
    "effects_generator",
    "level_free_positions",
)


def to_msgpack_env(model: GridModel, path) -> str:
    """Persist the model as Flatland's native MessagePack ``.mpk`` env dict.

    Writes the grid (rail bitmaps) as an environment with no agents, plus an
    ``railenv_editor`` extension carrying origin/city markers. Flatland reloads
    it with ``RailEnvPersister.load_env_dict(path)`` / ``load_new(path)``.
    """
    import msgpack
    from flatland.envs.persistence import RailEnvPersister

    full = RailEnvPersister.get_full_state(_build_env(model))
    env_dict = {k: full[k] for k in _MPK_KEYS if k in full}
    env_dict[EDITOR_META_KEY] = _editor_meta(model)
    Path(path).write_bytes(msgpack.packb(_msgpack_safe(env_dict)))
    return str(path)


def from_msgpack_env(path) -> GridModel:
    """Load a ``.mpk`` env (Flatland or editor-written) back into a GridModel."""
    import msgpack
    import msgpack_numpy  # noqa: F401
    from flatland.envs.persistence import RailEnvPersister  # noqa: F401  (patches msgpack_numpy)

    msgpack_numpy.patch()
    env_dict = msgpack.unpackb(Path(path).read_bytes(), use_list=False, raw=False)
    grid = np.asarray(env_dict["grid"], dtype=np.uint16)
    meta = env_dict.get(EDITOR_META_KEY) or {}
    origin = tuple(int(v) for v in meta.get("origin", (0, 0)))
    model = GridModel(width=grid.shape[1], height=grid.shape[0], cells=grid, origin=origin)
    model.cities = {(int(c[0]), int(c[1])) for c in meta.get("cities", [])}
    return model


def to_pickled_env(model: GridModel, path) -> str:
    """Legacy: persist a ready-to-load RailEnv via Flatland's ``RailEnvPersister``.

    Writes the grid (rail bitmaps + cities) as an environment with no agents.
    Returns the path string.
    """
    from flatland.envs.persistence import RailEnvPersister

    RailEnvPersister.save(_build_env(model), str(path))
    return str(path)
