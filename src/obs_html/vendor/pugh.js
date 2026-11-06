// obs-html carries ctrl's Pugh decision engine: this file is github.com/mb-89/ctrl src/core/pugh.js
// at commit 2839d765ff04d5586f1f0199203bbebf2d03cd22 (MIT, ctrl's package.json), copied unchanged below
// these four lines. The renderer embeds its pughEngine() for decision figures (features.py, pugh_engine);
// to update it, copy ctrl's file again under this header with its new commit.

// A Pugh decision matrix, generic: candidates marked against a datum on
// criteria, weighted, gated, ranked, and tested against its own weights.
// It knows nothing of what is being decided (design/output/pugh.md). One
// file, no imports, no clock, no Math.random: copy it into another project
// as it is.
//
//   decide(matrix)          → the result (data): marks, totals, fits, ranking,
//                             suggestion, weight sensitivity, weak spots
//   renderHtml(result, { style }) → the report: one standalone HTML page,
//                             bottom line first, figures as inline SVG, at
//                             most a printed page per option; its look is the
//                             host's style sheet (style: { css, license })
//   renderMarkdown(result)  → the decision as text, for a terminal or an agent
//
// The matrix (a plain object; the file shape is in pugh.md):
//   { title?, kind? (what is decided, for the heading: 'Controller benchmark'),
//     nouns?: { options: 'controllers', datum: 'the one set up now' } (the
//     subtitle's words), notes?: [the caller's notes], criteria: [{ key, label?, weight, better: 'lower'|'higher',
//       tolerance?, floor?, kind?: 'measured'|'judged' }],
//     candidates: [{ key, label?, values?: {criterion: number},
//       marks?: {criterion: −2…2 | [−2…2, …] (several raters)}, fits?, whyNot?,
//       suggestable?, keep?, tieBreak?, note?, figures?: [figure] }],
//     gates?: [{ criterion, maxRatio | max | min, why? }],
//     datum?: { prefer: [candidate keys] },
//     strong?: 2, sensitivity?: { step, draws, seed, holdShare, runnersUp } }

