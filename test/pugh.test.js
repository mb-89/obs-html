"use strict";

// ctrl's Pugh engine as this package carries it (src/obs_html/vendor/pugh.js) decides ctrl's own
// test matrices as ctrl's tests assert (fixtures/pugh-vectors.json): the weighted totals, the
// ranking, the suggestion, the verdict and each runner-up's single-weight tie point. The option
// card shows an option's label only where it says more than the short name (pugh-figure.js).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
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
  // The figure's script as the page loads it; it needs no page but the document it listens on.
  const page = {document: {addEventListener: () => {}}};
  vm.runInNewContext(fs.readFileSync(path.join(root, "src", "obs_html", "pugh-figure.js"), "utf8"), page);
  for (const [short, label, adds] of [
    ["Two lines", "Keep two lines", false], ["Artifact", "Answered artifact", false],
    ["Comment export", "Comment export", false], ["lines", "Keep two lines.", false],
    ["", "A page of the team wiki", true], ["HTML", "Answered artifact", true], ["two", "Keep twofold", true],
  ]) assert.equal(page.obsPugh.labelAdds(short, label), adds, `labelAdds(${short}, ${label})`);
})().catch(error => { console.error(error); process.exit(1); });
