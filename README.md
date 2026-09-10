<div align="center">

# RailEnv Editor

**A visual editor for [Flatland](https://github.com/flatland-association/flatland-rl) railway environments (`RailEnv`).**

Paint a rail grid, place cities and stations, get live connectivity feedback, and export a
loadable Flatland environment — from a desktop app or entirely in the browser.

[![CI](https://github.com/MathgeniusTB2/railenv-editor/actions/workflows/ci.yml/badge.svg)](https://github.com/MathgeniusTB2/railenv-editor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Flatland](https://img.shields.io/badge/flatland--rl-4.x-orange.svg)](https://github.com/flatland-association/flatland-rl)
[![Live demo](https://img.shields.io/badge/live%20demo-GitHub%20Pages-2f6fb3.svg)](https://mathgeniustb2.github.io/railenv-editor/)

[**Live web editor**](https://mathgeniustb2.github.io/railenv-editor/) ·
[Report a bug](https://github.com/MathgeniusTB2/railenv-editor/issues) ·
[Discussions](https://github.com/MathgeniusTB2/railenv-editor/discussions)

<img src="docs/hero.png" alt="RailEnv Editor web app showing a rail network" width="820">

</div>

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Export](#export)
- [Project layout](#project-layout)
- [Development](#development)
- [License](#license)

## Features

- **Two front ends, one file format.** A cross-platform **PySide6 desktop app** and a
  **dependency-free web editor** (no build step, no libraries) that open and save the same files.
- **Paint a network** with every valid Flatland tile: straights, turns, simple/symmetric
  switches, single/double slips, dead-end, and the **diamond crossing** (plus a level-free,
  over/under variant).
- **Cities and stations** as markers on top of the track, with selectable city buildings.
- **Live validation** against Flatland's real transition maps.
- **True-to-Flatland rendering** — the same **PILSVG** sprites and placement logic Flatland uses.
- **Infinite canvas** that grows in any direction as you draw; **Trim to content** to crop back.
- **Select / copy / paste / delete**, undo/redo, and drag-to-draw straight segments.
- **Single export**: Flatland's native MessagePack `.mpk`, loadable with `RailEnvPersister`.

## Screenshots

| Desktop / web editor | Every valid tile |
| :--: | :--: |
| <img src="docs/hero.png" alt="Editor with a demo network" width="440"> | <img src="docs/every-tile.png" alt="Every Flatland tile" width="150"> |

## Quick start

The desktop app uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras                          # create .venv + install everything (incl. flatland)
uv run python -m railenv_editor.app.main      # launch the desktop editor
```

If you only need the editor (no Flatland validation / `.mpk` export), `uv sync` is enough.

**Web editor:** open the [live demo](https://mathgeniustb2.github.io/railenv-editor/), or serve
the folder locally:

```bash
python -m http.server 8080 --directory web    # then open http://localhost:8080
```

## Usage

**Tools:** `P` paint · `E` erase · `S` select · `M` move/pan · `V` paste · `R` rotate · `F` flip.

**Tiles** are shown in a bar (native PILSVG icons) and can be picked by click or hotkey. The web
editor uses `0` station, `1`–`8` rail, `9` city, `L` level-free diamond. The desktop bar order is:
straight, right turn, left switch, right switch, symmetric switch, dead-end, single slip, double
slip, diamond, city, empty.

- **Drag** with paint/erase to draw a straight line between press and release.
- **Auto-expand:** dragging past an edge grows the grid in any direction.
- Middle-mouse drag pans; the mouse wheel zooms (`Cmd`/`Ctrl` + scroll in the browser).
- Drag a **marquee** with the select tool, then `Ctrl+C` / `Ctrl+V` / `Del`.

## Export

Save, open, and export all use a single format: Flatland's native **MessagePack `.mpk`** env dict,
which Flatland reloads with `RailEnvPersister.load_env_dict(path)` (or `load_new(path)`).

Editor-only state that Flatland does not model (canvas origin, city/station markers, level-free
crossings) rides along under an extra top-level `railenv_editor` key. `RailEnvPersister.set_full_state`
reads only known keys, so the same file stays a stock, loadable `RailEnv`:

```python
from flatland.envs.persistence import RailEnvPersister

env, env_dict = RailEnvPersister.load_new("network.mpk")
env.reset()
```

The legacy pickle exporter is still available as
`railenv_editor.editor.export.to_pickled_env`.

## Project layout

```
railenv_editor/        desktop app (PySide6)
  core/                grid model + Flatland transition catalogue
  editor/              canvas, palette, inspector, .mpk export/import
  app/                 window wiring and entrypoint
web/                   dependency-free web editor (no build step)
  envpkl.js            dependency-free pickle + msgpack reader/writer
  testmaps/            demo and every-tile maps
tools/                 sprite export, test-map generators, screenshots
tests/                 pytest suite
packaging/             PyInstaller spec
```

## Development

```bash
uv sync --all-extras
uv run pytest tests/ -q                 # tests
uv run ruff check .                     # lint
uv run --all-extras python tools/screenshot_web.py   # regenerate docs/ screenshots
```

Build desktop binaries with PyInstaller:

```bash
uv add --dev pyinstaller
uv run pyinstaller packaging/railenv_editor.spec
```

GitHub Actions runs CI on every push/PR and builds macOS `.app` / Windows `.exe` on version tags.

## License

[MIT](LICENSE) © 2026 MathgeniusTB2.

Rail sprites and rendering are derived from [Flatland](https://github.com/flatland-association/flatland-rl)
(MIT, © SBB AG), which this project targets.
