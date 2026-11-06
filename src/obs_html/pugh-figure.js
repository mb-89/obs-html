/* Decision figures, decided live in the reader (features.py, pugh; artifact-ui.md, Decision
   figures). The Document carries the matrix as the core checked it (obs capabilities/
   pugh-decisions); ctrl's engine (vendor/pugh.js, embedded before figures.js as
   globalThis.obsPughEngine) decides it here, unchanged. The figure hands the engine the fence's
   matrix with the reader's weights, a Checklist criterion where failed checklist items name
   options, and the reader's changed marks as the engine's own cell overrides.

   Top to bottom (artifact-ui.md, Decision figures): the options list, one line each and
   expandable; the winner line; then the tabs of TABS, each with its badge where it has one
   (Matrix: the table, or below ROWS_BELOW of the figure's width its rows; Checklist; Sensitivity;
   Pareto), and one tab for each section of the chapter the page rendered into the figure
   (render.py, decision tabs). The reader's weights, marks, rulings and tripwires, the options
   expanded and the tab are session-only view state, kept per figure anchor; readerState() gives
   the first four by figure anchor, options by letter. Print shows the options expanded, the
   winner line and the Matrix tab as the reader left it, with a caption note where weights or
   marks changed.

   A figure whose chapter carries an answer (obs input-model, Answers) shows the answer's weights,
   marks and rulings read-only (its spec's ``answered``); where the chapter asks for a bless
   (bless.js), the matrix's last row has a Pick key under each option other than the winner. */
