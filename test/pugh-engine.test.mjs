// ctrl's Pugh engine tests, ported: the tests of the engine's decision in github.com/mb-89/ctrl
// test/pugh.test.mjs at commit e98eba5f7bcb8abf2686dc336dedb28e91e7b698, under their names and
// unchanged but for the import, run against the engine as this package carries it
// (src/obs_html/vendor/pugh.js). Not ported: ctrl's tests of its own report, CLI, figures and
// browser page (renderHtml, renderMarkdown, tools/pugh.mjs, plotSvg's series), which obs does not
// use; obs's figure lays out the engine's result itself (pugh-figure.js).
//
// Copyright (c) 2026 mb-89. MIT License: ctrl's LICENSE, whose notice follows.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
// associated documentation files (the "Software"), to deal in the Software without restriction,
// including without limitation the rights to use, copy, modify, merge, publish, distribute,
// sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions: The above copyright notice and this
// permission notice shall be included in all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
// NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
// OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decide, markOf, worseRatio, normalizeMatrix, bottomLine, PughError } from '../src/obs_html/vendor/pugh.js';

const close = (a, b, tol, what = '') => assert.ok(Math.abs(a - b) <= tol, `${what} ${a} vs ${b} (tol ${tol})`);

// Three candidates on three measured criteria, marks worked out by hand.
const small = () => ({
  title: 'Small',
  criteria: [
    { key: 'err', weight: 3, better: 'lower', tolerance: 0.1, floor: 0 },
    { key: 'speed', weight: 2, better: 'higher', tolerance: 0.1, floor: 0 },
    { key: 'cost', weight: 1, better: 'lower', tolerance: 0.25, floor: 1 },
  ],
  candidates: [
    { key: 'D', values: { err: 1, speed: 10, cost: 9 } },
    { key: 'A', values: { err: 0.4, speed: 10.5, cost: 19 }, tieBreak: 2 },   // ++, S, −− ((19+1)/(9+1) = 2 → −, not beyond 2)
    { key: 'B', values: { err: 0.85, speed: 30, cost: 4 }, tieBreak: 1 },     // +, ++, + ((4+1)/(9+1) = 0.5 → +)
  ],
  datum: { prefer: ['D'] },
  sensitivity: { seed: 3, draws: 2000 },
});

test('marks follow the ratio bands, both directions, with the floor', () => {
  const lo = { better: 'lower', tolerance: 0.1, floor: 0 }, hi = { better: 'higher', tolerance: 0.1, floor: 0 };
  assert.equal(markOf(lo, 0.49, 1), 2);
  assert.equal(markOf(lo, 0.5, 1), 1);       // exactly ½: still +
  assert.equal(markOf(lo, 1 / 1.1, 1), 1);
  assert.equal(markOf(lo, 1.05, 1), 0);
  assert.equal(markOf(lo, 1.1, 1), -1);
  assert.equal(markOf(lo, 2, 1), -1);         // exactly ×2: still −
  assert.equal(markOf(lo, 2.01, 1), -2);
  assert.equal(markOf(hi, 2.01, 1), 2);       // higher is better: turned over
  assert.equal(markOf(hi, 0.49, 1), -2);
  assert.equal(markOf({ better: 'lower', tolerance: 0.2, floor: 2 }, 0, 1), 1);   // 0 % against 1 %: (0+2)/(1+2), not ×0
  assert.equal(markOf(lo, null, 1), null);
  assert.equal(markOf(lo, 0, 0), null);       // 0/0 without a floor: not judged
  close(worseRatio(hi, 4, 2), 0.5, 1e-12);
});

test('a small matrix, checked by hand', () => {
  const r = decide(small());
  const m = Object.fromEntries(r.candidates.map((c) => [c.key, c.marks]));
  assert.deepEqual(m.A, { err: 2, speed: 0, cost: -1 });
  assert.deepEqual(m.B, { err: 1, speed: 2, cost: 1 });
  assert.deepEqual(m.D, { err: 0, speed: 0, cost: 0 });
  const t = Object.fromEntries(r.candidates.map((c) => [c.key, c.total]));
  assert.equal(t.A, 3 * 2 + 0 - 1);   // 5
  assert.equal(t.B, 3 + 4 + 1);        // 8
  assert.deepEqual(r.ranking, ['B', 'A', 'D']);
  assert.equal(r.suggestion.key, 'B');
  assert.equal(r.datum.key, 'D');
});

