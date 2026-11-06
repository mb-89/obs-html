/* Decision figures, decided live in the reader (features.py, pugh; artifact-ui.md, Decision
   figures). The Document carries the matrix as the core checked it (obs capabilities/
   pugh-decisions); ctrl's engine (vendor/pugh.js, embedded before figures.js as
   globalThis.obsPughEngine) decides it here: the marks against the datum, the weighted totals,
   the ranking, the suggestion and the reverse sensitivity. The one-page view is the bottom line,
   then the matrix (options as columns, the datum first, the winner marked; criteria as rows with
   their weights), then, folded, what each option means and the sensitivity. The reader changes
   a weight in place and everything is decided again at once; Reset weights in the figure's options
   menu takes the matrix's own back. The weights are session-only view state, kept per figure
   anchor, so print shows the reader's view with a caption note. */
globalThis.obsPugh = (() => {
  const VIEW_NOTE = "View changed by the reader.";
  const states = new Map();  // figure anchor -> the reader's weights, by criterion key, this session only.
  const engine = () => globalThis.obsPughEngine;
  const percent = share => `${(100 * share).toFixed(1)} %`;
  const number = value => engine().fmt(value);
  const signed = value => (value > 0 ? `+${number(value)}` : value < 0 ? `−${number(-value)}` : "0");
  const symbol = mark => (mark === null || mark === undefined ? "?" : engine().SYMBOL[Math.round(mark)]);

  function element(tag, properties = {}, ...children) {
    const node = Object.assign(document.createElement(tag), properties);
    node.append(...children.filter(child => child !== null && child !== undefined && child !== false));
    return node;
  }
  function weightsOf(spec, anchor) {
    return {...Object.fromEntries(spec.matrix.criteria.map(c => [c.key, c.weight])), ...(states.get(anchor) || {})};
  }
  function changed(spec, anchor) {
    const weights = states.get(anchor) || {};
    return spec.matrix.criteria.some(c => c.key in weights && weights[c.key] !== c.weight);
  }
  /** The decision at the given weights, by criterion key: ctrl's decide() on the matrix with them. */
  function decide(spec, weights = {}) {
    const matrix = structuredClone(spec.matrix);
    for (const criterion of matrix.criteria) if (criterion.key in weights) criterion.weight = weights[criterion.key];
    return engine().decide(matrix);
  }
  function labelOf(spec, key) {
    const candidate = spec.matrix.candidates.find(c => c.key === key);
    return candidate ? String(candidate.label ?? candidate.key) : key;
  }
  function criterionLabel(result, key) {
    return result.criteria.find(c => c.key === key)?.label ?? key;
  }
  function tieText(result, tie) {
    if (!tie) return "no single weight makes it tie";
    if (tie.now) return "ties it now";
    return `${criterionLabel(result, tie.criterion)} weight ${number(tie.from)} → ${number(tie.to)}`;
  }
  function band(reasonable, step) {
    return reasonable ? `within the reasonable band (±${number(step)})` : `outside the reasonable band (±${number(step)})`;
  }
  /** The justification check: where ``chosen`` is not the winner, what would make it win. */
  function check(spec, result) {
    const chosen = spec.matrix.chosen;
    if (!chosen || !result.suggestion || chosen === result.suggestion.key) return null;
    const label = labelOf(spec, chosen), candidate = result.candidates.find(c => c.key === chosen);
    const line = element("p", {className: "pugh-check"});
    line.dataset.pughCheck = chosen;
    if (!candidate.fits) {
      line.append(element("strong", {textContent: `The chosen option, ${label}, is not the winner`}),
        `: it does not fit (${candidate.whyNot}), so no weight makes it win.`);
      return line;
    }
    const sensitivity = result.sensitivity, entry = sensitivity?.all.find(item => item.key === chosen);
    if (!entry) {
      line.append(element("strong", {textContent: `The chosen option, ${label}, is not the winner`}),
        ": it may be ranked but not suggested, so no weight makes it win.");
      return line;
    }
    const step = sensitivity.step;
    const single = !entry.tie
      ? element("span", {className: "pugh-unreasonable", textContent: "no single weight change makes it tie the winner"})
      : entry.tie.now ? element("span", {className: "pugh-reasonable", textContent: "it ties the winner now, and the tie-break decides"})
        : element("span", {className: entry.tie.reasonable ? "pugh-reasonable" : "pugh-unreasonable",
          textContent: `the smallest single change that makes it tie the winner is ${tieText(result, entry.tie)}, `
            + band(entry.tie.reasonable, step)});
    single.dataset.pughSingle = entry.tie?.reasonable ? "reasonable" : "unreasonable";
    if (entry.tie) single.dataset.pughTie = entry.tie.criterion ?? "";
    const allReasonable = entry.minChange && entry.minChange.maxStep <= step;
    const all = entry.minChange
      ? element("span", {className: allReasonable ? "pugh-reasonable" : "pugh-unreasonable",
        textContent: `the smallest change of all weights that does moves them by ${percent(entry.minChange.rel)} of their `
          + `size, one by at most ${number(entry.minChange.maxStep)}, ${band(allReasonable, step)}`})
      : element("span", {className: "pugh-unreasonable", textContent: "no change of the weights makes it tie the winner"});
    all.dataset.pughAll = allReasonable ? "reasonable" : "unreasonable";
    line.append(element("strong", {textContent: `The chosen option, ${label}, is not the winner`}), ": ", single, "; ", all, ".");
    return line;
  }
  function bottomLine(spec, result) {
    const box = element("div", {className: "pugh-bottom"});
    const suggestion = result.suggestion;
    if (!suggestion) {
      box.append(element("p", {textContent: "No option fits."}));
      return box;
    }
    const sensitivity = result.sensitivity;
    const line = element("p");
    line.dataset.pughWinner = suggestion.key;
    line.append("Winner: ", element("strong", {textContent: suggestion.label}),
      ` (${signed(suggestion.total)} against the datum ${result.datum.label})`);
    if (sensitivity) {
      const verdict = element("span", {className: `pugh-verdict pugh-${sensitivity.verdict}`,
        textContent: sensitivity.verdict === "holds" ? "the choice holds" : "the choice depends on the weights"});
      verdict.dataset.pughVerdict = sensitivity.verdict;
      line.append("; ", verdict, `: it wins ${percent(sensitivity.share)} of the weight draws within ±${number(sensitivity.step)}.`);
    } else line.append("; it is the only option to choose from.");
    box.append(line);
    const justification = check(spec, result);
    if (justification) box.append(justification);
    else if (spec.matrix.chosen === suggestion.key) box.append(element("p", {className: "pugh-chosen",
      textContent: `The chosen option, ${suggestion.label}, is the winner.`}));
    return box;
  }
  function matrixTable(spec, result, figure, {print}) {
    const scroll = element("div", {className: "pugh-scroll", tabIndex: 0});
    scroll.setAttribute("role", "region");
    scroll.setAttribute("aria-label", "Decision matrix");
    const table = element("table", {className: "pugh-matrix"});
    const order = [result.candidates.find(c => c.datum), ...result.candidates.filter(c => !c.datum)];
    const source = Object.fromEntries(spec.matrix.candidates.map(c => [c.key, c]));
    const head = element("tr", {}, element("th", {scope: "col", className: "pugh-criterion", textContent: "Criterion"}),
      element("th", {scope: "col", className: "pugh-weight", textContent: "Weight"}));
    for (const candidate of order) {
      const cell = element("th", {scope: "col", textContent: source[candidate.key].short || candidate.label});
      cell.title = candidate.label;
      cell.dataset.pughOption = candidate.key;
      if (candidate.datum) cell.classList.add("pugh-datum"), cell.append(element("span", {className: "pugh-tag", textContent: "datum"}));
      if (result.suggestion?.key === candidate.key) cell.classList.add("pugh-winner"), cell.append(element("span", {className: "pugh-tag", textContent: "winner"}));
      if (!candidate.fits) cell.classList.add("pugh-out"), cell.title += `: ${candidate.whyNot}`;
      head.append(cell);
    }
    const body = element("tbody");
    result.criteria.forEach((criterion, index) => {
      const row = element("tr", {}, element("th", {scope: "row", className: "pugh-criterion", textContent: criterion.label,
        title: criterion.label}));
      row.dataset.pughCriterion = criterion.key;
      const weight = result.weights[index];
      if (print) row.append(element("td", {className: "pugh-weight", textContent: number(weight)}));
      else {
        const input = element("input", {type: "number", min: "0", step: "0.5", value: String(weight), className: "pugh-weight-input"});
        input.setAttribute("aria-label", `Weight of ${criterion.label}`);
        input.dataset.pughWeight = criterion.key;
        input.addEventListener("change", () => {
          const value = Number(input.value);
          if (!Number.isFinite(value) || value < 0) { input.value = String(weight); return; }
          states.set(figure.id, {...(states.get(figure.id) || {}), [criterion.key]: value});
          draw(figure, spec);
          figure.querySelector(`[data-pugh-weight="${CSS.escape(criterion.key)}"]`)?.focus();
        });
        row.append(element("td", {className: "pugh-weight"}, input));
      }
      for (const candidate of order) {
        const mark = candidate.marks[criterion.key];
        const cell = element("td", {className: "pugh-mark", textContent: candidate.datum ? "S" : symbol(mark)});
        if (!candidate.fits) cell.classList.add("pugh-out");
        row.append(cell);
      }
      body.append(row);
    });
    const total = element("tr", {className: "pugh-total"}, element("th", {scope: "row", className: "pugh-criterion", textContent: "Weighted total"}),
      element("td", {className: "pugh-weight"}));
    for (const candidate of order) {
      const cell = element("td", {textContent: candidate.fits ? signed(candidate.total) : `× ${signed(candidate.total)}`});
      cell.dataset.pughTotal = candidate.key;
      if (!candidate.fits) cell.classList.add("pugh-out"), cell.title = candidate.whyNot;
      total.append(cell);
    }
    body.append(total);
    table.append(element("thead", {}, head), body);
    scroll.append(table);
    return scroll;
  }
  function meanings(spec) {
    const options = spec.matrix.candidates.filter(c => c.what || c.short);
    if (!options.length) return null;
    const list = element("dl", {className: "pugh-meanings"});
    for (const option of options) {
      list.append(element("dt", {textContent: `${option.short ? `${option.short}: ` : ""}${option.label ?? option.key}`}),
        element("dd", {textContent: option.what || ""}));
    }
    return element("details", {className: "pugh-fold"}, element("summary", {textContent: "What each option means"}), list);
  }
  function sensitivityFold(result) {
    const sensitivity = result.sensitivity;
    if (!sensitivity) return null;
    const table = element("table", {className: "pugh-sensitivity"});
    table.append(element("thead", {}, element("tr", {},
      ...["Option", "Single-weight tie point", "All weights", "Share of draws"].map(text => element("th", {scope: "col", textContent: text})))));
    const body = element("tbody");
    body.append(element("tr", {}, element("th", {scope: "row", textContent: `${result.suggestion.label} (winner)`}),
      element("td", {textContent: "—"}), element("td", {textContent: "—"}), element("td", {textContent: percent(sensitivity.share)})));
    for (const entry of sensitivity.all) {
      const row = element("tr", {}, element("th", {scope: "row", textContent: entry.label}),
        element("td", {textContent: entry.tie ? `${tieText(result, entry.tie)}${entry.tie.now ? "" : `, ${band(entry.tie.reasonable, sensitivity.step)}`}` : "none"}),
        element("td", {textContent: entry.minChange ? `${percent(entry.minChange.rel)}, largest step ${number(entry.minChange.maxStep)}` : "none"}),
        element("td", {textContent: percent(entry.share)}));
      row.dataset.pughRunnerUp = entry.key;
      body.append(row);
    }
    table.append(body);
    return element("details", {className: "pugh-fold"}, element("summary", {textContent: "Sensitivity"}),
      element("div", {className: "pugh-scroll"}, table));
  }
  function draw(figure, spec, host = figure.querySelector(".figure-live"), {print = false} = {}) {
    const result = decide(spec, states.get(figure.id) || {});
    const view = element("div", {className: "pugh-view"}, bottomLine(spec, result), matrixTable(spec, result, figure, {print}));
    for (const fold of [meanings(spec), sensitivityFold(result)]) if (fold) view.append(fold);
    host.replaceChildren(view);
    const reset = figure.querySelector(":scope > .figure-options .pugh-reset");
    if (reset) reset.disabled = !changed(spec, figure.id);
    figure.dataset.pughWinner = result.suggestion?.key ?? "";
    figure.classList.add("figure-pugh-ready");
    return result;
  }
  function render(figure, spec, host) {
    if (!engine()) {
      host.replaceChildren(element("p", {textContent: "Decision unavailable: its engine did not load.", role: "status"}));
      figure.dataset.figureError = "decision engine unavailable";
      try { globalThis.obsCapabilities?.fail("pugh", "the decision engine did not load"); } catch (_error) { /* No canary. */ }
      return;
    }
    draw(figure, spec, host);
  }
  /** The options menu's Reset weights (figures.js, FIGURE_OPTIONS): the matrix's own weights back. */
  function option(figure) {
    const reset = element("button", {type: "button", className: "filter-pill pugh-reset", textContent: "Reset weights",
      title: "Decide again with the matrix's own weights"});
    reset.disabled = !states.has(figure.id);
    reset.addEventListener("click", () => {
      states.delete(figure.id);
      draw(figure, JSON.parse(figure.dataset.figureSpec));
    });
    return reset;
  }
  /** The print copy of a figure: the reader's view, its weights as text, and a caption note where they changed. */
  function print(figure, spec) {
    draw(figure, spec, figure.querySelector(".figure-live"), {print: true});
    if (!changed(spec, figure.id) || figure.querySelector(".figure-view-note")) return;
    const note = element("span", {className: "figure-view-note", textContent: ` ${VIEW_NOTE}`});
    let caption = figure.querySelector("figcaption");
    if (!caption) { caption = element("figcaption"); figure.append(caption); }
    (caption.querySelector("p:last-child") || caption).append(note);
  }
  return {render, print, option, decide, VIEW_NOTE, state: anchor => states.get(anchor)};
})();
