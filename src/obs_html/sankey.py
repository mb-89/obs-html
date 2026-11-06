"""Split branch geometry, ported from a prior renderer and d3-sankey 0.12.3.

The fixed-sort breadth relaxation below derives from d3-sankey/src/sankey.js:
Copyright 2015, Mike Bostock
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:
* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.
* Neither the name of the author nor the names of contributors may be used to
  endorse or promote products derived from this software without specific prior
  written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import math
import re


def _text_length(value):
    return len(value.encode("utf-16-le", "surrogatepass")) // 2


COUNT_LABELS = {"unit": "records", "unique": "unique"}


def _label_size(node, count_labels=COUNT_LABELS):
    lines = node["label"].split("\n")
    unit, unique = count_labels["unit"], count_labels["unique"]
    if node.get("records") and not (
            len(lines) >= 3 and re.fullmatch(rf"[0-9]+ {re.escape(unit)}", lines[-2])
            and re.fullmatch(rf"[0-9]+ {re.escape(unique)}", lines[-1])):
        count = math.ceil(node["value"])
        lines += [f"{count} {unit}", f"{count} {unique}"]

    def width(line):
        # Conservative 12px glyph bounds keep static/browser geometry portable.
        total = 0
        for character in line:
            if character == " ":
                total += 4
            elif character in "iljtfIr":
                total += 6
            elif character in "mwMW%@&#":
                total += 12
            elif "A" <= character <= "Z":
                total += 9
            elif ord(character) < 128:
                total += 8
            else:
                total += 12 * _text_length(character)
        return total
    return max(map(width, lines)) + 8, len(lines) * 14 + 4, len(lines)


def split_layout(graph, *, details=None, minimum_width=0, count_labels=COUNT_LABELS):
    """Return portable geometry; figures.js carries the browser implementation."""
    nodes = [dict(node, sourceLinks=[], targetLinks=[]) for node in graph["nodes"]]
    by_id = {node["id"]: node for node in nodes}
    links = [dict(link, source=by_id[link["source"]], target=by_id[link["target"]])
             for link in graph["links"]]
    for link in links:
        link["source"]["sourceLinks"].append(link)
        link["target"]["targetLinks"].append(link)
    for node in nodes:
        for side in ("sourceLinks", "targetLinks"):
            node[side].sort(key=lambda link: link.get("order", 0))
        node["value"] = max(sum(link["value"] for link in node["sourceLinks"]),
                            sum(link["value"] for link in node["targetLinks"]))
    stages = sorted({node["stage"] for node in nodes})
    current = nodes
    depth = 0
    while current:
        following = {}
        for node in current:
            node["depth"] = depth
            for link in node["sourceLinks"]:
                following[link["target"]["id"]] = link["target"]
        depth += 1  # The graph has no cycle: every link moves to a later stage or to a placed sink.
        current = list(following.values())
    count = max(max(node["depth"] for node in nodes) + 1, stages[-1] - stages[0] + 1)
    labels = {node["id"]: _label_size(node, count_labels) for node in nodes}
    flow = [node for node in nodes if node.get("placement", "flow") == "flow"]
    flow_width = max((labels[node["id"]][0] for node in flow), default=0)
    flow_height = max((labels[node["id"]][1] for node in flow), default=0)
    branch_height = max((labels[node["id"]][1] for node in nodes
                         if node.get("placement") in ("above", "below")), default=0)
    groups = {}
    for node in nodes:
        if node.get("placement") not in ("above", "below"):
            continue
        sources = node["targetLinks"]
        source = by_id.get(node.get("branchSource")) or (sources[-1]["source"] if sources else node)
        destination_stage = source["stage"] + (-1 if node["placement"] == "above" else 1)
        destination = next((other for other in flow if other["stage"] == destination_stage), None)
        bar_width = 40 + max(0, node["value"] - 1) * .9
        key = tuple(sorted((source["stage"], destination_stage)))
        groups.setdefault(key, []).append(dict(node=node, source=source, destination=destination,
            barWidth=bar_width, footprint=max(bar_width, labels[node["id"]][0])))
    left = right_margin = 48
    spacing = max(180, flow_width * 2 + 46)
    packed = []
    for group in groups.values():
        lanes, loads = [[], []], [0, 0]
        for index, entry in enumerate(sorted(group, key=lambda entry: (
                -entry["barWidth"], entry["node"].get("branchOrder", 0),
                entry["node"]["id"].encode("utf-16-be", "surrogatepass")))):
            lane = index if index < 2 else 0 if loads[0] <= loads[1] else 1
            lanes[lane].append(entry)
            loads[lane] += entry["barWidth"] + 12
        required = max(sum(entry["footprint"] for entry in lane) + max(0, len(lane) - 1) * 12
                       for lane in lanes) + 48
        spacing = max(spacing, required)
        for entry in group:
            if entry["destination"] is None:
                if entry["node"]["placement"] == "above":
                    left = max(left, required)
                else:
                    right_margin = max(right_margin, required)
        packed.append(lanes)
    width = math.ceil(max(700, minimum_width,
                         left + right_margin + 14 + max(0, count - 1) * spacing))
    right = width - right_margin
    columns_size = {}
    for node in nodes:
        layer = min(count - 1, max(0, node["stage"] - stages[0]))
        columns_size[layer] = columns_size.get(layer, 0) + 1
    padding = max(18, flow_height + 18)
    largest = max(columns_size.values())
    available = max(340 + (largest - 1) * (padding - 18),
                    (largest - 1) * padding + flow_height + 140)
    upper_y = 12 + branch_height + 12 + 4
    top = upper_y + 4 + 18 + flow_height / 2
    bottom = top + available
    lower_y = bottom + flow_height / 2 + 18 + 4
    height = math.ceil(lower_y + 4 + 12 + branch_height + 12)
    if details is not None:
        details.update(left=left, right=right, top=top, bottom=bottom, padding=padding)
    columns = [[] for _ in range(count)]
    for node in nodes:
        layer = min(count - 1, max(0, node["stage"] - stages[0]))
        node["layer"] = layer
        node["x0"] = ((left + right - 14) / 2 if len(stages) == 1
                      else left + layer * (right - left - 14) / max(1, count - 1))
        node["x1"] = node["x0"] + 14
        columns[layer].append(node)
    for column in columns:
        column.sort(key=lambda node: node.get("order", 0))
    populated = [column for column in columns if column]
    scale = min((bottom - top - (len(column) - 1) * padding) /
                sum(node["value"] for node in column)
                for column in populated if any(node["value"] for node in column))
    for column in populated:
        y = top
        for node in column:
            node["y0"] = y
            node["y1"] = y + node["value"] * scale
            y = node["y1"] + padding
            for link in node["sourceLinks"]:
                link["width"] = link["value"] * scale
        extra = (bottom - y + padding) / (len(column) + 1)
        for index, node in enumerate(column):
            node["y0"] += extra * (index + 1)
            node["y1"] += extra * (index + 1)

    def ideal(source, target, forward):
        a, b = (source, target) if forward else (target, source)
        outgoing, incoming = (("sourceLinks", "targetLinks") if forward
                              else ("targetLinks", "sourceLinks"))
        endpoint = "target" if forward else "source"
        y = a["y0"] - (len(a[outgoing]) - 1) * padding / 2
        for link in a[outgoing]:
            if link[endpoint] is b:
                break
            y += link["width"] + padding
        for link in b[incoming]:
            if link["source" if forward else "target"] is a:
                break
            y -= link["width"]
        return y

    def shift(node, delta):
        node["y0"] += delta
        node["y1"] += delta

    def collide(column, beta):
        if not column:
            return

        def push(y, indices, down):
            for index in indices:
                node = column[index]
                delta = ((y - node["y0"]) if down else (node["y1"] - y)) * beta
                if delta > 1e-6:
                    shift(node, delta if down else -delta)
                y = node["y1"] + padding if down else node["y0"] - padding
        middle = len(column) // 2
        push(column[middle]["y0"] - padding, range(middle - 1, -1, -1), False)
        push(column[middle]["y1"] + padding, range(middle + 1, len(column)), True)
        push(bottom, range(len(column) - 1, -1, -1), False)
        push(top, range(len(column)), True)

    for iteration in range(6):
        alpha = .99 ** iteration
        beta = max(1 - alpha, (iteration + 1) / 6)
        for forward in (False, True):
            indices = range(1, count) if forward else range(count - 2, -1, -1)
            for index in indices:
                column = columns[index]
                for node in column:
                    y = total = 0
                    for link in node["targetLinks" if forward else "sourceLinks"]:
                        source, target = link["source"], link["target"]
                        value = link["value"] * (target["layer"] - source["layer"])
                        y += ideal(source, target, forward) * value
                        total += value
                    if total > 0:
                        shift(node, (y / total - node["y0"]) * alpha)
                collide(column, beta)
    for node in nodes:
        for side, endpoint in (("sourceLinks", "y0"), ("targetLinks", "y1")):
            y = node["y0"]
            for link in node[side]:
                link[endpoint] = y + link["width"] / 2
                y += link["width"]
    incoming = {(link["series"], link["target"]["id"]): link for link in links if link.get("series")}
    for link in links:
        previous = incoming.get((link.get("series"), link["source"]["id"]))
        if previous is not None:
            link["y0"] = previous["y1"]
    positions = {node["id"]: dict(x=node["x0"], y=node["y0"],
                                 width=14, height=node["y1"] - node["y0"])
                 for node in nodes}
    for node in flow:
        p = positions[node["id"]]
        end = p["x"] > width / 2
        p.update(labelX=p["x"] - 7 if end else p["x"] + p["width"] + 7,
                 labelY=p["y"] + p["height"] / 2 - (labels[node["id"]][2] - 1) * 7 + 4,
                 labelAnchor="end" if end else "start")
    for lanes in packed:
        for index, lane in enumerate(lanes):
            if not lane:
                continue
            for entry in lane:
                source, destination = entry["source"], entry["destination"]
                source_x = (source["x0"] + source["x1"]) / 2
                destination_x = ((destination["x0"] + destination["x1"]) / 2 if destination
                                 else 8 if entry["node"]["placement"] == "above" else width - 8)
                entry.update(left=min(source_x, destination_x) + 24, right=max(source_x, destination_x) - 24)
            left = min(entry["left"] for entry in lane)
            right = max(entry["right"] for entry in lane)
            available = right - left
            desired = sum(entry["footprint"] for entry in lane) + 12 * (len(lane) - 1)
            cursor = left + (available - desired) / 2
            for entry in lane:
                footprint, bar_width = entry["footprint"], entry["barWidth"]
                y = upper_y if index == 0 else lower_y
                lines = labels[entry["node"]["id"]][2]
                positions[entry["node"]["id"]] = dict(x=cursor + (footprint - bar_width) / 2,
                    y=y - 4, width=bar_width, height=8, horizontal=True, upper=index == 0,
                    labelX=cursor + footprint / 2, labelAnchor="middle",
                    labelY=y - 19 - (lines - 1) * 14 if index == 0 else y + 27)
                cursor += footprint + 12
    return width, height, scale, positions, [(link["y0"], link["y1"]) for link in links]