test('judged marks, several raters (median, spread), and a judged datum shift', () => {
  const mx = {
    criteria: [{ key: 'x', weight: 1, better: 'lower' }, { key: 'look', weight: 2, better: 'higher', kind: 'judged' }],
    candidates: [
      { key: 'D', values: { x: 1 } },
      { key: 'A', values: { x: 1 }, marks: { look: [2, 1, 2] } },
      { key: 'B', values: { x: 1 }, marks: { look: [-1, 1] } },
    ],
    datum: { prefer: ['D'] },
  };
  const r = decide(mx), A = r.candidates.find((c) => c.key === 'A'), B = r.candidates.find((c) => c.key === 'B');
  assert.equal(A.marks.look, 2); assert.equal(A.spread.look, 1);
  assert.equal(B.marks.look, 0); assert.equal(B.spread.look, 2);
  // With A unfit and preferred first, the datum falls back to D: no shift.
  // With A as the datum, B's look is shifted by A's own mark: 0 − 2 = −2.
  const r2 = decide({ ...mx, datum: { prefer: ['A'] } });
  assert.equal(r2.candidates.find((c) => c.key === 'B').marks.look, -2);
  assert.equal(r2.candidates.find((c) => c.key === 'D').marks.look, null);   // D has no judged mark: not judged
  assert.ok(r2.notes.some((n) => /shifted/.test(n)));
});

test('gates: a hard limit before the datum, a ratio to the datum after, the datum exempt', () => {
  const mx = small();
  mx.gates = [{ criterion: 'cost', max: 15 }, { criterion: 'err', maxRatio: 2 }];
  mx.candidates.push({ key: 'C', values: { err: 2.5, speed: 50, cost: 1 } });   // ×2.5 the datum's error
  const r = decide(mx), by = Object.fromEntries(r.candidates.map((c) => [c.key, c]));
  assert.equal(by.A.fits, false); assert.match(by.A.whyNot, /above 15/);
  assert.equal(by.C.fits, false); assert.match(by.C.whyNot, /×2.5/);
  assert.deepEqual(r.ranking, ['B', 'D']);
  // A gate may carry its own reason word.
  const why = decide({ ...mx, gates: [{ criterion: 'err', maxRatio: 2, why: 'fails the main job' }] });
  assert.match(why.candidates.find((c) => c.key === 'C').whyNot, /^fails the main job: err ×2.5/);
  // The datum's fallback: the first preferred that fits, else the first preferred.
  const fb = decide({ ...small(), gates: [{ criterion: 'cost', max: 5 }], datum: { prefer: ['A', 'B'] } });
  assert.equal(fb.datum.key, 'B');
  const none = decide({ ...small(), gates: [{ criterion: 'cost', max: 1 }], datum: { prefer: ['A', 'B'] } });
  assert.equal(none.datum.key, 'A'); assert.equal(none.datum.fits, false);
  assert.equal(none.suggestion, null);
  assert.equal(bottomLine(none), 'No candidate fits.');
  // A missing value passes a hard limit (it cannot judge it) and fails a ratio gate.
  const miss = decide({ ...small(), candidates: [...small().candidates, { key: 'E', values: { speed: 10, cost: 9 } }], gates: [{ criterion: 'err', maxRatio: 2 }] });
  assert.match(miss.candidates.find((c) => c.key === 'E').whyNot, /no number/);
});

