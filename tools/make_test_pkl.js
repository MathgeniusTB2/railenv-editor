// Generate a test .pkl (env dict) using the browser writer (runs in Node).
// Usage: node tools/make_test_pkl.js [out.pkl] [seed] [rows] [cols]
const fs = require("fs");
const EnvPkl = require(process.cwd() + "/web/envpkl.js");
const out = process.argv[2] || "/tmp/test.pkl";
const seed = Number(process.argv[3] || 1234);
const rows = Number(process.argv[4] || 3);
const cols = Number(process.argv[5] || 4);
const grid = Array.from({ length: rows }, (_, r) => Array.from({ length: cols }, (_, c) =>
  (r === 1 ? 1025 : 0))); // horizontal straight along row 1
fs.writeFileSync(out, Buffer.from(EnvPkl.buildEnvPkl(grid, seed)));
console.log("wrote", out, "seed", seed, "grid", rows + "x" + cols);
