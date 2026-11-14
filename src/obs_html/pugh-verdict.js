/* A decision figure's computed verdict and the reader's vetoes, lifts and datum (artifact-ui.md,
   The engine's bottom line; The reader's vetoes and datum): the pugh feature's part "verdict",
   which ships only in an artifact built with artifact.figures.decisionVerdict on (features.py).
   Without it the figure is what it was, byte for byte: pugh-figure.js calls this module only
   inside its "part verdict" regions, which the renderer strips where the part does not ship.

   Two layers. The pure one takes data and gives data, with no page: overridesOf turns the
   reader's changes into ctrl's engine overrides, bottomLineOf turns the engine's result into the
   bottom line's lines. The wiring draws those lines and the expander's keys, and keeps the
   reader's changes in the figure's view state (vetoes, lifts, datum). The engine itself is ctrl's,
   unchanged (vendor/pugh.js), and decides everything. */
globalThis.obsPughVerdict = (() => {
  const READER = "Changed by the reader";  // Every override needs a comment (ctrl's pugh.md, The person's changes).

  /** The reader's vetoes, lifts and datum as ctrl's engine overrides, datum first: ``changes`` is
      {vetoes: [letter], lifts: {letter: [veto id]}, datum: letter | null}, ``keyOf`` a letter's option key. */
  function overridesOf(changes, keyOf) {
    return [
      ...(changes.datum ? [{kind: "datum", candidate: keyOf(changes.datum), comment: READER}] : []),
      ...(changes.vetoes ?? []).map(letter => ({kind: "option", candidate: keyOf(letter), action: "veto", comment: READER})),
      ...Object.entries(changes.lifts ?? {}).flatMap(([letter, ids]) => ids.map(veto => ({kind: "lift", candidate: keyOf(letter), veto, comment: READER}))),
    ];
  }

  /** The engine's bottom line as lines of data, in order: the verdict, each of the engine's
      runners-up with its single-weight tie and whether that change is reasonable, then each option
      with a veto, in letter order, its standing and lifted vetoes. ``nameOf(key)`` names an option
      ("B · Close"), ``letterOf(key)`` gives its letter, ``number`` formats a number as the engine does. */
  function bottomLineOf(result, nameOf, letterOf, number) {
    const lines = [], sensitivity = result.sensitivity;
    const label = key => result.criteria.find(criterion => criterion.key === key)?.label ?? key;
    const percent = share => `${(100 * share).toFixed(1)} %`;
    if (result.suggestion && !sensitivity) lines.push({part: "verdict", text: `${nameOf(result.suggestion.key)} is the only option that fits.`});
    if (result.suggestion && sensitivity) {
      const share = `${nameOf(sensitivity.winner)} wins ${percent(sensitivity.share)} of the weight draws within ±${number(sensitivity.step)}.`;
      lines.push({part: "verdict", verdict: sensitivity.verdict,
        text: sensitivity.verdict === "holds" ? `The choice holds: ${share}` : `The choice depends on the weights: ${share}`});
      for (const runner of sensitivity.runnersUp) {
        const tie = runner.tie, who = nameOf(runner.key);
        lines.push({part: "runner-up", letter: letterOf(runner.key), reasonable: tie && !tie.now ? tie.reasonable : null,
          text: !tie ? `No single weight makes ${who} tie.` : tie.now ? `${who} ties it now.`
            : `${who} ties if ${label(tie.criterion)} goes ${number(tie.from)} → ${number(tie.to)}: ${tie.reasonable ? "a reasonable change" : "not a reasonable change"}.`});
      }
    }
    const reason = veto => (veto.by === "person" ? "vetoed by you" : veto.why);
    const sentence = text => (/[.!?]$/.test(text) ? text : `${text}.`);
    for (const candidate of [...result.candidates].sort((a, b) => letterOf(a.key).localeCompare(letterOf(b.key)))) {
      if (!candidate.vetoes.length) continue;
      const standing = candidate.vetoes.filter(veto => !veto.lifted), lifted = candidate.vetoes.filter(veto => veto.lifted);
      const said = [...standing.map(reason), ...lifted.map(veto => `lifted: ${reason(veto)}`)].join("; ");
      lines.push({part: "veto", letter: letterOf(candidate.key), text: `${nameOf(candidate.key)} is ${standing.length ? "out" : "in"}: ${sentence(said)}`});
    }
    return lines;
  }

  // The wiring: what pugh-figure.js calls inside its "part verdict" regions.
  const engine = () => globalThis.obsPughEngine;
  const changesOf = view => ({vetoes: view.vetoes ?? [], lifts: view.lifts ?? {}, datum: view.datum ?? null});
  const nameIn = figureModel => key => { const option = figureModel.byKey[key]; return option.short ? `${option.letter} · ${option.short}` : option.letter; };
  const letterIn = figureModel => key => figureModel.byKey[key].letter;
  function element(tag, properties = {}, ...children) {
    const node = Object.assign(document.createElement(tag), properties);
    node.append(...children.filter(child => child !== null && child !== undefined && child !== false));
    return node;
  }

  /** The figure's decision hands the engine these overrides first (pugh-figure.js, decide). */
  const overrides = (view, figureModel) => overridesOf(changesOf(view), letter => figureModel.byLetter[letter].key);
  /** Whether the reader changed a veto, a lift or the datum: Reset and print's caption note follow it. */
  const changed = view => Boolean(view && ((view.vetoes ?? []).length || Object.keys(view.lifts ?? {}).length || view.datum));
  /** The reader's changes for readerState(), each only where set, so a payload without them is as before. */
  function state(view) {
    const {vetoes, lifts, datum} = changesOf(view);
    return {...(vetoes.length ? {vetoes} : {}), ...(Object.keys(lifts).length ? {lifts} : {}), ...(datum ? {datum} : {})};
  }
  /** Reset restores the fence's vetoes and datum. */
  function reset(view) {
    delete view.vetoes;
    delete view.lifts;
    delete view.datum;
  }
  /** The bottom line's lines for the Proposed winner box, each a paragraph ``data-pugh-part`` names. */
  function bottomLine(result, figureModel) {
    return bottomLineOf(result, nameIn(figureModel), letterIn(figureModel), value => engine().fmt(value)).map((line, index) => {
      const node = element("p", {className: `pugh-bottom pugh-bottom-${line.part}`, textContent: line.text});
      node.style.marginBlock = index ? "0.2rem" : "0.6rem 0.2rem";
      node.dataset.pughPart = line.part;
      if (line.letter) node.dataset.pughFor = line.letter;
      if (line.verdict) node.dataset.pughVerdict = line.verdict;
      if (line.reasonable !== null && line.reasonable !== undefined) node.dataset.pughReasonable = String(line.reasonable);
      return node;
    });
  }
  /** An option's keys in its expander: Veto or Remove my veto, Make it the datum, and Lift or
      Restore after each of the engine's own vetoes; none where the figure is read only. */
  function actions({figure, spec, result, option, view, print, redraw}) {
    if (print || view.locked) return null;
    const candidate = result.candidates.find(c => c.key === option.key), letter = option.letter;
    const again = selector => { redraw(); figure.querySelector(selector)?.focus(); };
    const key = (text, data, pressed, act) => {
      const button = element("button", {type: "button", className: "filter-pill", textContent: text});
      Object.assign(button.dataset, data);
      if (pressed !== null) button.setAttribute("aria-pressed", String(pressed));
      button.addEventListener("click", event => { event.stopPropagation(); act(); });
      return button;
    };
    const box = element("div", {className: "pugh-option-actions"});
    Object.assign(box.style, {display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.35rem", margin: "0.3rem 0 0.15rem 1.6rem"});
    box.dataset.pughActions = letter;
    const vetoes = view.vetoes ?? [], vetoed = vetoes.includes(letter);
    box.append(key(vetoed ? "Remove my veto" : "Veto", {pughAction: "veto"}, vetoed, () => {
      view.vetoes = vetoed ? vetoes.filter(item => item !== letter) : [...vetoes, letter].sort();
      again(`[data-pugh-actions="${letter}"] [data-pugh-action="veto"]`);
    }));
    if (!candidate.datum) {
      const fence = spec.matrix.datum?.prefer?.[0] ?? spec.matrix.candidates[0].key;
      box.append(key("Make it the datum", {pughAction: "datum"}, null, () => {
        view.datum = option.key === fence ? null : letter;
        again(`[data-pugh-actions="${letter}"] [data-pugh-action="veto"]`);
      }));
    }
    for (const veto of candidate.vetoes.filter(item => item.by === "tool")) {
      const lifts = view.lifts?.[letter] ?? [], lifted = lifts.includes(veto.id);
      const line = element("span", {className: "pugh-option-veto"}, `${veto.why} `,
        key(lifted ? "Restore" : "Lift", {pughLift: `${letter}:${veto.id}`}, lifted, () => {
          const next = lifted ? lifts.filter(id => id !== veto.id) : [...lifts, veto.id];
          const {[letter]: _gone, ...rest} = view.lifts ?? {};
          view.lifts = next.length ? {...rest, [letter]: next} : rest;
          again(`[data-pugh-lift="${letter}:${veto.id}"]`);
        }));
      line.style.flexBasis = "100%";
      box.append(line);
    }
    return box;
  }
  /** The keys of a closed expander are hidden, not merely folded, so nothing counts them as on the page. */
  function fold(details) {
    const keys = details.querySelector(".pugh-option-actions");
    if (!keys) return;
    keys.hidden = !details.open;
    details.addEventListener("toggle", () => { keys.hidden = !details.open; });
  }
  return {overridesOf, bottomLineOf, overrides, changed, state, reset, bottomLine, actions, fold};
})();
