/* The computed verdict of a decision as data, without a page (cli.md, Printing the verdicts):
   what obs-html --print-verdicts prints (verdicts.py). No feature ships this module and no
   artifact carries it; verdicts.py runs it in Node.js after ctrl's engine (vendor/pugh.js, as
   globalThis.obsPughEngine), pugh-figure.js and pugh-verdict.js, each unchanged.

   One pure function: a figure's spec (figures.py, the pugh kind) in, its decision as data out.
   The decision is the figure's own (obsPugh.decide), the lines the bottom line's
   (obsPughVerdict.bottomLineOf), so the print says what the page draws with
   artifact.figures.decisionVerdict on. No clock: the engine draws from the fence's seed. */
globalThis.obsPughText = (() => {
  const engine = () => globalThis.obsPughEngine;
  /** An option as the bottom line names it, "B · Close" (pugh-verdict.js, nameIn). */
  const tag = option => (option.short ? `${option.letter} · ${option.short}` : option.letter);

  /** The decision of ``spec``: the bottom line's lines, the engine's suggestion, its ranking with
      each option's total, fit and vetoes, and its sensitivity with each runner-up's tie point. A
      spec with an answer (``answered``) is decided as the answer left it, as the page shows it. */
  function verdictOf(spec) {
    const view = {weights: {}, marks: {}, rulings: {}, ...structuredClone(spec.answered ?? {})};
    const {result, figureModel} = globalThis.obsPugh.decide(spec, view);
    const option = key => figureModel.byKey[key];
    const named = key => ({key, letter: option(key).letter, name: tag(option(key))});
    const lines = globalThis.obsPughVerdict.bottomLineOf(result, key => tag(option(key)), key => option(key).letter, engine().fmt);
    const candidate = key => result.candidates.find(item => item.key === key);
    const sensitivity = result.sensitivity;
    const label = key => result.criteria.find(criterion => criterion.key === key)?.label ?? key;
    return {
      lines: lines.map(line => ({...line})),
      suggestion: result.suggestion ? {...named(result.suggestion.key), total: result.suggestion.total} : null,
      ranking: [...result.ranking, ...result.candidates.map(item => item.key).filter(key => !result.ranking.includes(key))]
        .map(key => ({...named(key), total: candidate(key).total, fits: candidate(key).fits,
          vetoes: candidate(key).vetoes.map(veto => ({id: veto.id, by: veto.by, why: veto.why, lifted: Boolean(veto.lifted)}))})),
      sensitivity: sensitivity ? {
        verdict: sensitivity.verdict, winner: named(sensitivity.winner), share: sensitivity.share, step: sensitivity.step,
        draws: sensitivity.draws, seed: sensitivity.seed, holdShare: sensitivity.holdShare,
        runnersUp: sensitivity.runnersUp.map(runner => ({...named(runner.key), tie: runner.tie ? {
          criterion: runner.tie.criterion, label: label(runner.tie.criterion), from: runner.tie.from, to: runner.tie.to,
          reasonable: Boolean(runner.tie.reasonable), now: Boolean(runner.tie.now)} : null})),
      } : null,
    };
  }
  return {verdictOf};
})();
