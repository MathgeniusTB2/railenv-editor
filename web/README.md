# RailEnv Editor (web)

A dependency-free, static web editor for Flatland rail environments that
reproduces the **exact PILSVG look** (flatland's real track + terrain sprites and
its deterministic placement logic), and can export a **Flatland-loadable env**.

## Run

Serve the folder (GitHub Pages also works — no build, no backend):

```bash
python -m http.server 8080     # then open http://localhost:8080
```

## Features (at parity with the desktop app)

- Paint (drag = straight line), **freehand erase** (drag clears every cell swept), **select (drag a marquee)** + **Copy / Paste / Delete** (S, Ctrl+C, Ctrl+V, Del) to duplicate or clear a block.
- Tiles: **0** station, **1-8** rail (straight, turn, switch, sym-switch, single/double slip, diamond, dead-end), **9** city; **R** rotate, **F** flip, **E** erase, **P** paint.
- **Move/pan** tool (M) + **middle-drag** pan + smooth **arrow-key** panning.
- **Sprite-ghost** hover preview of the tile you're about to place.
- **Inspector** panel shows the **hovered** cell and the selected cell (value + 16-bit bits + markers).
- **Auto-grow in all directions** (content preserved), **Trim to content**, W/H resize.
- **Open/Load** a saved JSON, **New** blank, **Undo/Redo**.
- **Markers**: **City (`9`)** and **Station (`0`)** are separate markers placed
  **on top of a cell** — they keep the rail and render over the track (like
  Flatland). Rail can be drawn on a marker cell; **Empty/Erase** clears rail +
  markers.
- **City building submenu**: the **▾** on the City tile opens a thumbnail grid of
  all building sprites; pick one and the City tool places **that** building. Each
  city remembers its own building (changing the pick only affects new
  placements). Copy/paste, undo, trim and load all preserve it.
- **Level-free diamond crossings** (over-/underpasses): the **▾** on the Diamond
  tile opens a dropdown — **Diamond** or **Level-free** (`L`). A level-free cell
  is a diamond crossing that two trains may share (one horizontal, one vertical);
  it renders with Flatland's `Gleis_Diamond_Crossing_Level_Free` sprite
  (pseudo-transition `666`). It is **rotatable** (`R`/`F`/rotation buttons) to
  choose the over/under orientation — the rotation is kept per cell in the editor
  meta (Flatland itself always draws the sprite in its one fixed orientation).
  Overwriting the cell with any other rail (or erasing) **auto-clears** the flag.
  Copy/paste, undo, trim and load preserve it.
- **Infinite panning**: no scrollbars — the canvas fills the view and pans without
  bounds via wheel, middle-drag, the **Move** tool (`M`), or arrow keys. **Cmd/Ctrl+wheel**
  zooms around the cursor. Drawing just off the grid (but on-screen) auto-grows it;
  dragging off the canvas edge pauses placement so the grid can't run away.

## Export / Open

A single format for everything: **`.mpk`** (Flatland's native MessagePack env
dict). The same file is what `RailEnvPersister.save(env, "*.mpk")` writes and
`RailEnvPersister.load_env_dict("network.mpk")` reads via `msgpack.unpackb`, so
Flatland/Python can load it directly. The editor can also **Open** its own
`.mpk` back (grid + city/station markers + canvas origin).

Editor-only state that Flatland does not model is stored under an extra
top-level `railenv_editor` key:

```
{ ...Flatland env_dict...,
  "railenv_editor": { "version": 1, "origin": [x,y],
                      "cities": [[ax,ay,buildingIdx], ...],
                      "stations": [[ax,ay], ...],
                      "level_free": [[ax,ay], ...] } }
```

Level-free crossings are also written to Flatland's **standard**
`level_free_positions` key (as local `[row, col]`), so Flatland's
`GridResourceMap` honours them on load. `set_full_state` reads only known keys,
so the extra `railenv_editor` key is ignored and the file stays a valid `RailEnv`.

Both directions are produced by `web/envpkl.js` (`buildEnvMpk` / `parseEnvMpk`)
with **no dependencies**, and verified loadable in Flatland. Legacy JSON project
files can still be opened; the legacy pickle writer (`buildEnvPkl`) is kept for
old-Flatland consumers.

> Note: `RailEnvPersister.load_env_dict` chooses pickle vs msgpack purely from the
> filename, and its msgpack fallback only catches `ValueError` (not
> `pickle.UnpicklingError`). A msgpack file named `.pkl` therefore hard-fails —
> which is why the format is always `.mpk` here.

## Test map

`web/testmaps/every_tile.json` and `web/testmaps/every_tile.mpk` contain **every
valid Flatland tile (all 29 transitions)** plus an empty cell, city/station
markers and **level-free crossings**; open either with **Open**.
Regenerate them (plus a reader round-trip dump) with:

```bash
node tools/make_every_tile_map.js web/testmaps   # writes every_tile.{json,mpk,roundtrip.json}
.venv/bin/python tools/verify_pkl.py web/testmaps/every_tile.mpk
```

`tests/test_web_export.py` runs this end-to-end and asserts the `.mpk` loads in
Flatland (every cell a valid transition), round-trips grid + markers through the
dependency-free reader, and interops with the desktop app both ways.

## Assets

Sprites are flatland's real PILSVG art, exported by:

```bash
../.venv/bin/python ../tools/export_pilsvg.py   # regenerates web/assets/*
```

Verify: `tools/verify_look.py` confirms the renderer matches flatland (~4/255 diff);
`tools/verify_pkl.py` confirms a browser-generated `.pkl` loads in Flatland
(`node tools/make_test_pkl.js /tmp/test.pkl && ..python ../tools/verify_pkl.py /tmp/test.pkl`).
