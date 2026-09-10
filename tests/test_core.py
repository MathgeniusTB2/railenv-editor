"""Unit tests for the non-GUI core logic (transitions, model, export)."""

from pathlib import Path

from railenv_editor.core.grid_model import GridModel
from railenv_editor.core.transitions import Direction, exit_dirs, mirror, name_for_value, palette, value_for
from railenv_editor.editor import export as ex


def test_transition_values_are_in_flatland_vocabulary():
    for name, _rot in palette():
        v = value_for((name, 0))
        assert v in (0, 32800, 37408, 33825, 38433, 52275, 20994, 8192, 16386, 4608, 49186)
        assert name_for_value(v) != f"unknown({v})"


def test_exit_dirs_vertical_straight():
    assert exit_dirs(32800, Direction.NORTH) == [Direction.NORTH]
    assert exit_dirs(32800, Direction.SOUTH) == [Direction.SOUTH]
    assert exit_dirs(32800, Direction.EAST) == []


def test_exit_dirs_horizontal_straight():
    v = value_for(("vertical_straight", 90))
    assert v == 1025
    assert exit_dirs(v, Direction.EAST) == [Direction.EAST]
    assert exit_dirs(v, Direction.WEST) == [Direction.WEST]


def test_mirror():
    assert mirror(Direction.NORTH) == Direction.SOUTH
    assert mirror(Direction.EAST) == Direction.WEST


def test_rotation_match_flatland():
    assert value_for(("right_turn_from_south", 0)) == 16386
    assert value_for(("right_turn_from_south", 90)) == 4608
    assert value_for(("right_turn_from_south", 180)) == 2064
    assert value_for(("right_turn_from_south", 270)) == 72


def test_model_return_trip():
    m = GridModel(width=3, height=2)
    v = value_for(("vertical_straight", 90))
    m.set(0, 0, v)
    m.set(1, 0, v)
    data = m.to_dict()
    m2 = GridModel.from_dict(data)
    assert m2.width == 3 and m2.height == 2
    assert m2.get(0, 0) == v


def test_save_load(tmp_path: Path):
    m = GridModel(width=4, height=4)
    m.set(1, 1, value_for(("diamond_crossing", 0)))
    p = tmp_path / "net.railproj"
    m.save(p)
    m2 = GridModel.load(p)
    assert m2.get(1, 1) == 33825


def test_resize_fills_empty():
    m = GridModel(width=2, height=2)
    m.set(0, 0, 1025)
    m.resize(4, 4)
    assert m.get(0, 0) == 1025
    assert m.get(3, 3) == 0


def test_export_msgpack_env_roundtrip(flatland_available, tmp_path: Path):
    if not flatland_available:
        return
    import numpy as np
    from flatland.envs.persistence import RailEnvPersister

    m = GridModel(width=3, height=1)
    v = value_for(("vertical_straight", 90))
    for x in range(3):
        m.set(x, 0, v)
    m.origin = (-2, 5)
    m.cities = {(-1, 5)}
    p = tmp_path / "env.mpk"
    ex.to_msgpack_env(m, p)
    assert Path(p).stat().st_size > 0

    # stock Flatland loads it and ignores the editor extension key
    d = RailEnvPersister.load_env_dict(p)
    assert len(d["agents"]) == 0
    assert np.asarray(d["grid"]).tolist() == m.cells.tolist()
    assert ex.EDITOR_META_KEY in d

    # the editor reopens its own state
    m2 = ex.from_msgpack_env(p)
    assert (m2.width, m2.height) == (3, 1)
    assert m2.origin == (-2, 5)
    assert m2.cities == {(-1, 5)}
    assert m2.cells.tolist() == m.cells.tolist()


def test_every_tile_export_open_roundtrip(flatland_available, tmp_path: Path):
    """A grid with every valid Flatland tile exports, loads in Flatland, and reopens."""
    if not flatland_available:
        return
    import numpy as np
    from flatland.envs.grid.rail_env_grid import RailEnvTransitions
    from flatland.envs.persistence import RailEnvPersister

    from railenv_editor.core import transitions as T

    tiles = sorted(v for v in T.VALUE_TO_NAME if v != 0)
    assert 33825 in tiles  # diamond crossing
    m = GridModel(width=len(tiles), height=2)
    for x, v in enumerate(tiles):
        m.set(x, 0, v)
    m.set_city(0, 1, True)
    m.origin = (7, -3)
    p = tmp_path / "every_tile.mpk"
    ex.to_msgpack_env(m, p)
    assert Path(p).stat().st_size > 0

    # Flatland loads it; every cell is a valid transition and all 29 are present
    tr = RailEnvTransitions()
    env, env_dict = RailEnvPersister.load_new(p)
    env.reset()
    grid = np.asarray(env_dict["grid"])
    assert grid.shape == (2, len(tiles))
    assert all(tr.is_valid(int(v)) for v in grid.flatten())
    assert {int(v) for v in grid.flatten() if v} == set(tiles)

    # the editor reopens grid + origin + cities
    m2 = ex.from_msgpack_env(p)
    assert m2.cells.tolist() == m.cells.tolist()
    assert m2.origin == (7, -3)
    assert m2.cities == {(0, 1)}


