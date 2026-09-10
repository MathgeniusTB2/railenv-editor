/* Emit a Flatland-loadable environment file as a Python **pickle** (protocol 2),
 * equivalent to `RailEnvPersister.save(env, "*.pkl")` (which uses pickle.dumps).
 * Includes the numpy uint16 array via the exact numpy.core.multiarray reduce
 * twiddling, so flatland's load_env_dict / set_full_state rebuild the RailEnv.
 *
 * UMD: browser <script> -> window.EnvPkl ; Node -> module.exports.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.EnvPkl = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // pickle.dumps(np.zeros((2,3), uint16), protocol=2) — the fixed array template.
  var TEMPLATE_HEX =
    "8002636e756d70792e636f72652e6d756c746961727261790a5f7265636f6e7374727563740a7100636e756d7079" +
    "0a6e6461727261790a71014b00857102635f636f646563730a656e636f64650a710358010000006271045806" +
    "0000006c6174696e317105867106527107877108527109284b014b024b0386710a636e756d70790a64747970" +
    "650a710b58020000007532710c898887710d52710e284b0358010000003c710f4e4e4e4affffffff4affffff" +
    "ff4b0074711062896803580c00000000000000000000000000000071116805867112527113747114622e";

  function hexBytes(h) {
    var out = new Uint8Array(h.length >> 1);
    for (var i = 0; i < out.length; i++) out[i] = parseInt(h.substr(i * 2, 2), 16);
    return out;
  }
  function findSeq(a, seq) {
    outer: for (var i = 0; i + seq.length <= a.length; i++) {
      for (var j = 0; j < seq.length; j++) if (a[i + j] !== seq[j]) continue outer;
      return i;
    }
    return -1;
  }
  function u32le(v) { return new Uint8Array([v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255]); }
  function concat(parts) {
    var n = 0, i; for (i = 0; i < parts.length; i++) n += parts[i].length;
    var out = new Uint8Array(n), o = 0;
    for (i = 0; i < parts.length; i++) { out.set(parts[i], o); o += parts[i].length; }
    return out;
  }

  // pickle stores numpy's raw buffer as latin1 text -> UTF-8; bytes >= 0x80 expand.
  function utf8Latin1(raw) {
    var out = [];
    for (var i = 0; i < raw.length; i++) {
      var b = raw[i];
      if (b < 0x80) out.push(b);
      else { out.push(0xc0 | (b >> 6)); out.push(0x80 | (b & 0x3f)); }
    }
    return Uint8Array.from(out);
  }

  function numpyUint16(rows, cols, dataLE) {
    var t = hexBytes(TEMPLATE_HEX);
    var inner = t.slice(2, t.length - 1);        // drop PROTO (80 02) and STOP (2e)
    var si = findSeq(inner, [0x28, 0x4b, 0x01]); // MARK 1  (rows at +4, cols at +6)
    inner[si + 4] = rows & 0xff;
    inner[si + 6] = cols & 0xff;
    var di = findSeq(inner, [0x68, 0x03, 0x58]);
    var oldLen = inner[di + 3] | (inner[di + 4] << 8) | (inner[di + 5] << 16) | (inner[di + 6] << 24);
    var enc = utf8Latin1(dataLE);
    return concat([inner.slice(0, di + 3), u32le(enc.length), enc, inner.slice(di + 7 + oldLen)]);
  }

  function binUnicode(s) {
    var b = new Uint8Array(5 + s.length);
    b[0] = 0x58; b[1] = s.length & 0xff; b[2] = (s.length >> 8) & 0xff; b[3] = 0; b[4] = 0;
    for (var i = 0; i < s.length; i++) b[5 + i] = s.charCodeAt(i) & 0xff;
    return b;
  }
  function binInt(v) {
    if (v >= 0 && v < 256) return new Uint8Array([0x4b, v]);
    var u = v >>> 0; return new Uint8Array([0x4a, u & 255, (u >>> 8) & 255, (u >>> 16) & 255, (u >>> 24) & 255]);
  }

  var EMPTY_LIST = new Uint8Array([0x5d]);
  var EMPTY_DICT = new Uint8Array([0x7d]);
  var TUPLE1 = new Uint8Array([0x85]);
  var TUPLE2 = new Uint8Array([0x86]);
  var REDUCE = new Uint8Array([0x52]);
  var NONE = new Uint8Array([0x4e]);
  var SETITEM = new Uint8Array([0x73]);
  var APPEND = new Uint8Array([0x61]);

  // pickle protocol-2 set of (a, b) integer tuples: GLOBAL set, (list of TUPLE2), REDUCE.
  function pyPairSet(pairs) {
    var parts = [new Uint8Array([0x63]), asciiBytes("__builtin__"), new Uint8Array([0x0a]),
                 asciiBytes("set"), new Uint8Array([0x0a]), EMPTY_LIST];
    for (var i = 0; i < pairs.length; i++) parts.push(binInt(pairs[i][0]), binInt(pairs[i][1]), TUPLE2, APPEND);
    parts.push(TUPLE1, REDUCE);
    return concat(parts);
  }

  // ---- minimal MessagePack writer (for Flatland's native .mpk format) ----
  function asciiBytes(s) { var b = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i) & 0xff; return b; }
  function mpInt(v) {
    if (v >= 0) {
      if (v < 128) return Uint8Array.of(v);
      if (v < 256) return Uint8Array.of(0xcc, v);
      if (v < 65536) return Uint8Array.of(0xcd, (v >> 8) & 255, v & 255);
      if (v < 4294967296) return Uint8Array.of(0xce, (v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255);
      return Uint8Array.of(0xcf, 0, 0, 0, 0, (v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255);
    }
    if (v >= -32) return Uint8Array.of(0xe0 | (v + 32));
    if (v >= -128) return Uint8Array.of(0xd0, v & 255);
    if (v >= -32768) return Uint8Array.of(0xd1, (v >> 8) & 255, v & 255);
    return Uint8Array.of(0xd2, (v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255);
  }
  function mpStr(s) { var b = asciiBytes(s); if (b.length <= 31) return concat([Uint8Array.of(0xa0 | b.length), b]); if (b.length <= 255) return concat([Uint8Array.of(0xd9, b.length), b]); return concat([Uint8Array.of(0xda, (b.length >> 8) & 255, b.length & 255), b]); }
  function mpBin(b) { if (b.length <= 255) return concat([Uint8Array.of(0xc4, b.length), b]); if (b.length <= 65535) return concat([Uint8Array.of(0xc5, (b.length >> 8) & 255, b.length & 255), b]); return concat([Uint8Array.of(0xc6, (b.length >>> 24) & 255, (b.length >>> 16) & 255, (b.length >>> 8) & 255, b.length & 255), b]); }
  function mpArr(n) { return n <= 15 ? Uint8Array.of(0x90 | n) : concat([Uint8Array.of(0xdc, (n >> 8) & 255, n & 255)]); }
  function mpMap(n) { return n <= 15 ? Uint8Array.of(0x80 | n) : concat([Uint8Array.of(0xde, (n >> 8) & 255, n & 255)]); }
  var MP_TRUE = Uint8Array.of(0xc3), MP_NIL = Uint8Array.of(0xc0);

  function gridBytes(grid) {
    var rows = grid.length, cols = grid[0].length;
    var data = new Uint8Array(rows * cols * 2), o = 0;
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
      var v = grid[r][c] >>> 0;
      data[o++] = v & 0xff; data[o++] = (v >>> 8) & 0xff;
    }
    return data;
  }

  // Flatland's native msgpack env dict, matching msgpack_numpy's ndarray encoding
  // ({b'nd':True, b'type':'<u2', b'kind':b'', b'shape':(rows,cols), b'data':bytes}).
  // `meta` (optional) carries editor-only state under a top-level "railenv_editor"
  // key: {origin:[x,y], stations:[[x,y],...], level_free:[[x,y],...]}. The absolute
  // level-free cells are also written to Flatland's standard "level_free_positions"
  // (local [row,col]) so the level-free behaviour is honoured on load.
  function buildEnvMpk(grid, seed, meta) {
    var rows = grid.length, cols = grid[0].length;
    var origin = (meta && meta.origin) ? meta.origin : [0, 0];
    var lfAbs = (meta && meta.level_free) ? meta.level_free : [];
    var lfLocal = lfAbs.map(function (p) { return [(p[1] | 0) - (origin[1] | 0), (p[0] | 0) - (origin[0] | 0)]; });
    var parts = [mpMap(meta ? 12 : 11)];
    parts.push(mpStr("grid"), mpMap(5));
    parts.push(mpBin(asciiBytes("nd")), MP_TRUE);
    parts.push(mpBin(asciiBytes("type")), mpStr("<u2"));
    parts.push(mpBin(asciiBytes("kind")), mpBin(new Uint8Array(0)));
    parts.push(mpBin(asciiBytes("shape")), mpArr(2), mpInt(rows), mpInt(cols));
    parts.push(mpBin(asciiBytes("data")), mpBin(gridBytes(grid)));
    parts.push(mpStr("agents"), mpArr(0));
    parts.push(mpStr("max_episode_steps"), mpInt(500));
    parts.push(mpStr("elapsed_steps"), mpInt(0));
    parts.push(mpStr("random_seed"), mpInt(seed));
    parts.push(mpStr("seed_history"), mpArr(1), mpInt(seed));
    parts.push(mpStr("dev_pred_dict"), mpMap(0));
    parts.push(mpStr("dev_obs_dict"), mpMap(0));
    parts.push(mpStr("dones"), mpMap(0));
    parts.push(mpStr("effects_generator"), MP_NIL);
    parts.push(mpStr("level_free_positions"), mpArr(lfLocal.length));
    for (var li = 0; li < lfLocal.length; li++) parts.push(mpArr(2), mpInt(lfLocal[li][0]), mpInt(lfLocal[li][1]));
    if (meta) {
      var stations = meta.stations || [];
      parts.push(mpStr("railenv_editor"), mpMap(4));
      parts.push(mpStr("version"), mpInt(1));
      parts.push(mpStr("origin"), mpArr(2), mpInt(origin[0] | 0), mpInt(origin[1] | 0));
      parts.push(mpStr("stations"), mpArr(stations.length));
      for (var si = 0; si < stations.length; si++) {
        parts.push(mpArr(2), mpInt(stations[si][0] | 0), mpInt(stations[si][1] | 0));
      }
      parts.push(mpStr("level_free"), mpArr(lfAbs.length));
      for (var fi = 0; fi < lfAbs.length; fi++) {
        parts.push(mpArr(3), mpInt(lfAbs[fi][0] | 0), mpInt(lfAbs[fi][1] | 0), mpInt((lfAbs[fi][2] | 0) || 0));
      }
    }
    return concat(parts);
  }

  // ---- minimal MessagePack reader (dependency-free counterpart to the writer) ----
  function bytesToLatin1(b) { var s = ""; for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return s; }

  function ndarrayToGrid(nd) {
    if (!nd) return null;
    if (Array.isArray(nd)) return nd.map(function (row) { return row.slice(); });
    if (nd.nd !== true) return null;
    var shape = nd.shape.map(Number), rows = shape[0], cols = shape[1];
    var data = nd.data;
    var dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
    var type = (typeof nd.type === "string") ? nd.type : bytesToLatin1(nd.type);
    var big = type.charAt(0) === ">";
    var out = [];
    for (var r = 0; r < rows; r++) {
      var row = new Array(cols);
      for (var c = 0; c < cols; c++) row[c] = dv.getUint16((r * cols + c) * 2, !big);
      out.push(row);
    }
    return out;
  }

  // Parse a Flatland/editor .mpk back to {grid, origin, stations, seed}.
  function parseEnvMpk(input) {
    var buf = (input instanceof Uint8Array) ? input : new Uint8Array(input);
    var pos = 0;
    function need(n) { if (pos + n > buf.length) throw new Error("truncated msgpack"); }
    function u8() { need(1); return buf[pos++]; }
    function u16() { need(2); var v = (buf[pos] << 8) | buf[pos + 1]; pos += 2; return v; }
    function u32() { need(4); var v = buf[pos] * 0x1000000 + (buf[pos + 1] << 16) + (buf[pos + 2] << 8) + buf[pos + 3]; pos += 4; return v >>> 0; }
    function i8() { var v = u8(); return v < 128 ? v : v - 256; }
    function i16() { var v = u16(); return v < 32768 ? v : v - 65536; }
    function i32() { var v = u32(); return v < 0x80000000 ? v : v - 0x100000000; }
    function i64() { var hi = u32(), lo = u32(); return hi * 0x100000000 + lo; }
    function f32() { need(4); var v = new DataView(buf.buffer, buf.byteOffset + pos, 4).getFloat32(0); pos += 4; return v; }
    function f64() { need(8); var v = new DataView(buf.buffer, buf.byteOffset + pos, 8).getFloat64(0); pos += 8; return v; }
    function bytes(n) { need(n); var b = buf.subarray(pos, pos + n); pos += n; return b; }
    function str(n) { return bytesToLatin1(bytes(n)); }
    function arr(n) { var a = []; for (var i = 0; i < n; i++) a.push(read()); return a; }
    function map(n) { var o = {}; for (var i = 0; i < n; i++) { var k = read(); o[(k instanceof Uint8Array) ? bytesToLatin1(k) : String(k)] = read(); } return o; }
    function ext(n) { u8(); return bytes(n); }
    function read() {
      var c = u8();
      if (c < 0x80) return c;
      if (c >= 0xe0) return c - 256;
      if (c >= 0xa0 && c <= 0xbf) return str(c & 0x1f);
      if (c >= 0x90 && c <= 0x9f) return arr(c & 0x0f);
      if (c >= 0x80 && c <= 0x8f) return map(c & 0x0f);
      switch (c) {
        case 0xc0: return null;
        case 0xc2: return false;
        case 0xc3: return true;
        case 0xc4: return bytes(u8());
        case 0xc5: return bytes(u16());
        case 0xc6: return bytes(u32());
        case 0xc7: return ext(u8());
        case 0xc8: return ext(u16());
        case 0xc9: return ext(u32());
        case 0xca: return f32();
        case 0xcb: return f64();
        case 0xcc: return u8();
        case 0xcd: return u16();
        case 0xce: return u32();
        case 0xcf: return i64();
        case 0xd0: return i8();
        case 0xd1: return i16();
        case 0xd2: return i32();
        case 0xd3: return i64();
        case 0xd4: return ext(1);
        case 0xd5: return ext(2);
        case 0xd6: return ext(4);
        case 0xd7: return ext(8);
        case 0xd8: return ext(16);
        case 0xd9: return str(u8());
        case 0xda: return str(u16());
        case 0xdb: return str(u32());
        case 0xdc: return arr(u16());
        case 0xdd: return arr(u32());
        case 0xde: return map(u16());
        case 0xdf: return map(u32());
      }
      throw new Error("msgpack: unknown byte 0x" + c.toString(16));
    }
    var root = read();
    var meta = root.railenv_editor || {};
    var origin = (meta.origin || [0, 0]).map(Number);
    var levelFree = (meta.level_free || []).map(function (c) { return [Number(c[0]), Number(c[1]), Number(c[2] == null ? 0 : c[2])]; });
    if (!levelFree.length && root.level_free_positions) {
      // fall back to Flatland's standard key (local [row,col]) -> absolute [x,y]
      levelFree = root.level_free_positions.map(function (c) { return [origin[0] + Number(c[1]), origin[1] + Number(c[0]), 0]; });
    }
    return {
      grid: ndarrayToGrid(root.grid),
      origin: origin,
      stations: (meta.stations || []).map(function (c) { return [Number(c[0]), Number(c[1])]; }),
      level_free: levelFree,
      seed: root.random_seed == null ? 0 : Number(root.random_seed),
    };
  }

  // grid: rows x cols of uint16 ints. seed: integer.
  // levelFreeLocal: optional [[row,col],...] (Flatland's level_free_positions).
  function buildEnvPkl(grid, seed, levelFreeLocal) {
    var rows = grid.length, cols = grid[0].length;
    var data = new Uint8Array(rows * cols * 2), o = 0;
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
      var v = grid[r][c] >>> 0;
      data[o++] = v & 0xff; data[o++] = (v >>> 8) & 0xff; // little-endian uint16
    }
    var arrayVal = numpyUint16(rows, cols, data);
    var kv = [
      ["grid", arrayVal],
      ["agents", EMPTY_LIST],
      ["max_episode_steps", binInt(500)],
      ["elapsed_steps", binInt(0)],
      ["random_seed", binInt(seed)],
      ["seed_history", concat([EMPTY_LIST, binInt(seed), APPEND])],
      ["dev_pred_dict", EMPTY_DICT],
      ["dev_obs_dict", EMPTY_DICT],
      ["dones", EMPTY_DICT],
      ["effects_generator", NONE],
      ["level_free_positions", pyPairSet(levelFreeLocal || [])],
    ];
    var parts = [new Uint8Array([0x80, 0x02]), EMPTY_DICT];
    for (var i = 0; i < kv.length; i++) parts.push(binUnicode(kv[i][0]), kv[i][1], SETITEM);
    parts.push(new Uint8Array([0x2e]));
    return concat(parts);
  }

  return { buildEnvPkl: buildEnvPkl, buildEnvMpk: buildEnvMpk, parseEnvMpk: parseEnvMpk };
});
