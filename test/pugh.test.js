"use strict";

// ctrl's Pugh engine as this package carries it (src/obs_html/vendor/pugh.js) decides ctrl's own
// test matrices as ctrl's tests assert (fixtures/pugh-vectors.json): the weighted totals, the
// ranking, the suggestion, the verdict and each runner-up's single-weight tie point. The option
// card shows an option's label only where it says more than the short name (pugh-figure.js).
// The figure decides an existing deck's fences, obs's example deck (spec/examples/bless-deck), the
// same way every time: no clock, and the seed moves only the draws (capabilities/pugh-decisions,
// The rules).
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
  const page = {document: {addEventListener: () => {}}, obsPughEngine: engine, structuredClone};
  vm.runInNewContext(fs.readFileSync(path.join(root, "src", "obs_html", "pugh-figure.js"), "utf8"), page);
  for (const [short, label, adds] of [
    ["Two lines", "Keep two lines", false], ["Artifact", "Answered artifact", false],
    ["Comment export", "Comment export", false], ["lines", "Keep two lines.", false],
    ["", "A page of the team wiki", true], [null, "A page of the team wiki", true], ["HTML", "Answered artifact", true], ["two", "Keep twofold", true],
  ]) assert.equal(page.obsPugh.labelAdds(short, label), adds, `labelAdds(${short}, ${label})`);

  const yaml = require(path.join(root, "src", "obs_html", "vendor", "js-yaml.min.js"));
  const deck = path.resolve(root, "..", "..", "spec", "examples", "bless-deck");
  const fence = note => yaml.load(fs.readFileSync(path.join(deck, note), "utf8").match(/```pugh\n([\s\S]*?)\n```/)[1]);
  const decided = spec => {
    const {result} = page.obsPugh.decide(spec);
    const s = result.sensitivity;
    return {suggestion: result.suggestion.key, totals: result.candidates.map(c => [c.key, c.total, c.fits]),
      verdict: s.verdict, share: s.share, ties: s.runnersUp.map(x => [x.key, x.tie && [x.tie.criterion, x.tie.to, x.tie.reasonable]])};
  };
  for (const [note, suggestion, verdict] of [["swipe.md", "outside", "holds"], ["record.md", "html", "holds"]]) {
    const matrix = fence(note), spec = {matrix, shortNames: matrix.candidates.map(() => null)};
    const first = decided(spec), again = decided(structuredClone(spec));
    assert.deepEqual(again, first, `${note}: the same fence gives the same decision`);
    assert.equal(first.suggestion, suggestion, `${note}: suggestion`);
    assert.equal(first.verdict, verdict, `${note}: verdict`);
    const reseeded = decided({...spec, matrix: {...matrix, sensitivity: {...matrix.sensitivity, seed: 7}}});
    assert.deepEqual({...reseeded, share: first.share}, first, `${note}: another seed moves only the draws`);
  }
})().catch(error => { console.error(error); process.exit(1); });
