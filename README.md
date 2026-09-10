<div align="center">

# RailEnv Editor

**A dependency-free web editor for [Flatland](https://github.com/flatland-association/flatland-rl) railway environments (`RailEnv`).**

Paint a rail grid, place cities and stations, and export a loadable Flatland environment —
entirely in the browser, with no build step and no libraries.

[![CI](https://github.com/MathgeniusTB2/railenv-editor/actions/workflows/ci.yml/badge.svg)](https://github.com/MathgeniusTB2/railenv-editor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![No build step](https://img.shields.io/badge/build-none%20%E2%80%94%20static%20files-brightgreen.svg)](web/)
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

- **Zero dependencies, zero build.** A single static page (`web/`) — no framework, no bundler,
  no backend. Serve the folder or drop it on any static host.
- **Paint a network** with every valid Flatland tile: straights, turns, simple/symmetric
  switches, single/double slips, dead-end, and the **diamond crossing** (plus a level-free,
  over/under variant).
- **Cities and stations** as markers on top of the track, with selectable city buildings.
- **True-to-Flatland rendering** — the same **PILSVG** sprites and placement logic Flatland uses.
- **Infinite canvas** that pans without bounds and grows in any direction as you draw;
  **Trim to content** to crop back.
- **Select / copy / paste / delete**, undo/redo, and drag-to-draw straight segments.
- **Single export**: Flatland's native MessagePack `.mpk`, loadable with `RailEnvPersister`.

## Screenshots

| Web editor | Every valid tile |
| :--: | :--: |
| <img src="docs/hero.png" alt="Editor with a demo network" width="440"> | <img src="docs/every-tile.png" alt="Every Flatland tile" width="150"> |

## Quick start

Open the [live demo](https://mathgeniustb2.github.io/railenv-editor/), or serve the folder locally:

```bash
python -m http.server 8080 --directory web    # then open http://localhost:8080
```

That's it — the app is pure HTML/CSS/JS and needs no install. To run the validation
tests/tooling you'll need Python and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras
```

## Usage

**Tools:** `P` paint · `E` erase · `S` select · `M` move/pan · `V` paste · `R` rotate · `F` flip.

**Tiles** are shown in a bar (native PILSVG icons) and can be picked by click or hotkey:
`0` station, `1`–`8` rail, `9` city, `L` level-free diamond.

- **Drag** with paint/erase to draw a straight line between press and release.
- **Auto-expand:** drawing just off the grid grows it in any direction.
- Pan with the wheel, middle-drag, the **Move** tool (`M`) or arrow keys; `Cmd`/`Ctrl` + scroll zooms.
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

## Project layout

```
web/                   the editor (dependency-free, no build step)
  index.html           the app
  envpkl.js            dependency-free pickle + msgpack reader/writer
  assets/              Flatland PILSVG sprites + manifest
  testmaps/            demo and every-tile maps
railtiles.py           shared Flatland tile catalogue (used by tests/tools)
tools/                 sprite export, test-map generators, screenshots, look-parity check
tests/                 pytest suite validating the exports against flatland-rl
docs/                  README screenshots
```

## Development

```bash
uv sync --all-extras
uv run pytest tests/ -q                 # validate the browser exports against flatland-rl
uv run ruff check .                     # lint
uv run --all-extras python tools/screenshot_web.py    # regenerate docs/ screenshots
```

CI runs lint + tests on every push/PR, and the web app is deployed to GitHub Pages from `main`.

## License

[MIT](LICENSE) © 2026 MathgeniusTB2.

Rail sprites and rendering are derived from [Flatland](https://github.com/flatland-association/flatland-rl)
(MIT, © SBB AG), which this project targets.
