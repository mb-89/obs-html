/* Equation figures, plotted live (features.py, equations; artifact-ui.md, Equation figures).
   The Document's expression trees are evaluated with the embedded maths library (math.js, its
   Complex numbers) in complex arithmetic with principal branches: a result is a point of the
   plot only where its imaginary part vanishes. The visible range of the swept variable is
   sampled again at every zoom and pan; systems the core could not solve exactly are solved here,
   algebraic ones by Newton's method seeded from the defaults, differential ones by an adaptive
   Runge-Kutta (Dormand-Prince) integrator. Curves compute in short slices between which the page
   keeps running, with a progress status. The reader's view (traces added, the second axis's
   side, swapped axes, a family of curves, zoom) is session-only state, kept per figure anchor so
   print shows it. */
globalThis.obsEquations = (() => {
  const IMAGINARY = 1e-9;  // A result is real where |im| <= IMAGINARY * max(1, |re|).
  const SAMPLES = 240;  // Points per curve across the visible range of the swept variable.
  const SLICE_MILLISECONDS = 12;  // Longest computation between two yields to the page.
  const VIEW_NOTE = "View changed by the reader.";
  const SI_UNITS = {length: "m", mass: "kg", time: "s", current: "A", temperature: "K",
    substance: "mol", luminosity: "cd"};
  const states = new Map();  // figure anchor -> the reader's view state, for this session only.
  const complex = (re, im = 0) => new globalThis.math.Complex(re, im);
  const none = () => complex(NaN, NaN);

  function real(z) {
    if (!Number.isFinite(z.re) || !Number.isFinite(z.im)) return null;
    return Math.abs(z.im) <= IMAGINARY * Math.max(1, Math.abs(z.re)) ? z.re : null;
  }
  function pow(base, exponent) {
    // A real base to a real power stays real where the principal value is real.
    if (base.im === 0 && exponent.im === 0 && (base.re >= 0 || Number.isInteger(exponent.re))) {
      return complex(Math.pow(base.re, exponent.re));
    }
    return base.pow(exponent);
  }
  const realArguments = operation => (...values) => {
    const numbers = values.map(real);
    return numbers.some(number => number === null) ? none() : complex(operation(...numbers));
  };
  // Heaviside(0) = 1/2 and sign(0) = 0, as the shared test vectors fix them.
  const OPERATORS = {
    add: (...values) => values.reduce((total, value) => total.add(value)),
    mul: (...values) => values.reduce((total, value) => total.mul(value)),
    pow,
    exp: value => value.exp(), log: value => value.log(),
    sin: value => value.sin(), cos: value => value.cos(), tan: value => value.tan(),
    asin: value => value.asin(), acos: value => value.acos(), atan: value => value.atan(),
    sinh: value => value.sinh(), cosh: value => value.cosh(), tanh: value => value.tanh(),
    abs: value => complex(value.abs()),
    atan2: realArguments(Math.atan2),
    sign: realArguments(Math.sign),
    min: realArguments(Math.min), max: realArguments(Math.max),
    heaviside: realArguments((value, atZero = 0.5) => value > 0 ? 1 : value < 0 ? 0 : atZero),
  };
  const derivativeKey = (name, order) => `${name}'${order}`;

  /* An expression tree ($defs/expression) as a function of a scope {values, derivatives}. */
  function compile(tree) {
    if ("number" in tree) { const value = complex(tree.number); return () => value; }
    if ("constant" in tree) { const unit = complex(0, 1); return () => unit; }
    if ("symbol" in tree) {
      const name = tree.symbol;
      return scope => {
        const value = scope.values[name];
        return value === undefined || value === null ? none() : complex(value);
      };
    }
    if ("derivative" in tree) {
      const key = derivativeKey(tree.derivative, tree.order);
      return scope => {
        const value = scope.derivatives[key];
        return value === undefined || value === null ? none() : complex(value);
      };
    }
    const operator = OPERATORS[tree.op];
    if (!operator) throw new Error(`equations.js: the operator ${tree.op} has no evaluator`);
    const args = tree.args.map(compile);
    return scope => operator(...args.map(argument => argument(scope)));
  }
  const realValue = compiled => scope => real(compiled(scope));

  /* One tree at SI values: its real value, or null where it is no point of the plot. */
  function evaluate(tree, values, derivatives = []) {
    const scope = {values: {...values}, derivatives: {}};
    for (const item of derivatives) scope.derivatives[derivativeKey(item.of, item.order)] = item.value;
    return real(compile(tree)(scope));
  }

  /* A reader's expression, parsed by the maths library, as an expression tree over `names`. */
  const FUNCTIONS = {exp: "exp", log: "log", ln: "log", sin: "sin", cos: "cos", tan: "tan",
    asin: "asin", acos: "acos", atan: "atan", atan2: "atan2", sinh: "sinh", cosh: "cosh",
    tanh: "tanh", abs: "abs", sign: "sign", min: "min", max: "max", heaviside: "heaviside"};
  function parseExpression(text, names) {
    let node;
    try {
      node = globalThis.math.parse(text);
    } catch (error) {
      throw new Error(`cannot be parsed: ${error.message}`);
    }
    const tree = item => {
      if (item.type === "ParenthesisNode") return tree(item.content);
      if (item.type === "ConstantNode") {
        if (typeof item.value !== "number") throw new Error(`holds ${item.value}, which is no number`);
        return {number: item.value};
      }
      if (item.type === "SymbolNode") {
        if (names.includes(item.name)) return {symbol: item.name};
        if (item.name === "i") return {constant: "i"};
        if (item.name === "pi") return {number: Math.PI};
        if (item.name === "e") return {number: Math.E};
        throw new Error(`names ${item.name}, which is no variable of the figure (${names.join(", ")})`);
      }
      if (item.type === "OperatorNode") {
        const args = item.args.map(tree);
        const negative = value => ({op: "mul", args: [{number: -1}, value]});
        switch (item.fn) {
        case "add": return {op: "add", args};
        case "subtract": return {op: "add", args: [args[0], negative(args[1])]};
        case "multiply": return {op: "mul", args};
        case "divide": return {op: "mul", args: [args[0], {op: "pow", args: [args[1], {number: -1}]}]};
        case "pow": return {op: "pow", args};
        case "unaryMinus": return negative(args[0]);
        case "unaryPlus": return args[0];
        default: throw new Error(`uses the operator ${item.op}, which an equation figure does not evaluate`);
        }
      }
      if (item.type === "FunctionNode") {
        const name = item.fn.name;
        const args = item.args.map(tree);
        if (name === "sqrt") return {op: "pow", args: [args[0], {number: 0.5}]};
        if (FUNCTIONS[name]) return {op: FUNCTIONS[name], args};
        throw new Error(`calls ${name}, which is not among ${["sqrt", ...Object.keys(FUNCTIONS)].join(", ")}`);
      }
      throw new Error(`holds a ${item.type}, which is no expression of numbers, variables and functions`);
    };
    return tree(node);
  }

  /* Linear solve with partial pivoting; null where the matrix is singular. */
  function solveLinear(matrix, vector) {
    const size = vector.length;
    const a = matrix.map((row, index) => [...row, vector[index]]);
    for (let column = 0; column < size; column += 1) {
      let pivot = column;
      for (let row = column + 1; row < size; row += 1) {
        if (Math.abs(a[row][column]) > Math.abs(a[pivot][column])) pivot = row;
      }
      if (!(Math.abs(a[pivot][column]) > 1e-300)) return null;
      [a[column], a[pivot]] = [a[pivot], a[column]];
      for (let row = column + 1; row < size; row += 1) {
        const factor = a[row][column] / a[column][column];
        for (let k = column; k <= size; k += 1) a[row][k] -= factor * a[column][k];
      }
    }
    const result = new Array(size);
    for (let row = size - 1; row >= 0; row -= 1) {
      let sum = a[row][size];
      for (let k = row + 1; k < size; k += 1) sum -= a[row][k] * result[k];
      result[row] = sum / a[row][row];
    }
    return result;
  }

  /* Newton's method with a halving line search: the unknowns where the residuals vanish. */
  function newton(residuals, unknowns, scope, start) {
    const evaluateAt = point => {
      unknowns.forEach((name, index) => { scope.values[name] = point[index]; });
      const result = residuals.map(residual => residual(scope));
      return result.some(value => value === null) ? null : result;
    };
    const norm = values => Math.max(...values.map(Math.abs));
    let point = start.slice();
    let value = evaluateAt(point);
    if (!value) return null;
    const scale = Math.max(1, norm(value));
    for (let iteration = 0; iteration < 60; iteration += 1) {
      const jacobian = residuals.map(() => new Array(point.length));
      for (let column = 0; column < point.length; column += 1) {
        const step = 1e-7 * Math.max(1, Math.abs(point[column]));
        const moved = point.slice();
        moved[column] += step;
        const shifted = evaluateAt(moved);
        if (!shifted) return null;
        shifted.forEach((item, row) => { jacobian[row][column] = (item - value[row]) / step; });
      }
      const delta = solveLinear(jacobian, value.map(item => -item));
      if (!delta) return null;
      let damping = 1, next = null, nextValue = null;
      while (damping > 1e-4) {
        next = point.map((item, index) => item + damping * delta[index]);
        nextValue = evaluateAt(next);
        if (nextValue && norm(nextValue) < norm(value) * (1 - 1e-4 * damping) + 1e-300) break;
        damping /= 2;
        next = null;
      }
      if (!next) return norm(value) <= 1e-8 * scale ? point : null;
      const converged = delta.every((item, index) => Math.abs(damping * item) <= 1e-12 * (1 + Math.abs(next[index])));
      point = next;
      value = nextValue;
      if (converged || norm(value) <= 1e-14 * scale) return point;
    }
    return norm(value) <= 1e-8 * scale ? point : null;
  }

  // Dormand-Prince 5(4) coefficients.
  const DP_C = [0, 1 / 5, 3 / 10, 4 / 5, 8 / 9, 1, 1];
  const DP_A = [[], [1 / 5], [3 / 40, 9 / 40], [44 / 45, -56 / 15, 32 / 9],
    [19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729],
    [9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656],
    [35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84]];
  const DP_B = [35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84, 0];
  const DP_E = [71 / 57600, 0, -71 / 16695, 71 / 1920, -17253 / 339200, 22 / 525, -1 / 40];

  /* Integrates y' = f(t, y) from (t0, y0) and reports y at each of the ascending `times` >= t0. */
  async function integrate(f, t0, y0, times, report, tick) {
    const rtol = 1e-9, atol = 1e-12;
    let t = t0, y = y0.slice();
    const end = times.at(-1);
    let h = Math.max((end - t0) / 1000, 1e-12);
    let target = 0;
    while (target < times.length && times[target] <= t) { report(target, y); target += 1; }
    let steps = 0;
    while (target < times.length) {
      const toTarget = times[target] - t;
      const hits = h >= toTarget;
      if (hits) h = toTarget;
      const k = [];
      for (let stage = 0; stage < 7; stage += 1) {
        const point = y.map((value, index) => value + h * DP_A[stage].reduce(
          (sum, a, previous) => sum + a * k[previous][index], 0));
        const derivative = f(t + DP_C[stage] * h, point);
        if (!derivative) return;  // No real derivative: the curve ends here.
        k.push(derivative);
      }
      const next = y.map((value, index) => value + h * DP_B.reduce((sum, b, stage) => sum + b * k[stage][index], 0));
      const error = Math.max(...y.map((value, index) => Math.abs(h * DP_E.reduce(
        (sum, e, stage) => sum + e * k[stage][index], 0)) / (atol + rtol * Math.max(Math.abs(value), Math.abs(next[index])))));
      if (error <= 1 || h <= 1e-14 * Math.max(1, Math.abs(t))) {
        t = hits ? times[target] : t + h;
        y = next;
        while (target < times.length && times[target] <= t) { report(target, y); target += 1; }
      }
      if (!Number.isFinite(error)) return;
      h *= Math.min(5, Math.max(0.2, 0.9 * Math.pow(Math.max(error, 1e-10), -0.2)));
      steps += 1;
      if (steps % 64 === 0) await tick();
    }
  }

  /* The figure's model: compiled trees and the conversion of each plotted expression. */
  function model(spec) {
    const variables = spec.variables;
    const unknowns = spec.unknowns;
    const functions = Object.keys(variables).filter(name => variables[name].of);
    const names = Object.keys(variables);
    const defaults = Object.fromEntries(names.filter(name => "siValue" in variables[name].quantity)
      .map(name => [name, variables[name].quantity.siValue]));
    const movable = names.filter(name => variables[name].quantity.siRange && !unknowns.includes(name)
      && !functions.includes(name) && name !== spec.plot.sweep);
    const solution = spec.solution;
    const compiled = {};
    if (solution.method === "exact") {
      compiled.branches = solution.branches.map(branch => Object.entries(branch)
        .map(([name, tree]) => [name, realValue(compile(tree))]));
    } else if (solution.method === "algebraic") {
      compiled.residuals = solution.residuals.map(tree => realValue(compile(tree)));
    } else {
      compiled.derivatives = solution.derivatives.map(tree => realValue(compile(tree)));
    }
    return {spec, variables, unknowns, functions, names, defaults, movable, compiled};
  }

  function siUnit(dimension) {
    return Object.entries(dimension).map(([name, power]) =>
      `${SI_UNITS[name] || name}${power === 1 ? "" : `^${power}`}`).join("·");
  }
  /* How a plotted expression's SI value shows on its axis: the unit of the variable it names. */
  function scale(model, plotted) {
    const name = plotted.tree.symbol;
    const quantity = name && model.variables[name]?.quantity;
    if (quantity) {
      if (quantity.range && quantity.siRange && quantity.siRange[1] !== quantity.siRange[0]) {
        const [s0, s1] = quantity.siRange, [d0, d1] = quantity.range;
        const factor = (d1 - d0) / (s1 - s0);
        return {unit: quantity.unit, show: si => d0 + (si - s0) * factor, si: shown => s0 + (shown - d0) / factor};
      }
      if ("siValue" in quantity && quantity.siValue !== 0 && quantity.value !== 0) {
        const factor = quantity.value / quantity.siValue;
        return {unit: quantity.unit, show: si => si * factor, si: shown => shown / factor};
      }
      if (!quantity.unit) return {unit: "", show: si => si, si: shown => shown};
    }
    return {unit: siUnit(plotted.dimension), show: si => si, si: shown => shown};
  }
  const label = (source, unit) => unit ? `${source} [${unit}]` : source;

  function initialState(spec) {
    return {
      swap: false, side: "right", added: [],
      axes: spec.plot.y.map(item => item.axis),
      family: spec.plot.family ? {variable: spec.plot.family.variable, values: spec.plot.family.values.slice(),
        siValues: spec.plot.family.siValues.slice()} : null,
      range: null,  // The visible range of the swept variable's axis, in its display unit; null: all.
    };
  }
  const stateKey = state => JSON.stringify({...state, range: null});
  function changed(spec, state) {
    return state.range !== null || stateKey(state) !== stateKey(initialState(spec));
  }

  /* Every curve of the view: one per family value, y expression and solution branch. */
  function curves(model, state) {
    const {spec} = model;
    const ys = [...spec.plot.y.map((item, index) => ({...item, axis: state.axes[index]})),
      ...state.added];
    const family = state.family ? state.family.siValues.map((si, index) => ({si, shown: state.family.values[index]}))
      : [null];
    const branches = spec.solution.method === "exact" ? spec.solution.branches.length : 1;
    const familyUnit = state.family ? scale(model, {tree: {symbol: state.family.variable},
      dimension: model.variables[state.family.variable].quantity.dimension}).unit : "";
    const result = [];
    family.forEach(member => {
      for (let branch = 0; branch < branches; branch += 1) {
        result.push({member, branch, ys, name: y => [y.source,
          member ? `${state.family.variable} = ${member.shown}${familyUnit ? ` ${familyUnit}` : ""}` : "",
          branches > 1 ? `branch ${branch + 1}` : ""].filter(Boolean).join(", ")});
      }
    });
    return result;
  }

  /* The sweep values at which to sample: SAMPLES + 1 points over the SI interval. */
  const grid = ([low, high]) => Array.from({length: SAMPLES + 1}, (_, index) => low + (high - low) * index / SAMPLES);

  /* One curve's points: the sweep values and each y expression's SI values (null: no point). */
  async function sample(model, state, curve, sweeps, tick) {
    const {spec, compiled} = model;
    const scope = {values: {...model.defaults}, derivatives: {}};
    if (curve.member) scope.values[state.family.variable] = curve.member.si;
    const x = realValue(compile(spec.plot.x.tree));
    const ys = curve.ys.map(item => realValue(item.compiled || (item.compiled = compile(item.tree))));
    const points = {sweep: [], x: [], ys: ys.map(() => [])};
    const record = sweep => {
      points.sweep.push(sweep);
      points.x.push(x(scope));
      ys.forEach((y, index) => points.ys[index].push(y(scope)));
    };
    const method = spec.solution.method;
    if (method === "exact") {
      const branch = compiled.branches[curve.branch];
      for (const sweep of sweeps) {
        scope.values[spec.plot.sweep] = sweep;
        for (const [name] of branch) scope.values[name] = null;
        for (const [name, value] of branch) scope.values[name] = value(scope);
        record(sweep);
        await tick();
      }
    } else if (method === "algebraic") {
      const unknowns = model.unknowns;
      const seed = unknowns.map(name => spec.solution.guess[name] ?? 0);
      let previous = seed;
      for (const sweep of sweeps) {
        scope.values[spec.plot.sweep] = sweep;
        const solved = newton(compiled.residuals, unknowns, scope, previous) || newton(compiled.residuals, unknowns, scope, seed);
        if (solved) {
          unknowns.forEach((name, index) => { scope.values[name] = solved[index]; });
          previous = solved;
        } else unknowns.forEach(name => { scope.values[name] = null; });
        record(sweep);
        await tick();
      }
    } else {
      const {state: stateForm, start, initial, independent} = spec.solution;
      const place = (time, values) => {
        scope.values[independent] = time;
        stateForm.forEach((item, index) => {
          if (item.order === 0) scope.values[item.of] = values[index];
          else scope.derivatives[derivativeKey(item.of, item.order)] = values[index];
        });
      };
      const derivatives = (time, values) => {
        place(time, values);
        const result = compiled.derivatives.map(derivative => derivative(scope));
        return result.some(value => value === null) ? null : result;
      };
      const times = sweeps.filter(time => time >= start);
      await integrate(derivatives, start, initial, times, (index, values) => {
        const rates = derivatives(times[index], values);
        if (rates) stateForm.forEach((item, at) => { scope.derivatives[derivativeKey(item.of, item.order + 1)] = rates[at]; });
        record(times[index]);
      }, tick);
    }
    return points;
  }

  /* The SI interval of the swept variable that covers `range` on its axis, from earlier samples. */
  function interval(full, range, sampled, show) {
    if (!range) return full;
    const [low, high] = [Math.min(...range), Math.max(...range)];
    const covering = samples => {
      let lowest = Infinity, highest = -Infinity;
      for (const {sweep, x} of samples) {
        for (let index = 0; index + 1 < sweep.length; index += 1) {
          if (x[index] === null || x[index + 1] === null) continue;
          const a = show(x[index]), b = show(x[index + 1]);
          if (Math.max(a, b) >= low && Math.min(a, b) <= high) {
            lowest = Math.min(lowest, sweep[index]);
            highest = Math.max(highest, sweep[index + 1]);
          }
        }
      }
      return lowest < highest ? [lowest, highest] : null;
    };
    const shown = sampled.current.flatMap(points => points.x.filter(value => value !== null).map(show));
    const covered = shown.length && Math.min(...shown) <= low && Math.max(...shown) >= high;
    const found = (covered && covering(sampled.current)) || covering(sampled.overview);
    if (!found) return full;
    return [Math.max(full[0], found[0]), Math.min(full[1], found[1])];
  }

  async function compute(view, report) {
    const {model, state} = view;
    const spec = model.spec;
    const full = model.variables[spec.plot.sweep].quantity.siRange
      || [model.defaults[spec.plot.sweep], model.defaults[spec.plot.sweep]];
    const list = curves(model, state);
    const xScale = scale(model, spec.plot.x);
    const key = stateKey(state);
    if (view.overviewKey !== key) { view.overview = null; view.current = []; }
    const span = interval(full, state.range, {current: view.current || [], overview: view.overview || []},
      xScale.show);
    let sliceStart = performance.now();
    const generation = view.generation;
    const tick = async () => {
      if (performance.now() - sliceStart < SLICE_MILLISECONDS) return;
      await new Promise(resolve => setTimeout(resolve, 0));
      if (view.generation !== generation) throw new Error("stale");
      sliceStart = performance.now();
    };
    const results = [];
    for (const [index, curve] of list.entries()) {
      report(index, list.length);
      results.push(await sample(model, state, curve, grid(span), tick));
    }
    report(list.length, list.length);
    if (span === full) { view.overview = results; view.overviewKey = key; }
    view.current = results;
    return {list, results, xScale};
  }

  /* Plotly's traces and layout for computed curves under the view state. */
  function figureData(view, {list, results, xScale}) {
    const {model, state} = view;
    const spec = model.spec;
    const sweepAxis = state.swap ? "y" : "x", valueAxis = state.swap ? "x" : "y";
    const scales = new Map();
    const scaleOf = item => {
      if (!scales.has(item)) scales.set(item, scale(model, item));
      return scales.get(item);
    };
    const traces = [];
    list.forEach((curve, index) => {
      const points = results[index];
      const along = points.x.map(value => value === null ? null : xScale.show(value));
      curve.ys.forEach((item, at) => {
        const yScale = scaleOf(item);
        const values = points.ys[at].map(value => value === null ? null : yScale.show(value));
        const secondary = item.axis === "secondary";
        traces.push({
          type: "scatter", mode: "lines", name: curve.name(item), legendgroup: item.source,
          [sweepAxis]: along, [valueAxis]: values,
          [`${valueAxis}axis`]: secondary ? `${valueAxis}2` : valueAxis,
          connectgaps: false,
        });
      });
    });
    const ys = list[0]?.ys || [];
    const axisTitle = axis => [...new Set(ys.filter(item => (item.axis === "secondary") === (axis === 2))
      .map(item => label(item.source, scaleOf(item).unit)))].join(", ");
    const near = state.swap ? "bottom" : "left", far = state.swap ? "top" : "right";
    const secondarySide = state.side === "right" ? far : near;
    const layout = {
      uirevision: view.revision,
      [`${sweepAxis}axis`]: {title: {text: label(spec.plot.x.source, xScale.unit)}, zeroline: false},
      [`${valueAxis}axis`]: {title: {text: axisTitle(1)}, side: ys.some(item => item.axis === "secondary")
        ? (secondarySide === far ? near : far) : near, zeroline: false},
      showlegend: view.chart?._fullLayout?.showlegend ?? true, margin: {t: 32, r: 64, l: 64, b: 56},
    };
    if (ys.some(item => item.axis === "secondary")) {
      layout[`${valueAxis}axis2`] = {title: {text: axisTitle(2)}, overlaying: valueAxis, side: secondarySide,
        zeroline: false, showgrid: false};
    }
    if (state.range) {
      layout[`${sweepAxis}axis`].range = state.range.slice();
      layout[`${sweepAxis}axis`].autorange = false;
    }
    return {traces, layout};
  }

  const views = new WeakMap();  // figure element -> its live view

  function progress(host) {
    let status = host.querySelector(".equation-progress");
    if (!status) {
      status = document.createElement("p");
      status.className = "equation-progress";
      status.setAttribute("role", "status");
      status.hidden = true;
      host.append(status);
    }
    return (done, total) => {
      status.hidden = done >= total;
      status.textContent = done >= total ? "" : `Computing curve ${done + 1} of ${total}…`;
    };
  }

  /* Recomputes and redraws the figure's view; a newer redraw supersedes an older one. */
  async function redraw(figure) {
    const view = views.get(figure);
    view.generation += 1;
    const generation = view.generation;
    figure.classList.add("equation-computing");
    try {
      const computed = await compute(view, progress(view.host));
      if (generation !== view.generation) return;
      const {traces, layout} = figureData(view, computed);
      view.drawing = true;
      try {
        await globalThis.Plotly.react(view.chart, traces, {...view.base, ...layout}, view.config);
      } finally {
        view.drawing = false;
      }
      figure.dataset.equationDraws = String(Number(figure.dataset.equationDraws || 0) + 1);
      figure.classList.remove("equation-computing");
      figure.classList.add("figure-plot-ready");
    } catch (error) {
      if (error.message === "stale") return;
      figure.classList.remove("equation-computing");
      figure.dataset.figureError = String(error);
      throw error;
    }
  }

  function render(figure, spec, host) {
    if (!globalThis.math?.Complex) {
      const message = document.createElement("p");
      message.setAttribute("role", "status");
      message.textContent = "Equation figure unavailable: the maths library could not load.";
      host.append(message);
      figure.dataset.figureError = "maths library unavailable";
      globalThis.obsCapabilities?.fail?.("equations", "the maths library did not load");
      return;
    }
    const chart = document.createElement("div");
    chart.className = "figure-chart";
    host.append(chart);
    if (!states.has(figure.id)) states.set(figure.id, initialState(spec));
    const view = {
      figure, host, chart, model: model(spec), state: states.get(figure.id), generation: 0, revision: 1,
      base: {autosize: true, height: 450, dragmode: "pan"},
      config: {responsive: true, scrollZoom: true, displaylogo: false, displayModeBar: true,
        modeBarButtonsToRemove: ["toImage", "sendDataToCloud"]},
    };
    views.set(figure, view);
    redraw(figure).then(() => {
      const sweepAxis = () => view.state.swap ? "yaxis" : "xaxis";
      chart.on("plotly_relayout", event => {
        if (view.drawing) return;
        const axis = sweepAxis();
        if (event[`${axis}.autorange`]) view.state.range = null;
        else if (event[`${axis}.range[0]`] !== undefined || event[`${axis}.range`]) {
          view.state.range = (event[`${axis}.range`] || [event[`${axis}.range[0]`], event[`${axis}.range[1]`]]).map(Number);
        } else return;
        redraw(figure).catch(() => {});
      });
      new ResizeObserver(() => {
        if (!chart.isConnected || !chart.clientWidth || !chart.clientHeight || !chart._fullLayout) return;
        const width = chart.clientWidth, height = chart.clientHeight;
        if (chart._fullLayout.width === width && chart._fullLayout.height === height) return;
        view.base = {...view.base, height};
        globalThis.Plotly.relayout(chart, {width, height});
      }).observe(chart);
    }).catch(() => {});
  }

  /* A change of the reader's view: applied to the state, then drawn again from the full range. */
  function change(figure, apply, resetZoom = false) {
    const view = views.get(figure);
    if (!view) return;
    apply(view.state, view.model);
    if (resetZoom) { view.state.range = null; view.revision += 1; }
    redraw(figure).catch(() => {});
  }

  function field(labelText, control) {
    const wrapper = document.createElement("label");
    wrapper.className = "equation-option";
    const caption = document.createElement("span");
    caption.textContent = labelText;
    control.setAttribute("aria-label", labelText);
    wrapper.append(caption, control);
    return wrapper;
  }
  function element(tag, properties = {}) {
    return Object.assign(document.createElement(tag), properties);
  }
  function selectOf(options, value) {
    const select = element("select");
    for (const [key, text] of options) select.append(element("option", {value: key, textContent: text}));
    select.value = value;
    return select;
  }
  function errorLine() {
    const line = element("p", {className: "equation-option-error"});
    line.setAttribute("role", "alert");
    line.hidden = true;
    return {line, show(text) { line.hidden = !text; line.textContent = text; }};
  }
  const group = (name, ...children) => {
    const box = element("div", {className: `equation-options equation-options-${name}`});
    box.setAttribute("role", "group");
    box.append(...children);
    return box;
  };
  const buttonOf = (text, action) => {
    const button = element("button", {type: "button", className: "filter-pill", textContent: text});
    button.addEventListener("click", action);
    return button;
  };
  const specOf = figure => JSON.parse(figure.dataset.figureSpec);

  /* The equation figure's entries of the options menu (figures.js, FIGURE_OPTIONS). */
  const OPTIONS = {
    trace(figure) {
      const spec = specOf(figure);
      const names = [...Object.keys(spec.variables)];
      const input = element("input", {type: "text", placeholder: "Expression, e.g. 2*" + spec.plot.y[0].source});
      const axis = selectOf([["primary", "First y axis"], ["secondary", "Second y axis"]], "primary");
      const error = errorLine();
      const box = group("trace", field("Expression", input), field("Trace on", axis), error.line);
      box.setAttribute("aria-label", "Add trace");
      box.append(buttonOf("Add trace", () => {
        let tree;
        try {
          tree = parseExpression(input.value.trim(), names);
        } catch (failure) {
          error.show(`Trace ${JSON.stringify(input.value)} ${failure.message}. Write an expression of `
            + `the figure's variables (${names.join(", ")}).`);
          return;
        }
        error.show("");
        change(figure, state => state.added.push({source: input.value.trim(), tree, dimension: {},
          axis: axis.value}), true);
        input.value = "";
      }));
      return box;
    },
    axis(figure) {
      const select = selectOf([["right", "Right"], ["left", "Left"]], states.get(figure.id)?.side || "right");
      select.addEventListener("change", () => change(figure, state => { state.side = select.value; }));
      const box = group("axis", field("Second y axis", select));
      const spec = specOf(figure);
      spec.plot.y.forEach((item, index) => {
        const which = selectOf([["primary", "First"], ["secondary", "Second"]],
          states.get(figure.id)?.axes[index] || item.axis);
        which.addEventListener("change", () => change(figure, state => { state.axes[index] = which.value; }));
        box.append(field(`${item.source} on y axis`, which));
      });
      return box;
    },
    swap(figure) {
      const control = buttonOf("Swap x and y", () => {
        change(figure, state => { state.swap = !state.swap; }, true);
        control.setAttribute("aria-pressed", String(states.get(figure.id).swap));
      });
      control.setAttribute("aria-pressed", "false");
      control.title = "Show the swept variable on the vertical axis";
      return control;
    },
    family(figure) {
      const spec = specOf(figure);
      const movable = model(spec).movable;
      const current = spec.plot.family;
      const variable = selectOf([["", "None"], ...movable.map(name => [name, name])], current?.variable || "");
      const mode = selectOf([["steps", "Steps"], ["values", "Values"]], current ? "values" : "steps");
      const entry = element("input", {type: "text", value: current ? current.values.join(", ") : "5"});
      const error = errorLine();
      const box = group("family", field("Family over", variable), field("By", mode), field("Steps or values", entry),
        error.line);
      box.setAttribute("aria-label", "Family of curves");
      box.append(buttonOf("Apply family", () => {
        if (!variable.value) {
          error.show("");
          change(figure, state => { state.family = null; }, true);
          return;
        }
        const quantity = spec.variables[variable.value].quantity;
        const toSi = scale(model(spec), {tree: {symbol: variable.value}, dimension: quantity.dimension}).si;
        let values;
        if (mode.value === "steps") {
          const steps = Number(entry.value.trim());
          if (!Number.isInteger(steps) || steps < 1 || steps > 50) {
            error.show(`Steps ${JSON.stringify(entry.value)} is not a whole number from 1 to 50. Enter how many `
              + `values of ${variable.value} to spread over its range.`);
            return;
          }
          const [low, high] = quantity.range;
          values = steps === 1 ? [(low + high) / 2]
            : Array.from({length: steps}, (_, index) => Number((low + (high - low) * index / (steps - 1)).toPrecision(6)));
        } else {
          values = entry.value.split(",").map(item => Number(item.trim()));
          if (!values.length || values.some(item => !Number.isFinite(item))) {
            error.show(`Values ${JSON.stringify(entry.value)} are not numbers separated by commas. Enter `
              + `values of ${variable.value} in ${quantity.unit || "its unit"}.`);
            return;
          }
        }
        error.show("");
        change(figure, state => {
          state.family = {variable: variable.value, values, siValues: values.map(toSi)};
        }, true);
      }));
      return box;
    },
  };

  /* Print: the figure as the reader last saw it, and whether that differs from the initial plot. */
  async function printImage(figure, spec) {
    const state = states.get(figure.id) || initialState(spec);
    const host = document.createElement("div");
    host.style.cssText = "position:fixed;left:-10000px;top:0;width:900px;height:450px";
    document.body.append(host);
    const chart = document.createElement("div");
    host.append(chart);
    const view = {model: model(spec), state, generation: 0, revision: 1, current: [], overview: null};
    try {
      const computed = await compute(view, () => {});
      const {traces, layout} = figureData(view, computed);
      await globalThis.Plotly.newPlot(chart, traces, {...layout, width: 900, height: 450});
      return {src: await globalThis.Plotly.toImage(chart, {format: "svg", width: 900, height: 450}),
        changed: changed(spec, state)};
    } finally {
      globalThis.Plotly.purge(chart);
      host.remove();
    }
  }

  return {evaluate, parseExpression, render, option: (key, figure) => OPTIONS[key](figure),
    printImage, VIEW_NOTE, state: figure => states.get(figure.id)};
})();