test('sensitivity: tie points and the smallest change agree with brute force', () => {
  const mx = small();
  mx.candidates.push({ key: 'C', values: { err: 0.95, speed: 22, cost: 9 }, tieBreak: 0 });   // S, ++, S: total 4
  const r = decide(mx), s = r.sensitivity, w = r.weights;
  const marks = Object.fromEntries(r.candidates.map((c) => [c.key, r.criteria.map((cr) => c.marks[cr.key] ?? 0)]));
  const total = (k, ww) => marks[k].reduce((t, x, i) => t + x * ww[i], 0);
  assert.equal(s.winner, 'B');
  for (const ru of s.all) {
    // Brute force: scan each weight alone in steps of 0.001 from 0 to 20 for
    // the first point (nearest to its default) where the runner-up reaches the winner.
    let best = null;
    w.forEach((_, i) => {
      for (const dir of [-1, 1]) for (let d = 0; d <= 20; d += 0.001) {
        const ww = w.slice(); ww[i] = w[i] + dir * d;
        if (ww[i] < 0) break;
        if (total(ru.key, ww) >= total('B', ww) - 1e-9) { if (!best || d < best.d) best = { i, d }; break; }
      }
    });
    if (!ru.tie) { assert.equal(best, null, ru.key); continue; }
    close(Math.abs(ru.tie.to - ru.tie.from), best.d, 2e-3, `${ru.key} tie`);
    assert.equal(r.criteria[best.i].key, ru.tie.criterion);
    // The smallest change of all weights: the distance to the hyperplane of
    // equal totals (no weight hits 0 here), checked against its closed form.
    const D = marks[ru.key].map((x, i) => x - marks.B[i]), dw = D.reduce((t, x, i) => t + x * w[i], 0);
    close(ru.minChange.rel, Math.abs(dw) / Math.hypot(...D) / Math.hypot(...w), 1e-9, `${ru.key} min change`);
    // A random search never finds a smaller change that ties.
    let seed = 11; const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
    for (let n = 0; n < 2000; n++) {
      const ww = w.map((x) => Math.max(0, x + (rnd() * 2 - 1) * 3));
      if (total(ru.key, ww) >= total('B', ww)) assert.ok(Math.hypot(...ww.map((x, i) => x - w[i])) / Math.hypot(...w) >= ru.minChange.rel - 1e-9);
    }
  }
  // The shares add up to 1 and match a direct count with the same rule.
  const shares = [s.share, ...s.all.map((x) => x.share)];
  close(shares.reduce((a, b) => a + b, 0), 1, 1e-12);
});

test('verdict: the choice holds, depends on the weights, tied now', () => {
  const r = decide(small());
  assert.equal(r.sensitivity.verdict, 'holds');
  // robustShare, holdShare's old name, is still read.
  assert.equal(decide({ ...small(), sensitivity: { robustShare: 1.01 } }).sensitivity.verdict, 'depends');
  // Two identical candidates: tied now, the choice depends, the tie-break decides.
  const mx = small();
  mx.candidates.push({ key: 'B2', values: { ...mx.candidates[2].values }, tieBreak: 5 });
  const r2 = decide(mx), ru = r2.sensitivity.runnersUp.find((x) => x.key === 'B2');
  assert.equal(r2.suggestion.key, 'B');
  assert.equal(ru.tie.now, true);
  assert.equal(r2.sensitivity.verdict, 'depends');
  assert.match(bottomLine(r2), /the choice depends on the weights: .*B2 ties it now/);
});

test('deterministic: the same matrix gives the same result, the seed moves only the draws', () => {
  const a = JSON.stringify(decide(small())), b = JSON.stringify(decide(small()));
  assert.equal(a, b);
  const mx = small(); mx.candidates.push({ key: 'C', values: { err: 0.95, speed: 22, cost: 9 } });
  const s1 = decide({ ...mx, sensitivity: { seed: 1 } }), s2 = decide({ ...mx, sensitivity: { seed: 2 } });
  assert.deepEqual(s1.ranking, s2.ranking);
  assert.notEqual(s1.sensitivity.all[0].share, undefined);
});

test('bad matrices are refused with the place named', () => {
  const bad = (mx, re) => assert.throws(() => normalizeMatrix(mx), (e) => e instanceof PughError && re.test(e.message));
  bad({ criteria: [], candidates: [] }, /criteria/);
  bad({ ...small(), criteria: [{ key: 'err', weight: 1, better: 'up' }] }, /better/);
  bad({ ...small(), candidates: [{ key: 'D', values: { nope: 1 } }] }, /no such criterion/);
  bad({ ...small(), gates: [{ criterion: 'err', maxRatio: 2, max: 3 }] }, /exactly one/);
  bad({ ...small(), datum: { prefer: ['Z'] } }, /datum.prefer/);
  bad({ criteria: [{ key: 'j', weight: 1, better: 'higher', kind: 'judged' }], candidates: [{ key: 'a', marks: { j: 3 } }] }, /−2 to 2/);
});


// ---- Overrides (inputs 61–64) -----------------------------------------------

const withOv = (mx, ...overrides) => decide({ ...mx, overrides });
const cand = (r, k) => r.candidates.find((c) => c.key === k);

