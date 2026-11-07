/* One data-only interaction owner; figure state is deliberately local to each DOM view. */
(() => {
  "use strict";
  const initialized = new WeakSet();
  const overlayPlaceholders = new WeakMap();
  function button(label, action) {
    const item = document.createElement("button");
    item.type = "button"; item.textContent = label; item.addEventListener("click", action);
    return item;
  }
  let closeActiveOverlay = null;
  function imageMagnifier(figure) {
    // Expanded images only: a view-local transform, so reading view and print stay untouched.
    let image = null, scale = 1, x = 0, y = 0, drag = null;
    const draw = () => {
      image.style.transform = scale === 1 && !x && !y ? "" : `translate(${x}px, ${y}px) scale(${scale})`;
    };
    const reset = () => { scale = 1; x = 0; y = 0; draw(); };
    function zoom(factor, clientX, clientY) {
      const next = Math.min(8, Math.max(1, scale * factor));
      const bounds = image.getBoundingClientRect();
      const left = bounds.left - x, top = bounds.top - y;
      const px = clientX === undefined ? bounds.left + bounds.width / 2 - left : clientX - left;
      const py = clientY === undefined ? bounds.top + bounds.height / 2 - top : clientY - top;
      const ratio = next / scale;
      x = next === 1 ? 0 : x + (px - x) * (1 - ratio);
      y = next === 1 ? 0 : y + (py - y) * (1 - ratio);
      scale = next;
      draw();
    }
    const active = () => image && figure.classList.contains("figure-expanded");
    figure.addEventListener("wheel", event => {
      if (!active() || !image.contains(event.target)) return;
      event.preventDefault();
      zoom(event.deltaY > 0 ? 1 / 1.2 : 1.2, event.clientX, event.clientY);
    }, {passive: false});
    figure.addEventListener("pointerdown", event => {
      if (!active() || event.button !== 0 || event.target !== image || scale === 1) return;
      event.preventDefault();
      drag = {pointer: event.pointerId, x: event.clientX - x, y: event.clientY - y};
      image.setPointerCapture?.(event.pointerId);
    });
    figure.addEventListener("pointermove", event => {
      if (!drag || event.pointerId !== drag.pointer) return;
      x = event.clientX - drag.x; y = event.clientY - drag.y; draw();
    });
    const stop = () => { drag = null; };
    figure.addEventListener("pointerup", stop);
    figure.addEventListener("pointercancel", stop);
    figure.addEventListener("dblclick", event => { if (active() && event.target === image) reset(); });
    figure.addEventListener("keydown", event => {
      if (!active() || event.target !== image) return;
      if (event.key === "0" || event.key === "Home") reset();
      else if (event.key === "+" || event.key === "=") zoom(1.2);
      else if (event.key === "-") zoom(1 / 1.2);
      else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        const step = image.getBoundingClientRect().width / 10;
        x -= (event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0) * step;
        y -= (event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0) * step;
        draw();
      } else return;
      event.preventDefault();
    });
    return {
      open() {
        image = figure.querySelector(":scope > img");
        if (!image) return;
        image.classList.add("figure-magnifiable");
        image.tabIndex = 0;
        image.dataset.hoverHelp = "Wheel or +/- to zoom, drag or arrow keys to pan, double-click or 0 to reset";
      },
      close() {
        if (!image) return;
        reset();
        image.classList.remove("figure-magnifiable");
        image.removeAttribute("tabindex");
        image.removeAttribute("title");
        image = null; drag = null;
      },
    };
  }
  function overlayControls(figure) {
    const dialog = document.createElement("dialog");
    dialog.className = "figure-overlay";
    dialog.setAttribute("aria-label", "Enlarged figure");
    let placeholder = null;
    let originalParent = null;
    let fittedVisual = null;
    let originalVisualStyle = null;
    const magnifier = figure.dataset.figureKind === "image" ? imageMagnifier(figure) : null;
    function fitVisual() {
      if (!dialog.open) return;
      let visual = figure.querySelector(":scope > img, :scope > svg.figure-visual, :scope > .sankey-canvas");
      if (!visual || getComputedStyle(visual).display === "none") return;
      const style = getComputedStyle(figure);
      const caption = figure.querySelector(":scope > figcaption");
      const captionStyle = caption && getComputedStyle(caption);
      const captionHeight = caption ? caption.getBoundingClientRect().height +
        parseFloat(captionStyle.marginTop) + parseFloat(captionStyle.marginBottom) : 0;
      const width = figure.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      const height = figure.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - captionHeight;
      const frame = globalThis.obsSankey?.frame(visual);
      if (frame && height > 0) {
        // Spread the layout, not the glyphs, when height-limited fitting would letterbox it.
        const target = Math.ceil(Math.max(frame.width, width * frame.height / height));
        if (Math.abs(visual.viewBox.baseVal.width - target) > .5) {
          const replacement = frame.render(target);
          visual.replaceWith(replacement);
          visual = replacement;
        }
      }
      if (visual !== fittedVisual) {
        fittedVisual = visual;
        originalVisualStyle = visual.getAttribute("style");
      }
      const ratio = visual.tagName.toLowerCase() === "img" ?
        visual.naturalWidth / visual.naturalHeight : visual.viewBox.baseVal.width / visual.viewBox.baseVal.height;
      if (!Number.isFinite(ratio) || ratio <= 0) return;
      const fittedWidth = Math.max(1, Math.min(width, height * ratio));
      visual.style.width = `${fittedWidth}px`;
      visual.style.height = `${fittedWidth / ratio}px`;
      visual.style.maxWidth = "100%";
    }
    const fitObserver = new ResizeObserver(fitVisual);
    fitObserver.observe(figure);
    figure.addEventListener("load", fitVisual, true);
    figure.addEventListener("obs-figure-render", fitVisual);
    const expand = button("", () => {
      if (dialog.open) return;
      originalParent = figure.parentNode;
      placeholder = document.createComment("figure-position");
      originalParent.insertBefore(placeholder, figure);
      overlayPlaceholders.set(figure, placeholder);
      dialog.append(figure);
      document.body.append(dialog);
      figure.classList.add("figure-expanded");
      expand.hidden = true;
      close.hidden = false;
      dialog.showModal();
      document.dispatchEvent(new CustomEvent("obs-figure-overlay", {detail: {dialog, open: true}}));
      fitVisual();
      magnifier?.open();
      close.focus();
      closeActiveOverlay = closeFigure;
      requestAnimationFrame(() => {
        const chart = figure.querySelector(".figure-chart");
        if (chart && window.Plotly) Plotly.Plots.resize(chart);
      });
    });
    expand.className = "figure-expand";
    expand.setAttribute("aria-label", "Expand figure");
    expand.title = "Expand figure";
    globalThis.obsAssets.append(expand, "figure.expand");
    const close = button("", closeFigure);
    globalThis.obsAssets.append(close, "close");
    close.className = "figure-overlay-close";
    close.setAttribute("aria-label", "Close enlarged figure");
    close.title = "Close enlarged figure";
    close.hidden = true;
    figure.append(expand, close);
    dialog.addEventListener("cancel", event => {
      event.preventDefault();
      closeFigure();
    });
    dialog.addEventListener("keydown", event => {
      if (event.key !== "Tab") return;
      const focusable = [...dialog.querySelectorAll(
        'button:not([hidden]), select, input, textarea, a[href], [tabindex="0"]',
      )].filter(element => element.getClientRects().length);
      if (!focusable.length) {
        event.preventDefault();
        close.focus();
        return;
      }
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    });
    dialog.addEventListener("click", event => {
      // A link inside the figure navigates like one in prose: the overlay closes first.
      if (event.target.closest?.('a[href^="#"]')) closeFigure();
      if (event.target === dialog) closeFigure();
    });
    function closeFigure() {
      if (!dialog.open) return;
      dialog.close();
      document.dispatchEvent(new CustomEvent("obs-figure-overlay", {detail: {dialog, open: false}}));
      dialog.remove();
      magnifier?.close();
      figure.classList.remove("figure-expanded");
      if (fittedVisual) {
        const frame = globalThis.obsSankey?.frame(fittedVisual);
        if (originalVisualStyle === null) fittedVisual.removeAttribute("style");
        else fittedVisual.setAttribute("style", originalVisualStyle);
        if (frame) fittedVisual.replaceWith(frame.render(0));
        fittedVisual = null;
        originalVisualStyle = null;
      }
      if (placeholder?.parentNode) placeholder.replaceWith(figure);
      else originalParent?.append(figure);
      overlayPlaceholders.delete(figure);
      placeholder = null;
      originalParent = null;
      expand.hidden = false;
      close.hidden = true;
      closeActiveOverlay = null;
      expand.focus({preventScroll: true});
      requestAnimationFrame(() => {
        const chart = figure.querySelector(".figure-chart");
        if (chart && window.Plotly) Plotly.Plots.resize(chart);
      });
    }
    return {dialog, closeFigure};
  }
  function svgInspector(figure, spec, host) {
    const inspector = document.createElement("div");
    inspector.className = "figure-inspector";
    const controls = document.createElement("div");
    controls.className = "figure-controls";
    const select = document.createElement("select");
    select.setAttribute("aria-label", "Figure panel");
    spec.panels.forEach(panel => {
      const option = document.createElement("option");
      option.value = panel.id; option.textContent = panel.title || panel.id; select.append(option);
    });
    const ns = "http://www.w3.org/2000/svg";
    const viewport = document.createElementNS(ns, "svg");
    viewport.classList.add("figure-viewport");
    viewport.setAttribute("tabindex", "0");
    viewport.setAttribute("role", "img");
    viewport.setAttribute("aria-label", "Figure panel; wheel to zoom, drag to pan, 0 to reset");
    // An inline drawing (one with links) is copied, so its links work in the inspector too.
    const drawing = figure.querySelector(".figure-default");
    const image = drawing.src ? document.createElementNS(ns, "image") : drawing.cloneNode(true);
    image.removeAttribute("class");
    const full = spec.viewBox.split(/[ ,]+/).map(Number);
    image.setAttribute("x", full[0]); image.setAttribute("y", full[1]);
    image.setAttribute("width", full[2]); image.setAttribute("height", full[3]);
    if (drawing.src) image.setAttribute("href", drawing.src);
    viewport.append(image);
    const states = new Map(spec.panels.map(panel => [panel.id, panel.box.slice()]));
    function box() { return states.get(select.value); }
    function draw() { viewport.setAttribute("viewBox", box().join(" ")); }
    function reset() {
      states.set(select.value, spec.panels.find(panel => panel.id === select.value).box.slice());
      draw();
    }
    function zoom(factor, center) {
      const [x, y, w, h] = box();
      const base = spec.panels.find(panel => panel.id === select.value).box;
      const width = Math.min(base[2] * 8, Math.max(base[2] / 100, w * factor));
      factor = width / w;
      const p = center || {x: x + w / 2, y: y + h / 2};
      states.set(select.value, [p.x + (x - p.x) * factor, p.y + (y - p.y) * factor,
        width, h * factor]);
      draw();
    }
    function point(event) {
      return new DOMPoint(event.clientX, event.clientY).matrixTransform(viewport.getScreenCTM().inverse());
    }
    viewport.addEventListener("wheel", event => {
      event.preventDefault(); zoom(event.deltaY > 0 ? 1.2 : 1 / 1.2, point(event));
    }, {passive: false});
    let drag;
    viewport.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      drag = point(event); viewport.setPointerCapture(event.pointerId);
    });
    viewport.addEventListener("pointermove", event => {
      if (!drag) return;
      const now = point(event); const b = box();
      states.set(select.value, [b[0] + drag.x - now.x, b[1] + drag.y - now.y, b[2], b[3]]);
      draw();
    });
    const stop = () => { drag = null; };
    viewport.addEventListener("pointerup", stop);
    viewport.addEventListener("pointercancel", stop);
    viewport.addEventListener("dblclick", reset);
    viewport.addEventListener("keydown", event => {
      if (event.key === "0" || event.key === "Home") reset();
      else if (event.key === "+" || event.key === "=") zoom(1 / 1.2);
      else if (event.key === "-") zoom(1.2);
      else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        const b = box();
        b[0] += (event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0) * b[2] / 10;
        b[1] += (event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0) * b[3] / 10;
        draw();
      } else return;
      event.preventDefault();
    });
    select.addEventListener("change", draw);
    const zoomIn = button("", () => zoom(1 / 1.2));
    zoomIn.setAttribute("aria-label", "Zoom in"); zoomIn.title = "Zoom in";
    globalThis.obsAssets.append(zoomIn, "add");
    const zoomOut = button("", () => zoom(1.2));
    zoomOut.setAttribute("aria-label", "Zoom out"); zoomOut.title = "Zoom out";
    globalThis.obsAssets.append(zoomOut, "remove");
    controls.append(select, zoomIn, zoomOut, button("Reset panel", reset));
    inspector.append(controls, viewport); host.append(inspector);
    draw();
  }
  // The view options a kind registers (figures.py, FigureKind.options): each builds its control,
  // whose changes are session-only view state, never saved and never a change.
  const FIGURE_OPTIONS = {
    legend(figure) {
      const control = button("Legend", () => {
        const chart = figure.querySelector(".figure-chart");
        if (!chart?._fullLayout || !window.Plotly) return;
        const shown = chart._fullLayout.showlegend !== false;
        Plotly.relayout(chart, {showlegend: !shown});
        control.setAttribute("aria-pressed", String(!shown));
      });
      control.className = "filter-pill";
      control.setAttribute("aria-pressed", "true");
      control.title = "Show or hide the plot legend";
      return control;
    },
    // An equation figure's view options (equations.js).
    trace: figure => globalThis.obsEquations.option("trace", figure),
    axis: figure => globalThis.obsEquations.option("axis", figure),
    swap: figure => globalThis.obsEquations.option("swap", figure),
    family: figure => globalThis.obsEquations.option("family", figure),
    parallel: figure => globalThis.obsEquations.option("parallel", figure),
    // A decision figure's Reset weights (pugh-figure.js).
    weights: figure => globalThis.obsPugh.option(figure),
  };
  function optionsMenu(figure) {
    const keys = (figure.dataset.figureOptions || "").split(" ").filter(key => FIGURE_OPTIONS[key]);
    if (!keys.length) return;
    const {toggle, panel} = globalThis.obsOptionsMenu({
      label: "Figure options", toggleClass: "figure-options-toggle", panelClass: "figure-options",
    });
    // A kind's option may not apply to one figure: its builder then returns nothing.
    panel.append(...keys.map(key => FIGURE_OPTIONS[key](figure)).filter(Boolean));
    figure.append(toggle, panel);
  }
  function initialize(figure) {
    if (!figure.isConnected || figure.closest(".print-book")) return;
    if (initialized.has(figure)) return;
    initialized.add(figure);
    overlayControls(figure);
    optionsMenu(figure);
    if (!figure.hasAttribute("data-engineering-figure")) return;
    if (figure.dataset.figureKind === "sankey") {
      globalThis.obsSankey.render(figure, JSON.parse(figure.dataset.figureSpec));
      return;
    }
    const spec = JSON.parse(figure.dataset.figureSpec);
    const host = figure.querySelector(".figure-live");
    if (spec.kind === "svg") { svgInspector(figure, spec, host); return; }
    if (spec.kind === "pugh") { globalThis.obsPugh.render(figure, spec, host); return; }
    if (!window.Plotly) {
      const message = document.createElement("p");
      message.setAttribute("role", "status");
      message.textContent = "Interactive graph unavailable: Plotly could not load."
        + (figure.querySelector(".figure-default") ? " Showing the embedded static figure." : "");
      host.append(message);
      figure.dataset.figureError = "Plotly unavailable";
      try {
        globalThis.obsCapabilities?.fail("plotting", "the plotting library did not load");
      } catch (_error) { /* An HTML without the plotting canary reports nothing more. */ }
      return;
    }
    if (spec.kind === "equations") { globalThis.obsEquations.render(figure, spec, host); return; }
    const chart = document.createElement("div");
    chart.className = "figure-chart"; host.append(chart);
    const semanticBorder = getComputedStyle(document.documentElement)
      .getPropertyValue("--color-border").trim();
    const authoredLegend = spec.layout.legend || {};
    const layout = {
      ...structuredClone(spec.layout),
      legend: {...authoredLegend, borderwidth: 1, bordercolor: semanticBorder},
      autosize: true, height: 450, dragmode: "pan",
    };
    const ready = Plotly.newPlot(chart, structuredClone(spec.data), structuredClone(layout), {
      responsive: true, scrollZoom: true, displaylogo: false,
      displayModeBar: true,
      edits: {legendPosition: true},
      modeBarButtonsToRemove: ["toImage", "sendDataToCloud"],
    });
    ready.then(() => {
      figure.classList.add("figure-plot-ready");
      function legendKeyboard() {
        const legend = chart.querySelector("g.legend");
        if (!legend || legend.hasAttribute("tabindex")) return;
        legend.setAttribute("tabindex", "0");
        legend.setAttribute("role", "group");
        legend.setAttribute("aria-label", "Plot legend; drag frame or use arrow keys to move");
        legend.addEventListener("keydown", event => {
          if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
          event.preventDefault();
          event.stopPropagation();
          const current = chart._fullLayout.legend;
          const step = event.shiftKey ? 0.1 : 0.02;
          const dx = event.key === "ArrowLeft" ? -step : event.key === "ArrowRight" ? step : 0;
          const dy = event.key === "ArrowDown" ? -step : event.key === "ArrowUp" ? step : 0;
          Plotly.relayout(chart, {
            "legend.x": Math.max(0, Math.min(1, current.x + dx)),
            "legend.y": Math.max(0, Math.min(1, current.y + dy)),
          });
        });
      }
      // The legend correction converges (artifact-ui.md, Interactive engineering figures): it
      // runs on the next frame, at most once per frame, and leaves alone a legend whose box and
      // plot box are the ones it last corrected, so a box its own relayout did not move cannot
      // loop the page.
      let legendFrame = 0, corrected = "";
      function keepLegendReachable() {
        legendFrame = 0;
        const legend = chart.querySelector("g.legend");
        if (!legend || !chart.isConnected) return;
        const box = legend.getBoundingClientRect(), bounds = chart.getBoundingClientRect();
        const dx = box.width > bounds.width || box.left < bounds.left ? bounds.left - box.left :
          box.right > bounds.right ? bounds.right - box.right : 0;
        const dy = box.height > bounds.height || box.top < bounds.top ? bounds.top - box.top :
          box.bottom > bounds.bottom ? bounds.bottom - box.bottom : 0;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) { corrected = ""; return; }
        const measured = JSON.stringify([box.left, box.top, box.width, box.height,
          bounds.left, bounds.top, bounds.width, bounds.height]);
        if (measured === corrected) return;
        corrected = measured;
        const layout = chart._fullLayout;
        Plotly.relayout(chart, {
          "legend.x": layout.legend.x + dx / layout._size.w,
          "legend.y": layout.legend.y - dy / layout._size.h,
        });
      }
      chart.on("plotly_afterplot", () => {
        legendKeyboard();
        legendFrame ||= requestAnimationFrame(keepLegendReachable);
      });
      legendKeyboard();
      const observer = new ResizeObserver(() => {
        if (!chart.isConnected || !chart.clientWidth || !chart.clientHeight) return;
        const width = chart.clientWidth, height = chart.clientHeight;
        if (chart._fullLayout.width === width && chart._fullLayout.height === height) return;
        Plotly.relayout(chart, {width, height});
      });
      observer.observe(chart);
    }).catch(error => {
      chart.remove(); figure.dataset.figureError = String(error);
      const message = document.createElement("p");
      message.textContent = `Interactive figure unavailable: ${error}`; host.append(message);
    });
  }
  function scan(root) {
    if (root.nodeType !== 1 && root !== document) return;
    if (root.matches?.("[data-artifact-figure]")) initialize(root);
    root.querySelectorAll("[data-artifact-figure]").forEach(initialize);
  }
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(scan)))
    .observe(document.body, {childList: true, subtree: true});
  const artifactData = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
  document.documentElement.style.setProperty(
    "--figure-prose-width-multiplier", artifactData.figures.proseWidthMultiplier,
  );
  document.documentElement.style.setProperty(
    "--figure-viewport-gutter", `${artifactData.figures.viewportGutterRem}rem`,
  );
  document.documentElement.style.setProperty(
    "--figure-viewport-height-ratio", artifactData.figures.viewportHeightRatio,
  );
  document.addEventListener("obs-chapter-changing", () => closeActiveOverlay?.());
  document.addEventListener("obs-print-start", () => closeActiveOverlay?.());
  window.obsFigures = {
    setProjection(sourceNote, graph) {
      if (graph !== null && (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.links) ||
          !Array.isArray(graph.data?.where))) throw new Error("Invalid projected Sankey.");
      // Only an artifact with a Sankey figure ships its drawing (features.py, sankey), and only
      // such a figure reads a projection.
      globalThis.obsSankey?.project(sourceNote, graph === null ? null : structuredClone(graph));
      this.projectSankeys(document);
    },
    pageNode: node => overlayPlaceholders.get(node) || node,
    // A figure the page layout places (pages.js): a decision figure's height is its drawn view,
    // so it is drawn at once, as the reader sees it, or in a print copy as it prints; so are its details and its Proposed winner box.
    place(figure) {
      if (figure.matches("[data-pugh-details], [data-pugh-proposed]")) { globalThis.obsPugh.placeDetails(figure); return; }
      if (figure.dataset.figureKind !== "pugh" || figure.classList.contains("figure-pugh-ready")) return;
      if (figure.closest(".print-book")) globalThis.obsPugh.print(figure, JSON.parse(figure.dataset.figureSpec));
      else initialize(figure);
    },
    projectSankeys(container) {
      container.querySelectorAll('[data-figure-kind="sankey"]').forEach(figure => {
        const spec = JSON.parse(figure.dataset.figureSpec);
        if (spec.data) globalThis.obsSankey.update(figure, spec);
      });
    },
    async preparePrint(container) {
      // A decision figure prints the reader's view (pugh-figure.js).
      for (const figure of container.querySelectorAll('[data-figure-kind="pugh"]')) {
        globalThis.obsPugh.print(figure, JSON.parse(figure.dataset.figureSpec));
      }
      // An equation figure prints the reader's view; a caption note says where it changed.
      for (const figure of container.querySelectorAll('[data-figure-kind="equations"]:not(:has(> img))')) {
        if (!window.Plotly) throw new Error("Cannot print graph: Plotly could not load.");
        const {src, changed} = await globalThis.obsEquations.printImage(figure, JSON.parse(figure.dataset.figureSpec));
        const image = document.createElement("img");
        image.className = "figure-default";
        image.alt = figure.querySelector("figcaption")?.textContent || figure.id;
        image.src = src;
        figure.prepend(image);
        if (changed) {
          const note = document.createElement("span");
          note.className = "figure-view-note";
          note.textContent = ` ${globalThis.obsEquations.VIEW_NOTE}`;
          let caption = figure.querySelector("figcaption");
          if (!caption) { caption = document.createElement("figcaption"); figure.append(caption); }
          (caption.querySelector("p:last-child") || caption).append(note);
        }
      }
      for (const figure of container.querySelectorAll('[data-figure-kind="plot"]:not(:has(> img))')) {
        if (!window.Plotly) throw new Error("Cannot print graph: Plotly could not load.");
        const spec = JSON.parse(figure.dataset.figureSpec);
        const chart = document.createElement("div");
        figure.querySelector(".figure-live").append(chart);
        try {
          await Plotly.newPlot(chart, spec.data, {...spec.layout, width: 900, height: 450});
          const image = document.createElement("img");
          image.className = "figure-default";
          image.alt = figure.querySelector("figcaption")?.textContent || spec.alt || spec.source;
          image.src = await Plotly.toImage(chart, {format: "svg", width: 900, height: 450});
          figure.prepend(image);
        } finally {
          Plotly.purge(chart);
          chart.remove();
        }
      }
    },
  };
  window.addEventListener("beforeprint", () => closeActiveOverlay?.());
  scan(document);
})();
