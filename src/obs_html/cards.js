(() => {
  "use strict";
  const artifact = globalThis.obsArtifact;
  const projections = new Map();
  const selections = new Map();
  const counts = new Map();
  let population;
  let owners;
  let pending = false;
  let initialized = !globalThis.obsStartup;
  // A distinct count reads the property its conditions read (obs capabilities/queries#Conditions).
  const values = (record, field) => globalThis.obsQuery.propertyTexts(record, field);
  function owner(path) {
    owners ||= new Map(artifact.records.map(record => [record.sourcePath, record]));
    return owners.get(path);
  }
  // A query's conditions: those of its from chain, then its own where. Its count and its
  // drill-down both read them, so a drill-down shows exactly the counted rows.
  function conditionChain(query, visiting = new Set()) {
    if (!query.from) return query.where || [];
    if (visiting.has(query.from)) throw new Error(`Count query reference cycle: ${query.from}`);
    const source = owner(`${query.from}.md`)?.frontmatter.query;
    if (!source || !Array.isArray(source.where)) throw new Error(`Missing count query owner: ${query.from}`);
    return [...conditionChain(source, new Set([...visiting, query.from])), ...(query.where || [])];
  }
  // A metric link names its table; its table filter derives from the query it counts
  // (obs capabilities/cards-metrics), which is why the core refuses a hand-written one.
  const drillDown = (link, query) => `${link}?tableFilter=${
    encodeURIComponent(globalThis.obsQuery.conditionsExpression(conditionChain(query)))}`;
  function select(query, projectionKey = "") {
    // An ignored note is never counted (artifact.js, selectable); an explicit owner still resolves.
    population ||= artifact.records.filter(record => artifact.selectable(record) && artifact.matchesFilter(record));
    const cacheKey = JSON.stringify([projectionKey, query.from || "", query.where]);
    if (selections.has(cacheKey)) return selections.get(cacheKey);
    const projection = projections.get(projectionKey);
    // Conditions match as every other artifact selection does (query.js, compileConditions).
    const conditions = globalThis.obsQuery.compileConditions(conditionChain(query));
    const result = population.filter(record => {
      const fields = projection?.[record.sourcePath];
      return conditions.match(fields ? {...record, frontmatter: {...record.frontmatter, ...fields}} : record);
    });
    selections.set(cacheKey, result);
    return result;
  }
  function evaluate(query, projectionKey = "") {
    const cacheKey = JSON.stringify([projectionKey, query]);
    if (counts.has(cacheKey)) return counts.get(cacheKey);
    const selected = select(query, projectionKey);
    const value = query.distinct
      ? new Set(selected.flatMap(record => values(record, query.distinct)).map(String)).size
      : selected.length;
    counts.set(cacheKey, value);
    return value;
  }
  const inclusive = (container, selector) => [
    ...(container.matches?.(selector) ? [container] : []), ...container.querySelectorAll(selector),
  ];
  function quantityQuery(path) {
    const query = owner(`${path}.md`)?.frontmatter.query;
    if (!query) throw new Error(`Missing quantity query: ${path}`);
    return query;
  }
  function cardMetrics(card) {
    const metrics = JSON.parse(card.dataset.recordCard).map(metric => ({...metric,
      ...(metric.link ? {link: drillDown(metric.link, {where: metric.where, ...(metric.from ? {from: metric.from} : {})})} : {}),
      ...(metric.secondaryLink ? {secondaryLink: drillDown(metric.secondaryLink, quantityQuery(metric.secondary))} : {})}));
    if (!card.dataset.recordSeries) return metrics;
    const series = JSON.parse(card.dataset.recordSeries);
    let entries = owner(`${series.sourceNote}.md`)?.frontmatter;
    for (const part of series.property.split(".")) entries = entries?.[part];
    if (!Array.isArray(entries)) throw new Error(`Missing metric series data: ${series.sourceNote}/${series.property}`);
    const labels = new Set();
    for (const entry of entries) {
      const label = entry[series.labelProperty], distinct = entry[series.distinctProperty];
      if (typeof label !== "string" || !label.trim() || labels.has(label) ||
          typeof distinct !== "string" || !distinct.trim()) throw new Error("Invalid metric series data.");
      labels.add(label);
      let link;
      if (series.link) {
        const target = owner(`${series.link.note}.md`);
        if (!target) throw new Error(`Missing metric destination: ${series.link.note}`);
        const literal = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replaceAll("/", "\\/");
        const filter = `${series.link.groupProperty}:/^${literal}$/`;
        link = `#${target.slug}?tableFilter=${encodeURIComponent(filter)}`;
      }
      metrics.push({label, distinct, where: series.where, tone: series.tone,
        toneRules: series.toneRules, ...(link ? {link} : {})});
    }
    return metrics;
  }
  function update(container = document) {
    if (!initialized) return;
    inclusive(container, "[data-record-card]").forEach(card => {
      const metrics = cardMetrics(card);
      const host = card.querySelector(".record-metrics");
      if (host && host.children.length !== metrics.length) {
        host.replaceChildren(...metrics.map((metric, index) => {
          const slot = document.createElement("div");
          slot.dataset.recordMetric = index;
          slot.setAttribute("role", "status");
          return slot;
        }));
      }
      metrics.forEach((metric, index) => {
        const projection = metric.obs?.projection || "";
        const numerator = evaluate({where: metric.where,
          ...(metric.from ? {from: metric.from} : {}),
          ...(metric.distinct ? {distinct: metric.distinct} : {})}, projection);
        const denominator = metric.denominator ? evaluate({
          where: metric.denominator, ...(metric.from ? {from: metric.from} : {}),
          ...(metric.distinct ? {distinct: metric.distinct} : {}),
        }, projection) : null;
        const value = denominator === null ? String(numerator) :
          denominator ? `${(100 * numerator / denominator).toFixed(1)}%` : "-";
        const secondaryQuery = metric.secondary && quantityQuery(metric.secondary);
        const numbers = {primary: numerator,
          secondary: secondaryQuery ? evaluate(secondaryQuery) : undefined,
          remaining: denominator === null ? undefined : denominator - numerator};
        const rule = metric.toneRules?.find(condition => Number.isFinite(numbers[condition.value]) &&
          (condition.when === "zero" ? numbers[condition.value] === 0 : numbers[condition.value] > 0));
        const tone = denominator === 0 ? "neutral" : rule?.tone || metric.tone || "neutral";
        const slot = card.querySelector(`[data-record-metric="${index}"]`);
        slot.removeAttribute("aria-busy");
        const lines = slot.parentElement.classList.contains("record-metrics--lines");
        slot.className = `record-metric record-metric--${tone}`;
        slot.replaceChildren();
        const valueNode = document.createElement(metric.link && !metric.secondary ? "a" : "span");
        valueNode.className = "record-metric-value";
        if (metric.link && !metric.secondary) {
          valueNode.href = metric.link;
          valueNode.setAttribute("aria-label", `${value} ${metric.label}`);
        }
        const strong = document.createElement(lines ? "span" : "strong");
        strong.textContent = value;
        if (metric.secondary) {
          valueNode.innerHTML = metric.valueHtml;
          const references = valueNode.querySelectorAll("[data-quantity-reference]");
          if (metric.link) references[0].href = metric.link;
          if (metric.secondaryLink) references[1].href = metric.secondaryLink;
        } else valueNode.append(strong);
        const label = document.createElement("span");
        label.className = "record-metric-label";
        label.textContent = metric.label;
        slot.append(...(lines ? [label, valueNode] : [valueNode, label]));
      });
    });
    inclusive(container, "[data-quantity-reference]").forEach(link => {
      const note = owner(link.dataset.quantityReference);
      if (!note || note.frontmatter.kind !== "quantity" || !note.frontmatter.query) {
        throw new Error(`Missing quantity query: ${link.dataset.quantityReference}`);
      }
      const unit = note.frontmatter.unit;
      link.textContent = `${evaluate(note.frontmatter.query)}${unit ? ` ${unit.trim()}` : ""}`;
      link.removeAttribute("aria-busy");
    });
  }
  function invalidate() {
    population = undefined;
    owners = undefined;
    selections.clear();
    counts.clear();
    if (pending) return;
    pending = true;
    queueMicrotask(() => {pending = false; update();});
  }
  document.addEventListener("obs-artifact-filter", invalidate);
  document.addEventListener("obs-canonical-property-change", invalidate);
  document.addEventListener("obs-chapter-change", () => update());
  document.addEventListener("obs-pages-layout", () => update());
  document.addEventListener("obs-print-start", () => update());
  new MutationObserver(mutations => {
    mutations.flatMap(mutation => [...mutation.addedNodes]).filter(node => node.nodeType === 1 &&
      (node.matches("[data-record-cards], [data-quantity-reference]") ||
       node.querySelector("[data-record-cards], [data-quantity-reference]"))).forEach(node => update(node));
  }).observe(document.body, {childList: true, subtree: true});
  globalThis.obsRecordMetrics = {evaluate, select};
  globalThis.obsCards = {
    setProjection(key, fieldsBySourcePath) {
      if (fieldsBySourcePath === null) projections.delete(key);
      else projections.set(key, structuredClone(fieldsBySourcePath));
      invalidate();
    },
  };
  if (globalThis.obsStartup) globalThis.obsStartup.defer("Numeric summaries", () => {
    initialized = true;
    population = undefined;
    selections.clear();
    counts.clear();
    update();
  });
  update();
})();
