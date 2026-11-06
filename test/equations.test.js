"use strict";

// Draws the step-response figure of the equations fixture Document (test/fixtures/documents)
// through equations.js, as a figure draws its curves, without a page: every curve of a family
// through critical damping has every point, from the core's piecewise solution and, where the
// core marks a value for the numeric solver, from the numeric system.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
vm.runInThisContext(fs.readFileSync(path.join(root, "maths", "node_modules", "mathjs", "lib", "browser", "math.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(root, "src", "obs_html", "equations.js"), "utf8"));

const document = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "documents", "equations.json"), "utf8"));
const bodies = [];
const walk = node => {
  if (node && typeof node === "object") {
    if (node.type === "figures" && node.attrs.kind === "equations") bodies.push(node.children[0].attrs);
    Object.values(node).forEach(walk);
  }
};
walk(document.chapters);
const step = bodies.find(body => body.equations[0].source === "y'' + 2*zeta*w*y' + w**2*y = w**2*u");
const sweeps = Array.from({length: 241}, (_, index) => 10 * index / 240);
const critical = t => 1 - (1 + 2 * t) * Math.exp(-2 * t);

async function curve(spec, zeta) {
  const points = await globalThis.obsEquations.curvePoints(spec, {zeta, w: 2, u: 1}, sweeps);
  assert.equal(points.sweep.length, sweeps.length, `zeta = ${zeta}: a point at every t`);
  points.ys[0].forEach((y, index) => assert.ok(Number.isFinite(y), `zeta = ${zeta}, t = ${points.sweep[index]}`));
  return points;
}

(async () => {
  assert.equal(step.solution.method, "exact");
  for (const zeta of [0.1, 0.45, 0.8, 1, 1.15, 1.5]) await curve(step, zeta);
  const exact = await curve(step, 1);
  exact.sweep.forEach((t, index) => assert.ok(Math.abs(exact.ys[0][index] - critical(t)) <= 1e-9, `t = ${t}`));

  // Where the core marks zeta = 1 for the numeric solver, the curve integrates the state form there.
  const [branch] = step.solution.branches;
  const general = branch.y.piecewise.at(-1).value;
  const symbol = name => ({symbol: name});
  const product = (...args) => ({op: "mul", args});
  const marked = {...step, solution: {method: "exact", branches: [{y: general}], numeric: {
    when: {relation: "eq", args: [symbol("zeta"), {number: 1}]},
    system: {method: "differential", independent: "t", start: 0, initial: [0, 0],
      state: [{of: "y", order: 0}, {of: "y", order: 1}],
      derivatives: [{derivative: "y", order: 1}, {op: "add", args: [
        product(symbol("w"), symbol("w"), symbol("u")),
        product({number: -2}, symbol("zeta"), symbol("w"), {derivative: "y", order: 1}),
        product({number: -1}, symbol("w"), symbol("w"), symbol("y"))]}]}}}};
  const unmarked = await globalThis.obsEquations.curvePoints({...marked, solution: {...marked.solution, numeric: undefined}},
    {zeta: 1, w: 2, u: 1}, sweeps);
  assert.ok(unmarked.ys[0].slice(1).every(y => y === null), "the general form alone has no point at zeta = 1");
  const numeric = await curve(marked, 1);
  numeric.sweep.forEach((t, index) => assert.ok(Math.abs(numeric.ys[0][index] - critical(t)) <= 1e-6, `t = ${t}`));
  await curve(marked, 0.45);
})().catch(error => { console.error(error); process.exit(1); });
