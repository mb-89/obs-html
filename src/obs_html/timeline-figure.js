(() => {
  "use strict";
  // The timeline figure kind (figures.py, FIGURE_KINDS; artifact-ui.md, Timeline figures): dated
  // note records as one column per lane and one row per day, with named bands between the past
  // and the planned rows. It ships only with a timeline figure (features.py, timeline); figures.js
  // frames and expands it and calls render, place and print.
  //
  // model is the one pure part: the figure's content and the records in, the lanes and the rows
  // out, no page and no clock (obs input-model, Timeline figures, owns the order it returns). The
  // rest only reads the page's records and draws the model.

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DAY = /^\d{4}-\d{2}-\d{2}$/;
  const TONES = new Set(["neutral", "positive", "warning", "negative"]);  // input.schema.json, $defs/tone.

  /** A field's text, as a query condition reads a single value: text as it is, a number or a
      boolean as its text, anything else none. */
  function textOf(value) {
    if (typeof value === "string") return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    return "";
  }
  /** "2 Nov" for 2026-11-02. */
  function shortDay(day) {
    return `${Number(day.slice(8, 10))} ${MONTHS[Number(day.slice(5, 7)) - 1]}`;
  }
  const byText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  /** A record as the timeline places it: its row key, lane, day, label, text, flags and whether it is a marker. */
  function placed(content, record, bandValues) {
    const fields = record.fields || {};
    const band = content.band ? textOf(fields[content.band]) : "";
    const day = textOf(fields[content.date]);
    const inBand = Boolean(band) && bandValues.has(band);
    if (!inBand && !DAY.test(day)) return null;
    const flags = content.flags && Array.isArray(fields[content.flags]) ? fields[content.flags] : [];
    return {
      key: inBand ? `band:${band}` : day,
      lane: textOf(fields[content.lane]),
      day: DAY.test(day) ? day : "",
      path: record.path, slug: record.slug,
      label: (content.label && textOf(fields[content.label])) || record.title || record.path,
      text: content.text ? textOf(fields[content.text]) : "",
      flags: flags.filter(flag => flag && typeof flag.label === "string" && flag.label)
        .map(flag => ({label: flag.label, tone: TONES.has(flag.tone) ? flag.tone : "neutral"})),
      marker: Boolean(content.marker) && fields[content.marker] === true,
    };
  }
  /** The lanes in display order: the content's lanes, else the population's lane names in
      case-insensitive order. */
  function lanesOf(content, population) {
    if (Array.isArray(content.lanes)) return [...content.lanes];
    const bandValues = new Set((content.bands || []).map(band => band.value));
    const names = new Set(population.map(record => placed(content, record, bandValues)?.lane).filter(Boolean));
    return [...names].sort((a, b) => byText(a.toLowerCase(), b.toLowerCase()) || byText(a, b));
  }
  /**
   * The timeline's lanes and rows from its content and the records to draw (each {path, slug,
   * title, fields}); ``population`` fixes the lanes, so a filter that empties a lane keeps its column.
   * A row is a year divider ({kind: "year", year}) or {kind, key, label, anchor, cells}: kind past,
   * band or planned; one cell per lane, {lane, stop, count, last, markers, items}.
   */
  function model(content, records, population = records) {
    const lanes = lanesOf(content, population);
    const bands = content.bands || [];
    const bandValues = new Set(bands.map(band => band.value));
    const entries = records.map(record => placed(content, record, bandValues))
      .filter(entry => entry && lanes.includes(entry.lane))
      .sort((a, b) => byText(a.day, b.day) || byText(a.path, b.path));
    const byKey = new Map();
    entries.forEach(entry => {
      if (!byKey.has(entry.key)) byKey.set(entry.key, []);
      byKey.get(entry.key).push(entry);
    });
    const row = (kind, key, label, stop) => {
      const held = byKey.get(key) || [];
      return {kind, key, label, anchor: false, cells: lanes.map(lane => {
        const here = held.filter(entry => entry.lane === lane);
        const items = here.filter(entry => !entry.marker);
        return {lane, stop: here.length ? stop : "none", count: items.length, last: items.at(-1)?.label || "",
                markers: here.filter(entry => entry.marker).map(entry => entry.label), items};
      })};
    };
    const days = [...byKey.keys()].filter(key => DAY.test(key)).sort();
    const rows = [];
    let year = null;
    const dated = (day, kind) => {
      if (year !== null && day.slice(0, 4) !== year) rows.push({kind: "year", year: day.slice(0, 4)});
      year = day.slice(0, 4);
      rows.push(row(kind, day, shortDay(day), kind));
    };
    days.filter(day => day <= content.today).forEach(day => dated(day, "past"));
    const past = rows.length;
    const banded = at => bands.filter(band => band.at === at)
      .forEach(band => rows.push(row("band", `band:${band.value}`, band.label, "band")));
    banded("today");
    days.filter(day => day > content.today).forEach(day => dated(day, "planned"));
    banded("end");
    const anchor = content.anchor === "today"
      ? rows.slice(past).find(item => item.kind !== "year")
      : rows.find(item => item.key === `band:${content.anchor}`);
    if (anchor) anchor.anchor = true;
    return {lanes, rows, empty: entries.length === 0};
  }

  // ---- The page: records, state and drawing ------------------------------------------------

  const EMPTY = "No records to show.";
  const drawn = new WeakMap();  // A figure node: drawn live or as a print copy.
  const states = new Map();  // By figure anchor: the rows and items the reader opened.
  function state(figure) {
    if (!states.has(figure.id)) states.set(figure.id, {rows: new Set(), items: new Set()});
    return states.get(figure.id);
  }
  /** A copy's view of the reader's state: a page layout prefixes a copy's id (pages.js, fixLinks),
      so the copy reads the state of the live figure whose anchor its id ends with, and writes none. */
  function copied(figure) {
    const key = [...states.keys()].find(anchor => figure.id === anchor || figure.id.endsWith(`-${anchor}`));
    return key ? states.get(key) : {rows: new Set(), items: new Set()};
  }
  /** The query's conditions: those of its from chain, then its own where (as cards.js reads a count). */
  function conditions(query, records, visiting = new Set()) {
    if (!query.from) return query.where || [];
    if (visiting.has(query.from)) throw new Error(`Timeline query reference cycle: ${query.from}`);
    const owner = records.find(record => record.sourcePath === `${query.from}.md`)?.frontmatter?.query;
    if (!owner || !Array.isArray(owner.where)) throw new Error(`Missing timeline query owner: ${query.from}`);
    return [...conditions(owner, records, new Set([...visiting, query.from])), ...(query.where || [])];
  }
  /** The records the figure's query selects, under the reader's filter where ``filtered``. */
  function selected(spec, filtered) {
    const artifact = globalThis.obsArtifact;
    const match = globalThis.obsQuery.compileConditions(conditions(spec.records, artifact.records)).match;
    return artifact.records.filter(record => artifact.selectable(record) &&
      (!filtered || artifact.matchesFilter(record)) && match(record))
      .map(record => ({path: record.sourcePath, slug: record.slug, title: record.title, fields: record.frontmatter}));
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function cellNode(cell) {
    const node = element("span", `timeline-cell timeline-cell--${cell.stop}`);
    if (cell.stop === "none") return node;
    node.append(element("span", "timeline-stop"));
    if (cell.count) node.append(element("span", "timeline-count", String(cell.count)));
    if (cell.markers.length) {
      node.append(element("span", "timeline-marker",
        cell.markers.at(-1) + (cell.markers.length > 1 ? ` +${cell.markers.length - 1}` : "")));
    }
    if (cell.last) node.append(element("span", "timeline-label", cell.last));
    return node;
  }
  function itemNode(item, opened, onToggle) {
    const details = element("details", "timeline-item");
    details.dataset.timelineItem = item.path;
    details.open = opened;
    const summary = element("summary", "", item.label);
    item.flags.forEach(flag => summary.append(" ", element("span", `timeline-flag timeline-flag--${flag.tone}`, flag.label)));
    details.append(summary);
    if (item.text) details.append(element("p", "timeline-text", item.text));
    const link = element("a", "internal-link timeline-link", `Open ${item.label}`);
    link.href = `#${item.slug}`;
    details.append(link);
    details.addEventListener("toggle", () => onToggle(details.open));
    return details;
  }
  function rowNode(row, view, live) {
    if (row.kind === "year") return element("p", "timeline-year", row.year);
    const details = element("details", `timeline-row timeline-row--${row.kind}`);
    details.dataset.timelineRow = row.key;
    if (row.anchor) details.dataset.timelineAnchor = "";
    details.open = view.rows.has(row.key);
    const summary = element("summary", "timeline-summary");
    summary.append(element("span", "timeline-when", row.label), ...row.cells.map(cellNode));
    details.append(summary);
    const list = element("div", "timeline-list");
    row.cells.filter(cell => cell.count || cell.markers.length).forEach(cell => {
      list.append(element("p", "timeline-list-lane", cell.lane));
      cell.markers.forEach(marker => list.append(element("p", "timeline-marker-line", marker)));
      if (!cell.items.length) return;
      const items = element("ul", "timeline-items");
      cell.items.forEach(item => {
        const key = `${row.key}\0${item.path}`;
        const entry = element("li");
        entry.append(itemNode(item, live && view.items.has(key), open => {
          if (open) view.items.add(key); else view.items.delete(key);
        }));
        items.append(entry);
      });
      list.append(items);
    });
    details.append(list);
    if (live) {
      details.addEventListener("toggle", () => {
        if (details.open) view.rows.add(row.key); else view.rows.delete(row.key);
      });
    }
    return details;
  }
  /** Draw the figure into its body: live under the reader's filter, or as its print copy, which reads
      the reader's opened rows and never writes them. */
  function draw(figure, spec, live) {
    const host = figure.querySelector(".timeline-figure");
    const shown = model(spec, selected(spec, live), selected(spec, false));
    if (shown.empty) {
      host.replaceChildren(element("p", "timeline-empty", EMPTY));
      return;
    }
    const grid = element("div", "timeline");
    grid.dataset.timelineLanes = String(shown.lanes.length);
    const header = element("div", "timeline-lanes");
    header.append(element("span", "timeline-when"), ...shown.lanes.map(lane => element("span", "timeline-lane-name", lane)));
    grid.append(header, ...shown.rows.map(row => rowNode(row, live ? state(figure) : copied(figure), live)));
    host.replaceChildren(grid);
  }
  const spec = figure => JSON.parse(figure.dataset.figureSpec);
  /** Draw the figure live, following the filter, each time the page places it: a page layout may
      move or reuse a node it drew as a print copy (pages.js), which is drawn live again here. */
  const following = new WeakSet();
  function render(figure) {
    drawn.set(figure, "live");
    draw(figure, spec(figure), true);
    if (following.has(figure)) return;
    following.add(figure);
    const update = () => {
      if (!figure.isConnected) {
        document.removeEventListener("obs-artifact-filter", update);
        following.delete(figure);
        return;
      }
      if (drawn.get(figure) === "live") draw(figure, spec(figure), true);
    };
    document.addEventListener("obs-artifact-filter", update);
  }
  function print(figure) {
    if (drawn.has(figure)) return;
    drawn.set(figure, "print");
    draw(figure, spec(figure), false);
  }
  /** A page layout placed the figure (figures.js, place): drawn now, so its page holds its height. */
  function place(figure) {
    if (figure.closest(".print-book")) print(figure);
    else render(figure);
  }
  /** The chapter just opened at its top, not at a heading or a block: centre the anchor row of its
      first timeline figure that has an anchor (artifact-ui.md, Timeline figures). */
  function anchorChapter(slug) {
    const scroller = document.querySelector("[data-chapter-scroll]");
    const body = document.querySelector("[data-active-chapter] [data-chapter-body]");
    if (!scroller || !body || scroller.scrollTop !== 0) return;
    let hash = "";
    try { hash = decodeURIComponent(window.location.hash.slice(1)); } catch { hash = ""; }
    if (hash.startsWith(`${slug}/`) || hash.startsWith(`${slug}?`)) return;
    const figure = [...body.querySelectorAll('[data-figure-kind="timeline"]')].find(item => spec(item).anchor);
    if (!figure) return;
    render(figure);
    const row = figure.querySelector("[data-timeline-anchor]");
    if (!row) return;
    const frame = scroller.getBoundingClientRect(), box = row.getBoundingClientRect();
    scroller.scrollTop += box.top - frame.top - (scroller.clientHeight - box.height) / 2;
  }
  /** Run ``then`` once the artifact has finished starting (artifactStatus ready), whose layout the
      anchor row's place depends on. */
  function whenReady(then) {
    const root = document.documentElement;
    if (root.dataset.artifactStatus === "ready") { then(); return; }
    const observer = new MutationObserver(() => {
      if (root.dataset.artifactStatus !== "ready") return;
      observer.disconnect();
      then();
    });
    observer.observe(root, {attributes: true, attributeFilter: ["data-artifact-status"]});
  }
  if (typeof document !== "undefined") {
    // After the chapter's own navigation (a heading, a block) and once the page lays it out.
    const opened = event => whenReady(() => requestAnimationFrame(() => anchorChapter(event.detail.slug)));
    document.addEventListener("obs-chapter-change", opened);
    document.addEventListener("obs-chapter-content-ready", opened);
  }
  globalThis.obsTimeline = {model, render, place, print, EMPTY};
})();