def test_export_pickled_env_legacy(flatland_available, tmp_path: Path):
    if not flatland_available:
        return
    from flatland.envs.persistence import RailEnvPersister

    m = GridModel(width=3, height=1)
    v = value_for(("vertical_straight", 90))
    for x in range(3):
        m.set(x, 0, v)
    p = tmp_path / "env.pkl"
    ex.to_pickled_env(m, p)
    assert Path(p).stat().st_size > 0
    d = RailEnvPersister.load_env_dict(p)
    assert len(d["agents"]) == 0


def test_drag_segment_cells_horizontal():
    from railenv_editor.editor.canvas import RailGraphicsScene

    assert RailGraphicsScene._segment_cells((2, 4), (6, 4)) == [(2, 4), (3, 4), (4, 4), (5, 4), (6, 4)]
    assert RailGraphicsScene._segment_cells((6, 4), (2, 4)) == [(6, 4), (5, 4), (4, 4), (3, 4), (2, 4)]


def test_drag_segment_cells_vertical():
    from railenv_editor.editor.canvas import RailGraphicsScene

    assert RailGraphicsScene._segment_cells((5, 1), (5, 4)) == [(5, 1), (5, 2), (5, 3), (5, 4)]


def test_marquee_cells_in_rect():
    from railenv_editor.editor.canvas import RailGraphicsScene

    cells = RailGraphicsScene._cells_in_rect((2, 2), (4, 3))
    assert set(cells) == {(2, 2), (3, 2), (4, 2), (2, 3), (3, 3), (4, 3)}


def test_tile_dedup_covers_catalogue():
    from railenv_editor.core import transitions as T

    assert len(T.TILE_DEDUP) == 10
    assert T.TILE_DEDUP[-1][0] == T.EMPTY  # empty is last
    assert T.TILE_DEDUP[-2][0] == T.CITY   # city second-to-last

    rail_values = [v for n, v in T.TILE_DEDUP if n not in (T.CITY, T.EMPTY)]

    def reachable(start):
        seen = {start}
        frontier = [start]
        while frontier:
            v = frontier.pop()
            for nxt in (T.rotate(v, 90), T.flip_value(v), T.flip_value(v, "ns")):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return seen

    covered = set().union(*(reachable(v) for v in rail_values)) - {0}
    assert covered == set(v for v in T.VALUE_TO_NAME if v != 0)


def test_flip_is_closed_and_involution():
    from railenv_editor.core import transitions as T

    for v in T.VALUE_TO_NAME:
        f = T.flip_value(v)
        assert f in T.VALUE_TO_NAME or f == 0, f"{v} -> {f}"
        assert T.flip_value(f) == int(v), "flip must be an involution"
    assert T.flip_value(16386) == 4608
    assert T.flip_value(37408) == 49186
    assert T.flip_value(33825) == 33825  # diamond


def test_grow_to_include_all_directions():
    from railenv_editor.core.grid_model import GridModel

    m = GridModel(width=4, height=4)
    m.grow_to_include([(2, 2)])
    assert m.origin == (0, 0)
    m.grow_to_include([(-3, 5), (7, -2)])
    assert m.in_bounds(-3, 5) and m.in_bounds(7, -2)
    assert m.origin == (-3, -2)
    m.set(2, 2, 1025)
    assert m.get(2, 2) == 1025


def test_city_rail_mutually_exclusive():
    from railenv_editor.core.grid_model import GridModel

    m = GridModel(width=3, height=3)
    m.set(1, 1, 1025)
    m.set_city(1, 1, True)
    assert m.get(1, 1) == 0
    assert (1, 1) in m.cities
    m.set(1, 1, 32800)
    assert m.get(1, 1) == 32800
    assert (1, 1) not in m.cities


def test_shrink_to_content_and_normalized_grid():
    from railenv_editor.core.grid_model import GridModel

    m = GridModel(width=8, height=8)
    m.grow_to_include([(3, 4)])
    m.set(3, 4, 1025)
    m.set(5, 6, 32800)
    m.shrink_to_content()
    assert (m.width, m.height) == (3, 3)
    assert m.get(3, 4) == 1025
    assert m.get(5, 6) == 32800


def test_diff_cells():
    import numpy as np

    from railenv_editor.editor.canvas import _diff_cells

    a = np.zeros((2, 2), dtype=np.uint16)
    b = np.zeros((2, 2), dtype=np.uint16)
    b[0, 1] = 1025
    b[1, 0] = 32800
    assert _diff_cells(a, b) == {(1, 0), (0, 1)}
    assert _diff_cells(a, a) == set()


def test_open_sides_and_segments():
    from railenv_editor.editor.canvas import _cell_segments, _open_sides

    assert _open_sides(0) == []
    assert _open_sides(1025) == [1, 3]
    segs = _cell_segments(2, 3, 40, 1025)
    assert len(segs) == 1
    (x0, y0), (x1, y1) = segs[0]
    assert x0 == 2 * 40 + 40 and x1 == 2 * 40


def test_exit_dirs_matches_flatland(flatland_available):
    if not flatland_available:
        return
    from flatland.envs.grid.rail_env_grid import RailEnvTransitions
    from flatland.envs.rail_generators import RailGridTransitionMap

    trans = RailEnvTransitions()
    for name, _rot in palette():
        v = value_for((name, 0))
        mp = RailGridTransitionMap(width=3, height=3, transitions=trans)
        mp.grid[1, 1] = int(v)
        for o in range(4):
            lib = [d for d in range(4) if mp.get_transition(((1, 1), o), d) > 0]
            assert lib == exit_dirs(v, o), f"{name} incoming {o}"
