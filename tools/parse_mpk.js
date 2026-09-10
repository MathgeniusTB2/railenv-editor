// Read a .mpk with the browser's dependency-free reader and print the result as
// JSON, so Python tests can exercise the web "Open" path on a file written by
// either the web exporter or the desktop app.
// Usage: node tools/parse_mpk.js <file.mpk>
const fs = require("fs");
const EnvPkl = require(process.cwd() + "/web/envpkl.js");

const file = process.argv[2];
if (!file) {
  console.error("usage: node tools/parse_mpk.js <file.mpk>");
  process.exit(2);
}
const parsed = EnvPkl.parseEnvMpk(fs.readFileSync(file));
process.stdout.write(JSON.stringify(parsed));
