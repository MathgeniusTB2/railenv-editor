"""Verify the browser exporters (web/envpkl.js) produce Flatland-loadable envs.

Runs the Node generator, then loads the native msgpack (.mpk) output (and the
legacy pickle) through Flatland's ``RailEnvPersister``, checks the grid
round-trips exactly, and exercises the dependency-free reader.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import railtiles as T

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "make_every_tile_map.js"

ALL_TILES = {v for v in T.VALUE_TO_NAME if v != 0}


def _flatland():
    return pytest.importorskip("flatland")


def _generate(tmp_path: Path) -> None:
    subprocess.run(["node", str(GENERATOR), str(tmp_path)], cwd=ROOT, check=True,
                   capture_output=True, text=True)


def test_every_tile_map_has_every_valid_tile(tmp_path: Path):
    """The generated fixture covers all 29 valid Flatland transitions + empty."""
    if shutil.which("node") is None:
        pytest.skip("node not available")
    _generate(tmp_path)
    data = json.loads((tmp_path / "every_tile.json").read_text())
    assert data["width"] == 4
    values = {v for row in data["grid"] for v in row if v}
    assert values == ALL_TILES
    assert 33825 in values  # diamond crossing


@pytest.mark.parametrize("ext", ["pkl", "mpk"])
def test_web_export_loads_in_flatland(flatland_available, tmp_path: Path, ext: str):
    if not flatland_available:
        pytest.skip("flatland not available")
    if shutil.which("node") is None:
        pytest.skip("node not available")
    _flatland()
    from flatland.envs.persistence import RailEnvPersister

    _generate(tmp_path)
    expected = json.loads((tmp_path / "every_tile.json").read_text())

    env_dict = RailEnvPersister.load_env_dict(tmp_path / f"every_tile.{ext}")
    grid = env_dict["grid"]
    assert grid.shape == (expected["height"], expected["width"])
    assert grid.tolist() == expected["grid"]
    assert len(env_dict["agents"]) == 0
    # level-free crossings survive (local (row, col))
    lf = set(map(tuple, env_dict["level_free_positions"]))
    assert lf == {(c[1], c[0]) for c in expected["level_free"]}


def test_every_tile_mpk_loads_as_railenv(flatland_available, tmp_path: Path):
    """The every-tile .mpk restores a live RailEnv whose grid holds every tile."""
    if not flatland_available:
        pytest.skip("flatland not available")
    if shutil.which("node") is None:
        pytest.skip("node not available")
    from flatland.envs.grid.rail_env_grid import RailEnvTransitions
    from flatland.envs.persistence import RailEnvPersister

    _generate(tmp_path)
    env, env_dict = RailEnvPersister.load_new(tmp_path / "every_tile.mpk")
    env.reset()

    expected = json.loads((tmp_path / "every_tile.json").read_text())
    assert (env.width, env.height) == (expected["width"], expected["height"])

    tr = RailEnvTransitions()
    grid = env_dict["grid"]
    assert all(tr.is_valid(int(v)) for v in grid.flatten())
    assert {int(v) for v in grid.flatten() if v} == ALL_TILES


def test_web_mpk_roundtrips_editor_state(tmp_path: Path):
    """The browser .mpk writer/reader round-trips grid + city/station/level-free markers."""
    if shutil.which("node") is None:
        pytest.skip("node not available")

    _generate(tmp_path)
    expected = json.loads((tmp_path / "every_tile.json").read_text())
    got = json.loads((tmp_path / "every_tile.roundtrip.json").read_text())

    assert got["grid"] == expected["grid"]
    assert got["origin"] == expected["origin"]
    assert sorted(got["cities"]) == sorted(expected["cities"])
    assert sorted(got["stations"]) == sorted(expected["stations"])
    assert sorted(got["level_free"]) == sorted(expected["level_free"])
