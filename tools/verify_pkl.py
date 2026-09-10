"""Verify a browser-generated .pkl loads in Flatland via RailEnvPersister.

Usage: .venv/bin/python tools/verify_pkl.py /tmp/test.mpk
"""
from __future__ import annotations

import sys

import numpy as np
from flatland.envs.persistence import RailEnvPersister


def main(path: str) -> int:
    env_dict = RailEnvPersister.load_env_dict(path)
    grid = np.asarray(env_dict["grid"], dtype=np.uint16)
    print("loaded env_dict: grid", grid.shape, "| agents", len(env_dict.get("agents", [])))
    if "malfunction" in env_dict and env_dict.get("malfunction") is not None:
        print("  (malfunction present)")

    # now restore it into a live RailEnv to be sure it's usable
    from flatland.envs.grid.rail_env_grid import RailEnvTransitions
    from flatland.envs.rail_env import RailEnv
    from flatland.envs.rail_generators import RailFromGridGen, RailGridTransitionMap
    from flatland.envs.observations import GlobalObsForRailEnv

    from flatland.envs.persistence import RailEnvPersister as P

    rm = RailGridTransitionMap(width=grid.shape[1], height=grid.shape[0], transitions=RailEnvTransitions())
    rm.grid = grid

    def lg(rail, n, h, ns, nr):
        from flatland.envs.timetable_utils import Line
        return Line(agent_waypoints={}, agent_speeds=[])

    def tt(a, dm, h, nr):
        class T:
            pass
        t = T(); t.max_episode_steps = 500; t.earliest_departures = []; t.latest_arrivals = []
        return t

    env = RailEnv(width=grid.shape[1], height=grid.shape[0], number_of_agents=0,
                  rail_generator=RailFromGridGen(rm), line_generator=lg, timetable_generator=tt,
                  obs_builder_object=GlobalObsForRailEnv())
    env.reset()
    P.set_full_state(env, env_dict)
    assert (env.rail.grid == grid).all(), "grid mismatch after restore"
    env.reset()
    print("OK: restored into RailEnv, grid matches, reset works")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/test.mpk"))
