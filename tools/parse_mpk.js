// Read a .mpk with the browser's dependency-free reader and print the result as
// JSON, for inspecting env files from the command line.
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
