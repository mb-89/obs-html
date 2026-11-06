(() => {
  // The Sankey figure kind's drawing (figures.py, FIGURE_KINDS; artifact-ui.md, Interactive engineering figures): a static
  // graph, or one whose counts follow the reader's filter. It ships only with a Sankey figure
  // (features.py, sankey); figures.js frames, expands and fits what it draws.
  const sankeyFrames = new WeakMap();
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
  globalThis.obsSankey = {
    render(figure, spec) {
      if (spec.data) dynamicSankey(figure, spec);
      else figure.querySelector(".sankey-canvas").replaceWith(
        sankeySvg(spec, spec.links.map((link, index) => ({...link, index}))));
    },
    update: updateDynamicSankey,
    // The layout a drawn Sankey refits to its frame (figures.js, overlayControls).
    frame: visual => sankeyFrames.get(visual),
    project(sourceNote, graph) {
      if (graph === null) projections.delete(sourceNote);
      else projections.set(sourceNote, graph);
    },
  };
})();