// The whole engine is one function, pughEngine, so a report can carry the
// very same code (its source) and decide again in the browser: nothing is
// copied, nothing can drift. The module exports what it returns.
function pughEngine() {
  const PUGH_VERSION = 1;
  const SYMBOL = { 2: '++', 1: '+', 0: 'S', [-1]: '−', [-2]: '−−' };
  const DEFAULTS = { strong: 2, tolerance: 0.1, floor: 0, step: 1, draws: 4000, seed: 1, holdShare: 0.75, runnersUp: 3 };

  class PughError extends Error {
    constructor(code, message) { super(message); this.code = code; }
  }

  const finite = (v) => typeof v === 'number' && Number.isFinite(v);
  const isMark = (v) => Number.isInteger(v) && v >= -2 && v <= 2;
  const clampMark = (v) => Math.max(-2, Math.min(2, v));

  // A seeded generator (a 32-bit linear congruential one): the same seed gives
  // the same draws on every machine.
  function rng(seed) {
    let s = seed >>> 0 || 1;
    return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
  }

  // ---- The matrix, checked -----------------------------------------------------

  // A checked copy with the defaults filled in; a matrix that cannot be
  // decided is refused with a sentence that names the place (fail fast).
  function normalizeMatrix(m) {
    if (!m || typeof m !== 'object') throw new PughError('no-matrix', 'the matrix is not an object');
    const fail = (code, msg) => { throw new PughError(code, msg); };
    if (!Array.isArray(m.criteria) || !m.criteria.length) fail('no-criteria', 'criteria: a list of at least one criterion');
    if (!Array.isArray(m.candidates) || m.candidates.length < 1) fail('no-candidates', 'candidates: a list of at least one candidate');
    const keys = new Set();
    const criteria = m.criteria.map((c, i) => {
      const where = `criteria[${i}]`;
      if (typeof c?.key !== 'string' || !c.key) fail('bad-criterion', `${where}.key: a name`);
      if (keys.has(c.key)) fail('bad-criterion', `${where}.key: '${c.key}' twice`);
      keys.add(c.key);
      if (!finite(c.weight) || c.weight < 0) fail('bad-criterion', `${where}.weight: a number ≥ 0`);
      if (c.better !== 'lower' && c.better !== 'higher') fail('bad-criterion', `${where}.better: 'lower' or 'higher'`);
      const tolerance = c.tolerance ?? DEFAULTS.tolerance, floor = c.floor ?? DEFAULTS.floor, kind = c.kind ?? 'measured';
      if (!finite(tolerance) || tolerance < 0) fail('bad-criterion', `${where}.tolerance: a number ≥ 0`);
      if (!finite(floor) || floor < 0) fail('bad-criterion', `${where}.floor: a number ≥ 0`);
      if (kind !== 'measured' && kind !== 'judged') fail('bad-criterion', `${where}.kind: 'measured' or 'judged'`);
      return { key: c.key, label: String(c.label ?? c.key), weight: c.weight, better: c.better, tolerance, floor, kind };
    });
    const byKey = Object.fromEntries(criteria.map((c) => [c.key, c]));
    const ckeys = new Set();
    const candidates = m.candidates.map((c, i) => {
      const where = `candidates[${i}]`;
      if (typeof c?.key !== 'string' || !c.key) fail('bad-candidate', `${where}.key: a name`);
      if (ckeys.has(c.key)) fail('bad-candidate', `${where}.key: '${c.key}' twice`);
      ckeys.add(c.key);
      const values = {}, marks = {};
      for (const [k, v] of Object.entries(c.values ?? {})) {
        if (!byKey[k]) fail('bad-candidate', `${where}.values.${k}: no such criterion`);
        if (byKey[k].kind !== 'measured') fail('bad-candidate', `${where}.values.${k}: '${k}' is judged: give marks`);
        if (v !== null && typeof v !== 'number') fail('bad-candidate', `${where}.values.${k}: a number or null`);
        values[k] = v;
      }
      for (const [k, v] of Object.entries(c.marks ?? {})) {
        if (!byKey[k]) fail('bad-candidate', `${where}.marks.${k}: no such criterion`);
        if (byKey[k].kind !== 'judged') fail('bad-candidate', `${where}.marks.${k}: '${k}' is measured: give values`);
        const list = [].concat(v);
        if (!list.length || !list.every(isMark)) fail('bad-candidate', `${where}.marks.${k}: a whole number from −2 to 2, or a list of them (one per rater)`);
        marks[k] = list;
      }
      if (c.tieBreak !== undefined && !finite(c.tieBreak)) fail('bad-candidate', `${where}.tieBreak: a number`);
      const figures = (c.figures ?? []).map((f, j) => normalizeFigure(f, `${where}.figures[${j}]`, fail));
      return {
        key: c.key, label: String(c.label ?? c.key), values, marks, fits: c.fits !== false, whyNot: c.fits === false ? String(c.whyNot ?? 'does not fit') : '',
        suggestable: c.suggestable !== false, keep: !!c.keep, tieBreak: c.tieBreak ?? null, note: c.note ? String(c.note) : '', figures,
      };
    });
    const gates = (m.gates ?? []).map((g, i) => {
      const where = `gates[${i}]`;
      if (!byKey[g?.criterion]) fail('bad-gate', `${where}.criterion: one of ${criteria.map((c) => c.key).join(', ')}`);
      const kinds = ['maxRatio', 'max', 'min'].filter((k) => g[k] !== undefined);
      if (kinds.length !== 1 || !finite(g[kinds[0]])) fail('bad-gate', `${where}: exactly one of maxRatio, max, min, a number`);
      if (kinds[0] === 'maxRatio' && !(g.maxRatio >= 1)) fail('bad-gate', `${where}.maxRatio: at least 1`);
      if (kinds[0] !== 'maxRatio' && byKey[g.criterion].kind !== 'measured') fail('bad-gate', `${where}: a hard limit needs a measured criterion`);
      return { criterion: g.criterion, [kinds[0]]: g[kinds[0]], why: g.why ? String(g.why) : '' };
    });
    const prefer = m.datum?.prefer ?? [candidates[0].key];
    if (!Array.isArray(prefer) || !prefer.length || !prefer.every((k) => ckeys.has(k))) fail('bad-datum', `datum.prefer: candidate keys (${[...ckeys].join(', ')})`);
    const strong = m.strong ?? DEFAULTS.strong;
    if (!finite(strong) || strong <= 1) fail('bad-strong', 'strong: a ratio above 1');
    // robustShare: the old name of holdShare (the verdict was renamed so it
    // cannot be read as a controller's robustness).
    const { robustShare, ...given } = m.sensitivity ?? {};
    const s = { ...DEFAULTS, ...(robustShare !== undefined ? { holdShare: robustShare } : {}), ...given };
    for (const k of ['step', 'draws', 'seed', 'holdShare', 'runnersUp']) if (!finite(s[k]) || s[k] < 0) fail('bad-sensitivity', `sensitivity.${k}: a number ≥ 0`);
    // The person's overrides (inputs 61–64), each with a comment: a
    // criterion's weight or tolerance; a cell vetoed (out of the calculation)
    // or nudged; an option vetoed or nudged; one of the tool's vetoes lifted;
    // another datum.
    const KINDS = { criterion: ['criterion'], cell: ['candidate', 'criterion'], option: ['candidate'], lift: ['candidate'], datum: ['candidate'] };
    const overrides = (m.overrides ?? []).map((o, i) => {
      const where = `overrides[${i}]`;
      if (!o || !KINDS[o.kind]) fail('bad-override', `${where}.kind: one of ${Object.keys(KINDS).join(', ')}`);
      if (typeof o.comment !== 'string' || !o.comment.trim()) fail('bad-override', `${where}.comment: say why (every change carries a comment)`);
      for (const f of KINDS[o.kind]) {
        if (f === 'criterion' && !byKey[o.criterion]) fail('bad-override', `${where}.criterion: one of ${criteria.map((c) => c.key).join(', ')}`);
        if (f === 'candidate' && !ckeys.has(o.candidate)) fail('bad-override', `${where}.candidate: one of ${[...ckeys].join(', ')}`);
      }
      const out = { kind: o.kind, comment: o.comment.trim(), ...(o.criterion ? { criterion: o.criterion } : {}), ...(o.candidate ? { candidate: o.candidate } : {}) };
      if (o.kind === 'criterion') {
        if (o.weight === undefined && o.tolerance === undefined) fail('bad-override', `${where}: a weight or a tolerance`);
        if (o.weight !== undefined) { if (!finite(o.weight) || o.weight < 0) fail('bad-override', `${where}.weight: a number ≥ 0`); out.weight = o.weight; }
        if (o.tolerance !== undefined) { if (!finite(o.tolerance) || o.tolerance < 0) fail('bad-override', `${where}.tolerance: a number ≥ 0`); out.tolerance = o.tolerance; }
      }
      if (o.kind === 'lift') {
        if (typeof o.veto !== 'string' || !o.veto) fail('bad-override', `${where}.veto: the id of the tool's veto to lift`);
        out.veto = o.veto;
      }
      if (o.kind === 'cell' || o.kind === 'option') {
        if (o.action !== 'veto' && o.action !== 'nudge') fail('bad-override', `${where}.action: 'veto' or 'nudge'`);
        out.action = o.action;
        if (o.action === 'nudge') {
          if (!Number.isInteger(o.by) || !o.by || Math.abs(o.by) > 4) fail('bad-override', `${where}.by: a whole number of steps, ±1 … ±4, not 0`);
          out.by = o.by;
        }
      }
      return out;
    });
    return {
      title: String(m.title ?? 'Decision'), kind: String(m.kind ?? 'Decision'), nouns: { options: String(m.nouns?.options ?? 'options'), datum: String(m.nouns?.datum ?? 'the datum') }, notes: Array.isArray(m.notes) ? m.notes.map(String) : [], criteria, candidates, gates, datum: { prefer }, strong, overrides,
      sensitivity: { step: s.step, draws: Math.round(s.draws), seed: s.seed, holdShare: s.holdShare, runnersUp: Math.round(s.runnersUp) },
    };
  }

  // A figure for the report: ready SVG, or panels of series to plot (stacked,
  // sharing x). { title, svg } | { title, xLabel?, xRange?: [x0, x1],
  // panels: [{ yLabel?, series: [{ label, x: [], y: [], role?: 'option' |
  // 'datum' | 'reference' | 'other' }] }] } ('series' alone is one panel).
  const ROLES = ['option', 'datum', 'reference', 'other'];
  function normalizeFigure(f, where, fail) {
    if (!f || typeof f !== 'object' || typeof f.title !== 'string') fail('bad-figure', `${where}.title: a title`);
    if (typeof f.svg === 'string') return { title: f.title, svg: f.svg };
    const panels = f.panels ?? (f.series ? [{ yLabel: f.yLabel, series: f.series }] : null);
    if (!Array.isArray(panels) || !panels.length) fail('bad-figure', `${where}: svg, or panels (or series) to plot`);
    if (f.xRange && !(Array.isArray(f.xRange) && f.xRange.length === 2 && f.xRange.every(finite) && f.xRange[1] > f.xRange[0])) fail('bad-figure', `${where}.xRange: [x0, x1], x0 < x1`);
    return {
      title: f.title, xLabel: f.xLabel ? String(f.xLabel) : '', xRange: f.xRange ?? null,
      panels: panels.map((p, k) => {
        if (!Array.isArray(p?.series) || !p.series.length) fail('bad-figure', `${where}.panels[${k}].series: a list of series`);
        return {
          yLabel: p.yLabel ? String(p.yLabel) : '',
          series: p.series.map((sr, i) => {
            const at = `${where}.panels[${k}].series[${i}]`;
            if (!Array.isArray(sr?.x) || !Array.isArray(sr?.y) || sr.x.length !== sr.y.length || sr.x.length < 2) fail('bad-figure', `${at}: x and y, lists of the same length (2 or more)`);
            const role = sr.role ?? 'other';
            if (!ROLES.includes(role)) fail('bad-figure', `${at}.role: one of ${ROLES.join(', ')}`);
            return { label: String(sr.label ?? ''), x: sr.x, y: sr.y, role };
          }),
        };
      }),
    };
  }

  // ---- Marks -------------------------------------------------------------------

  // How many times worse a is than b on this criterion (1: the same; ½: twice
  // as good), the floor added to both so tiny numbers do not read as huge
  // ratios: q = (a + f)/(b + f), turned over when higher is better.
  function worseRatio(criterion, a, b) {
    const f = criterion.floor;
    return criterion.better === 'lower' ? (a + f) / (b + f) : (b + f) / (a + f);
  }

  // The five-point mark of a measured value against the datum's: S within the
  // tolerance, ±1 beyond it up to the strong ratio, ±2 beyond that; null when
  // either number is missing.
  function markOf(criterion, a, b, strong = DEFAULTS.strong) {
    if (!finite(a) || !finite(b)) return null;
    const q = worseRatio(criterion, a, b), up = 1 + criterion.tolerance;
    if (!Number.isFinite(q)) return null;
    if (q < 1 / strong) return 2;
    if (q <= 1 / up) return 1;
    if (q > strong) return -2;
    if (q >= up) return -1;
    return 0;
  }

  const median = (list) => {
    const s = [...list].sort((x, y) => x - y), n = s.length;
    return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
  };

  // ---- The decision ------------------------------------------------------------

  function decide(matrix) {
    const m0 = normalizeMatrix(matrix), { candidates, strong } = m0;
    // The person's overrides, gathered (inputs 61–64); later ones of a kind win.
    const ov = m0.overrides, cellKey = (c, k) => `${c}\u0000${k}`;
    const critOv = new Map(), cellVeto = new Map(), cellNudge = new Map(), optVeto = new Map(), optNudge = new Map(), lifts = new Map();
    let datumOv = null;
    for (const o of ov) {
      if (o.kind === 'criterion') critOv.set(o.criterion, { ...critOv.get(o.criterion), ...('weight' in o ? { weight: o.weight } : {}), ...('tolerance' in o ? { tolerance: o.tolerance } : {}) });
      else if (o.kind === 'cell' && o.action === 'veto') cellVeto.set(cellKey(o.candidate, o.criterion), o.comment);
      else if (o.kind === 'cell') cellNudge.set(cellKey(o.candidate, o.criterion), (cellNudge.get(cellKey(o.candidate, o.criterion)) ?? 0) + o.by);
      else if (o.kind === 'option' && o.action === 'veto') optVeto.set(o.candidate, o.comment);
      else if (o.kind === 'option') optNudge.set(o.candidate, (optNudge.get(o.candidate) ?? 0) + o.by);
      else if (o.kind === 'lift') lifts.set(cellKey(o.candidate, o.veto), o.comment);
      else if (o.kind === 'datum') datumOv = o.candidate;
    }
    // The criteria as the person set them (weight, tolerance); the matrix's
    // own values stay in `defaults`.
    const criteria = m0.criteria.map((c) => ({ ...c, ...(critOv.get(c.key) ?? {}), defaults: { weight: c.weight, tolerance: c.tolerance } }));
    const m = { ...m0, criteria };
    const weights = criteria.map((c) => c.weight);
    const notes = [...m.notes];
    // Vetoes, one per reason (input 64): the caller's verdict, each hard gate
    // that fails, each ratio gate that fails, and the person's own. A tool's
    // veto can be lifted by the person, each on its own, with a comment; the
    // option is in when no veto remains.
    const veto = (r, id, why, by = 'tool') => r.vetoes.push({ id, by, why, lifted: by === 'tool' ? lifts.get(cellKey(r.key, id)) ?? '' : '' });
    const gateWhy = (g, text) => `${g.why ? `${g.why}: ` : ''}${text}`;
    const rows = candidates.map((c) => {
      const r = { ...c, vetoes: [] };
      if (c.fits === false) veto(r, 'given', c.whyNot);
      m.gates.forEach((g, gi) => {
        if (g.maxRatio !== undefined || cellVeto.has(cellKey(c.key, g.criterion))) return;   // a cell the person took out plays no part
        const cr = criteria.find((x) => x.key === g.criterion), v = c.values[g.criterion];
        if (!finite(v)) return;   // not measured: the gate cannot judge it
        if (g.max !== undefined && v > g.max) veto(r, `gate${gi}`, gateWhy(g, `${cr.label} ${fmt(v)} above ${fmt(g.max)}`));
        if (g.min !== undefined && v < g.min) veto(r, `gate${gi}`, gateWhy(g, `${cr.label} ${fmt(v)} below ${fmt(g.min)}`));
      });
      if (optVeto.has(c.key)) veto(r, 'person', optVeto.get(c.key), 'person');
      return r;
    });
    const settle = (r) => { const open = r.vetoes.filter((v) => !v.lifted); r.fits = !open.length; r.whyNot = open.map((v) => (v.by === 'person' ? `vetoed by the person: ${v.why}` : v.why)).join('; '); };
    rows.forEach(settle);
    // The datum: the person's choice; else the first preferred candidate that
    // fits; if none does, the first preferred all the same (the result says
    // it does not fit).
    const prefer = m.datum.prefer.map((k) => rows.find((r) => r.key === k));
    const datum = datumOv ? rows.find((r) => r.key === datumOv) : prefer.find((r) => r.fits) ?? prefer[0];
    if (datumOv) notes.push(`the datum is ${datum.label}, the person's choice`);
    else if (datum.key !== m.datum.prefer[0]) notes.push(`the datum is ${datum.label}: ${prefer[0].label} does not fit (${prefer[0].whyNot})`);
    if (!datum.fits) notes.push(`the datum ${datum.label} does not fit (${datum.whyNot}); it is kept as the reference`);
    // Judged marks are given against the first preferred candidate; against
    // another datum they are shifted by that datum's own mark.
    const judgedShift = Object.fromEntries(criteria.filter((c) => c.kind === 'judged').map((c) => [c.key, datum.marks[c.key] ? median(datum.marks[c.key]) : 0]));
    if (Object.values(judgedShift).some((v) => v)) notes.push(`judged marks are shifted to the datum ${datum.label}`);
    for (const r of rows) {
      r.marks_ = {}; r.spread = {};
      for (const c of criteria) {
        if (r === datum) { r.marks_[c.key] = 0; continue; }
        if (c.kind === 'measured') r.marks_[c.key] = markOf(c, r.values[c.key], datum.values[c.key], strong);
        else if (r.marks[c.key]) {
          r.marks_[c.key] = clampMark(median(r.marks[c.key]) - judgedShift[c.key]);
          if (r.marks[c.key].length > 1) r.spread[c.key] = Math.max(...r.marks[c.key]) - Math.min(...r.marks[c.key]);
        } else r.marks_[c.key] = null;
      }
      // The person's cells: a veto takes the mark out (it adds nothing and
      // plays no part in this option's gates); a nudge moves it, within ±2.
      r.toolMarks = { ...r.marks_ }; r.overridden = {};
      if (r === datum) continue;
      for (const c of criteria) {
        const k = cellKey(r.key, c.key);
        if (cellVeto.has(k)) { r.marks_[c.key] = null; r.overridden[c.key] = 'veto'; }
        else if (cellNudge.has(k)) { r.marks_[c.key] = clampMark((r.marks_[c.key] ?? 0) + cellNudge.get(k)); r.overridden[c.key] = 'nudge'; }
      }
    }
    // Ratio gates against the datum (the datum itself is exempt), each its own veto.
    for (const r of rows) {
      if (r === datum) continue;
      m.gates.forEach((g, gi) => {
        if (g.maxRatio === undefined || r.overridden[g.criterion] === 'veto') return;   // a cell the person took out plays no part
        const cr = criteria.find((x) => x.key === g.criterion);
        const b = datum.values[g.criterion], a = r.values[g.criterion];
        if (cr.kind === 'judged') {
          // A judged gate: no more than the strong mark below the datum.
          const mk = r.marks_[g.criterion];
          if (mk !== null && mk <= -2 && g.maxRatio <= strong) veto(r, `gate${gi}`, gateWhy(g, `${cr.label}: much worse than the datum (−−)`));
          return;
        }
        if (!finite(b)) return;
        if (!finite(a)) { veto(r, `gate${gi}`, gateWhy(g, `${cr.label}: no number`)); return; }
        const q = worseRatio(cr, a, b);
        if (q > g.maxRatio) veto(r, `gate${gi}`, gateWhy(g, `${cr.label} ×${fmt(q)} of the datum's (at most ×${fmt(g.maxRatio)})`));
      });
      settle(r);
    }
    // Lifts that found no veto of that id: said, not silently dropped.
    for (const o of ov) if (o.kind === 'lift' && !rows.find((r) => r.key === o.candidate).vetoes.some((v) => v.id === o.veto)) notes.push(`${rows.find((r) => r.key === o.candidate).label}: there is no veto '${o.veto}' to lift`);
    const markList = (r) => criteria.map((c) => r.marks_[c.key]);
    const totalOf = (marks, w) => marks.reduce((t, s, i) => t + (s ?? 0) * w[i], 0);
    // An option nudged by the person: each step is one weighted mark at the
    // largest weight, a fixed amount (it does not move with the weights in
    // the sensitivity draws).
    const nudgeUnit = Math.max(...weights, 0);
    for (const r of rows) { r.offset = (optNudge.get(r.key) ?? 0) * nudgeUnit; r.total = (r === datum ? 0 : totalOf(markList(r), weights)) + r.offset; }
    const better = (a, b) => b.total - a.total || (a.tieBreak ?? 0) - (b.tieBreak ?? 0) || rows.indexOf(a) - rows.indexOf(b);
    const ranking = rows.filter((r) => r.fits).sort(better);
    const eligible = ranking.filter((r) => r.suggestable);
    const best = eligible[0] ?? null;
    const above = best ? ranking.slice(0, ranking.indexOf(best)) : [];
    const sens = eligible.length > 1 ? sensitivity(eligible, criteria, weights, m.sensitivity) : null;
    // Pugh's controlled convergence, as a hint only: where the winner is worse
    // than the datum, which fitting candidates are better there (a hybrid
    // might take that from them). It changes no mark and no rank.
    const weakSpots = [];
    if (best) for (const c of criteria) {
      const mk = best.marks_[c.key];
      if (mk === null || mk >= 0) continue;
      const stronger = ranking.filter((r) => r !== best && (r.marks_[c.key] ?? -Infinity) > mk).map((r) => r.key);
      weakSpots.push({ criterion: c.key, mark: mk, strongerAt: stronger });
    }
    // Why each ranks where it does: its marks times their weights, the largest
    // gains and losses against the datum.
    const parts = (r) => criteria.map((c, i) => ({ criterion: c.key, mark: r.marks_[c.key], contribution: (r.marks_[c.key] ?? 0) * weights[i] })).filter((x) => x.contribution);
    const out = (r) => ({
      key: r.key, label: r.label, values: r.values, marks: r.marks_, spread: r.spread, total: r.total, fits: r.fits, whyNot: r.whyNot,
      toolMarks: r.toolMarks, overridden: r.overridden, offset: r.offset, nudge: optNudge.get(r.key) ?? 0, vetoes: r.vetoes,
      suggestable: r.suggestable, keep: r.keep, tieBreak: r.tieBreak, note: r.note, datum: r === datum, figures: r.figures,
      gains: parts(r).filter((x) => x.contribution > 0).sort((a, b) => b.contribution - a.contribution),
      losses: parts(r).filter((x) => x.contribution < 0).sort((a, b) => a.contribution - b.contribution),
    });
    const result = {
      version: PUGH_VERSION, title: m.title, kind: m.kind, nouns: m.nouns, strong, criteria, weights, gates: m.gates, input: matrix, nudgeUnit,
      datum: { key: datum.key, label: datum.label, fits: datum.fits, whyNot: datum.whyNot },
      candidates: rows.map(out),
      ranking: ranking.map((r) => r.key),
      suggestion: best ? { key: best.key, label: best.label, total: best.total, keep: best.keep, above: above.map((r) => r.key) } : null,
      sensitivity: sens,
      weakSpots,
      notes,
      overrides: [],
    };
    if (ov.length) {
      const base = decide({ ...matrix, overrides: [] });
      result.overrides = effectsOf(result, base, ov);
      result.before = { suggestion: base.suggestion?.label ?? null, total: base.suggestion?.total ?? null };
    }
    return result;
  }

  // What each of the person's overrides changed, in words, against the
  // decision without any of them; and what the suggestion was before.
  function effectsOf(res, base, ov) {
    const C = (r, k) => r.candidates.find((c) => c.key === k), L = (k) => C(res, k).label, crit = (k) => res.criteria.find((c) => c.key === k).label;
    const sym = (v) => (v === null || v === undefined ? '?' : SYMBOL[Math.round(v)]);
    const list = ov.map((o) => {
      let effect = '';
      if (o.kind === 'criterion') {
        const cr = res.criteria.find((c) => c.key === o.criterion);
        effect = [o.weight !== undefined ? `${cr.label}: weight ${fmt(cr.defaults.weight)} → ${fmt(o.weight)}` : '', o.tolerance !== undefined ? `${cr.label}: tolerance ${fmt(cr.defaults.tolerance)} → ${fmt(o.tolerance)}` : ''].filter(Boolean).join('; ');
      } else if (o.kind === 'cell') {
        const was = C(res, o.candidate).toolMarks[o.criterion];
        effect = C(res, o.candidate).datum ? `${L(o.candidate)} · ${crit(o.criterion)}: the datum's cell is 0 by definition; not applied`
          : o.action === 'veto' ? `${L(o.candidate)} · ${crit(o.criterion)}: ${sym(was)} taken out of the calculation`
            : `${L(o.candidate)} · ${crit(o.criterion)}: ${sym(was)} → ${sym(C(res, o.candidate).marks[o.criterion])}`;
      } else if (o.kind === 'option') effect = o.action === 'veto' ? `${L(o.candidate)}: vetoed, out of the ranking` : `${L(o.candidate)}: nudged ${o.by > 0 ? 'up' : 'down'} ${Math.abs(o.by)} step${Math.abs(o.by) > 1 ? 's' : ''}, ${o.by > 0 ? '+' : '−'}${fmt(Math.abs(o.by) * res.nudgeUnit)} on its total (one step: a mark at the largest weight, ${fmt(res.nudgeUnit)}); total now ${signed(C(res, o.candidate).total)}`;
      else if (o.kind === 'lift') {
        const c = C(res, o.candidate), v = c.vetoes.find((x) => x.id === o.veto), open = c.vetoes.filter((x) => !x.lifted).length;
        effect = !v ? `${L(o.candidate)}: no veto '${o.veto}' to lift` : `${L(o.candidate)}: the tool's veto lifted (${v.why}); ${open ? `${open} veto${open > 1 ? 'es' : ''} remain${open > 1 ? '' : 's'}` : 'it is back in'}`;
      } else if (o.kind === 'datum') effect = `the datum: ${base.datum.label} → ${res.datum.label}`;
      return { ...o, effect };
    });
    return list;
  }

  // ---- Reverse sensitivity -----------------------------------------------------
  // The totals are linear in the weights, T_k = Σ w_i m_ki, so each question
  // has an exact answer (pugh.md, "Sensitivity"). Among the candidates the
  // suggestion is chosen from, the first being the winner:
  //   tie       for each runner-up, the smallest change of one weight at which
  //             it ties the winner (the weight kept ≥ 0)
  //   minChange the smallest Euclidean change of all weights together that
  //             makes it tie (kept ≥ 0), as a share of the weights' size
  //   share     SMAA's rank-1 acceptability: the share of seeded draws, each
  //             weight uniform within ±step of its own (at least 0.01), and
  //             each multi-rater mark one rater drawn at random, it wins
  // Reasonable: every weight within ±step of its default and above 0. The
  // choice holds ('holds') when no reasonable single change ties a runner-up
  // and the winner takes at least holdShare of the draws; else it depends on
  // the weights ('depends'). The words are about the decision, never about a
  // controller's robustness.
  function sensitivity(cands, criteria, w, opts = DEFAULTS) {
    const { step, draws, seed, holdShare, runnersUp } = { ...DEFAULTS, ...opts };
    // An option the person nudged carries its fixed offset (decide()).
    const marks = cands.map((r) => criteria.map((c) => r.marks_[c.key])), off = cands.map((r) => r.offset ?? 0);
    const T = (k, ww, mm = marks) => mm[k].reduce((t, s, i) => t + (s ?? 0) * ww[i], off[k]);
    const iw = 0, list = [];
    for (let j = 1; j < cands.length; j++) {
      const gap = T(iw, w) - T(j, w);
      let tie = null;
      criteria.forEach((cr, i) => {
        const slope = (marks[j][i] ?? 0) - (marks[iw][i] ?? 0);
        if (!slope) return;
        const d = gap / slope;
        if (w[i] + d < 0) return;
        if (!tie || Math.abs(d) < Math.abs(tie.d)) tie = { i, d };
      });
      // The same total now, with no weight that tells them apart: tied now.
      if (!tie && Math.abs(gap) < 1e-9) tie = { i: -1, d: 0 };
      const D = criteria.map((_, i) => (marks[j][i] ?? 0) - (marks[iw][i] ?? 0));
      let ww = w.slice();
      for (let it = 0; it < 20; it++) {
        const dw = D.reduce((t, x, i) => t + x * ww[i], 0);
        if (dw >= -1e-12) break;
        const free = D.map((x, i) => (ww[i] > 0 || x > 0 ? x : 0)), nn = free.reduce((t, x) => t + x * x, 0);
        if (!nn) { ww = null; break; }
        ww = ww.map((x, i) => Math.max(0, x - (dw / nn) * free[i]));
      }
      list.push({
        key: cands[j].key, label: cands[j].label, total: T(j, w),
        tie: !tie ? null : tie.i < 0 ? { criterion: null, from: null, to: null, now: true, reasonable: true }
          : { criterion: criteria[tie.i].key, from: w[tie.i], to: w[tie.i] + tie.d, now: Math.abs(tie.d) < 1e-9, reasonable: Math.abs(tie.d) <= step && w[tie.i] + tie.d > 0 },
        minChange: ww ? { rel: Math.hypot(...ww.map((x, i) => x - w[i])) / (Math.hypot(...w) || 1), maxStep: Math.max(...ww.map((x, i) => Math.abs(x - w[i]))) } : null,
      });
    }
    // The draws: weights first (in criterion order), then a rater for each
    // multi-rater mark (in candidate, criterion order), so a matrix without
    // raters draws exactly the weights.
    const r = rng(seed), wins = new Array(cands.length).fill(0);
    const multi = [];
    cands.forEach((c, k) => criteria.forEach((cr, i) => { if ((c.marks[cr.key]?.length ?? 0) > 1 && c.marks_[cr.key] !== null) multi.push({ k, i, list: c.marks[cr.key], shift: c.marks_[cr.key] - median(c.marks[cr.key]) }); }));
    for (let n = 0; n < draws; n++) {
      const ww = w.map((x) => Math.max(0.01, x - step + 2 * step * r()));
      let mm = marks;
      if (multi.length) {
        mm = marks.map((row) => row.slice());
        for (const { k, i, list, shift } of multi) mm[k][i] = clampMark(list[Math.min(list.length - 1, Math.floor(r() * list.length))] + shift);
      }
      let bk = 0, bt = -Infinity;
      cands.forEach((c, k) => { const t = T(k, ww, mm); if (t > bt + 1e-12 || (Math.abs(t - bt) <= 1e-12 && (c.tieBreak ?? 0) < (cands[bk].tieBreak ?? 0))) { bt = t; bk = k; } });
      wins[bk]++;
    }
    const share = wins.map((x) => (draws ? x / draws : 0));
    list.forEach((x, j) => { x.share = share[j + 1]; });
    const reasonableFlip = list.some((x) => x.tie?.reasonable);
    return {
      winner: cands[0].key, verdict: !reasonableFlip && share[0] >= holdShare ? 'holds' : 'depends',
      share: share[0], step, draws, seed, holdShare,
      runnersUp: list.slice(0, runnersUp), all: list,
    };
  }

  // ---- Reports -----------------------------------------------------------------
  // The report is HTML (input 59): one standalone page, its graphs inline SVG,
  // no script, printable. Bottom line first (the suggestion, whether it holds,
  // the main reason), then the matrix, then one compact section per option
  // that fits (why it ranks where it does, its weak spots, at most two
  // figures), a line for each one that does not. The page budget: at most one
  // printed page per option compared, the matrix aside. Markdown stays as the
  // command line's text (renderMarkdown).

  function fmt(v, digits = 3) {
    if (v === null || v === undefined) return '—';
    if (!Number.isFinite(v)) return v > 0 ? '∞' : String(v);
    if (v !== 0 && (Math.abs(v) >= 1e4 || Math.abs(v) < 1e-3)) return v.toExponential(1);
    return String(Number(v.toPrecision(digits)));
  }
  const signed = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmt(Math.abs(v))}`;
  const pct = (v) => `${fmt(100 * v)} %`;
  const labelOf = (res, key) => res.candidates.find((c) => c.key === key)?.label ?? key;
  const critLabel = (res, key) => res.criteria.find((c) => c.key === key)?.label ?? key;
  const listOf = (res, xs, n = 3) => xs.slice(0, n).map((x) => `${critLabel(res, x.criterion)} (${SYMBOL[Math.round(x.mark)]})`).join(', ');

  // The main reason, in words: the suggestion's largest gains against the datum.
  function mainReason(res) {
    const c = res.suggestion && res.candidates.find((x) => x.key === res.suggestion.key);
    if (!c) return '';
    if (c.datum) return res.ranking.length > 1 ? 'no other option that fits beats it' : 'it is the only option that fits';
    return c.gains.length ? `mainly ${listOf(res, c.gains, 2)}${c.losses.length ? `, against ${listOf(res, c.losses, 1)}` : ''}` : '';
  }

  // The bottom line, one sentence: what to choose, how much it depends on the
  // weights, and the main reason.
  function bottomLine(res) {
    const s = res.suggestion;
    if (!s) return 'No candidate fits.';
    const head = s.keep ? `Keep **${s.label}**: nothing beats it` : `Suggestion: **${s.label}** (${signed(s.total)} against the datum ${res.datum.label})`;
    const sv = res.sensitivity;
    const rob = !sv ? 'the only candidate that fits and may be suggested'
      : sv.verdict === 'holds' ? `the choice holds: it wins ${pct(sv.share)} of the weight draws within ±${fmt(sv.step)}`
        : `the choice depends on the weights: it wins ${pct(sv.share)} of the weight draws within ±${fmt(sv.step)}${(() => { const f = sv.runnersUp.find((x) => x.tie?.reasonable || x.tie?.now); return f ? `; ${f.label} ${f.tie.now ? 'ties it now' : `ties if ${critLabel(res, f.tie.criterion)} goes ${fmt(f.tie.from)} → ${fmt(f.tie.to)}`}` : ''; })()}`;
    const why = s.keep ? '' : mainReason(res);
    const above = s.above.length ? ` Ranked above it but not to be suggested: ${s.above.map((k) => labelOf(res, k)).join(', ')}.` : '';
    return `${head}; ${rob}${why ? `; ${why}` : ''}.${above}`;
  }

  function runnerRows(res) {
    return (res.sensitivity?.runnersUp ?? []).map((x) => [
      x.label, signed(x.total),
      !x.tie ? 'no single weight' : x.tie.now ? 'tied now (the tie-break decides)' : `${critLabel(res, x.tie.criterion)} ${fmt(x.tie.from)} → ${fmt(x.tie.to)}`,
      !x.tie || x.tie.now ? (x.tie?.now ? 'yes' : '—') : x.tie.reasonable ? 'yes' : 'no',
      x.minChange ? `${pct(x.minChange.rel)} (largest ${fmt(x.minChange.maxStep)})` : '—',
      pct(x.share),
    ]);
  }

  // Text for a terminal or an agent (the command line's default output).
  function renderMarkdown(res) {
    const L = [`# ${res.title}`, '', bottomLine(res), ''];
    const cols = res.candidates;
    L.push(`Datum: **${res.datum.label}**. Marks: ++ much better, + better, S same (within the tolerance), − worse, −− much worse (beyond ×${fmt(res.strong)}), ? not judged (counts as S).`, '');
    L.push(`| Criterion (weight) | ${cols.map((c) => c.label).join(' | ')} |`, `|---|${cols.map(() => ':-:').join('|')}|`);
    for (const cr of res.criteria) L.push(`| ${cr.label}${cr.kind === 'judged' ? ' (judged)' : ''} (${fmt(cr.weight)}) | ${cols.map((c) => (c.datum ? 'D' : c.marks[cr.key] === null ? '?' : SYMBOL[Math.round(c.marks[cr.key])] + (c.spread[cr.key] ? ` ±${fmt(c.spread[cr.key] / 2)}` : ''))).join(' | ')} |`);
    L.push(`| **Weighted** | ${cols.map((c) => (c.datum ? '0' : signed(c.total))).join(' | ')} |`);
    L.push(`| **Fits** | ${cols.map((c) => (c.fits ? 'yes' : 'no')).join(' | ')} |`, '');
    L.push(`Ranking: ${res.ranking.map((k, i) => `${i + 1}. ${labelOf(res, k)} (${signed(cols.find((c) => c.key === k).total)})`).join('; ') || 'none fits'}.`);
    const out = cols.filter((c) => !c.fits);
    if (out.length) L.push('', `Not ranked: ${out.map((c) => `${c.label}: ${c.whyNot}`).join('; ')}.`);
    if (res.sensitivity) {
      L.push('', `Runners-up (reasonable: every weight within ±${fmt(res.sensitivity.step)} of its default):`, '', '| Runner-up | Total | Ties when one weight changes | Reasonable | All weights together | Share of draws |', '|---|---|---|---|---|---|');
      for (const row of runnerRows(res)) L.push(`| ${row.join(' | ')} |`);
    }
    if (res.weakSpots.length) L.push('', `Weak spots of the suggestion (for a hybrid): ${res.weakSpots.map((w) => `${critLabel(res, w.criterion)} (${SYMBOL[Math.round(w.mark)]}${w.strongerAt.length ? `; better there: ${w.strongerAt.map((k) => labelOf(res, k)).join(', ')}` : ''})`).join('; ')}.`);
    if (res.notes.length) L.push('', ...res.notes.map((n) => `Note: ${n}.`));
    return `${L.join('\n')}\n`;
  }

  const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const bold = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // ---- Figures (inline SVG) ---------------------------------------------------

  // Colours are the page's design-system tokens, with the light theme's values
  // as fallbacks, so a report reads on screen, in the page and on paper.
  // Lines are classes (pl-option, pl-datum, pl-reference, pl-other): their
  // colours and dashes come from the style sheet (Loop Tuner's: the scope's
  // screen and channel colours, input 65).
  const n4 = (v) => Number(v.toFixed(2));
  // Round axis ends and a few ticks (1, 2, 5 × 10ⁿ).
  function ticks(lo, hi, n = 4) {
    if (!(hi > lo)) { hi = lo + 1; lo -= 1; }
    const raw = (hi - lo) / n, p = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 5, 10].map((k) => k * p).find((x) => x >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9 * step; v += step) out.push(Number(v.toPrecision(12)));
    return out;
  }
  // At most 300 points a series, the extremes of each bucket kept.
  function thin(x, y, x0, x1, n = 150) {
    const idx = [];
    for (let i = 0; i < x.length; i++) if (x[i] >= x0 && x[i] <= x1 && finite(y[i])) idx.push(i);
    if (idx.length <= 2 * n) return idx;
    const out = [], per = idx.length / n;
    for (let b = 0; b < n; b++) {
      const part = idx.slice(Math.floor(b * per), Math.floor((b + 1) * per));
      if (!part.length) continue;
      let lo = part[0], hi = part[0];
      for (const i of part) { if (y[i] < y[lo]) lo = i; if (y[i] > y[hi]) hi = i; }
      out.push(...(lo < hi ? [lo, hi] : lo > hi ? [hi, lo] : [lo]));
    }
    return out;
  }

  function plotSvg(fig, { width = 320, panelHeight = 90 } = {}) {
    if (fig.svg) return fig.svg;
    const left = 38, right = 6, top = 4, gap = 8, bottom = 22;
    const all = fig.panels.flatMap((p) => p.series);
    const xs = all.flatMap((sr) => [Math.min(...sr.x), Math.max(...sr.x)]);
    const [x0, x1] = fig.xRange ?? [Math.min(...xs), Math.max(...xs)];
    const H = top + fig.panels.length * (panelHeight + gap) - gap + bottom, W = width;
    const X = (v) => left + ((v - x0) / (x1 - x0 || 1)) * (W - left - right);
    const g = [`<svg class="rpt-plot" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(fig.title)}">`];
    fig.panels.forEach((p, k) => {
      const y0p = top + k * (panelHeight + gap);
      let lo = Infinity, hi = -Infinity;
      for (const sr of p.series) for (const i of thin(sr.x, sr.y, x0, x1)) { lo = Math.min(lo, sr.y[i]); hi = Math.max(hi, sr.y[i]); }
      if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
      const pad = (hi - lo) * 0.06 || Math.abs(hi) * 0.1 || 1; lo -= pad; hi += pad;
      const Y = (v) => y0p + panelHeight - ((v - lo) / (hi - lo)) * panelHeight;
      g.push(`<rect class="pl-frame" x="${left}" y="${y0p}" width="${W - left - right}" height="${panelHeight}"/>`);
      for (const t of ticks(lo, hi, 3)) g.push(`<line class="pl-grid" x1="${left}" x2="${W - right}" y1="${n4(Y(t))}" y2="${n4(Y(t))}"/><text x="${left - 3}" y="${n4(Y(t) + 3)}" text-anchor="end">${esc(fmt(t))}</text>`);
      if (p.yLabel) g.push(`<text x="${left + 3}" y="${y0p + 9}">${esc(p.yLabel)}</text>`);
      // The option on top: draw reference, datum, other, then the option.
      const order = ['reference', 'datum', 'other', 'option'];
      for (const sr of [...p.series].sort((a, b) => order.indexOf(a.role) - order.indexOf(b.role))) {
        const pts = thin(sr.x, sr.y, x0, x1).map((i) => `${n4(X(sr.x[i]))},${n4(Y(Math.min(hi, Math.max(lo, sr.y[i]))))}`).join(' ');
        g.push(`<polyline class="pl-s pl-${sr.role}" points="${pts}"/>`);
      }
    });
    const yb = H - bottom;
    for (const t of ticks(x0, x1, 5)) g.push(`<text x="${n4(X(t))}" y="${yb + 10}" text-anchor="middle">${esc(fmt(t))}</text>`);
    if (fig.xLabel) g.push(`<text x="${W - right}" y="${yb + 19}" text-anchor="end">${esc(fig.xLabel)}</text>`);
    // The legend, once, from the first panel's series.
    let lx = left;
    for (const sr of fig.panels[0].series) {
      if (!sr.label) continue;
      g.push(`<line class="pl-s pl-${sr.role}" x1="${lx}" x2="${lx + 12}" y1="${yb + 16}" y2="${yb + 16}"/><text class="pl-key" x="${lx + 15}" y="${yb + 19}">${esc(sr.label)}</text>`);
      lx += 22 + 6.2 * sr.label.length;
    }
    g.push('</svg>');
    return g.join('');
  }

  // The sensitivity at a glance: the winner's share of the draws, and for each
  // runner-up the weight it hangs on: its default, the reasonable band
  // (±step), and the tie point.
  function sensitivitySvg(res, { width = 480 } = {}) {
    const sv = res.sensitivity;
    if (!sv) return '';
    const rows = sv.runnersUp.filter((x) => x.tie && !x.tie.now), rowH = 22, top = 24, left = 190, right = 30;
    const H = top + Math.max(1, rows.length) * rowH + 12, W = width;
    const hiW = Math.max(1, ...rows.map((x) => Math.max(x.tie.to, x.tie.from + sv.step))) * 1.05;
    const X = (v) => left + (Math.max(0, Math.min(hiW, v)) / hiW) * (W - left - right);
    const g = [`<svg class="rpt-sensplot" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="weight sensitivity">`];
    const winW = (W - left - right) * sv.share;
    g.push(`<text x="0" y="12">${esc(labelOf(res, sv.winner).slice(0, 34))} wins</text><rect class="sp-frame" x="${left}" y="4" width="${W - left - right}" height="10"/><rect class="sp-${sv.verdict}" x="${left}" y="4" width="${n4(winW)}" height="10"/><text x="${W - right + 3}" y="12">${esc(pct(sv.share))}</text>`);
    rows.forEach((x, k) => {
      const y = top + k * rowH + 10, w = x.tie.from;
      g.push(`<text x="0" y="${y - 2}">${esc(x.label.slice(0, 34))}</text><text class="dim" x="0" y="${y + 8}">ties if ${esc(critLabel(res, x.tie.criterion).slice(0, 26))}: ${esc(fmt(w))} → ${esc(fmt(x.tie.to))}</text>`);
      g.push(`<line class="sp-line" x1="${left}" x2="${W - right}" y1="${y}" y2="${y}"/>`);
      g.push(`<rect class="sp-band" x="${n4(X(Math.max(0, w - sv.step)))}" y="${y - 4}" width="${n4(X(w + sv.step) - X(Math.max(0, w - sv.step)))}" height="8"/>`);
      g.push(`<line class="sp-default" x1="${n4(X(w))}" x2="${n4(X(w))}" y1="${y - 5}" y2="${y + 5}"/>`);
      g.push(`<path class="sp-tie${x.tie.reasonable ? ' reasonable' : ''}" d="M${n4(X(x.tie.to))},${y - 5} l4,5 l-4,5 l-4,-5 z"/>`);
    });
    if (!rows.length) g.push(`<text class="dim" x="0" y="${top + 10}">No single weight makes a runner-up tie.</text>`);
    g.push(`<text class="dim" x="${left}" y="${H - 1}">the weight: | its default, band: ±${esc(fmt(sv.step))} (reasonable), ◆ where they tie</text>`);
    g.push('</svg>');
    return g.join('');
  }

  // ---- The HTML report ------------------------------------------------------------
  // Interactive (input 61): the report carries its matrix and this engine's
  // own source, so in a browser the person can change a weight, veto or nudge
  // a mark or an option, veto a gate's verdict, choose another datum, each
  // with a comment, and everything is decided again at once. Without scripts
  // it reads as the static report it is. Controls are hidden in print, and
  // the person's changes print under the bottom line.

  // Its look is the host's one style sheet (input 65: "one master style
  // sheet. Everything goes through there"): the report writes classes only
  // (.rpt…, .btn, .dialog, the plots' .rpt-plot), never a colour, a size or a
  // style of its own. Loop Tuner's sheet is src/ui/style.css; tools/build.mjs's
  // reportStyle() hands it over as opts.style, and the report embeds it.
  // Without it the page is plain HTML. A saved report carries the same sheet.
  const MAX_FIGURES = 2;
  const THEMES = [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']];

  // The report as a standalone HTML page (standalone: false gives the
  // <section> alone). style: { css, license } (above); theme: 'light' or
  // 'dark' fixes the page's theme (data-theme), else it follows the system.
  // open: the keys of the options shown open. sections: false leaves each
  // option's panel out (what the page budget is measured against).
  // interactive: false leaves out the matrix and the engine (a static page).
  //   One table, an option a row (inputs 66, 67): the criteria are its
  //   columns, their names on end, each one's weight and tolerance in the
  //   head (the only place they are changed); the datum is the first row,
  //   then the ranking, then the vetoed options, greyed. A row, collapsed,
  //   is the option's bottom line: its name, its total (× when vetoed) and
  //   its marks, each changed in place. It opens (a <details>) to its
  //   vetoes, its notes, its actions and its figures. Whatever the person
  //   can change is a field (.field), the page's one look for "enter here";
  //   nothing is said twice.
  function renderHtml(res, { standalone = true, sections = true, interactive = true, live = false, style = null, theme = 'system', open = [] } = {}) {
    const rows = [res.datum.key, ...res.ranking.filter((k) => k !== res.datum.key), ...res.candidates.filter((c) => !c.fits && c.key !== res.datum.key).map((c) => c.key)].map((k) => res.candidates.find((c) => c.key === k));
    const cls = (mk) => (mk > 0 ? 'plus' : mk < 0 ? 'minus' : '');
    const btn = (label, data, aria = '') => `<button type="button" class="btn btn-sm" ${Object.entries(data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ')}${aria ? ` aria-label="${esc(aria)}"` : ''}>${esc(label)}</button>`;
    // A value the person can change: a field, with its own name for a reader.
    const field = (text, data, aria, extra = '') => `<button type="button" class="field field-sm rpt-field${extra ? ` ${extra}` : ''}" ${Object.entries(data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ')} aria-label="${esc(aria)}">${text}</button>`;
    const sym = (v) => (v === null || v === undefined ? '?' : SYMBOL[Math.round(v)]);
    const pctTol = (t) => `±${fmt(100 * t)} %`;
    const words = (t) => t.split(' ').map((w) => `<span class="rpt-word">${esc(w)}</span>`).join(' ');
    // One page with nothing open (input 68): what it is, the bottom line,
    // the keys and the person's changes as one line, the sensitivity, the
    // table. Everything else opens: the changes, the runners-up, each row.
    const nIn = res.candidates.filter((c) => c.fits).length, nOut = res.candidates.length - nIn;
    const h = [`<section class="rpt${live ? ' live' : ''}">`, `<h1>${esc(res.kind)}: ${esc(res.title)}</h1>`,
      `<p class="dim rpt-sub">${res.candidates.length} ${esc(res.nouns.options)} compared on ${res.criteria.length} criteria against ${esc(res.nouns.datum)}, ${esc(res.datum.label)}; ${nIn} in${nOut ? `, ${nOut} vetoed` : ''}.${res.datum.fits ? '' : ` <span class="minus">${esc(res.datum.label)} itself fails: ${esc(res.datum.whyNot)}.</span>`}</p>`,
      `<p class="rpt-bottom" data-bottom>${bold(bottomLine(res))}</p>`];
    // The keys, live only: Undo, Save, Export, Print (what is open, or
    // everything), and the theme (the page's own; print is always light).
    const themes = `<span class="seg" role="group" aria-label="Theme">${THEMES.map(([k, label]) => `<button type="button" class="btn btn-sm" data-theme-set="${k}" aria-pressed="${k === theme}">${label}</button>`).join('')}</span>`;
    h.push(`<div class="rpt-tools rpt-live">${btn('Undo', { tool: 'undo' })}${btn('Save report', { tool: 'save' })}${btn('Export changes', { tool: 'export' })}${btn('Print', { tool: 'print' })}${btn('Print with everything open', { tool: 'print-all' })}${themes}</div>`);
    // The person's changes: one line, their list behind it.
    if (res.overrides?.length) {
      const n = res.overrides.length, was = res.before && res.before.suggestion !== (res.suggestion?.label ?? null) ? `; without them the suggestion was ${esc(res.before.suggestion ?? 'none')}` : '';
      h.push(`<details class="rpt-more rpt-person" data-more="changes"${open.includes('changes') ? ' open' : ''}><summary class="disclosure"><span class="chev" aria-hidden="true"></span>${n} change${n > 1 ? 's' : ''} by you${was}</summary>${res.overrides.map((o) => `<p>${esc(o.effect)} <span class="dim">— “${esc(o.comment)}”</span></p>`).join('')}</details>`);
    }
    // The sensitivity, said for what it is; the runners-up's numbers behind it.
    if (res.sensitivity) {
      h.push(`<figure class="rpt-sens">${sensitivitySvg(res)}<figcaption>How far a weight must move before another option wins</figcaption></figure>`);
      h.push(`<details class="rpt-more" data-more="runners"${open.includes('runners') ? ' open' : ''}><summary class="disclosure"><span class="chev" aria-hidden="true"></span>The runners-up in numbers</summary><div class="rpt-scroll"><table><thead><tr>${['Runner-up', 'Total', 'Ties when one weight changes', `Reasonable (±${esc(fmt(res.sensitivity.step))})`, 'All weights together', 'Share of draws'].map((t) => `<th>${t}</th>`).join('')}</tr></thead><tbody>${runnerRows(res).map((row) => `<tr>${row.map((v) => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`);
    }
    h.push(`<p class="dim rpt-key">Datum: <strong>${esc(res.datum.label)}</strong>, the first row. ++ much better, + better, S the same within the tolerance, − worse, −− much worse (beyond ×${esc(fmt(res.strong))}), ? not judged; × after a total: vetoed. <span class="rpt-live">A boxed value can be changed; a dashed frame, changed by you; a row opens to its vetoes, actions and plots.</span></p>`);
    // The head: the criteria on end, then their weights and tolerances.
    const head = [`<div class="rpt-grid rpt-head"><span class="rpt-name">Option</span><span class="rpt-total">Total</span>${res.criteria.map((cr) => `<span class="rpt-c"><span class="rpt-vhead">${words(cr.label)}${cr.kind === 'judged' ? ' <span class="rpt-word">(judged)</span>' : ''}</span></span>`).join('')}</div>`];
    head.push(`<div class="rpt-grid"><span class="rpt-name">Weight</span><span class="rpt-total"></span>${res.criteria.map((cr, i) => `<span class="rpt-c">${field(esc(fmt(res.weights[i])), { weight: cr.key }, `${cr.label}: weight ${fmt(res.weights[i])}; change`, res.weights[i] !== cr.defaults.weight ? 'changed' : '')}</span>`).join('')}</div>`);
    head.push(`<div class="rpt-grid"><span class="rpt-name" title="the band within which a mark is S">Tolerance</span><span class="rpt-total"></span>${res.criteria.map((cr) => `<span class="rpt-c">${cr.kind === 'measured' ? field(esc(pctTol(cr.tolerance)), { tol: cr.key }, `${cr.label}: tolerance ${pctTol(cr.tolerance)}; change`, `rpt-tol${cr.tolerance !== cr.defaults.tolerance ? ' changed' : ''}`) : '<span class="dim">—</span>'}</span>`).join('')}</div>`);
    // A row per option: its bottom line in the <summary>, the rest in its panel.
    const optRows = rows.map((c) => {
      const standing = c.vetoes.filter((v) => !v.lifted);
      const total = `${c.datum && !c.offset ? '0' : esc(signed(c.total))}${c.fits ? '' : `<span class="rpt-x" title="${esc(c.whyNot)}"> ×</span>`}`;
      const marks = res.criteria.map((cr) => {
        if (c.datum) return '<span class="rpt-c dim">D</span>';
        const mk = c.marks[cr.key], ov = c.overridden?.[cr.key];
        const text = ov === 'veto' ? `<span class="vetoed">${esc(sym(c.toolMarks[cr.key]))}</span>` : esc(sym(mk));
        return `<span class="rpt-c">${field(text, { cell: `${c.key}|${cr.key}` }, `${c.label}, ${cr.label}: ${ov === 'veto' ? 'vetoed' : sym(mk)}; change`, [ov === 'veto' ? '' : cls(mk ?? 0), ov ? 'changed' : ''].join(' ').trim())}</span>`;
      }).join('');
      const summary = `<summary class="rpt-grid"><span class="rpt-name"><span class="chev" aria-hidden="true"></span><span>${words(c.label)}</span></span><span class="rpt-total${c.nudge ? ' changed' : ''}" data-total="${esc(c.key)}" data-value="${c.total}">${total}</span>${marks}</summary>`;
      const panel = [];
      if (sections) {
        if (c.vetoes.length) panel.push(`<ul class="rpt-vetoes">${c.vetoes.map((v) => `<li class="${v.lifted ? 'dim' : 'minus'}">${v.by === 'person' ? 'Vetoed by the person' : 'The tool’s veto'}: ${esc(v.why)}${v.lifted ? ` <span class="dim">— lifted: “${esc(v.lifted)}”</span>` : ''} <span class="rpt-live">${v.by === 'person' ? btn('Remove my veto', { act: 'unveto', cand: c.key }) : v.lifted ? btn('Restore', { restore: `${c.key}|${v.id}` }) : btn('Lift…', { lift: `${c.key}|${v.id}` })}</span></li>`).join('')}</ul>`);
        if (c.datum) panel.push('<p class="dim">The datum: every other option is marked against it.</p>');
        if (c.key === res.suggestion?.key && res.weakSpots.length) panel.push(`<p class="dim">Weak spots (for a hybrid): ${esc(res.weakSpots.map((w) => `${critLabel(res, w.criterion)}${w.strongerAt.length ? ` (better there: ${w.strongerAt.slice(0, 3).map((k) => labelOf(res, k)).join(', ')})` : ''}`).join('; '))}.</p>`);
        if (!c.suggestable) panel.push('<p class="dim">Not to be suggested (it needs a change outside the options), but compared.</p>');
        if (c.note) panel.push(`<p class="dim">${esc(c.note)}</p>`);
        const acts = [standing.some((v) => v.by === 'person') ? '' : btn('Veto the option…', { act: 'veto', cand: c.key }), btn('Nudge up…', { act: 'up', cand: c.key }), btn('Nudge down…', { act: 'down', cand: c.key }), c.datum ? '' : btn('Make it the datum…', { act: 'datum', cand: c.key })].join('');
        panel.push(`<div class="rpt-acts rpt-live">${acts}</div>`);
        // Figures while the option is in (input 62: a vetoed option's come
        // back with it).
        const figs = c.fits ? (c.figures ?? []).slice(0, MAX_FIGURES) : [];
        if (figs.length) panel.push(`<div class="rpt-figs">${figs.map((f) => `<figure>${plotSvg(f)}<figcaption>${esc(f.title)}</figcaption></figure>`).join('')}</div>`);
      }
      return `<details class="rpt-opt${c.fits ? '' : ' out'}" data-section="${esc(c.key)}" data-fits="${c.fits}"${open.includes(c.key) ? ' open' : ''}>${summary}<div class="rpt-panel">${panel.join('')}</div></details>`;
    });
    // A table wider than its place scrolls in its own box, the names held.
    h.push(`<div class="rpt-scroll">${head.join('')}${optRows.join('')}</div>`);
    if (res.notes.length) h.push(`<details class="rpt-more" data-more="notes"${open.includes('notes') ? ' open' : ''}><summary class="disclosure"><span class="chev" aria-hidden="true"></span>${res.notes.length} note${res.notes.length > 1 ? 's' : ''} from the tool</summary>${res.notes.map((n) => `<p class="dim">${esc(n)}.</p>`).join('')}</details>`);
    h.push('</section>');
    const body = h.join('\n');
    if (!standalone) return body;
    const SCRIPT = 'scr' + 'ipt', end = `</${SCRIPT}>`;
    const embedded = !interactive || !res.input ? '' : `\n<${SCRIPT} type="application/json" id="pugh-matrix">${JSON.stringify(res.input).replace(/</g, '\\u003c')}${end}\n<${SCRIPT}>(function () { var E = (${pughEngine.toString().replace(/<\/(script)/gi, '<\\/$1')})(); E.boot(document); })();${end}`;
    const sheet = style ? `<style id="rpt-style"${style.license ? ` data-license="${esc(style.license)}"` : ''}>\n${style.css.replace(/<\/(style)/gi, '<\\/$1')}\n</style>` : '';
    return `<!doctype html>\n<html lang="en"${theme === 'light' || theme === 'dark' ? ` data-theme="${theme}"` : ''}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(res.title)}</title>${sheet}</head><body>\n${body}${embedded}\n</body></html>\n`;
  }

  // ---- In the browser -------------------------------------------------------
  // boot(document): read the matrix the report carries, decide again on every
  // change, and draw the report in place. State: the overrides, and an undo
  // stack of them. A host page may set window.pughDownload(name, text, type)
  // to take Save and Export through its own download path (Loop Tuner's).

  function boot(doc) {
    const win = doc.defaultView, data = JSON.parse(doc.getElementById('pugh-matrix').textContent);
    const base = { ...data, overrides: [] };
    let overrides = (data.overrides ?? []).slice();
    const undo = [];
    let res = null;
    const section = () => doc.querySelector('section.rpt');
    // The theme is the page's: data-theme on <html>, none for the system's.
    const html = doc.documentElement, themeNow = () => html.dataset.theme || 'system';
    // Drawn again on every change, the rows the person opened stay open and
    // the table stays where it was scrolled to.
    function render(focus) {
      res = decide({ ...base, overrides });
      const open = [...doc.querySelectorAll('details.rpt-opt[open], details.rpt-more[open]')].map((d) => d.dataset.section ?? d.dataset.more);
      const left = doc.querySelector('.rpt-scroll')?.scrollLeft ?? 0;
      section().outerHTML = renderHtml(res, { standalone: false, live: true, theme: themeNow(), open });
      const box = doc.querySelector('.rpt-scroll');
      if (box) box.scrollLeft = left;
      win.pughState = { overrides: overrides.slice(), result: res };
      if (focus) doc.querySelector(focus)?.focus();
    }
    function change(next, focus) { undo.push(overrides); overrides = next; render(focus); }
    function download(name, text, type) {
      if (typeof win.pughDownload === 'function') return win.pughDownload(name, text, type);
      const a = doc.createElement('a');
      a.href = win.URL.createObjectURL(new win.Blob([text], { type }));
      a.download = name;
      doc.body.appendChild(a); a.click(); a.remove();
    }
    const slug = String(data.title ?? 'decision').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'decision';
    // The dialog: what to do, and why (a comment for every change).
    const dlg = doc.createElement('dialog');
    dlg.className = 'dialog rpt-dialog';
    doc.body.appendChild(dlg);
    function ask(title, choices, { weight = null, focus } = {}) {
      dlg.innerHTML = `<form method="dialog"><strong>${esc(title)}</strong>${weight !== null ? `<label>Weight <input id="pugh-weight" type="number" min="0" step="0.5" value="${esc(weight)}"></label>` : ''}<label>Why (kept with the change) <textarea id="pugh-comment" rows="2"></textarea></label><p id="pugh-error" class="dim" role="alert"></p><div class="rpt-acts">${choices.map((c) => `<button type="button" class="btn btn-sm" data-do="${esc(c.id)}">${esc(c.label)}</button>`).join('')}<button type="button" class="btn btn-sm" data-do="cancel">Cancel</button></div></form>`;
      dlg.onclick = (e) => {
        const b = e.target.closest('[data-do]');
        if (!b) return;
        if (b.dataset.do === 'cancel') { dlg.close(); doc.querySelector(focus)?.focus(); return; }
        const choice = choices.find((c) => c.id === b.dataset.do), comment = dlg.querySelector('#pugh-comment').value.trim();
        if (choice.needsComment !== false && !comment) { dlg.querySelector('#pugh-error').textContent = 'Say why: every change carries a comment.'; dlg.querySelector('#pugh-comment').focus(); return; }
        const w = dlg.querySelector('#pugh-weight');
        const next = choice.apply(comment, w ? Number(w.value) : null);
        if (next === null) { dlg.querySelector('#pugh-error').textContent = 'A weight is a number ≥ 0.'; return; }
        dlg.close();
        change(next, focus);
      };
      dlg.showModal();
      (dlg.querySelector('#pugh-weight') ?? dlg.querySelector('#pugh-comment')).focus();
    }
    const without = (pred) => overrides.filter((o) => !pred(o));
    const sym = (v) => (v === null || v === undefined ? '?' : SYMBOL[Math.round(v)]);
    doc.addEventListener('click', (e) => {
      if (!section()?.contains(e.target)) return;
      const t = e.target.closest('[data-cell], [data-weight], [data-tol], [data-act], [data-lift], [data-restore], [data-tool], [data-theme-set]');
      if (!t) return;
      e.preventDefault();   // a mark in a row's summary changes the mark, it does not open the row
      const d = t.dataset;
      if (d.themeSet) {
        if (d.themeSet === 'system') delete html.dataset.theme; else html.dataset.theme = d.themeSet;
        render(`[data-theme-set="${d.themeSet}"]`);
        return;
      }
      if (d.tool) {
        if (d.tool === 'undo' && undo.length) { overrides = undo.pop(); render('[data-tool="undo"]'); }
        if (d.tool === 'save') {
          // The same sheet and the chosen theme go with the saved report.
          const st = doc.getElementById('rpt-style');
          download(`${slug}.html`, renderHtml(decide({ ...base, overrides }), { style: st ? { css: st.textContent, license: st.dataset.license } : null, theme: themeNow() }), 'text/html');
        }
        if (d.tool === 'export') download(`${slug}-changes.json`, `${JSON.stringify(overrides, null, 1)}\n`, 'application/json');
        if (d.tool === 'print') win.print();
        if (d.tool === 'print-all') {
          // Everything open for the long version, then back as it was.
          const shut = [...doc.querySelectorAll('section.rpt details:not([open])')];
          shut.forEach((x) => { x.open = true; });
          win.addEventListener('afterprint', () => shut.forEach((x) => { x.open = false; }), { once: true });
          win.print();
        }
        return;
      }
      // A criterion's weight or tolerance (the same for every option).
      const critOf = (k) => res.criteria.find((c) => c.key === k);
      const setCrit = (k, field, v, comment) => {
        const prev = overrides.filter((o) => o.kind === 'criterion' && o.criterion === k).reduce((a2, o) => ({ ...a2, ...o }), {});
        return [...without((o) => o.kind === 'criterion' && o.criterion === k), { ...prev, kind: 'criterion', criterion: k, [field]: v, comment }];
      };
      if (d.weight || d.tol) {
        const k = d.weight || d.tol, cr = critOf(k), field = d.weight ? 'weight' : 'tolerance', focus = `[data-${d.weight ? 'weight' : 'tol'}="${k}"]`;
        const now = field === 'weight' ? res.weights[res.criteria.indexOf(cr)] : cr.tolerance;
        ask(`${cr.label}: its ${field}${field === 'weight' ? ' (the same for every option)' : ' (relative: 0.1 is ±10 %)'}`, [
          { id: 'set', label: `Set the ${field}`, apply: (comment, v) => (Number.isFinite(v) && v >= 0 ? setCrit(k, field, v, comment) : null) },
          { id: 'clear', label: 'Back to the default', needsComment: false, apply: () => without((o) => o.kind === 'criterion' && o.criterion === k) },
        ], { weight: now, focus });
        return;
      }
      if (d.cell) {
        const [ck, k] = d.cell.split('|'), c = res.candidates.find((x) => x.key === ck), cr = critOf(k);
        const mine = (o) => o.kind === 'cell' && o.candidate === ck && o.criterion === k;
        ask(`${c.label} · ${cr.label}: the tool's mark ${sym(c.toolMarks[k])}`, [
          { id: 'veto', label: 'Veto it (out of the calculation)', apply: (comment) => [...without(mine), { kind: 'cell', candidate: ck, criterion: k, action: 'veto', comment }] },
          { id: 'up', label: 'Nudge up', apply: (comment) => [...without((o) => mine(o) && o.action === 'veto'), { kind: 'cell', candidate: ck, criterion: k, action: 'nudge', by: 1, comment }] },
          { id: 'down', label: 'Nudge down', apply: (comment) => [...without((o) => mine(o) && o.action === 'veto'), { kind: 'cell', candidate: ck, criterion: k, action: 'nudge', by: -1, comment }] },
          { id: 'clear', label: 'Remove my changes', needsComment: false, apply: () => without(mine) },
        ], { focus: `[data-cell="${ck}|${k}"]` });
        return;
      }
      if (d.lift || d.restore) {
        const [ck, id] = (d.lift || d.restore).split('|'), c = res.candidates.find((x) => x.key === ck), v = c.vetoes.find((x) => x.id === id);
        const mine = (o) => o.kind === 'lift' && o.candidate === ck && o.veto === id;
        if (d.restore) { change(without(mine), `[data-section="${ck}"] [data-lift="${ck}|${id}"]`); return; }
        ask(`${c.label}: lift the tool's veto “${v.why}”`, [{ id: 'lift', label: 'Lift it', apply: (comment) => [...without(mine), { kind: 'lift', candidate: ck, veto: id, comment }] }], { focus: `[data-restore="${ck}|${id}"]` });
        return;
      }
      if (d.act) {
        const ck = d.cand, c = res.candidates.find((x) => x.key === ck), focus = `[data-section="${ck}"] summary`;
        if (d.act === 'unveto') { change(without((o) => o.kind === 'option' && o.action === 'veto' && o.candidate === ck), `[data-act="veto"][data-cand="${ck}"]`); return; }
        const make = {
          veto: ['Veto the option', (comment) => [...overrides, { kind: 'option', candidate: ck, action: 'veto', comment }]],
          up: ['Nudge it up a step', (comment) => [...overrides, { kind: 'option', candidate: ck, action: 'nudge', by: 1, comment }]],
          down: ['Nudge it down a step', (comment) => [...overrides, { kind: 'option', candidate: ck, action: 'nudge', by: -1, comment }]],
          datum: ['Make it the datum', (comment) => [...without((o) => o.kind === 'datum'), { kind: 'datum', candidate: ck, comment }]],
        }[d.act];
        const choices = [{ id: d.act, label: make[0], apply: make[1] }];
        if (d.act === 'up' || d.act === 'down') choices.push({ id: 'clear', label: 'Remove my nudges', needsComment: false, apply: () => without((o) => o.kind === 'option' && o.action === 'nudge' && o.candidate === ck) });
        ask(`${c.label}: ${make[0].toLowerCase()}${d.act === 'up' || d.act === 'down' ? ` (a step is one mark at the largest weight, ${fmt(res.nudgeUnit)})` : ''}`, choices, { focus });
      }
    });
    render();
  }

  return { PUGH_VERSION, SYMBOL, DEFAULTS, PughError, rng, normalizeMatrix, worseRatio, markOf, decide, sensitivity, fmt, mainReason, bottomLine, renderMarkdown, plotSvg, sensitivitySvg, renderHtml, boot };
}

export const { PUGH_VERSION, SYMBOL, DEFAULTS, PughError, rng, normalizeMatrix, worseRatio, markOf, decide, sensitivity, fmt, mainReason, bottomLine, renderMarkdown, plotSvg, sensitivitySvg, renderHtml, boot } = pughEngine();
