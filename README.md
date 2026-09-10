# RailEnv Editor

A cross-platform (Windows + macOS) desktop GUI for visually designing **Flatland**
railway environments (`RailEnv`). You paint a rail grid, place agent start/target
points, get live connectivity validation, and export to a runnable Flatland
environment (`.mpk`).

## Install (uv is the default)

This repo is managed with [uv](https://docs.astral.sh/uv/). Install uv, then:

```bash
uv sync --all-extras        # create .venv + install everything (incl. flatland)
uv run python -m railenv_editor.app.main   # launch the editor
```

If you only need the editor itself (no Flatland validation/msgpack export):

```bash
uv sync
uv run python -m railenv_editor.app.main
```

Everyday commands:

```bash
uv add <package>            # add a dependency (updates pyproject.toml + uv.lock)
uv run pytest tests/ -q     # run tests in the managed venv
uv run ruff check .         # lint
```

Optional — install Flatland for real transition-map validation, the **PILSVG**
backdrop, and `RailEnvPersister` export:

```bash
uv add flatland-rl
```

## Usage

- **Tools:** `P` paint · `E` erase · `S` select · `M` move/pan · `V` paste.
- **Tiles:** shown in the bar at the bottom of the window (native PILSVG icons);
  pick them by clicking or with `0`–`9` (city = `9`, empty is last and click-only).
  The bar order is: straight, right turn, left switch, right switch, symmetric
  switch, dead-end, single slip, double slip, diamond, city, empty.
- **Rotate:** `R` / `Shift+R` rotate the current tile (the rotation controls only
  appear for rotatable rail tiles, not for Empty or City).
- **Drag** with the paint/erase tool draws a straight rail line between press and
  release; the on-screen preview is the tile's real PILSVG render.
- **Auto-expand:** dragging past an edge grows the grid in any direction to fit
  what you drew; use **Trim to content** (toolbar) to crop back to the content.
- Middle-mouse drag pans; the mouse wheel zooms.

## Export

The grid is rendered in the **Flatland PILSVG** style (the same `RenderTool`
backend used elsewhere). Save/Open/Export all use a single format: Flatland's
native **MessagePack `.mpk`** env dict, which Flatland reloads with
`RailEnvPersister.load_env_dict(path)` (or `load_new(path)`). Editor-only state
(canvas origin, city markers) rides along under an extra top-level
`railenv_editor` key that Flatland ignores, so the same file is both a project
file and a loadable `RailEnv`. The legacy pickle exporter is still available as
`railenv_editor.editor.export.to_pickled_env`.

## Build binaries

```bash
uv add --dev pyinstaller
uv run pyinstaller packaging/railenv_editor.spec
```

GitHub Actions builds macOS `.app` and Windows `.exe` in `packaging/`.