globalThis.obsPugh = (() => {
  const VIEW_NOTE = "View changed by the reader.";
  const CHECKLIST = "checklist";  // The key of the row failed checklist items make (the core reserves it).
  const MARKS = [-2, -1, 0, 1, 2];
  const states = new Map();  // figure anchor -> the reader's view state, this session only.
  const engine = () => globalThis.obsPughEngine;
  const percent = share => `${(100 * share).toFixed(1)} %`;
  const number = value => engine().fmt(value);
  const signed = value => (value > 0 ? `+${number(value)}` : value < 0 ? `−${number(-value)}` : "0");
  const symbol = mark => (mark === null || mark === undefined ? "?" : engine().SYMBOL[Math.round(mark)]);
  const letterOf = index => String.fromCharCode(65 + index);
  /** Whether an option's label says more than its short name, so the options list and a
      letter's popover show it (artifact-ui.md, Decision figures): not where the short name's words are all the label's
      words or a run of them, "Two lines" of "Keep two lines"; always where there is no short name. */
  const labelAdds = (short, label) => {
    const words = text => (text ?? "").toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
    const name = words(short), said = words(label);
    return !name.length || !said.some((_, start) => name.every((word, index) => said[start + index] === word));
  };
  /** An option where there is room: its letter and short name, "B · Close". */
  const tag = option => (option.short ? `${option.letter} · ${option.short}` : option.letter);

  function element(tag, properties = {}, ...children) {
    const node = Object.assign(document.createElement(tag), properties);
    node.append(...children.filter(child => child !== null && child !== undefined && child !== false));
    return node;
  }
  function state(anchor, answered) {
    if (!states.has(anchor)) {
      states.set(anchor, {weights: {}, marks: {}, rulings: {}, open: {}, tab: "matrix",
        ...(answered ? {...structuredClone({weights: {}, marks: {}, rulings: {}, ...answered}), locked: true} : {})});
      delete states.get(anchor).winner;
    }
    return states.get(anchor);
  }
  function changed(anchor) {
    const view = states.get(anchor);
    return Boolean(view && (Object.keys(view.weights).length || Object.values(view.marks).some(marks => Object.keys(marks).length)));
  }
  const texts = value => (value === undefined ? [] : [].concat(value));

  /** The options with their letters, the failed checklist items and the matrix the engine decides.
      An option's short name is the one the core resolved (spec.shortNames; obs input-model, Pugh
      decision figures), null where its letter stands alone. */
  function model(spec) {
    const options = spec.matrix.candidates.map((candidate, index) => {
      const name = String(candidate.label ?? candidate.key);
      return {key: candidate.key, letter: letterOf(index), name, short: spec.shortNames[index], what: candidate.what || "",
        wins: texts(candidate.wins), losses: texts(candidate.losses)};
    });
    const byLetter = Object.fromEntries(options.map(option => [option.letter, option]));
    const byKey = Object.fromEntries(options.map(option => [option.key, option]));
    const checklist = spec.matrix.checklist || [];
    const failed = checklist.filter(item => !item.pass);
    const counts = {};
    for (const item of failed) for (const letter of item.options || []) counts[letter] = (counts[letter] || 0) + 1;
    return {options, byLetter, byKey, checklist, failed, counts, row: Object.keys(counts).length > 0};
  }
  function matrixFor(spec, figureModel, weights) {
    const matrix = structuredClone(spec.matrix);
    delete matrix.checklist; delete matrix.checklistWeight; delete matrix.chosen;
    if (figureModel.row) {
      matrix.criteria.push({key: CHECKLIST, label: "Checklist", weight: spec.matrix.checklistWeight ?? 3,
        better: "higher", kind: "judged"});
      matrix.candidates.forEach((candidate, index) => {
        candidate.marks = {...candidate.marks, [CHECKLIST]: Math.max(-2, -(figureModel.counts[letterOf(index)] || 0))};
      });
    }
    for (const criterion of matrix.criteria) if (criterion.key in weights) criterion.weight = weights[criterion.key];
    return matrix;
  }
  /** The decision with the reader's weights and marks: ctrl's decide(); a changed mark is the
      engine's cell override, a nudge from the mark it computes to the reader's. */
  function decide(spec, view = {weights: {}, marks: {}}) {
    const figureModel = model(spec);
    const matrix = matrixFor(spec, figureModel, view.weights);
    const base = engine().decide(matrix);
    const overrides = [];
    for (const [letter, marks] of Object.entries(view.marks)) {
      const option = figureModel.byLetter[letter], computed = base.candidates.find(c => c.key === option.key);
      if (computed.datum) continue;  // The datum's marks are S by definition.
      for (const [criterion, mark] of Object.entries(marks)) {
        const by = mark - (computed.marks[criterion] ?? 0);
        if (by) overrides.push({kind: "cell", candidate: option.key, criterion, action: "nudge", by, comment: "Changed by the reader"});
      }
    }
    const result = overrides.length ? engine().decide({...matrix, overrides}) : base;
    return {result, figureModel};
  }
  /** The smallest change of all weights (kept >= 0) at which ``key`` draws level with the winner:
      the weights themselves, which the engine's minChange measures but does not return, by the
      same projection the engine makes (pugh.md, Sensitivity). */
  function allWeights(result, key) {
    const winner = result.candidates.find(c => c.key === result.suggestion.key);
    const other = result.candidates.find(c => c.key === key);
    const difference = result.criteria.map(c => (other.marks[c.key] ?? 0) - (winner.marks[c.key] ?? 0));
    let weights = result.weights.slice();
    for (let step = 0; step < 20; step++) {
      const gap = difference.reduce((total, x, i) => total + x * weights[i], 0) + (other.offset ?? 0) - (winner.offset ?? 0);
      if (gap >= -1e-12) break;
      const free = difference.map((x, i) => (weights[i] > 0 || x > 0 ? x : 0)), size = free.reduce((t, x) => t + x * x, 0);
      if (!size) return null;
      weights = weights.map((x, i) => Math.max(0, x - (gap / size) * free[i]));
    }
    return weights;
  }
  /** One world in plain words: "A wins if Speed weighs below 0.5 instead of 2", and the all-weights change. */
  function world(result, entry, name) {
    const criterion = key => result.criteria.find(c => c.key === key)?.label ?? key;
    let single;
    if (!entry.tie) single = `No change of one weight makes ${name} win.`;
    else if (entry.tie.now) single = `${name} ties the winner now; the tie-break decides.`;
    else if (entry.tie.to <= 1e-9) single = `${name} draws level if ${criterion(entry.tie.criterion)} weighs 0 instead of `
      + `${number(entry.tie.from)}.`;
    else single = `${name} wins if ${criterion(entry.tie.criterion)} weighs ${entry.tie.to < entry.tie.from ? "below" : "above"} `
      + `${number(entry.tie.to)} instead of ${number(entry.tie.from)}.`;
    const weights = entry.minChange ? allWeights(result, entry.key) : null;
    const moves = weights ? result.criteria.map((c, i) => [c, result.weights[i], weights[i]])
      .filter(([, from, to]) => Math.abs(to - from) >= 0.005) : [];
    const all = !weights ? "No change of all the weights together makes it win."
      : !moves.length ? "The weights as they stand already tie it."
        : `Or, all together: ${moves.map(([c, from, to]) => `${c.label} ${number(from)} → ${number(to)}`).join(", ")}.`;
    return {single, all, closeness: entry.minChange ? entry.minChange.rel : Infinity};
  }
  function named(option) {
    return element("span", {className: "pugh-named"}, element("span", {className: "pugh-letter", textContent: option.letter}),
      option.short ? ` · ${option.short}` : "");
  }

  /** The winner line, always shown, outside any tab. */
  function bottomLine(spec, result, figureModel) {
    const box = element("div", {className: "pugh-bottom"});
    box.dataset.pughPart = "winner";
    const suggestion = result.suggestion;
    if (!suggestion) return box.append(element("p", {textContent: "No option fits."})), box;
    const line = element("p");
    line.dataset.pughWinner = figureModel.byKey[suggestion.key].letter;
    line.append("Winner: ", element("strong", {}, named(figureModel.byKey[suggestion.key])),
      ` (${signed(suggestion.total)} against the datum `, named(figureModel.byKey[result.datum.key]), ")");
    const sensitivity = result.sensitivity;
    if (sensitivity) {
      const verdict = element("span", {className: `pugh-verdict pugh-${sensitivity.verdict}`,
        textContent: sensitivity.verdict === "holds" ? "the choice holds" : "the choice depends on the weights"});
      verdict.dataset.pughVerdict = sensitivity.verdict;
      line.append("; ", verdict, `: it wins ${percent(sensitivity.share)} of the random weight draws.`);
    } else line.append("; it is the only option to choose from.");
    box.append(line);
    return box;
  }
  /** The options, one line each ("A · Keep open"; the letter and label where there is no short
      name): expanding one shows its label where that says more, its sentence, its wins and its
      losses. What the reader expanded stays expanded while the figure redraws; print expands all. */
  function optionsList(figureModel, view, print) {
    const list = element("ul", {className: "pugh-option-list"}, ...figureModel.options.map(option => {
      const said = (part, label) => (option[part].length
        ? element("p", {className: `pugh-option-${part}`}, element("strong", {textContent: `${label}: `}), option[part].join("; ")) : null);
      const details = element("details", {open: print || Boolean(view.open[option.letter])},
        element("summary", {}, named(option), !option.short ? ` · ${option.name}` : ""),
        option.short && labelAdds(option.short, option.name) ? element("p", {className: "pugh-option-label", textContent: option.name}) : null,
        option.what ? element("p", {className: "pugh-option-what", textContent: option.what}) : null,
        said("wins", "Wins"), said("losses", "Losses"));
      if (!print) details.addEventListener("toggle", () => { view.open[option.letter] = details.open; });
      const item = element("li", {}, details);
      item.dataset.pughOption = option.letter;
      return item;
    }));
    list.dataset.pughPart = "options";
    return list;
  }
  /** An option's popover: its letter and short name, datum or winner, its label where that says
      more and its sentence (a column head's and a row letter's alike). */
  function aboutOption(figure, option, candidate, winner) {
    const pop = element("div", {className: "pugh-about", id: `${figure.id}--pugh-about-${option.letter}`, hidden: true},
      element("p", {}, element("strong", {}, named(option)),
        `${candidate.datum ? " (the datum)" : ""}${candidate.key === winner ? " (the winner)" : ""}`),
      labelAdds(option.short, option.name) ? element("p", {textContent: option.name}) : null,
      option.what ? element("p", {textContent: option.what}) : null);
    pop.setAttribute("role", "tooltip");
    return pop;
  }
  /** An option's wins or losses as a count, "2", its texts in a popover on hover, focus or tap;
      nothing where it has none. */
  function countKey(figure, option, part) {
    const said = option[part];
    if (!said.length) return null;
    const noun = part === "wins" ? (said.length === 1 ? "win" : "wins") : (said.length === 1 ? "loss" : "losses");
    const pop = element("div", {className: "pugh-texts-pop", id: `${figure.id}--pugh-${part}-${option.letter}`, hidden: true},
      element("p", {}, element("strong", {}, named(option)), ` · ${said.length} ${noun}`),
      element("ul", {}, ...said.map(text => element("li", {textContent: text}))));
    pop.setAttribute("role", "tooltip");
    const key = element("button", {type: "button", className: "pugh-count", textContent: String(said.length)});
    key.dataset.pughCount = option.letter;
    key.setAttribute("aria-label", `${option.letter}: ${said.length} ${noun}`);
    key.setAttribute("aria-describedby", pop.id);
    key.setAttribute("aria-expanded", "false");
    aboutControl(key, pop);
    return {key, pop};
  }
  function markChooser(figure, spec, view, letter, criterion, current, cell) {
    figure.querySelectorAll(".pugh-chooser").forEach(open => open.remove());
    const chooser = element("span", {className: "pugh-chooser"});
    chooser.setAttribute("role", "group");
    chooser.setAttribute("aria-label", "Choose a mark");
    for (const mark of MARKS) {
      const choice = element("button", {type: "button", className: "filter-pill", textContent: symbol(mark)});
      choice.setAttribute("aria-pressed", String(mark === current));
      choice.dataset.pughChoice = String(mark);
      choice.addEventListener("click", event => {
        event.stopPropagation();
        view.marks[letter] = {...view.marks[letter], [criterion]: mark};
        draw(figure, spec);
      });
      chooser.append(choice);
    }
    chooser.addEventListener("keydown", event => {
      if (event.key === "Escape") { event.stopPropagation(); chooser.remove(); }
    });
    cell.append(chooser);
    chooser.querySelector('[aria-pressed="true"]')?.focus();
  }
  function table(figure, spec, result, figureModel, view, {print: shown}) {
    const print = shown || view.locked;
    const scroll = element("div", {className: "pugh-scroll", tabIndex: 0});
    scroll.dataset.pughForm = "table";
    scroll.setAttribute("role", "region");
    scroll.setAttribute("aria-label", "Decision matrix");
    const order = [result.candidates.find(c => c.datum), ...result.candidates.filter(c => !c.datum)];
    const winner = result.suggestion?.key;
    const head = element("tr", {}, element("th", {scope: "col", className: "pugh-criterion", textContent: "Criterion"}),
      element("th", {scope: "col", className: "pugh-weight", textContent: "Weight"}));
    for (const candidate of order) {
      const option = figureModel.byKey[candidate.key];
      const said = [element("span", {className: "pugh-letter", textContent: option.letter}),
        option.short ? element("span", {className: "pugh-column-name", textContent: option.short}) : null,
        candidate.datum ? element("span", {className: "pugh-tag", textContent: "datum"}) : null,
        candidate.key === winner ? element("span", {className: "pugh-tag", textContent: "winner"}) : null];
      const cell = element("th", {scope: "col", title: candidate.fits ? `${option.letter}: ${option.name}` : candidate.whyNot});
      if (shown) cell.append(...said.filter(Boolean));
      else {
        // The head is a control: its option's popover, with the full label, on hover, focus or tap.
        const key = element("button", {type: "button", className: "pugh-head-key"}, ...said.filter(Boolean));
        const pop = aboutOption(figure, option, candidate, winner);
        key.dataset.pughHead = option.letter;
        key.setAttribute("aria-label", `Option ${option.letter}`);
        key.setAttribute("aria-describedby", pop.id);
        key.setAttribute("aria-expanded", "false");
        aboutControl(key, pop);
        cell.append(key, pop);
      }
      cell.dataset.pughOption = option.letter;
      if (candidate.datum) cell.classList.add("pugh-datum");
      if (candidate.key === winner) cell.classList.add("pugh-winner");
      if (!candidate.fits) cell.classList.add("pugh-out");
      head.append(cell);
    }
    const body = element("tbody");
    result.criteria.forEach((criterion, index) => {
      const row = element("tr", {}, element("th", {scope: "row", className: "pugh-criterion", textContent: criterion.label}));
      row.dataset.pughCriterion = criterion.key;
      const weight = result.weights[index], weightChanged = criterion.key in view.weights;
      if (print) row.append(element("td", {className: `pugh-weight${weightChanged ? " pugh-changed" : ""}`, textContent: number(weight)}));
      else {
        const input = element("input", {type: "number", min: "0", step: "0.5", value: String(weight),
          className: `pugh-weight-input${weightChanged ? " pugh-changed" : ""}`});
        input.setAttribute("aria-label", `Weight of ${criterion.label}${weightChanged ? ", changed" : ""}`);
        input.dataset.pughWeight = criterion.key;
        input.addEventListener("change", () => {
          const value = Number(input.value);
          if (!Number.isFinite(value) || value < 0) { input.value = String(weight); return; }
          view.weights[criterion.key] = value;
          draw(figure, spec);
          figure.querySelector(`[data-pugh-weight="${CSS.escape(criterion.key)}"]`)?.focus();
        });
        row.append(element("td", {className: "pugh-weight"}, input));
      }
      for (const candidate of order) {
        const option = figureModel.byKey[candidate.key], mark = candidate.marks[criterion.key];
        const markChanged = criterion.key in (view.marks[option.letter] || {}) && !candidate.datum;
        const cell = element("td", {className: `pugh-mark${markChanged ? " pugh-changed" : ""}${candidate.fits ? "" : " pugh-out"}`});
        cell.dataset.pughMark = `${option.letter}:${criterion.key}`;
        if (print || candidate.datum) cell.textContent = candidate.datum ? "S" : symbol(mark);
        else {
          const button = element("button", {type: "button", className: "pugh-mark-button", textContent: symbol(mark)});
          button.setAttribute("aria-label", `${option.letter}, ${criterion.label}: ${symbol(mark)}${markChanged ? ", changed" : ""}; change it`);
          button.addEventListener("click", () => markChooser(figure, spec, view, option.letter, criterion.key, mark, cell));
          cell.append(button);
        }
        row.append(cell);
      }
      body.append(row);
    });
    const total = element("tr", {className: "pugh-total"}, element("th", {scope: "row", className: "pugh-criterion", textContent: "Weighted total"}),
      element("td", {className: "pugh-weight"}));
    for (const candidate of order) {
      const cell = element("td", {textContent: candidate.fits ? signed(candidate.total) : `× ${signed(candidate.total)}`});
      cell.dataset.pughTotal = figureModel.byKey[candidate.key].letter;
      if (!candidate.fits) cell.classList.add("pugh-out"), cell.title = candidate.whyNot;
      total.append(cell);
    }
    body.append(total);
    for (const [part, label] of [["wins", "Wins"], ["losses", "Losses"]]) {
      if (!figureModel.options.some(option => option[part].length)) continue;
      const row = element("tr", {className: "pugh-texts"}, element("th", {scope: "row", className: "pugh-criterion", textContent: label}),
        element("td", {className: "pugh-weight"}));
      row.dataset.pughTexts = part;
      for (const candidate of order) {
        const option = figureModel.byKey[candidate.key];
        if (shown) { row.append(element("td", {className: "pugh-said", textContent: option[part].join("; ")})); continue; }
        const count = countKey(figure, option, part);
        row.append(element("td", {}, ...(count ? [count.key, count.pop] : [])));
      }
      body.append(row);
    }
    const picks = print ? [] : order.map(c => (c.key === winner ? null : globalThis.obsBless?.columnKey(figure.id, figureModel.byKey[c.key].letter)));
    if (picks.some(Boolean)) {
      const row = element("tr", {className: "pugh-picks"}, element("th", {scope: "row", className: "pugh-criterion", textContent: "Pick"}),
        element("td", {className: "pugh-weight"}));
      for (const pick of picks) row.append(element("td", {}, pick));
      body.append(row);
    }
    scroll.append(element("table", {className: "pugh-matrix"}, element("thead", {}, head), body));
    return scroll;
  }
  /** A letter in the rows, a column head and a Wins or Losses count are controls: hovering one,
      focusing it or tapping it shows its popover (its option's letter, label and sentence, or the
      texts counted) under its line or cell; a second tap, or a tap elsewhere, closes it. One shows
      at a time. */
  let about = null;
  function closeAbout() {
    if (!about) return;
    about.pop.hidden = true;
    about.head.setAttribute("aria-expanded", "false");
    about = null;
  }
  function openAbout(head, pop) {
    if (about?.head === head) return;
    closeAbout();
    head.closest(".pugh-row")?.append(pop);  // In the rows, under the line; a column head's stays in its cell.
    pop.hidden = false;
    head.setAttribute("aria-expanded", "true");
    about = {head, pop};
  }
  document.addEventListener("pointerdown", event => {
    if (about && !about.head.contains(event.target) && !about.pop.contains(event.target)) closeAbout();
  }, true);
  function aboutControl(head, pop) {
    let wasOpen = false;
    head.addEventListener("pointerdown", () => { wasOpen = about?.head === head; });
    head.addEventListener("click", event => {
      // A tap focuses (which opens) before it clicks: what decides is whether it was open before the tap.
      const open = event.detail === 0 ? about?.head === head : wasOpen;
      if (open) closeAbout(); else openAbout(head, pop);
      wasOpen = about?.head === head;
    });
    head.addEventListener("focus", () => openAbout(head, pop));
    head.addEventListener("blur", () => { if (about?.head === head) closeAbout(); });
    head.addEventListener("pointerenter", event => { if (event.pointerType === "mouse") openAbout(head, pop); });
    head.addEventListener("pointerleave", event => { if (event.pointerType === "mouse" && about?.head === head) closeAbout(); });
    head.addEventListener("keydown", event => { if (event.key === "Escape" && about?.head === head) { event.stopPropagation(); closeAbout(); } });
  }
  /** The weight a step key sets: half a step up or down, never below 0. */
  function stepped(weight, direction) {
    return Math.max(0, Math.round((weight + direction * 0.5) * 2) / 2);
  }
  /** The matrix at a narrow width: one line per criterion, its name over the full width, then its
      weight stepper and one cell per option headed by its letter; the total and the wins and
      losses the same way. The table's data, the table's keys; options by letter, named in tooltips. */
  function rows(figure, spec, result, figureModel, view) {
    const locked = Boolean(view.locked);
    const box = element("div", {className: "pugh-rows"});
    box.dataset.pughForm = "rows";
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", "Decision matrix");
    const order = [result.candidates.find(c => c.datum), ...result.candidates.filter(c => !c.datum)];
    const winner = result.suggestion?.key;
    const abouts = Object.fromEntries(order.map(candidate => {
      const option = figureModel.byKey[candidate.key];
      const about = aboutOption(figure, option, candidate, winner);
      box.append(about);
      return [option.letter, about];
    }));
    const head = candidate => {
      const option = figureModel.byKey[candidate.key];
      const letter = element("button", {type: "button", className: "pugh-cell-head", textContent: option.letter});
      letter.dataset.pughHead = option.letter;
      letter.setAttribute("aria-label", `Option ${option.letter}`);
      letter.setAttribute("aria-describedby", abouts[option.letter].id);
      letter.setAttribute("aria-expanded", "false");
      aboutControl(letter, abouts[option.letter]);
      return letter;
    };
    const cell = (candidate, className = "") => {
      const node = element("div", {className: `pugh-cell${className}${candidate.key === winner ? " pugh-winner" : ""}`
        + `${candidate.datum ? " pugh-datum" : ""}${candidate.fits ? "" : " pugh-out"}`});
      if (!candidate.fits) node.title = candidate.whyNot;
      return node;
    };
    const line = (name, className = "") => {
      const row = element("div", {className: `pugh-row${className}`}, element("p", {className: "pugh-row-name", textContent: name}));
      const cells = element("div", {className: "pugh-row-cells"});
      row.append(cells);
      return {row, cells};
    };
    result.criteria.forEach((criterion, index) => {
      const {row, cells} = line(criterion.label);
      row.dataset.pughCriterion = criterion.key;
      const weight = result.weights[index], weightChanged = criterion.key in view.weights;
      const value = element("span", {className: `pugh-weight-value${weightChanged ? " pugh-changed" : ""}`, textContent: number(weight)});
      value.dataset.pughWeight = criterion.key;
      value.setAttribute("aria-label", `Weight of ${criterion.label}: ${number(weight)}${weightChanged ? ", changed" : ""}`);
      const step = (sign, direction, label) => {
        const key = element("button", {type: "button", className: "pugh-step", textContent: label});
        key.dataset.pughStep = `${criterion.key}:${sign}`;
        key.setAttribute("aria-label", `${direction < 0 ? "Lower" : "Raise"} the weight of ${criterion.label}`);
        key.disabled = direction < 0 && weight <= 0;
        key.addEventListener("click", () => {
          view.weights[criterion.key] = stepped(weight, direction);
          draw(figure, spec);
          figure.querySelector(`[data-pugh-step="${CSS.escape(key.dataset.pughStep)}"]`)?.focus();
        });
        return key;
      };
      cells.append(element("span", {className: "pugh-stepper"},
        ...(locked ? [value] : [step("-", -1, "−"), value, step("+", 1, "+")])));
      for (const candidate of order) {
        const option = figureModel.byKey[candidate.key], mark = candidate.marks[criterion.key];
        const markChanged = criterion.key in (view.marks[option.letter] || {}) && !candidate.datum;
        const node = cell(candidate, markChanged ? " pugh-changed" : "");
        node.dataset.pughMark = `${option.letter}:${criterion.key}`;
        node.append(head(candidate));
        if (locked || candidate.datum) node.append(element("span", {className: "pugh-cell-value", textContent: candidate.datum ? "S" : symbol(mark)}));
        else {
          const button = element("button", {type: "button", className: "pugh-mark-button", textContent: symbol(mark)});
          button.setAttribute("aria-label", `${option.letter} ${option.name}, ${criterion.label}: ${symbol(mark)}${markChanged ? ", changed" : ""}; change it`);
          button.addEventListener("click", () => markChooser(figure, spec, view, option.letter, criterion.key, mark, node));
          node.append(button);
        }
        cells.append(node);
      }
      box.append(row);
    });
    const total = line("Weighted total", " pugh-total");
    total.cells.append(element("span", {className: "pugh-stepper pugh-stepper-space"}));
    for (const candidate of order) {
      const node = cell(candidate);
      node.dataset.pughTotal = figureModel.byKey[candidate.key].letter;
      node.append(head(candidate), element("span", {className: "pugh-cell-value",
        textContent: candidate.fits ? signed(candidate.total) : `× ${signed(candidate.total)}`}));
      total.cells.append(node);
    }
    box.append(total.row);
    for (const [part, label] of [["wins", "Wins"], ["losses", "Losses"]]) {
      if (!figureModel.options.some(option => option[part].length)) continue;
      const texts = line(label, " pugh-texts");
      texts.row.dataset.pughTexts = part;
      texts.cells.append(element("span", {className: "pugh-stepper pugh-stepper-space"}));
      for (const candidate of order) {
        const node = cell(candidate), count = countKey(figure, figureModel.byKey[candidate.key], part);
        node.append(head(candidate), ...(count ? [count.key, count.pop] : [element("span", {className: "pugh-cell-value"})]));
        texts.cells.append(node);
      }
      box.append(texts.row);
    }
    const picks = locked ? [] : order.filter(c => c.key !== winner)
      .map(c => globalThis.obsBless?.columnKey(figure.id, figureModel.byKey[c.key].letter)).filter(Boolean);
    if (picks.length) box.append(element("div", {className: "pugh-picks"}, ...picks));
    return box;
  }
  function checklistPanel(figureModel) {
    if (!figureModel.checklist.length) return element("p", {textContent: "No checklist items."});
    return element("ul", {className: "pugh-checklist"}, ...figureModel.checklist.map(item => {
      const entry = element("li", {className: item.pass ? "pugh-pass" : "pugh-fail"},
        element("strong", {textContent: `${item.pass ? "✓ Passed" : "✗ Failed"}: `}), `${item.item} `,
        element("span", {className: "pugh-answer", textContent: item.answer}),
        item.options?.length ? ` (fails ${item.options.join(", ")})` : "");
      entry.dataset.pughItem = item.pass ? "pass" : "fail";
      return entry;
    }));
  }
  /** Where the fence's chosen option is not the winner: why, in the form of a world, else null. */
  function chosenWorld(spec, result, figureModel) {
    const chosen = spec.matrix.chosen && figureModel.byKey[spec.matrix.chosen];
    if (!chosen || !result.suggestion || chosen.key === result.suggestion.key) return null;
    const entry = (result.sensitivity?.all ?? []).find(item => item.key === chosen.key);
    const candidate = result.candidates.find(c => c.key === chosen.key);
    const why = !candidate.fits ? `it does not fit (${candidate.whyNot}).`
      : entry ? (({single, all}) => `${single} ${all}`)(world(result, entry, tag(chosen)))
        : "it may be ranked but not suggested.";
    return {option: chosen, why, line: `You chose ${tag(chosen)}, but ${tag(figureModel.byKey[result.suggestion.key])} wins: `};
  }
  function sensitivityPanel(figure, spec, result, figureModel, view) {
    const panel = element("div", {className: "pugh-whatif"});
    if (!result.suggestion) return panel.append(element("p", {textContent: "No option fits."})), panel;
    const winner = figureModel.byKey[result.suggestion.key];
    const entries = result.sensitivity?.all ?? [];
    const worlds = entries.map(entry => ({entry, option: figureModel.byKey[entry.key], said: world(result, entry, tag(figureModel.byKey[entry.key]))}));
    const closest = worlds.filter(item => Number.isFinite(item.said.closeness)).sort((a, b) => a.said.closeness - b.said.closeness)[0];
    const top = element("p", {className: "pugh-whatif-top"});
    top.dataset.pughUnless = closest ? closest.option.letter : "";
    if (closest) top.append(element("strong", {textContent: `${tag(winner)} wins unless: `}), `${closest.said.single} ${closest.said.all}`);
    else top.append(element("strong", {textContent: "No change of weights makes another option win."}));
    panel.append(top);
    const chosen = chosenWorld(spec, result, figureModel);
    if (chosen) {
      const line = element("p", {className: "pugh-whatif-chosen"}, element("strong", {textContent: chosen.line}), chosen.why);
      line.dataset.pughChosen = chosen.option.letter;
      panel.append(line);
    }
    const list = element("ul", {className: "pugh-worlds"});
    for (const {option, said} of worlds) {
      const ruling = view.rulings[option.letter] || {};
      const item = element("li", {}, element("p", {}, `${said.single} ${said.all}`,
        spec.matrix.chosen === option.key ? element("em", {textContent: " (the chosen option)"}) : null));
      item.dataset.pughWorld = option.letter;
      const keys = element("div", {className: "pugh-ruling"});
      for (const [value, label] of [["could", "Could happen"], ["nonsense", "Nonsense"]]) {
        const key = element("button", {type: "button", className: "filter-pill", textContent: label});
        key.setAttribute("aria-pressed", String(ruling.ruling === value));
        key.dataset.pughRuling = value;
        key.disabled = Boolean(view.locked);
        key.addEventListener("click", () => {
          view.rulings[option.letter] = ruling.ruling === value ? {} : {...ruling, ruling: value};
          draw(figure, spec);
        });
        keys.append(key);
      }
      item.append(keys);
      if (ruling.ruling === "could") {
        const tripwire = element("input", {type: "text", className: "pugh-tripwire", value: ruling.tripwire || "",
          placeholder: "A sign to watch for"});
        tripwire.setAttribute("aria-label", `Tripwire for ${option.letter}: a sign to watch for`);
        tripwire.dataset.pughTripwire = option.letter;
        tripwire.readOnly = Boolean(view.locked);
        tripwire.addEventListener("change", () => {
          view.rulings[option.letter] = {...view.rulings[option.letter], tripwire: tripwire.value.trim()};
          draw(figure, spec);
        });
        item.append(tripwire);
      }
      list.append(item);
    }
    for (const candidate of result.candidates.filter(c => !c.fits)) {
      list.append(element("li", {}, element("p", {textContent: `${tag(figureModel.byKey[candidate.key])} does not fit: ${candidate.whyNot}.`})));
    }
    panel.append(list);
    return panel;
  }
  /** The Sensitivity flag's reasons: the choice depends on the weights, a world the reader ruled
      "could happen", the fence's chosen option is not the winner. */
  function sensitivityFlag({spec, result, figureModel, view}) {
    const reasons = [];
    if (result.sensitivity?.verdict === "depends") reasons.push("the choice depends on the weights");
    if (Object.values(view.rulings).some(ruling => ruling.ruling === "could")) reasons.push("a world could happen");
    if (chosenWorld(spec, result, figureModel)) reasons.push("the chosen option does not win");
    return reasons.length ? {flag: true, says: reasons.join("; ")} : null;
  }
  /** The figure's tabs, in order, after which come the chapter's sections: each its key, label,
      panel, whether it is disabled and its badge, a function of the decision that returns a count
      ({count, says}), a flag ({flag: true, says}) or null (artifact-ui.md, Tab badges). */
  const TABS = [
    {key: "matrix", label: "Matrix",
      panel: ({figure, spec, result, figureModel, view, print}) => (!print && narrow(figure)
        ? rows(figure, spec, result, figureModel, view) : table(figure, spec, result, figureModel, view, {print}))},
    {key: "checklist", label: "Checklist", panel: ({figureModel}) => checklistPanel(figureModel),
      disabled: ({figureModel}) => !figureModel.checklist.length,
      badge: ({figureModel}) => (figureModel.failed.length ? {count: figureModel.failed.length, says: `${figureModel.failed.length} failed`} : null)},
    {key: "sensitivity", label: "Sensitivity",
      panel: ({figure, spec, result, figureModel, view}) => sensitivityPanel(figure, spec, result, figureModel, view),
      badge: sensitivityFlag},
    {key: "pareto", label: "Pareto", panel: () => null, disabled: () => true},
  ];
  /** A tab's badge in the adapter's tab control: a count or a flag after its label, said in the
      tab's accessible name; none where the badge says nothing. */
  function tabBadge(tab, label, badge) {
    tab.replaceChildren(element("span", {className: "tab-label", textContent: label}));
    tab.removeAttribute("aria-label");
    if (!badge) return;
    const mark = element("span", {className: `tab-badge${badge.flag ? " tab-badge-flag" : ""}`, title: badge.says,
      textContent: badge.flag ? "" : String(badge.count)});
    mark.dataset.tabBadge = badge.flag ? "flag" : String(badge.count);
    mark.setAttribute("aria-hidden", "true");
    tab.append(mark);
    tab.setAttribute("aria-label", `${label}, ${badge.says}`);
  }
  /** The chapter's sections after the figure, which the page renders into the figure as one more
      tab each (render.py, decision tabs): wherever a draw left them, so each keeps its nodes. */
  const extras = figure => [...figure.querySelectorAll(".pugh-extra")];
  const tabsOf = figure => [...TABS, ...extras(figure).map((node, index) => ({key: `extra-${index + 1}`, label: node.dataset.pughExtra, section: node}))];
  function tabs(figure, spec, view, panels, all, context) {
    const list = element("div", {className: "data-table-detail-tabs pugh-tabs"});
    list.dataset.pughPart = "tabs";
    list.setAttribute("role", "tablist");
    list.setAttribute("aria-label", "Decision views");
    const enabled = all.filter(tab => !tab.disabled?.(context)).map(tab => tab.key);
    const buttons = all.map((tab, index) => {
      const button = element("button", {type: "button", id: `${figure.id}--pugh-tab-${tab.key}`});
      tabBadge(button, tab.label, tab.badge?.(context));
      button.setAttribute("role", "tab");
      button.setAttribute("aria-controls", panels[index].id);
      button.setAttribute("aria-selected", String(view.tab === tab.key));
      button.tabIndex = view.tab === tab.key ? 0 : -1;
      button.disabled = !enabled.includes(tab.key);
      button.dataset.pughTab = tab.key;
      panels[index].setAttribute("aria-labelledby", button.id);
      button.addEventListener("click", () => { view.tab = tab.key; draw(figure, spec); figure.querySelector(`[data-pugh-tab="${tab.key}"]`)?.focus(); });
      button.addEventListener("keydown", event => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        event.stopPropagation();
        const position = enabled.indexOf(view.tab);
        view.tab = enabled[(position + (event.key === "ArrowRight" ? 1 : enabled.length - 1)) % enabled.length];
        draw(figure, spec);
        figure.querySelector(`[data-pugh-tab="${view.tab}"]`)?.focus();
      });
      return button;
    });
    list.append(...buttons);
    return list;
  }
  /** The view keeps to the prose around the figure, inside its frame, clear of the chapter controls:
      its inline margins are the frame's overhang beyond its parent's content box. */
  const fitted = new WeakSet();
  function fit(figure) {
    const view = figure.querySelector(".figure-live > *"), parent = figure.parentElement;
    if (!view || !parent) return;
    const style = getComputedStyle(parent), outer = parent.getBoundingClientRect(), frame = figure.getBoundingClientRect();
    const left = outer.left + parseFloat(style.paddingLeft), right = outer.right - parseFloat(style.paddingRight);
    view.style.marginInline = `${Math.max(0, left - frame.left)}px ${Math.max(0, frame.right - right)}px`;
    if (fitted.has(figure) || typeof ResizeObserver !== "function") return;
    fitted.add(figure);
    const observer = new ResizeObserver(() => {
      if (!figure.isConnected) return observer.disconnect();
      const shown = figure.querySelector("[data-pugh-form]")?.dataset.pughForm;
      if (shown && shown !== (narrow(figure) ? "rows" : "table")) draw(figure, JSON.parse(figure.dataset.figureSpec));
      else fit(figure);
    });
    observer.observe(figure);
    observer.observe(parent);
  }
  /** Below ROWS_BELOW (in rem) of the figure's own width, the matrix is rows (artifact-ui.md, Decision figures). */
  const ROWS_BELOW = 36;
  function narrow(figure) {
    const width = figure.clientWidth;
    return width > 0 && width < ROWS_BELOW * parseFloat(getComputedStyle(document.documentElement).fontSize);
  }
  function draw(figure, spec, host = figure.querySelector(".figure-live"), {print = false} = {}) {
    const view = state(figure.id, spec.answered);
    const {result, figureModel} = decide(spec, view);
    const context = {figure, spec, result, figureModel, view, print};
    const all = tabsOf(figure);
    const matrix = element("div", {className: "pugh-view"}, TABS[0].panel(context));
    view.winner = result.suggestion ? figureModel.byKey[result.suggestion.key].letter : "";
    if (!print && !view.locked && changed(figure.id)) {
      const reset = element("button", {type: "button", className: "filter-pill pugh-reset", textContent: "Reset"});
      reset.title = "Restore the fence's weights and marks";
      reset.addEventListener("click", () => reset_(figure, spec));
      matrix.append(reset);
    }
    const top = [optionsList(figureModel, view, print), bottomLine(spec, result, figureModel)];
    const sections = all.filter(tab => tab.section).map(tab => tab.section);
    if (print) {
      sections.forEach(section => { section.hidden = false; section.removeAttribute("role"); });
      host.replaceChildren(element("div", {className: "pugh-view"}, ...top, matrix, ...sections));
    } else {
      if (!all.some(tab => tab.key === view.tab && !tab.disabled?.(context))) view.tab = "matrix";
      const panels = all.map((tab, index) => {
        const panel = tab.section ?? (index ? element("div", {className: "pugh-view"}, tab.panel(context)) : matrix);
        if (!tab.section) panel.id = `${figure.id}--pugh-panel-${tab.key}`;
        panel.setAttribute("role", "tabpanel");
        panel.hidden = view.tab !== tab.key;
        return panel;
      });
      host.replaceChildren(element("div", {className: "pugh-figure-view"}, ...top, tabs(figure, spec, view, panels, all, context), ...panels));
    }
    const menuReset = figure.querySelector(":scope > .figure-options .pugh-reset");
    if (menuReset) menuReset.disabled = view.locked || !changed(figure.id);
    figure.dataset.pughWinner = view.winner;
    figure.classList.add("figure-pugh-ready");
    if (!print) fit(figure);
    return result;
  }
  function reset_(figure, spec) {
    const view = state(figure.id, spec.answered);
    if (view.locked) return;  // An answer's changes are the record; nothing resets them.
    view.weights = {};
    view.marks = {};
    draw(figure, spec);
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
  /** Opens the tab that holds ``target``, a chapter section the page rendered into a decision
      figure or a place inside one, for the artifact's one way of revealing a place (artifact.js,
      revealSource); a figure not yet drawn opens at that tab. Elsewhere it does nothing. */
  function reveal(target) {
    const section = target?.closest?.(".pugh-extra");
    const figure = section?.closest('[data-figure-kind="pugh"]');
    if (!figure) return;
    const spec = JSON.parse(figure.dataset.figureSpec);
    state(figure.id, spec.answered).tab = `extra-${extras(figure).indexOf(section) + 1}`;
    if (figure.classList.contains("figure-pugh-ready") && !figure.closest(".print-book")) draw(figure, spec);
  }
  /** The options menu's Reset (figures.js, FIGURE_OPTIONS): the fence's weights and marks back. */
  function option(figure) {
    const reset = element("button", {type: "button", className: "filter-pill pugh-reset", textContent: "Reset",
      title: "Restore the fence's weights and marks"});
    reset.disabled = Boolean(states.get(figure.id)?.locked) || !changed(figure.id);
    reset.addEventListener("click", () => reset_(figure, JSON.parse(figure.dataset.figureSpec)));
    return reset;
  }
  /** The print copy of a figure: the Matrix tab as the reader left it, and a caption note where it changed. */
  function print(figure, spec) {
    draw(figure, spec, figure.querySelector(".figure-live"), {print: true});
    if (!changed(figure.id) || figure.querySelector(".figure-view-note")) return;
    const note = element("span", {className: "figure-view-note", textContent: ` ${VIEW_NOTE}`});
    let caption = figure.querySelector("figcaption");
    if (!caption) { caption = element("figcaption"); figure.append(caption); }
    (caption.querySelector("p:last-child") || caption).append(note);
  }
  /** The reader's changed weights and marks, rulings and tripwires, and the winner they give, by figure
      anchor (a figure the reader left as it was, or one an answer shows, is not listed), options by letter. */
  function readerState() {
    const marked = view => Object.fromEntries(Object.entries(view.marks).filter(([, marks]) => Object.keys(marks).length));
    return Object.fromEntries([...states].filter(([, view]) => !view.locked)
      .map(([anchor, view]) => [anchor, structuredClone({weights: view.weights, marks: marked(view), rulings: view.rulings,
        winner: view.winner})])
      .filter(([, view]) => Object.keys(view.weights).length || Object.keys(view.marks).length || Object.keys(view.rulings).length));
  }
  /** A figure's options as it letters and names them: letter, name and short name (model), for the
      bless pill's "Picked B · Close" (bless.js). */
  const options = spec => model(spec).options.map(({letter, name, short}) => ({letter, name, short}));
  return {render, print, option, reveal, decide, allWeights, readerState, options, labelAdds, VIEW_NOTE};
})();
