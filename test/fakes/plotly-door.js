/* The plotting library door's fake (architecture.md, Library doors; library_fakes.py): obsPlotly's
   calls answered without Plotly. A chart is drawn as a placeholder of the size its layout and
   element give, with Plotly's default margins, one g.trace per trace in its type's layer (g.scatterlayer), a legend box placed by legend.x and legend.y in the
   plot area where the legend shows, and the door's events; test_library_doors_browser.py holds it
   to the door's contract. */
globalThis.obsPlotly = (() => {
  const SVG = "http://www.w3.org/2000/svg";
  const MARGIN = {l: 80, r: 80, t: 100, b: 80};  // Plotly's default margins.
  const LEGEND = {x: 1.02, y: 1};  // Plotly's default legend position, in plot fractions.
  const charts = new WeakMap();  // chart -> {data, layout, handlers, drawn}
  const svg = (tag, attributes) => {
    const element = document.createElementNS(SVG, tag);
    for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
    return element;
  };
  const set = (target, path, value) => {
    const keys = path.split(".");
    let object = target;
    for (const key of keys.slice(0, -1)) object = object[key] = {...(object[key] || {})};
    object[keys.at(-1)] = value;
  };
  const emit = (state, event, detail) => (state.handlers[event] || []).forEach(handler => handler(detail));
  function draw(chart, state) {
    const {layout, data} = state;
    const width = layout.width ?? (chart.clientWidth || 700), height = layout.height ?? (chart.clientHeight || 450);
    const margin = {...MARGIN, ...(layout.margin || {})};
    const plot = {width: Math.max(1, width - margin.l - margin.r), height: Math.max(1, height - margin.t - margin.b)};
    const showlegend = layout.showlegend ?? data.length > 1;
    const legend = {x: layout.legend?.x ?? LEGEND.x, y: layout.legend?.y ?? LEGEND.y};
    state.drawn = {width, height, showlegend, legend, plot};
    chart.classList.add("js-plotly-plot");
    const container = document.createElement("div");
    container.className = "plot-container plotly";
    const box = document.createElement("div");
    box.className = "svg-container";
    box.style.cssText = `position: relative; width: 100%; height: ${height}px`;
    const main = svg("svg", {class: "main-svg", width, height});
    main.style.cssText = "position: absolute; left: 0; top: 0; overflow: visible";
    main.append(svg("rect", {class: "bg", x: margin.l, y: margin.t, width: plot.width, height: plot.height, fill: "none"}));
    const layers = {};
    for (const trace of data) {
      const type = trace.type || "scatter";
      layers[type] ||= main.appendChild(svg("g", {class: `${type}layer`}));
      layers[type].append(svg("g", {class: "trace"}));
    }
    if (showlegend) {
      const entries = Math.max(1, data.length);
      const group = svg("g", {class: "legend",
        transform: `translate(${margin.l + legend.x * plot.width}, ${margin.t + (1 - legend.y) * plot.height})`});
      group.append(svg("rect", {class: "bg", width: 120, height: 10 + 19 * entries, fill: "none"}));
      main.append(group);
    }
    box.append(main);
    container.append(box);
    chart.replaceChildren(container);
    emit(state, "afterplot");
  }
  function plot(chart, data, layout = {}, _config = {}) {
    const state = charts.get(chart) || {handlers: {}};
    Object.assign(state, {data: structuredClone(data || []), layout: structuredClone(layout)});
    charts.set(chart, state);
    draw(chart, state);
    return Promise.resolve(chart);
  }
  return {
    available: () => true,
    plot,
    react: plot,
    relayout(chart, update) {
      const state = charts.get(chart);
      if (!state) return Promise.reject(new Error("This element is not a drawn chart."));
      for (const [path, value] of Object.entries(update)) set(state.layout, path, value);
      draw(chart, state);
      emit(state, "relayout", {...update});
      return Promise.resolve(chart);
    },
    resize(chart) {
      const state = charts.get(chart);
      if (state) draw(chart, state);
    },
    image: (chart, {width, height}) => Promise.resolve("data:image/svg+xml," + encodeURIComponent(
      `<svg xmlns="${SVG}" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`
      + `<rect width="${width}" height="${height}" fill="none" stroke="currentColor"/></svg>`)),
    purge(chart) {
      charts.delete(chart);
      chart.replaceChildren();
      chart.classList.remove("js-plotly-plot");
    },
    layout(chart) {
      const drawn = charts.get(chart)?.drawn;
      return drawn ? structuredClone(drawn) : null;
    },
    legend: chart => chart.querySelector("g.legend"),
    on(chart, event, handler) {
      const state = charts.get(chart) || {handlers: {}};
      charts.set(chart, state);
      (state.handlers[event] ||= []).push(handler);
    },
  };
})();