test('overrides: a criterion’s weight and tolerance', () => {
  const r = withOv(small(), { kind: 'criterion', criterion: 'speed', weight: 0, comment: 'speed does not matter here' });
  assert.equal(cand(r, 'B').total, 3 + 0 + 1);   // speed's ++ no longer counts
  assert.equal(r.weights[1], 0);
  assert.match(r.overrides[0].effect, /speed: weight 2 → 0/);
  // A wider tolerance turns B's err + (0.85 against 1) into S at tolerance 0.5: 1/1.5 < 0.85.
  const t = withOv(small(), { kind: 'criterion', criterion: 'err', tolerance: 0.5, comment: 'only big differences count' });
  assert.equal(cand(small() && decide(small()), 'B').marks.err, 1);
  assert.equal(cand(t, 'B').marks.err, 0);
  assert.match(t.overrides[0].effect, /err: tolerance 0.1 → 0.5/);
});

test('overrides: a cell vetoed (out of the totals and the gates) or nudged', () => {
  const v = withOv(small(), { kind: 'cell', candidate: 'B', criterion: 'speed', action: 'veto', comment: 'speed test was wrong' });
  assert.equal(cand(v, 'B').marks.speed, null);
  assert.equal(cand(v, 'B').toolMarks.speed, 2);
  assert.equal(cand(v, 'B').total, 3 + 1);
  const n = withOv(small(), { kind: 'cell', candidate: 'A', criterion: 'cost', action: 'nudge', by: -1, comment: 'too expensive to run' });
  assert.equal(cand(n, 'A').marks.cost, -2);
  assert.equal(cand(n, 'A').total, 6 + 0 - 2);
  // A vetoed cell plays no part in its option's gates.
  const mx = { ...small(), gates: [{ criterion: 'cost', max: 15 }] };
  assert.equal(cand(decide(mx), 'A').fits, false);
  assert.equal(cand(withOv(mx, { kind: 'cell', candidate: 'A', criterion: 'cost', action: 'veto', comment: 'cost is negotiable' }), 'A').fits, true);
});

test('overrides: an option vetoed or nudged (a step is one mark at the largest weight)', () => {
  const v = withOv(small(), { kind: 'option', candidate: 'B', action: 'veto', comment: 'unacceptable effort' });
  assert.equal(cand(v, 'B').fits, false);
  assert.match(cand(v, 'B').whyNot, /vetoed by the person: unacceptable effort/);
  assert.equal(v.suggestion.key, 'A');
  assert.equal(v.before.suggestion, 'B');
  const n = withOv(small(), { kind: 'option', candidate: 'B', action: 'nudge', by: -1, comment: 'unacceptable effort function' });
  assert.equal(n.nudgeUnit, 3);
  assert.equal(cand(n, 'B').total, 8 - 3);
  assert.deepEqual(n.ranking, ['B', 'A', 'D']);   // 5 = 5: B's tieBreak 1 beats A's 2
  const n2 = withOv(small(), { kind: 'option', candidate: 'B', action: 'nudge', by: -1, comment: 'a' }, { kind: 'option', candidate: 'B', action: 'nudge', by: -1, comment: 'b' });
  assert.equal(cand(n2, 'B').total, 2);
  assert.equal(n2.suggestion.key, 'A');
  // The nudge is a fixed offset in the sensitivity too.
  assert.equal(n2.sensitivity.winner, 'A');
});

test('overrides: the tool’s vetoes, one per reason, each lifted on its own', () => {
  const mx = { ...small(), gates: [{ criterion: 'cost', max: 15, why: 'too dear' }, { criterion: 'err', maxRatio: 1.05, why: 'main job' }] };
  mx.candidates[1] = { ...mx.candidates[1], values: { err: 1.2, speed: 10.5, cost: 19 } };   // A fails both gates
  const r = decide(mx), A = cand(r, 'A');
  assert.deepEqual(A.vetoes.map((v) => v.id), ['gate0', 'gate1']);
  assert.equal(A.fits, false);
  const one = withOv(mx, { kind: 'lift', candidate: 'A', veto: 'gate0', comment: 'the budget can stretch' });
  assert.equal(cand(one, 'A').fits, false, 'one veto remains');
  assert.match(one.overrides[0].effect, /1 veto remains/);
  const both = withOv(mx, { kind: 'lift', candidate: 'A', veto: 'gate0', comment: 'the budget can stretch' }, { kind: 'lift', candidate: 'A', veto: 'gate1', comment: 'close enough' });
  assert.equal(cand(both, 'A').fits, true);
  assert.ok(both.ranking.includes('A'));
  assert.match(both.overrides[1].effect, /it is back in/);
  // The caller's verdict is a veto too, liftable.
  const given = { ...small(), candidates: small().candidates.map((c) => (c.key === 'A' ? { ...c, fits: false, whyNot: 'diverges' } : c)) };
  assert.deepEqual(cand(decide(given), 'A').vetoes.map((v) => v.id), ['given']);
  assert.equal(cand(withOv(given, { kind: 'lift', candidate: 'A', veto: 'given', comment: 'a model artefact' }), 'A').fits, true);
  // A lift of a veto that is not there is said, not dropped silently.
  assert.ok(withOv(small(), { kind: 'lift', candidate: 'A', veto: 'gate9', comment: 'x' }).notes.some((n) => /no veto 'gate9'/.test(n)));
});

