"use strict";

// The computed verdict's pure layer (src/obs_html/pugh-verdict.js; artifact-ui.md, The engine's bottom
// line): data in, data out, no page. overridesOf turns the reader's changes into ctrl's engine overrides,
// which ctrl's engine (vendor/pugh.js) takes as they are; bottomLineOf words the engine's result.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {pathToFileURL} = require("node:url");

const root = path.resolve(__dirname, "..");
const vectors = require(path.join(__dirname, "fixtures", "pugh-vectors.json"));

(async () => {
  const engine = await import(pathToFileURL(path.join(root, "src", "obs_html", "vendor", "pugh.js")));
  const context = {};  // No document: the pure layer needs no page.
  vm.runInNewContext(fs.readFileSync(path.join(root, "src", "obs_html", "pugh-verdict.js"), "utf8"), context);
  const {overridesOf, bottomLineOf} = context.obsPughVerdict;
  const {matrix} = vectors.matrices.find(vector => vector.name === "small with C");
  const keys = {A: "D", B: "A", C: "B", D: "C"};  // The figure's letters of ctrl's options, in the fence's order.
  const letters = Object.fromEntries(Object.entries(keys).map(([letter, key]) => [key, letter]));
  const nameOf = key => letters[key], letterOf = key => letters[key];

  // The reader's changes are the engine's own overrides, datum first, each with a comment.
  const overrides = overridesOf({vetoes: ["C"], lifts: {B: ["gate0"]}, datum: "D"}, letter => keys[letter]);
  assert.deepEqual(JSON.parse(JSON.stringify(overrides)), [
    {kind: "datum", candidate: "C", comment: "Changed by the reader"},
    {kind: "option", candidate: "B", action: "veto", comment: "Changed by the reader"},
    {kind: "lift", candidate: "A", veto: "gate0", comment: "Changed by the reader"}]);
  assert.deepEqual(overridesOf({}, letter => keys[letter]).length, 0, "no changes, no overrides");
  const vetoed = engine.decide({...matrix, overrides: overridesOf({vetoes: ["C"]}, letter => keys[letter])});
  assert.equal(vetoed.suggestion.key, "A", "the engine decides the reader's veto");

  // The bottom line: the verdict, each of the engine's runners-up with its tie, then the vetoes.
  const lines = bottomLineOf(engine.decide(matrix), nameOf, letterOf, engine.fmt);
  assert.deepEqual(JSON.parse(JSON.stringify(lines)), [
    {part: "verdict", verdict: "holds", text: "The choice holds: C wins 96.0 % of the weight draws within ±1."},
    {part: "runner-up", letter: "B", reasonable: false, text: "B ties if speed goes 2 → 0.5: not a reasonable change."},
    {part: "runner-up", letter: "D", reasonable: null, text: "No single weight makes D tie."},
    {part: "runner-up", letter: "A", reasonable: null, text: "No single weight makes A tie."}]);
  const out = bottomLineOf(vetoed, nameOf, letterOf, engine.fmt);
  assert.deepEqual(JSON.parse(JSON.stringify(out.at(-1))), {part: "veto", letter: "C", text: "C is out: vetoed by you."});
  const gated = engine.decide({...matrix, gates: [{criterion: "cost", max: 15, why: "over budget"}],
    overrides: overridesOf({lifts: {B: ["gate0"]}}, letter => keys[letter])});
  assert.equal(bottomLineOf(gated, nameOf, letterOf, engine.fmt).at(-1).text, "B is in: lifted: over budget: cost 19 above 15.");
  // The same fence gives the same lines.
  assert.deepEqual(bottomLineOf(engine.decide(matrix), nameOf, letterOf, engine.fmt), lines);
})().catch(error => { console.error(error); process.exit(1); });
