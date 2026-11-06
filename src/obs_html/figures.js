/* One data-only interaction owner; figure state is deliberately local to each DOM view. */
(() => {
  "use strict";
  const initialized = new WeakSet();
  const overlayPlaceholders = new WeakMap();
  const sankeyFrames = new WeakMap();
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
      const frame = sankeyFrames.get(visual);
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
        const frame = sankeyFrames.get(fittedVisual);
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
  const SVG = "http://www.w3.org/2000/svg";
  const sankeyConditionsMatch = (record, conditions) => globalThis.obsQuery.compileConditions(conditions).match(record);
  /*
   * Fixed-sort breadth relaxation ported from d3-sankey 0.12.3/src/sankey.js.
   * Copyright 2015, Mike Bostock
   * All rights reserved.
   *
   * Redistribution and use in source and binary forms, with or without modification,
   * are permitted provided that the following conditions are met:
   * * Redistributions of source code must retain the above copyright notice, this
   *   list of conditions and the following disclaimer.
   * * Redistributions in binary form must reproduce the above copyright notice,
   *   this list of conditions and the following disclaimer in the documentation
   *   and/or other materials provided with the distribution.
   * * Neither the name of the author nor the names of contributors may be used to
   *   endorse or promote products derived from this software without specific prior
   *   written permission.
   * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
   * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
   * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
   * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
   * ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
   * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
   * LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
   * ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
   * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
   * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
   */
  function sankeyCountLabels(spec) {
    return {unit: "records", unique: "unique", ...spec.countLabels};
  }
  function splitSankeyLayout(spec, inputLinks, minimumWidth = 0) {
    const nodes = spec.nodes.map(node => ({...node, sourceLinks: [], targetLinks: []}));
    const byId = new Map(nodes.map(node => [node.id, node]));
    const links = inputLinks.map(link => ({...link, source: byId.get(link.source), target: byId.get(link.target)}));
    links.forEach(link => { link.source.sourceLinks.push(link); link.target.targetLinks.push(link); });
    const sum = (items, getter) => items.reduce((total, item) => total + getter(item), 0);
    nodes.forEach(node => {
      node.sourceLinks.sort((a, b) => (a.order || 0) - (b.order || 0));
      node.targetLinks.sort((a, b) => (a.order || 0) - (b.order || 0));
      node.value = Math.max(sum(node.sourceLinks, link => link.value), sum(node.targetLinks, link => link.value));
    });
    const stages = [...new Set(nodes.map(node => node.stage))].sort((a, b) => a - b);
    let current = new Set(nodes), depth = 0;
    while (current.size) {
      const next = new Set();
      current.forEach(node => {
        node.depth = depth;
        node.sourceLinks.forEach(link => next.add(link.target));
      });
      if (++depth > nodes.length) throw new Error("Circular split Sankey.");
      current = next;
    }
    const count = Math.max(Math.max(...nodes.map(node => node.depth)) + 1, stages.at(-1) - stages[0] + 1);
    const labels = new Map(nodes.map(node => {
      const lines = node.label.split("\n");
      const {unit, unique} = sankeyCountLabels(spec);
      const counted = (line, word) => line !== undefined && line.endsWith(` ${word}`) &&
        /^\d+$/.test(line.slice(0, -word.length - 1));
      if (node.records && !(lines.length >= 3 && counted(lines.at(-2), unit) &&
          counted(lines.at(-1), unique))) {
        lines.push(`${Math.ceil(node.value)} ${unit}`, `${Math.ceil(node.value)} ${unique}`);
      }
      // Conservative 12px glyph bounds keep static/browser geometry portable.
      const textWidth = line => [...line].reduce((total, character) => total + (
        character === " " ? 4 : "iljtfIr".includes(character) ? 6 :
        "mwMW%@&#".includes(character) ? 12 : /^[A-Z]$/.test(character) ? 9 :
        character.charCodeAt(0) < 128 ? 8 : 12 * character.length), 0);
      return [node.id, {width: Math.max(...lines.map(textWidth)) + 8,
        height: lines.length * 14 + 4, lines: lines.length}];
    }));
    const flow = nodes.filter(node => !node.placement || node.placement === "flow");
    const flowWidth = Math.max(0, ...flow.map(node => labels.get(node.id).width));
    const flowHeight = Math.max(0, ...flow.map(node => labels.get(node.id).height));
    const branchHeight = Math.max(0, ...nodes.filter(node => ["above", "below"].includes(node.placement))
      .map(node => labels.get(node.id).height));
    const groups = new Map();
    nodes.filter(node => ["above", "below"].includes(node.placement)).forEach(node => {
      const source = byId.get(node.branchSource) || node.targetLinks.at(-1)?.source || node;
      const sourceStage = source.stage, destinationStage = sourceStage + (node.placement === "above" ? -1 : 1);
      const destination = flow.find(other => other.stage === destinationStage);
      const barWidth = 40 + Math.max(0, node.value - 1) * .9;
      const key = `${Math.min(sourceStage, destinationStage)}:${Math.max(sourceStage, destinationStage)}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push({node, source, destination, barWidth,
        footprint: Math.max(barWidth, labels.get(node.id).width)});
    });
    let left = 48, rightMargin = 48, spacing = Math.max(180, flowWidth * 2 + 46);
    const packed = [];
    groups.forEach(group => {
      const lanes = [[], []], loads = [0, 0];
      [...group].sort((a, b) => b.barWidth - a.barWidth ||
        (a.node.branchOrder || 0) - (b.node.branchOrder || 0) ||
        (a.node.id < b.node.id ? -1 : a.node.id > b.node.id ? 1 : 0)).forEach((entry, index) => {
        const lane = index < 2 ? index : loads[0] <= loads[1] ? 0 : 1;
        lanes[lane].push(entry); loads[lane] += entry.barWidth + 12;
      });
      const required = Math.max(...lanes.map(lane =>
        sum(lane, entry => entry.footprint) + Math.max(0, lane.length - 1) * 12)) + 48;
      spacing = Math.max(spacing, required);
      group.forEach(entry => {
        if (!entry.destination) {
          if (entry.node.placement === "above") left = Math.max(left, required);
          else rightMargin = Math.max(rightMargin, required);
        }
      });
      packed.push(lanes);
    });
    const naturalWidth = Math.ceil(Math.max(700, left + rightMargin + 14 + Math.max(0, count - 1) * spacing));
    const width = Math.ceil(Math.max(naturalWidth, minimumWidth));
    const right = width - rightMargin;
    const columnSizes = new Map();
    nodes.forEach(node => {
      const layer = Math.min(count - 1, Math.max(0, node.stage - stages[0]));
      columnSizes.set(layer, (columnSizes.get(layer) || 0) + 1);
    });
    const padding = Math.max(18, flowHeight + 18), largest = Math.max(...columnSizes.values());
    const available = Math.max(340 + (largest - 1) * (padding - 18),
      (largest - 1) * padding + flowHeight + 140);
    const upperY = 12 + branchHeight + 12 + 4;
    const top = upperY + 4 + 18 + flowHeight / 2, bottom = top + available;
    const lowerY = bottom + flowHeight / 2 + 18 + 4;
    const height = Math.ceil(lowerY + 4 + 12 + branchHeight + 12);
    const columns = Array.from({length: count}, () => []);
    nodes.forEach(node => {
      node.layer = Math.min(count - 1, Math.max(0, node.stage - stages[0]));
      node.x0 = stages.length === 1 ? (left + right - 14) / 2
        : left + node.layer * (right - left - 14) / Math.max(1, count - 1);
      node.x1 = node.x0 + 14;
      columns[node.layer].push(node);
    });
    columns.forEach(column => column.sort((a, b) => (a.order || 0) - (b.order || 0)));
    const populated = columns.filter(column => column.length);
    const scale = Math.min(...populated.filter(column => column.some(node => node.value)).map(column =>
      (bottom - top - (column.length - 1) * padding) / sum(column, node => node.value)));
    populated.forEach(column => {
      let y = top;
      column.forEach(node => {
        node.y0 = y; node.y1 = y + node.value * scale;
        y = node.y1 + padding;
        node.sourceLinks.forEach(link => { link.width = link.value * scale; });
      });
      const extra = (bottom - y + padding) / (column.length + 1);
      column.forEach((node, index) => {
        node.y0 += extra * (index + 1); node.y1 += extra * (index + 1);
      });
    });
    function ideal(source, target, forward) {
      const a = forward ? source : target, b = forward ? target : source;
      const outgoing = forward ? "sourceLinks" : "targetLinks", incoming = forward ? "targetLinks" : "sourceLinks";
      const endpoint = forward ? "target" : "source";
      let y = a.y0 - (a[outgoing].length - 1) * padding / 2;
      for (const link of a[outgoing]) {
        if (link[endpoint] === b) break;
        y += link.width + padding;
      }
      for (const link of b[incoming]) {
        if (link[forward ? "source" : "target"] === a) break;
        y -= link.width;
      }
      return y;
    }
    function shift(node, delta) { node.y0 += delta; node.y1 += delta; }
    function collide(column, beta) {
      if (!column.length) return;
      function push(y, start, down) {
        for (let index = start; index >= 0 && index < column.length; index += down ? 1 : -1) {
          const node = column[index], delta = (down ? y - node.y0 : node.y1 - y) * beta;
          if (delta > 1e-6) shift(node, down ? delta : -delta);
          y = down ? node.y1 + padding : node.y0 - padding;
        }
      }
      const middle = column.length >> 1;
      push(column[middle].y0 - padding, middle - 1, false);
      push(column[middle].y1 + padding, middle + 1, true);
      push(bottom, column.length - 1, false); push(top, 0, true);
    }
    for (let iteration = 0; iteration < 6; iteration++) {
      const alpha = .99 ** iteration, beta = Math.max(1 - alpha, (iteration + 1) / 6);
      for (const forward of [false, true]) {
        for (let index = forward ? 1 : count - 2; index >= 0 && index < count; index += forward ? 1 : -1) {
          const column = columns[index];
          column.forEach(node => {
            let y = 0, total = 0;
            node[forward ? "targetLinks" : "sourceLinks"].forEach(link => {
              const value = link.value * (link.target.layer - link.source.layer);
              y += ideal(link.source, link.target, forward) * value; total += value;
            });
            if (total > 0) shift(node, (y / total - node.y0) * alpha);
          });
          collide(column, beta);
        }
      }
    }
    nodes.forEach(node => {
      for (const [side, endpoint] of [["sourceLinks", "y0"], ["targetLinks", "y1"]]) {
        let y = node.y0;
        node[side].forEach(link => { link[endpoint] = y + link.width / 2; y += link.width; });
      }
    });
    const incoming = new Map(links.filter(link => link.series).map(link => [`${link.series}\0${link.target.id}`, link]));
    links.forEach(link => {
      const previous = incoming.get(`${link.series}\0${link.source.id}`);
      if (previous) link.y0 = previous.y1;
    });
    const positions = new Map(nodes.map(node => [node.id,
      {x: node.x0, y: node.y0, width: 14, height: node.y1 - node.y0}]));
    flow.forEach(node => {
      const p = positions.get(node.id), end = p.x > width / 2;
      Object.assign(p, {labelX: end ? p.x - 7 : p.x + p.width + 7,
        labelY: p.y + p.height / 2 - (labels.get(node.id).lines - 1) * 7 + 4,
        labelAnchor: end ? "end" : "start"});
    });
    packed.forEach(lanes => {
      lanes.forEach((lane, index) => {
        if (!lane.length) return;
        lane.forEach(entry => {
          const sourceX = (entry.source.x0 + entry.source.x1) / 2;
          const destinationX = entry.destination ? (entry.destination.x0 + entry.destination.x1) / 2
            : entry.node.placement === "above" ? 8 : width - 8;
          Object.assign(entry, {left: Math.min(sourceX, destinationX) + 24, right: Math.max(sourceX, destinationX) - 24});
        });
        const left = Math.min(...lane.map(entry => entry.left)), right = Math.max(...lane.map(entry => entry.right));
        const available = right - left;
        const desired = sum(lane, entry => entry.footprint) + 12 * (lane.length - 1);
        let cursor = left + (available - desired) / 2;
        lane.forEach(entry => {
          const footprint = entry.footprint, barWidth = entry.barWidth;
          const y = index === 0 ? upperY : lowerY, lines = labels.get(entry.node.id).lines;
          positions.set(entry.node.id, {x: cursor + (footprint - barWidth) / 2,
            y: y - 4, width: barWidth, height: 8, horizontal: true, upper: index === 0,
            labelX: cursor + footprint / 2, labelAnchor: "middle",
            labelY: index === 0 ? y - 19 - (lines - 1) * 14 : y + 27});
          cursor += footprint + 12;
        });
      });
    });
    return {width, height, naturalWidth, scale, positions, centers: new Map(links.map(link =>
      [link.index, {source: link.y0, target: link.y1}]))};
  }
  function sankeySvg(spec, links, minimumWidth = 0) {
    if (!links.length) {
      const empty = document.createElementNS(SVG, "svg");
      empty.classList.add("sankey-canvas");
      empty.setAttribute("width", "700");
      empty.setAttribute("height", "180");
      empty.style.setProperty("--sankey-width", "700px");
      empty.setAttribute("viewBox", "0 0 700 180");
      empty.setAttribute("role", "img");
      empty.setAttribute("aria-label", figureCaption(spec));
      const message = document.createElementNS(SVG, "text");
      message.setAttribute("x", "350");
      message.setAttribute("y", "90");
      message.setAttribute("text-anchor", "middle");
      message.textContent = "No matching records";
      empty.append(message);
      return empty;
    }
    const stages = [...new Set(spec.nodes.map(node => node.stage))].sort((a, b) => a - b);
    const columns = new Map(stages.map(stage => [stage, []]));
    const incoming = new Map(spec.nodes.map(node => [node.id, 0]));
    const outgoing = new Map(spec.nodes.map(node => [node.id, 0]));
    const byId = new Map(spec.nodes.map(node => [node.id, node]));
    const fromLinks = new Map(spec.nodes.map(node => [node.id, []]));
    const toLinks = new Map(spec.nodes.map(node => [node.id, []]));
    spec.nodes.forEach(node => columns.get(node.stage).push(node));
    links.forEach(link => {
      outgoing.set(link.source, outgoing.get(link.source) + link.value);
      incoming.set(link.target, incoming.get(link.target) + link.value);
      fromLinks.get(link.source).push(link);
      toLinks.get(link.target).push(link);
    });
    const weight = node => Math.max(incoming.get(node.id), outgoing.get(node.id));
    const largestColumn = Math.max(...[...columns.values()]
      .map(column => column.reduce((sum, node) => sum + weight(node), 0)));
    const labelWidth = Math.max(...spec.nodes.flatMap(node => node.label.split("\n").map(line => line.length))) * 7 + 24;
    let width = Math.max(700, 160 + Math.max(180, labelWidth) * (stages.length - 1));
    const railCount = placement => Math.max(0, ...[...columns.values()].map(column =>
      column.filter(node => node.placement === placement).length));
    const above = railCount("above"), below = railCount("below");
    let height = Math.max(680, 120 + Math.max(...[...columns.values()].map(column => column.length)) * 24)
      + (above + below) * 60;
    const left = 80, right = width - 80, top = 52 + above * 60, bottom = height - 52 - below * 60;
    const stageX = index => stages.length === 1 ? (left + right) / 2
      : left + (right - left) * index / (stages.length - 1);
    const available = bottom - top;
    const gap = spec.nodes.some(node => node.label.includes("\n")) ? 52 : 12, minimum = 10;
    let low = 0, high = available / Math.max(largestColumn, 1);
    const columnHeight = (column, scale) =>
      column.filter(node => !node.placement || node.placement === "flow")
        .reduce((sum, node) => sum + Math.max(minimum, weight(node) * scale) + gap, -gap);
    for (let index = 0; index < 64; index += 1) {
      const scale = (low + high) / 2;
      if ([...columns.values()].some(column => columnHeight(column, scale) > available)) high = scale;
      else low = scale;
    }
    let scale = low, positions = new Map();
    stages.forEach((stage, index) => {
      const x = stageX(index);
      const column = columns.get(stage);
      let y = top + (available - columnHeight(column, scale)) / 2;
      const rails = {above: 0, below: 0};
      column.forEach(node => {
        if (node.placement === "above" || node.placement === "below") {
          const upper = node.placement === "above";
          const rail = rails[node.placement]++;
          const barWidth = Math.max(40, Math.min(120, 40 + Math.max(0, weight(node) - 1) * .9));
          const sourceStage = Math.max(...toLinks.get(node.id).map(link => byId.get(link.source).stage));
          const sourceX = stageX(stages.indexOf(sourceStage));
          const center = Number.isFinite(sourceStage) ? (sourceX + x) / 2 : x;
          positions.set(node.id, {x: center - barWidth / 2, y: upper ? 52 + rail * 60 : bottom + 40 + rail * 60,
            height: 8, width: barWidth, horizontal: true});
          return;
        }
        const h = Math.max(minimum, weight(node) * scale);
        positions.set(node.id, {x, y, height: h, width: 18});
        y += h + gap;
      });
    });
    let linkCenters = new Map();
    spec.nodes.forEach(node => {
      const p = positions.get(node.id);
      let y = p.y + (p.height - outgoing.get(node.id) * scale) / 2;
      fromLinks.get(node.id).forEach(link => {
        const thickness = link.value * scale;
        linkCenters.set(link.index, {source: y + thickness / 2});
        y += thickness;
      });
    });
    spec.nodes.forEach(node => {
      const p = positions.get(node.id);
      let y = p.y + (p.height - incoming.get(node.id) * scale) / 2;
      toLinks.get(node.id).forEach(link => {
        const thickness = link.value * scale;
        linkCenters.get(link.index).target = y + thickness / 2;
        y += thickness;
      });
    });
    const incomingSeries = new Map(links.filter(link => link.series).map(link =>
      [`${link.series}\0${link.target}`, link]));
    links.forEach(link => {
      const incoming = link.series && incomingSeries.get(`${link.series}\0${link.source}`);
      if (incoming) linkCenters.get(link.index).source = linkCenters.get(incoming.index).target;
    });
    let splitFrame;
    if (spec.branchLayout === "split") {
      const layout = splitSankeyLayout(spec, links, minimumWidth);
      ({width, height, scale, positions} = layout);
      linkCenters = layout.centers;
      splitFrame = {width: layout.naturalWidth, height, render: minimum => sankeySvg(spec, links, minimum)};
    }
    const number = value => Number(value.toPrecision(6)).toString();
    const element = (name, attributes, parent) => {
      const item = document.createElementNS(SVG, name);
      Object.entries(attributes).forEach(([key, value]) => item.setAttribute(key, String(value)));
      parent.append(item);
      return item;
    };
    const svg = document.createElementNS(SVG, "svg");
    svg.classList.add("sankey-canvas");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", figureCaption(spec));
    svg.style.setProperty("--sankey-width", `${width}px`);
    element("title", {}, svg).textContent = figureCaption(spec);
    links.forEach(link => {
      const source = byId.get(link.source), target = byId.get(link.target);
      const centers = linkCenters.get(link.index);
      const sourcePosition = positions.get(source.id), targetPosition = positions.get(target.id);
      const startX = sourcePosition.x + sourcePosition.width;
      let endX = targetPosition.x, endY = centers.target;
      if (targetPosition.horizontal) {
        const fraction = Math.max(0, Math.min(1, (centers.source - sourcePosition.y) / Math.max(1, sourcePosition.height)));
        const reverse = spec.branchLayout === "split" &&
          (targetPosition.x + targetPosition.width / 2 - startX) *
          (targetPosition.y + 4 - sourcePosition.y - sourcePosition.height / 2) > 0;
        endX += (reverse ? 1 - fraction : fraction) * targetPosition.width;
        endY = targetPosition.y + targetPosition.height / 2;
      }
      const control = (endX - startX) * (spec.branchLayout === "split" ? .5 : .45);
      const pathData = targetPosition.horizontal
        ? `M ${number(startX)} ${number(centers.source)} C ${number((startX + endX) / 2)} ${number(centers.source)}, ${number(endX)} ${number((centers.source + endY) / 2)}, ${number(endX)} ${number(endY)}`
        : `M ${number(startX)} ${number(centers.source)} C ${number(startX + control)} ${number(centers.source)}, ${number(endX - control)} ${number(endY)}, ${number(endX)} ${number(endY)}`;
      const path = element("path", {
        class: "sankey-link",
        "data-link-index": link.index,
        "data-flow-value": number(link.value),
        ...(link.series ? {"data-series": link.series} : {}),
        d: pathData,
        fill: "none", stroke: link.color || source.color || target.color || "#73869a",
        "stroke-opacity": ".48", "stroke-width": number(link.value * scale),
      }, svg);
      const label = link.label || number(link.value);
      element("title", {}, path).textContent =
        `${source.label} → ${target.label}: ${label} (${number(link.value)})`;
      if (link.originColor && link.value) {
        path.setAttribute("stroke-dasharray", "10 10");
        const origin = path.cloneNode(true);
        origin.classList.replace("sankey-link", "sankey-origin");
        origin.setAttribute("stroke", link.originColor);
        origin.setAttribute("stroke-dashoffset", "10");
        origin.setAttribute("pointer-events", "none");
        svg.append(origin);
      }
      if (link.series || link.where) {
        path.setAttribute("tabindex", "0");
        path.setAttribute("role", "button");
        path.setAttribute("aria-label", label);
        const highlight = active => svg.querySelectorAll("[data-series]").forEach(segment =>
          segment.setAttribute("stroke-opacity", active ? segment.dataset.series === link.series ? "1" : ".12" : ".48"));
        path.addEventListener("mouseenter", () => highlight(true));
        path.addEventListener("mouseleave", () => highlight(false));
        path.addEventListener("focus", () => highlight(true));
        path.addEventListener("blur", () => highlight(false));
        const select = () => {
          if (link.where) globalThis.obsFilter.selectExpression(sankeySelection(spec, [link.where]));
        };
        path.addEventListener("click", select);
        path.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
        });
      }
      if (link.value * scale >= 24) {
        element("text", {
          class: "sankey-link-label", x: number((startX + endX) / 2),
          y: number((centers.source + endY) / 2 + 4), "text-anchor": "middle",
        }, svg).textContent = label;
      }
    });
    spec.nodes.forEach(node => {
      const p = positions.get(node.id);
      const group = element("g", {"class": "sankey-node", "data-node-id": node.id}, svg);
      const rect = element("rect", {
        x: number(p.x), y: number(p.y), width: number(p.width), height: number(p.height),
        rx: 2, fill: node.color || "#587894",
      }, group);
      element("title", {}, rect).textContent =
        `${node.label}; incoming ${number(incoming.get(node.id))}, outgoing ${number(outgoing.get(node.id))}`;
      const labelX = p.labelX ?? p.x + p.width / 2;
      const lines = node.label.split("\n");
      const lower = spec.branchLayout === "split" && p.horizontal ? !p.upper : node.placement === "below";
      const labelY = p.labelY ?? (lower ? p.y + 22 : p.y - 7 - (lines.length - 1) * 14);
      const text = element("text", {
        x: number(labelX), y: number(labelY), "text-anchor": p.labelAnchor || "middle", class: "sankey-label",
      }, group);
      lines.forEach((line, index) =>
        element("tspan", {x: number(labelX), dy: index ? "1.15em" : "0"}, text).textContent = line);
      element("title", {}, text).textContent = node.label;
      const membership = spec.links.filter(link => link.source === node.id || link.target === node.id)
        .map(link => link.where).filter(Boolean);
      const selection = node.selection ?? (membership.length ? sankeySelection(spec, membership) : "");
      if (selection) {
        group.setAttribute("tabindex", "0");
        group.setAttribute("role", "button");
        group.setAttribute("aria-label", `Filter ${node.label}`);
        const select = () => globalThis.obsFilter.selectExpression(selection);
        group.addEventListener("click", select);
        group.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
        });
      }
    });
    if (splitFrame) sankeyFrames.set(svg, splitFrame);
    return svg;
  }
  function figureCaption(spec) { return spec.alt || spec.caption || spec.source || "Figure"; }
  // One selection: the population, the OR of the membership's conditions and the node's own
  // records.where. A counted node's label counts what this expression matches, and its
  // drill-down selects the same expression.
  function sankeySelection(spec, membership, own = []) {
    const expression = globalThis.obsQuery.conditionsExpression;
    const branches = [...new Set(membership.map(conditions => `(${expression(conditions)})`))];
    const population = expression(spec.data?.where);
    const narrowing = expression(own);
    return [population && `(${population})`, `(${branches.join(" OR ")})`, narrowing && `(${narrowing})`]
      .filter(Boolean).join(" AND ");
  }
  const projections = new Map();
  function updateDynamicSankey(figure, spec) {
    if (spec.sourceNote) {
      const owner = globalThis.obsArtifact.records.find(record =>
        record.sourcePath === `${spec.sourceNote}.md`);
      const graph = projections.get(spec.sourceNote) || owner?.frontmatter?.graph;
      if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.links) ||
          !Array.isArray(graph.data?.where)) {
        throw new Error(`Missing canonical Sankey source note: ${spec.sourceNote}`);
      }
      spec = {...spec, ...graph};
    }
    const records = globalThis.obsArtifact.records.filter(record => globalThis.obsArtifact.selectable(record) &&
      globalThis.obsArtifact.matchesFilter(record) && sankeyConditionsMatch(record, spec.data.where));
    const links = spec.links.map((link, index) => ({
      ...link,
      index,
      value: records.reduce((sum, record) =>
        sum + (sankeyConditionsMatch(record, link.where) ? 1 : 0), 0),
    })).filter(link => link.value > 0);
    const activeNodes = new Set(links.flatMap(link => [link.source, link.target]));
    const nodes = spec.nodes.filter(node => activeNodes.has(node.id)).map(node => {
      if (!node.records) return node;
      const incident = links.filter(link => link.source === node.id || link.target === node.id);
      const selection = sankeySelection(spec, incident.map(link => link.where), node.records.where);
      const selected = records.filter(globalThis.obsQuery.compile(selection).match);
      const contributions = incident.filter(link => link.target === node.id && link.unique);
      const unique = new Set(selected.flatMap(record => {
        const fields = contributions.length ? contributions.filter(link =>
          sankeyConditionsMatch(record, link.where)).map(link => link.unique) : [node.unique];
        return fields.flatMap(field => {
          return field ? globalThis.obsQuery.propertyTexts(record, field).filter(item => item !== "") : [];
        });
      })).size;
      const words = sankeyCountLabels(spec);
      return {...node, selection,
        label: `${node.label}\n${selected.length} ${words.unit}\n${unique} ${words.unique}`};
    });
    figure.querySelector(".sankey-canvas").replaceWith(sankeySvg({...spec, nodes}, links));
    figure.dispatchEvent(new CustomEvent("obs-figure-render"));
  }
  function dynamicSankey(figure, spec) {
    const update = () => {
      if (!figure.isConnected) {
        document.removeEventListener("obs-artifact-filter", update);
        return;
      }
      updateDynamicSankey(figure, spec);
    };
    update();
    document.addEventListener("obs-artifact-filter", update);
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
      const spec = JSON.parse(figure.dataset.figureSpec);
      if (spec.data) dynamicSankey(figure, spec);
      else figure.querySelector(".sankey-canvas").replaceWith(
        sankeySvg(spec, spec.links.map((link, index) => ({...link, index}))));
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
      function keepLegendReachable() {
        const legend = chart.querySelector("g.legend");
        if (!legend) return;
        const box = legend.getBoundingClientRect(), bounds = chart.getBoundingClientRect();
        const dx = box.width > bounds.width || box.left < bounds.left ? bounds.left - box.left :
          box.right > bounds.right ? bounds.right - box.right : 0;
        const dy = box.height > bounds.height || box.top < bounds.top ? bounds.top - box.top :
          box.bottom > bounds.bottom ? bounds.bottom - box.bottom : 0;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
        const layout = chart._fullLayout;
        Plotly.relayout(chart, {
          "legend.x": layout.legend.x + dx / layout._size.w,
          "legend.y": layout.legend.y - dy / layout._size.h,
        });
      }
      chart.on("plotly_afterplot", () => {
        legendKeyboard();
        keepLegendReachable();
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
      if (graph === null) projections.delete(sourceNote);
      else {
        if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.links) ||
            !Array.isArray(graph.data?.where)) throw new Error("Invalid projected Sankey.");
        projections.set(sourceNote, structuredClone(graph));
      }
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
        if (spec.data) updateDynamicSankey(figure, spec);
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
