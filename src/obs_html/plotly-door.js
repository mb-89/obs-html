/* The plotting library's door (architecture.md, Library doors): the one script that calls Plotly.
   Figures (figures.js) and equation figures (equations.js) draw through it; the library itself is
   embedded before it, or loaded from its CDN (libraries.py). */
globalThis.obsPlotly = (() => {
  const library = () => globalThis.Plotly;
  const EVENTS = {afterplot: "plotly_afterplot", relayout: "plotly_relayout"};
  return {
    /* Whether the library loaded. */
    available: () => Boolean(library()),
    /* Draw `chart` anew; resolves once it is drawn. */
    plot: (chart, data, layout, config) => library().newPlot(chart, data, layout, config),
    /* Draw `chart` again with new data and layout, keeping what its layout's uirevision keeps. */
    react: (chart, data, layout, config) => library().react(chart, data, layout, config),
    /* Change the drawn layout by `update`, keyed by layout paths ("legend.x", "width"). */
    relayout: (chart, update) => library().relayout(chart, update),
    /* Fit a responsive chart to its element's size. */
    resize: chart => library().Plots.resize(chart),
    /* An SVG image of the drawn chart, as a data URL. */
    image: (chart, {width, height}) => library().toImage(chart, {format: "svg", width, height}),
    /* Release the chart's drawing and its listeners. */
    purge: chart => library().purge(chart),
    /* The drawn chart's size, legend and plot area; null before it is drawn. */
    layout(chart) {
      const drawn = chart?._fullLayout;
      if (!drawn) return null;
      return {width: drawn.width, height: drawn.height, showlegend: drawn.showlegend !== false,
        legend: {x: drawn.legend?.x, y: drawn.legend?.y}, plot: {width: drawn._size.w, height: drawn._size.h}};
    },
    /* The drawn legend's element, or null where the chart shows none. */
    legend: chart => chart.querySelector("g.legend"),
    /* Call `handler` on each of the chart's `event`s: "afterplot", after every drawing, or
       "relayout", with the layout paths a reader's zoom or pan changed. */
    on: (chart, event, handler) => chart.on(EVENTS[event], handler),
  };
})();
