"use strict";

// ctrl's Pugh engine as this package carries it (src/obs_html/vendor/pugh.js) decides ctrl's own
// test matrices as ctrl's tests assert (fixtures/pugh-vectors.json): the weighted totals, the
// ranking, the suggestion, the verdict and each runner-up's single-weight tie point.
const assert = require("node:assert/strict");
const path = require("node:path");
const {pathToFileURL} = require("node:url");

const root = path.resolve(__dirname, "..");
const vectors = require(path.join(__dirname, "fixtures", "pugh-vectors.json"));

(async () => {
  const engine = await import(pathToFileURL(path.join(root, "src", "obs_html", "vendor", "pugh.js")));
  assert.ok(vectors.matrices.length >= 3, "pugh-vectors.json: at least three of ctrl's matrices");
  for (const {name, matrix, expected} of vectors.matrices) {
    const result = engine.decide(matrix);
    assert.deepEqual(Object.fromEntries(result.candidates.map(c => [c.key, c.total])), expected.totals, `${name}: totals`);
    assert.deepEqual(result.ranking, expected.ranking, `${name}: ranking`);
    assert.equal(result.suggestion?.key ?? null, expected.suggestion, `${name}: suggestion`);
    assert.equal(result.sensitivity?.verdict ?? null, expected.verdict, `${name}: verdict`);
    const ties = Object.fromEntries((result.sensitivity?.all ?? []).map(x => [x.key, x.tie && {
      criterion: x.tie.criterion, to: x.tie.to, now: x.tie.now, reasonable: x.tie.reasonable}]));
    assert.deepEqual(ties, expected.ties, `${name}: tie points`);
  }
})().catch(error => { console.error(error); process.exit(1); });
