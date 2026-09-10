// Build a test map containing every valid Flatland tile (all 29 transitions:
// 9 base tiles x 4 rotations) plus an empty cell, city/station markers and
// level-free crossings. Writes:
//   - a JSON map the editor can open (Open button)
//   - a browser-written .pkl (pickle) and .mpk (native Flatland msgpack)
// Usage: node tools/make_every_tile_map.js [outdir]
const fs = require("fs");
const path = require("path");
const EnvPkl = require(process.cwd() + "/web/envpkl.js");

const outdir = process.argv[2] || "/tmp";
const seed = 0;

// bit math mirrored from web/index.html
const BLOCK = [12, 8, 4, 0];
const Bit = {
  exit(v, inc) { const o = []; for (let d = 0; d < 4; d++) if (v & (1 << (BLOCK[inc] + (3 - d)))) o.push(d); return o; },
  build(p) { let nv = 0; for (const [f, t] of p) nv |= 1 << ((3 - f) * 4 + (3 - t)); return nv; },
  rotate(v, deg) { const k = ((deg % 360) / 90) | 0; if (!k) return v; const p = []; for (let f = 0; f < 4; f++) for (const t of this.exit(v, f)) p.push([f, t]);
    return this.build(p.map(([f, t]) => [(f + k) % 4, (t + k) % 4])); },
};

// base palette values (from web/index.html TILES). The 9 base tiles, each rotated
// through 4 x 90deg, cover all 29 valid Flatland transitions (both handednesses of
// simple switch, all slips, and the diamond crossing).
const base = [
  ["vertical_straight", 32800],
  ["right_turn_from_south", 16386],
  ["simple_switch_north_left", 37408],
  ["simple_switch_north_right", 49186],
  ["symmetric_switch_from_south", 20994],
  ["single_slip_SW", 38433],
  ["double_slip_NW_SE", 52275],
  ["diamond_crossing", 33825],
  ["dead_end_from_south", 8192],
];

// one row per tile type; each column is a 90deg rotation -> every variant.
// A final all-empty row represents the empty tile.
const cols = 4;
const railRows = base.map((b) => Array.from({ length: cols }, (_, c) => Bit.rotate(b[1], c * 90)));
const grid = railRows.concat([Array.from({ length: cols }, () => 0)]);
const rows = grid.length;

for (const row of grid) for (const v of row) if (v < 0 || v > 65535) throw new Error("bad value " + v);

// city markers (x, y, building index) and station markers (x, y)
const cities = [[0, 0, 3], [1, 0, 7], [2, 0, 11], [3, 0, 18]];
const stations = [[0, rows - 1], [1, rows - 1], [2, rows - 1], [3, rows - 1]];
// level-free diamond crossings (absolute x, y, rotation degrees) — row 6 is the diamond row
const level_free = [[0, 6, 0], [2, 6, 90]];
const levelFreeLocal = level_free.map(([x, y]) => [y, x]); // (row, col)

const map = { width: cols, height: rows, origin: [0, 0], grid, cities, stations, level_free };
const jsonPath = path.join(outdir, "every_tile.json");
fs.writeFileSync(jsonPath, JSON.stringify(map, null, 2));

const pklPath = path.join(outdir, "every_tile.pkl");
const mpkPath = path.join(outdir, "every_tile.mpk");
const roundtripPath = path.join(outdir, "every_tile.roundtrip.json");
fs.writeFileSync(pklPath, Buffer.from(EnvPkl.buildEnvPkl(grid, seed, levelFreeLocal)));
const mpk = EnvPkl.buildEnvMpk(grid, seed, { origin: map.origin, cities, stations, level_free });
fs.writeFileSync(mpkPath, Buffer.from(mpk));
fs.writeFileSync(roundtripPath, JSON.stringify(EnvPkl.parseEnvMpk(mpk), null, 2));

console.log("tiles:  " + base.map(b => b[0]).join(", "));
console.log("wrote:  " + jsonPath);
console.log("wrote:  " + pklPath);
console.log("wrote:  " + mpkPath);
console.log("wrote:  " + roundtripPath);
console.log("grid " + rows + "x" + cols + " (" + (rows * cols) + " cells, every valid tile x4 rotations + empty row)");