// Input 62: a lifted veto is as if the tool had never set it, and the
// person's veto and the tool's are one and the same thing.
const decision = (r) => ({ ranking: r.ranking, suggestion: r.suggestion?.key, totals: r.candidates.map((c) => [c.key, c.total, c.fits]), sensitivity: r.sensitivity && { verdict: r.sensitivity.verdict, share: r.sensitivity.share } });
test('a lifted tool veto ranks the option as decide() does without that gate', () => {
  const gates = [{ criterion: 'cost', max: 15, why: 'too dear' }, { criterion: 'err', maxRatio: 1.05, why: 'main job' }];
  const mx = { ...small(), gates, candidates: small().candidates.map((c) => (c.key === 'A' ? { ...c, values: { err: 1.2, speed: 10.5, cost: 19 } } : c)) };   // only A fails, both gates
  for (const [gi, id] of [[0, 'gate0'], [1, 'gate1']]) {
    const other = gates.filter((_, k) => k !== gi);
    const lifted = withOv(mx, { kind: 'lift', candidate: 'A', veto: id, comment: 'x' }, { kind: 'lift', candidate: 'A', veto: gi ? 'gate0' : 'gate1', comment: 'y' });
    const without = decide({ ...mx, gates: [] });
    assert.deepEqual(decision(lifted), decision(without), `${id} and the other lifted: as without both gates`);
    const one = withOv(mx, { kind: 'lift', candidate: 'A', veto: id, comment: 'x' });
    assert.deepEqual(decision(one), decision(decide({ ...mx, gates: other })), `${id} lifted: as without that gate`);
  }
});

test('the person’s veto and the tool’s are one path: the same ranking either way', () => {
  const byTool = decide({ ...small(), candidates: small().candidates.map((c) => (c.key === 'B' ? { ...c, fits: false, whyNot: 'diverges' } : c)) });
  const byPerson = withOv(small(), { kind: 'option', candidate: 'B', action: 'veto', comment: 'diverges' });
  assert.deepEqual(decision(byPerson), decision(byTool));
  assert.deepEqual(cand(byPerson, 'B').vetoes.map(({ by, why }) => [by, why]), [['person', 'diverges']]);
  assert.deepEqual(cand(byTool, 'B').vetoes.map(({ by, why }) => [by, why]), [['tool', 'diverges']]);
  // Lifting the tool's and removing the person's both give the matrix back.
  assert.deepEqual(decision(withOv(byTool.input, { kind: 'lift', candidate: 'B', veto: 'given', comment: 'x' })), decision(decide(small())));
});

test('overrides: another datum; bad overrides are refused', () => {
  const r = withOv(small(), { kind: 'datum', candidate: 'B', comment: 'B is what we know' });
  assert.equal(r.datum.key, 'B');
  assert.equal(cand(r, 'D').marks.err, -1);   // 1 against 0.85
  assert.match(r.overrides[0].effect, /the datum: D → B/);
  const bad = (o, re) => assert.throws(() => withOv(small(), o), (e) => e instanceof PughError && re.test(e.message));
  bad({ kind: 'cell', candidate: 'A', criterion: 'err', action: 'veto' }, /comment/);
  bad({ kind: 'cell', candidate: 'A', criterion: 'err', action: 'nudge', by: 0, comment: 'x' }, /by/);
  bad({ kind: 'option', candidate: 'Z', action: 'veto', comment: 'x' }, /candidate/);
  bad({ kind: 'criterion', criterion: 'err', comment: 'x' }, /a weight or a tolerance/);
  bad({ kind: 'nope', comment: 'x' }, /kind/);
});

// ---- The interactive report in a browser ----------------------------------------

// Drives the report as a person would: a click, the dialog, a comment, the
// button. The page decides with the engine it carries; the result must equal
