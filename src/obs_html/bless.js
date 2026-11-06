/* Bless verdicts (features.py, bless): a chapter that asks for a bless (obs input-model, Bless
   requests) shows a pill with its state in the top band and, beside it, the verdict keys Bless,
   Decline, Ask and Pick. Decline, Ask and Pick take a one-line comment in the band, under the
   keys; Pick takes another option of the chapter's decision figure by its letter, here or from
   the option's column head ("Pick B"). A complete verdict opens the next chapter of the walk.
   Send hands every complete verdict to the answer sink (answers.js) as one payload whose fields
   obs's src/obs/answers.schema.json owns; spec/capabilities/bless.md owns the contract and
   artifact-ui.md the top band. The verdicts are session state; which were sent is kept in
   browser storage per chapter version, so a sent verdict shows as sent until its chapter changes. */
globalThis.obsBless = (() => {
  const LABELS = {bless: "Bless", decline: "Decline", ask: "Ask", pick: "Pick"};
  const GLYPHS = {bless: "✓", decline: "✗", ask: "?", pick: "⇄"};
  const STATES = {bless: "Blessed", decline: "Declined", ask: "Question", pick: "Picked"};
  const NEEDS_COMMENT = new Set(["decline", "ask", "pick"]);
  const data = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
  const template = document.createElement("template");
  /** Each decision figure of a note: its anchor and its options' letters and names (pugh-figure.js letters them). */
  const decisions = html => {
    template.innerHTML = html;
    return [...template.content.querySelectorAll('[data-figure-kind="pugh"][data-figure-spec]')].map(figure => ({
      anchor: figure.id,
      options: JSON.parse(figure.dataset.figureSpec).matrix.candidates.map((candidate, index) => ({
        letter: String.fromCharCode(65 + index), name: String(candidate.label ?? candidate.key)})),
    }));
  };
  // Each asking chapter's decision figures' specs by anchor, answered or not: the pill names a picked
  // option by the figure's own short name (obsPugh.options, pugh-figure.js).
  const specs = new Map(data.notes.filter(note => note.bless).flatMap(note => {
    template.innerHTML = note.html;
    return [...template.content.querySelectorAll('[data-figure-kind="pugh"][data-figure-spec]')]
      .map(figure => [figure.id, JSON.parse(figure.dataset.figureSpec)]);
  }));
  const requests = new Map(data.notes.filter(note => note.bless).map(note => [note.slug, {
    ...note.bless, title: note.title, figures: note.bless.answer ? [] : decisions(note.html)}]));
  const asking = [...requests].filter(([, request]) => !request.answer).map(([slug]) => slug);
  const verdicts = new Map();  // chapter -> {verdict, comment, pick}, this session only.
  const sentKey = slug => `obs-bless-sent:${data.document?.title ?? document.title}:${slug}`;
  const readSent = slug => {
    try {
      const sent = JSON.parse(globalThis.localStorage.getItem(sentKey(slug)) || "null");
      return sent?.version === requests.get(slug).version ? sent : null;
    } catch { return null; }
  };
  const writeSent = (slug, verdict) => {
    try { globalThis.localStorage.setItem(sentKey(slug), JSON.stringify({version: requests.get(slug).version, verdict})); }
    catch (error) { globalThis.obsCapabilities?.fail("bless", `localStorage.setItem threw: ${error?.message || error}`); }
  };
  const complete = verdict => Boolean(verdict && (!NEEDS_COMMENT.has(verdict.verdict) || verdict.comment?.trim())
    && (verdict.verdict !== "pick" || verdict.pick));
  let active = null;

  function element(tag, properties = {}, ...children) {
    const node = Object.assign(document.createElement(tag), properties);
    node.append(...children.filter(child => child !== null && child !== undefined));
    return node;
  }
  const controls = element("div", {className: "bless-controls"});
  controls.dataset.bless = "";
  const pill = element("span", {className: "bless-pill"});
  pill.dataset.blessPill = "";
  pill.setAttribute("role", "status");
  const keys = element("div", {className: "bless-keys"});
  keys.setAttribute("role", "group");
  keys.setAttribute("aria-label", "Verdict");
  const keyButtons = Object.keys(LABELS).map(verdict => {
    const key = element("button", {type: "button", className: "icon-button bless-key", textContent: GLYPHS[verdict],
      title: LABELS[verdict]});
    key.dataset.blessKey = verdict;
    key.setAttribute("aria-label", LABELS[verdict]);
    key.addEventListener("click", () => choose(verdict));
    return key;
  });
  keys.append(...keyButtons);
  const entry = element("div", {className: "bless-entry"});
  entry.dataset.blessEntry = "";
  entry.hidden = true;
  const picks = element("div", {className: "bless-picks"});
  picks.setAttribute("role", "group");
  picks.setAttribute("aria-label", "Pick another option");
  const comment = element("input", {type: "text", className: "bless-comment", placeholder: "Your comment (needed)"});
  comment.dataset.blessComment = "";
  comment.addEventListener("input", () => {
    const verdict = verdicts.get(active);
    if (verdict) verdict.comment = comment.value, update();
  });
  comment.addEventListener("keydown", event => {
    event.stopPropagation();  // Typing never walks the chapters.
    if (event.key === "Escape") closeEntry();
    if (event.key === "Enter") finish();
  });
  entry.append(picks, comment);
  const send = element("button", {type: "button", className: "bless-send", textContent: "Send"});
  send.dataset.blessSend = "";
  send.addEventListener("click", () => sendVerdicts());
  controls.append(pill, keys, entry, send);

  const pickLabel = (figure, option) => `Pick ${option.letter}`;
  function pickKeys(slug) {
    const request = requests.get(slug), verdict = verdicts.get(slug);
    picks.replaceChildren(...request.figures.flatMap(figure => {
      const winner = document.getElementById(figure.anchor)?.dataset.pughWinner;
      return figure.options.filter(option => option.letter !== winner).map(option => {
        const key = element("button", {type: "button", className: "filter-pill", textContent: pickLabel(figure, option),
          title: `Pick ${option.letter}: ${option.name}`});
        key.dataset.blessPick = `${figure.anchor}:${option.letter}`;
        key.setAttribute("aria-pressed", String(verdict?.pick?.figure === figure.anchor && verdict.pick.option === option.letter));
        key.addEventListener("click", () => pick(figure.anchor, option.letter));
        return key;
      });
    }));
    picks.hidden = verdict?.verdict !== "pick";
  }
  function openEntry() {
    const verdict = verdicts.get(active);
    entry.hidden = false;
    comment.value = verdict.comment || "";
    comment.setAttribute("aria-label", `Comment on ${STATES[verdict.verdict].toLowerCase()}, needed`);
    pickKeys(active);
    comment.focus();
  }
  function closeEntry() { entry.hidden = true; }
  function next() {
    const step = document.querySelector('[data-step="1"]');
    if (step && !step.disabled) step.click();
  }
  function finish() {
    if (!complete(verdicts.get(active))) { update(); return; }
    closeEntry();
    next();
  }
  function choose(verdict) {
    const previous = verdicts.get(active);
    verdicts.set(active, {...previous, verdict, ...(verdict === "pick" ? {} : {pick: undefined})});
    update();
    if (NEEDS_COMMENT.has(verdict)) openEntry();
    else { closeEntry(); next(); }
  }
  /** Pick another option of a decision figure of the active chapter, from the band or its column head. */
  function pick(anchor, letter) {
    const previous = verdicts.get(active);
    verdicts.set(active, {...previous, verdict: "pick", pick: {figure: anchor, option: letter}});
    update();
    openEntry();
    if (complete(verdicts.get(active))) comment.select();
  }
  /** The pill's parts: the chapter's state, then what follows it, each part its own " · " detail. */
  function stateParts(slug) {
    const request = requests.get(slug);
    if (request.answer) return [...verdictParts(request.answer), "recorded"];
    const verdict = verdicts.get(slug), sent = readSent(slug);
    if (verdict?.verdict && complete(verdict) && sent && same(sent.verdict, verdict)) return [...verdictParts(verdict), "sent"];
    if (verdict?.verdict) return [...verdictParts(verdict), ...(complete(verdict) ? [] : ["needs a comment"])];
    if (sent) return [...verdictParts(sent.verdict), "sent"];
    return ["Bless pending"];
  }
  /** Whether a sent verdict is the reader's verdict as it stands. */
  const same = (sent, verdict) => sent.verdict === verdict.verdict && (sent.comment ?? "") === (verdict.comment?.trim() ?? "")
    && sent.pick?.figure === verdict.pick?.figure && sent.pick?.option === verdict.pick?.option;
  /** A verdict's state and, for Pick, the picked option's short name where its figure gives one. */
  function verdictParts(verdict) {
    if (verdict.verdict !== "pick" || !verdict.pick) return [STATES[verdict.verdict]];
    const spec = specs.get(verdict.pick.figure);
    const short = spec && globalThis.obsPugh.options(spec).find(option => option.letter === verdict.pick.option)?.short;
    return [`Picked ${verdict.pick.option}`, ...(short ? [short] : [])];
  }
  function update() {
    const request = active && requests.get(active);
    controls.hidden = !request && !asking.length;
    pill.hidden = keys.hidden = !request;
    if (!request) closeEntry();
    else {
      const verdict = verdicts.get(active);
      // The state first; each detail after it is a part of its own, which the pill drops whole where
      // the band has no room for it (base.css, the pill), so "Picked B · Close" reads "Picked B".
      const [state, ...details] = stateParts(active);
      pill.replaceChildren(element("span", {className: "bless-pill-state", textContent: state}),
        ...details.map(detail => element("span", {className: "bless-pill-detail", textContent: ` · ${detail}`})));
      pill.dataset.blessState = request.answer ? "recorded" : verdict?.verdict ? (complete(verdict) ? verdict.verdict : "incomplete")
        : readSent(active) ? "sent" : "pending";
      pill.title = request.outdated ? `Bless pending: the answer given at an earlier version is outdated` : pill.textContent;
      keys.hidden = Boolean(request.answer);
      for (const key of keyButtons) {
        key.setAttribute("aria-pressed", String(verdict?.verdict === key.dataset.blessKey));
        key.hidden = key.dataset.blessKey === "pick" && !request.figures.length;
      }
      if (!entry.hidden) pickKeys(active);
    }
    const done = asking.filter(slug => complete(verdicts.get(slug))).length;
    send.hidden = !asking.length;
    send.disabled = done === 0;
    send.textContent = `Send ${done}/${asking.length}`;
    send.setAttribute("aria-label", `Send ${done} of ${asking.length} verdicts`);
    send.title = send.getAttribute("aria-label");
    document.querySelectorAll("[data-bless-column-pick]").forEach(key => {
      const [anchor, letter] = key.dataset.blessColumnPick.split(":");
      const current = verdicts.get(active)?.pick;
      key.setAttribute("aria-pressed", String(current?.figure === anchor && current.option === letter));
    });
  }
  /** The payload: each complete verdict with the chapter's version and the reader's changes to its decision figures. */
  function payload() {
    const changes = globalThis.obsPugh?.readerState() ?? {};
    return {verdicts: asking.filter(slug => complete(verdicts.get(slug))).map(slug => {
      const {verdict, comment: text, pick: picked} = verdicts.get(slug);
      const figures = Object.fromEntries(requests.get(slug).figures.filter(figure => changes[figure.anchor])
        .map(figure => [figure.anchor, changes[figure.anchor]]));
      return {chapter: slug, version: requests.get(slug).version, verdict,
        ...(NEEDS_COMMENT.has(verdict) ? {comment: text.trim()} : {}), ...(picked ? {pick: picked} : {}),
        ...(Object.keys(figures).length ? {figures} : {})};
    })};
  }
  async function sendVerdicts() {
    const answers = payload();
    if (!answers.verdicts.length) return;
    send.disabled = true;
    try {
      const result = await globalThis.obsArtifact.sendAnswers(answers);
      if (result.sink !== "text") for (const verdict of answers.verdicts) writeSent(verdict.chapter, verdict);
    } catch (_error) {
      // answers.js shows the payload as text and names the failure; nothing is lost.
    } finally {
      update();
    }
  }
  /** A decision figure's column-head key, "Pick B", where its chapter asks; null elsewhere (pugh-figure.js). */
  function columnKey(anchor, letter) {
    const slug = [...requests.keys()].find(key => requests.get(key).figures.some(figure => figure.anchor === anchor));
    if (!slug || slug !== active) return null;
    const key = element("button", {type: "button", className: "filter-pill bless-column-pick", textContent: `Pick ${letter}`});
    key.dataset.blessColumnPick = `${anchor}:${letter}`;
    const current = verdicts.get(slug)?.pick;
    key.setAttribute("aria-pressed", String(current?.figure === anchor && current.option === letter));
    key.addEventListener("click", event => { event.stopPropagation(); pick(anchor, letter); });
    return key;
  }

  document.querySelector("[data-top-band-end]").prepend(controls);
  document.addEventListener("obs-chapter-change", ({detail}) => {
    active = detail.slug;
    closeEntry();
    update();
  });
  update();
  return Object.freeze({columnKey, payload, verdicts: () => structuredClone(Object.fromEntries(verdicts))});
})();
