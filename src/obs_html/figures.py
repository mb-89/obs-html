"""The one figure frame and the figure kinds it frames: images, SVG drawings, Sankey diagrams,
stored-data plots, Mermaid and PlantUML diagrams, equation figures and decision figures (the Document's ``figures`` nodes, obs
input-model, Figure input direction).

Reader: whoever changes how a figure is framed or adds a figure kind (artifact-ui.md, One
figure frame).

Every figure is one frame (``frame``): the ``obs-figure`` element with the kind's body, then the
caption with its number; figures.js gives every frame its expansion button and, where its kind
registers options, its options menu, and figures.css's one ``.obs-figure`` rule styles every
frame. A kind is one ``FIGURE_KINDS`` entry: its body renderer, its options and the reader
features it needs (features.py); it never changes the frame.

A plot body draws the two shapes of a FigureDescriptor's ``data``, which the core's
figure.schema.json owns (obs input-model, Figure descriptor): ``traces`` (numeric series on the
descriptor's panels) and ``sankey`` (a graph).
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import math
import re
from functools import cache
from html import escape
from importlib.resources import files
from typing import Callable
from xml.etree import ElementTree

from jsonschema import Draft202012Validator

from .errors import InputError, schema_error
from .figure_links import FigureLink, inline_svg
from .figure_styles import scope_styles
from .sankey import COUNT_LABELS
from .timings import stage as timed


FIGURE = "figure"
"""The field a message names a figure by: the figure fence it comes from."""
REMEDY = "Correct the figure's descriptor; see obs capabilities/figure-descriptor"


def figure_error(source: str, field: str, problem: str, remedy: str = REMEDY) -> InputError:
    """A figure this adapter cannot draw; ``source`` is the note of its figure fence."""
    return InputError(source, f"{FIGURE}.{field}", problem, remedy)


@dataclass(frozen=True)
class Body:
    """What a kind renders inside the frame."""

    html: str
    spec: dict | None = None
    """The runtime's spec of an interactive body (figures.js), on the frame as data-figure-spec."""
    name: str = ""
    """A name the body gives its figure's anchor where it has no block id (a descriptor's id)."""
    presents: str = ""
    """The kind the runtime presents it as, where it differs from the node's (a descriptor's Sankey)."""


@dataclass(frozen=True)
class FigureKind:
    """One figure kind: its body renderer, its options and the reader features it needs."""

    body: Callable[[dict, str, str, dict[str, FigureLink]], Body]
    """The body from the kind's node attrs, the figure's accessible name, its note and the links
    the core resolved in its SVG (figure_links.py), keyed by the link as the SVG holds it."""
    options: tuple[str, ...] = ()
    """The view options of the figure's options menu: keys of figures.js's FIGURE_OPTIONS, whose
    changes are session-only view state. A kind without options shows no menu."""
    features: tuple[str, ...] = ()
    """The keys of the reader features (features.py) a figure of this kind needs."""
    authored: bool = False
    """Its inline drawing is authored content, whose ``<style>`` figure_styles.py scopes to its own
    figure. A diagram's SVG is the core's output, which scopes its styles itself, and is left as drawn."""


def _image_body(attrs: dict, alt: str, _source: str, links: dict[str, FigureLink]) -> Body:
    alt = alt or "Figure"
    if links:
        return Body(inline_svg(base64.b64decode(attrs["data"]).decode("utf-8"), links, alt))
    return Body(f'<img class="figure-visual" src="data:{escape(attrs["mediaType"], quote=True)};base64,'
                f'{attrs["data"]}" alt="{escape(alt, quote=True)}">')


def _svg_body(attrs: dict, alt: str, source: str, links: dict[str, FigureLink]) -> Body:
    """The exact drawing as an image, or inline where it has links; with panels, the runtime's
    panel inspector."""
    markup, alt = attrs["svg"], alt or "Figure"
    if links:
        image = inline_svg(markup, links, alt)
    else:
        uri = "data:image/svg+xml;base64," + base64.b64encode(markup.encode("utf-8")).decode("ascii")
        image = f'<img class="figure-default figure-visual" src="{uri}" alt="{escape(alt, quote=True)}">'
    if "panels" not in attrs:
        return Body(image)
    view_box = ElementTree.fromstring(markup).get("viewBox")
    if not view_box or len(re.split(r"[,\s]+", view_box.strip())) != 4:
        raise InputError(source, f"{FIGURE}.svg", "has panels but its svg element has no viewBox of four "
                         "numbers, which the panel boxes are measured in", "Give the svg element a viewBox")
    return Body(f'{image}<div class="figure-live" aria-label="Interactive figure"></div>',
                {"kind": "svg", "panels": attrs["panels"], "viewBox": view_box, "alt": alt})


def _sankey_body(attrs: dict, alt: str, source: str, _links: dict[str, FigureLink]) -> Body:
    graph, nodes = _sankey_graph(attrs["graph"], source, "graph")
    return _sankey(graph, nodes, alt or "Figure", COUNT_LABELS | attrs.get("countLabels", {}))


def _plot_body(attrs: dict, alt: str, source: str, _links: dict[str, FigureLink]) -> Body:
    descriptor = attrs["descriptor"]
    data, name = descriptor["data"], descriptor["id"]
    if "sankey" in data:
        graph, nodes = _sankey_graph(data["sankey"], source)
        body = _sankey(graph, nodes, alt or name, COUNT_LABELS | data.get("countLabels", {}))
        return Body(body.html, body.spec, name, "sankey")
    if "traces" in data:
        payload = {**_plot(descriptor, source), "kind": "plot", "source": name, "alt": alt or name}
        return Body('<div class="figure-live" aria-label="Interactive figure"></div>', payload, name)
    raise unsupported(source)


def _equations_body(attrs: dict, alt: str, _source: str, _links: dict[str, FigureLink]) -> Body:
    """An equation figure's live plot: the runtime (equations.js) evaluates the Document's body,
    which the core checked against its schema, so the spec is that body as it is."""
    return Body('<div class="figure-live" aria-label="Interactive figure"></div>',
                {"kind": "equations", "alt": alt or "Equation figure", **attrs})


def _pugh_body(attrs: dict, alt: str, _source: str, _links: dict[str, FigureLink]) -> Body:
    """A decision figure: the runtime (pugh-figure.js) decides the Document's matrix, which the core
    checked against its schema, with ctrl's engine; without scripts its title and size stand."""
    matrix = attrs["matrix"]
    summary = (f'{escape(matrix.get("title", "Decision"))}: {len(matrix["candidates"])} options on '
               f'{len(matrix["criteria"])} criteria.')
    return Body(f'<div class="figure-live pugh-figure" aria-label="Decision"><p class="pugh-static">{summary}</p></div>',
                {"kind": "pugh", "alt": alt or "Decision", "matrix": matrix, "shortNames": attrs["shortNames"]})


FIGURE_KINDS: dict[str, FigureKind] = {
    "image": FigureKind(_image_body, authored=True),
    "svg": FigureKind(_svg_body, authored=True),
    # Drawn in the page by its own script (sankey-figure.js), whose counts follow the filter.
    "sankey": FigureKind(_sankey_body, features=("sankey",)),
    "plot": FigureKind(_plot_body, options=("legend",), features=("plotting",)),
    # A diagram's body is the SVG the core drew at build time: no diagram library ships.
    "mermaid": FigureKind(_svg_body),
    "plantuml": FigureKind(_svg_body),
    # Plotted with the plotting library; evaluated and solved with the maths library.
    "equations": FigureKind(_equations_body, options=("legend", "trace", "axis", "swap", "family", "parallel"),
                            features=("plotting", "equations")),
    # Decided in the page with ctrl's engine.
    "pugh": FigureKind(_pugh_body, options=("weights",), features=("pugh",)),
}
"""The figure kinds this adapter renders, by the core's kind (obs src/obs/figure.py, FIGURE_KINDS)."""


def frame(kind: str, body: Body, anchor: str, caption: list[str], number: str = "",
          options: tuple[str, ...] = ()) -> str:
    """The one figure frame of every kind: the body, then the caption with its number.

    ``caption`` holds the caption's paragraphs as phrasing HTML; ``number`` is the figure's
    generated number, shown only before a caption; ``options`` are the view options of the
    figure's options menu, which figures.js builds only where there are some.
    """
    presents = body.presents or kind
    attributes = f' id="{escape(anchor, quote=True)}"'
    if options:
        attributes += f' data-figure-options="{escape(" ".join(options), quote=True)}"'
    number_html = f'<span class="figure-number">{escape(number)}:</span> ' if number and caption else ""
    if number_html:
        attributes += f' data-figure-number="{escape(number, quote=True)}"'
    if body.spec is not None:
        spec = escape(json.dumps(body.spec, separators=(",", ":"), allow_nan=False), quote=True)
        attributes += f' data-engineering-figure data-figure-spec="{spec}"'
    if len(caption) == 1:
        caption_html = f"<figcaption>{number_html}{caption[0]}</figcaption>"
    elif caption:
        caption_html = "<figcaption>" + "".join(
            f"<p>{number_html if index == 0 else ''}{paragraph}</p>" for index, paragraph in enumerate(caption)
        ) + "</figcaption>"
    else:
        caption_html = ""
    return (f'<figure class="obs-figure figure-{presents}" data-artifact-figure data-figure-kind="{presents}"'
            f'{attributes}>{body.html}{caption_html}</figure>\n')


@timed("figures")
def render_figure(node: dict, chapter: str, position: int, caption: list[str], caption_text: str,
                  source: str, number: str = "", links: dict[str, FigureLink] | None = None,
                  answered: dict[str, dict] | None = None) -> str:
    """One figures node in its frame. ``position`` counts the chapter's figures from 1, for an
    anchor where neither a block id nor the body names one; ``caption_text`` is the caption's
    plain text, the accessible name where the figure has no alt; ``links`` are the links the
    core resolved in the figure's SVG, with their chapter hrefs; ``answered`` are the reader's changes an
    answer recorded, by figure anchor, which an interactive body's spec carries (obs input-model, Answers)."""
    attrs = node["attrs"]
    [child] = node["children"]
    kind = FIGURE_KINDS[attrs["kind"]]
    body = kind.body(child["attrs"], attrs.get("alt") or caption_text, source, links or {})  # "" leaves the kind's default.
    if "block" in attrs:
        anchor = f"{chapter}--block-{attrs['block']}"
    else:
        anchor = f"{chapter}--figure-{body.name or position}"
    if kind.authored:
        body = Body(scope_styles(body.html, anchor, source), body.spec, body.name, body.presents)
    if body.spec is not None and anchor in (answered or {}):
        body = Body(body.html, {**body.spec, "answered": answered[anchor]}, body.name, body.presents)
    return frame(attrs["kind"], body, anchor, caption, number, kind.options)


@cache
def _sankey_validator():
    """The core's one Sankey graph shape: figure.schema.json's ``$defs/sankeyGraph``."""
    schema = json.loads(files("obs").joinpath("figure.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator({"$schema": schema["$schema"], "$defs": schema["$defs"],
                                 "$ref": "#/$defs/sankeyGraph"})


def _sankey_graph(graph, source: str, field: str = "data.sankey"):
    """A Sankey graph, checked as this adapter draws it: a sankey figure's ``graph`` or a
    descriptor's ``data.sankey``, against the core's shape, then the rules a schema cannot state.
    obs-document checks the shape and the link ends already; a Document file given to obs-html
    directly arrives unchecked, so this check stays."""
    error = schema_error(list(_sankey_validator().iter_errors(graph)), source,
                         "obs capabilities/figure-descriptor", prefix=f"{FIGURE}.{field}")
    if error is not None:
        raise error
    nodes = graph["nodes"]
    by_id = {}
    for index, node in enumerate(nodes):
        if node["id"] in by_id:
            raise figure_error(source, f"{field}.nodes[{index}].id", f"is {node['id']!r}, the id of an earlier "
                               "node", "Give every node its own id")
        by_id[node["id"]] = node
        if node["stage"] < 0 and node.get("placement") not in {"above", "below"}:
            raise figure_error(source, f"{field}.nodes[{index}].placement", "is missing or flow, but a node "
                               "on a negative stage is a placed sink", "Place it above or below")
    sources = {link["source"] for link in graph["links"]}
    for index, node in enumerate(nodes):
        if "branchSource" in node:
            anchor = by_id.get(node["branchSource"])
            if anchor is None or anchor.get("placement", "flow") != "flow":
                raise figure_error(source, f"{field}.nodes[{index}].branchSource", f"is {node['branchSource']!r}, "
                                   "which is no flow node of the graph", "Name an existing flow node")
    for index, node in enumerate(nodes):
        if node.get("placement") in {"above", "below"} and node["id"] in sources:
            raise figure_error(source, f"{field}.nodes[{index}].placement", f"is {node['placement']!r}, but "
                               "a placed sink has no outgoing links", "Remove its outgoing links or place "
                               "it in the flow")
    for index, link in enumerate(graph["links"]):
        value = link["value"]
        if isinstance(value, bool) or not math.isfinite(value):
            raise figure_error(source, f"{field}.links[{index}].value", f"is {value!r}, not a finite number",
                               "Give the link a finite number")
        source_node = by_id.get(link["source"])
        target_node = by_id.get(link["target"])
        if source_node is None or target_node is None:
            end = "source" if source_node is None else "target"
            raise figure_error(source, f"{field}.links[{index}].{end}", f"is {link[end]!r}, which is no node "
                               "of the graph", "Name an existing node")
        placed_sink = target_node.get("placement") in {"above", "below"}
        if source_node["stage"] >= target_node["stage"] and not placed_sink:
            raise figure_error(source, f"{field}.links[{index}].target", f"is {link['target']!r}, on stage "
                               f"{target_node['stage']}, not after its source's stage {source_node['stage']}",
                               "Link each node to one on a later stage")
    return graph, by_id


def _sankey_number(value):
    return format(value, ".6g")


def _sankey(graph, nodes, alt: str, count_labels) -> Body:
    """A Sankey body: its static drawing and the runtime's spec, which redraws it."""
    spec = {"kind": "sankey", "alt": alt, **graph, "countLabels": count_labels}
    return Body(_render_sankey(graph, nodes, alt, count_labels=count_labels), spec)


def _render_sankey(graph, nodes, accessible_name, *, layout_width=0, count_labels=COUNT_LABELS,
                   standalone_style=None):
    """The Sankey drawing's SVG; with standalone_style, a standalone SVG styled by that CSS."""
    stages = sorted({node["stage"] for node in graph["nodes"]})
    columns = {stage: [] for stage in stages}
    incoming = {node["id"]: 0.0 for node in graph["nodes"]}
    outgoing = {node["id"]: 0.0 for node in graph["nodes"]}
    links_from = {node["id"]: [] for node in graph["nodes"]}
    links_to = {node["id"]: [] for node in graph["nodes"]}
    for node in graph["nodes"]:
        columns[node["stage"]].append(node)
    for link in graph["links"]:
        outgoing[link["source"]] += link["value"]
        incoming[link["target"]] += link["value"]
        links_from[link["source"]].append(link)
        links_to[link["target"]].append(link)
    weights = {
        node["id"]: max(incoming[node["id"]], outgoing[node["id"]])
        for node in graph["nodes"]
    }
    largest_column = max(sum(weights[node["id"]] for node in column) for column in columns.values())
    label_width = max(len(node["label"]) for node in graph["nodes"]) * 7 + 24
    stage_spacing = max(180, label_width)
    width = max(700, 160 + stage_spacing * (len(stages) - 1))
    tallest_column = max(len(column) for column in columns.values())
    above = max(sum(node.get("placement") == "above" for node in column) for column in columns.values())
    below = max(sum(node.get("placement") == "below" for node in column) for column in columns.values())
    height = max(680, 120 + tallest_column * 24) + (above + below) * 60
    left, right = 80, width - 80
    def stage_x(index):
        return (left + right) / 2 if len(stages) == 1 else left + (right - left) * index / (len(stages) - 1)

    top, bottom = 52 + above * 60, height - 52 - below * 60
    available = bottom - top
    node_gap = 12
    min_node_height = 10
    high = available / max(largest_column, 1)

    def column_height(column, scale):
        flow = [node for node in column if node.get("placement", "flow") == "flow"]
        return sum(max(min_node_height, weights[node["id"]] * scale) for node in flow) + node_gap * (len(flow) - 1)

    low = 0.0
    for _ in range(64):
        scale = (low + high) / 2
        if any(column_height(column, scale) > available for column in columns.values()):
            high = scale
        else:
            low = scale
    scale = low
    positions = {}
    for index, stage in enumerate(stages):
        x = stage_x(index)
        column = columns[stage]
        used = column_height(column, scale)
        y = top + (available - used) / 2
        rails = {"above": 0, "below": 0}
        for node in column:
            placement = node.get("placement", "flow")
            if placement in rails:
                rail = rails[placement]
                rails[placement] += 1
                bar_width = max(40, min(120, 40 + max(0, weights[node["id"]] - 1) * 0.9))
                source_stages = [nodes[link["source"]]["stage"] for link in links_to[node["id"]]]
                source_x = stage_x(stages.index(max(source_stages))) if source_stages else x
                positions[node["id"]] = {
                    "x": (source_x + x) / 2 - bar_width / 2,
                    "y": 52 + rail * 60 if placement == "above" else bottom + 40 + rail * 60,
                    "height": 8, "width": bar_width, "horizontal": True,
                }
                continue
            node_height = max(min_node_height, weights[node["id"]] * scale)
            positions[node["id"]] = {"x": x, "y": y, "height": node_height, "width": 18}
            y += node_height + node_gap

    link_centers = {}
    for node_id, links in links_from.items():
        position = positions[node_id]
        total = outgoing[node_id] * scale
        y = position["y"] + (position["height"] - total) / 2
        for link in links:
            thickness = link["value"] * scale
            link_centers[id(link)] = (y + thickness / 2, None)
            y += thickness
    for node_id, links in links_to.items():
        position = positions[node_id]
        total = incoming[node_id] * scale
        y = position["y"] + (position["height"] - total) / 2
        for link in links:
            thickness = link["value"] * scale
            source_y, _ = link_centers[id(link)]
            link_centers[id(link)] = (source_y, y + thickness / 2)
            y += thickness

    incoming_series = {
        (link["series"], link["target"]): link
        for link in graph["links"] if "series" in link
    }
    for link in graph["links"]:
        incoming_link = incoming_series.get((link.get("series"), link["source"]))
        if incoming_link is not None:
            _, end_y = link_centers[id(link)]
            link_centers[id(link)] = (link_centers[id(incoming_link)][1], end_y)
    if graph.get("branchLayout") == "split":
        from .sankey import split_layout
        width, height, scale, positions, centers = split_layout(
            graph, minimum_width=layout_width, count_labels=count_labels,
        )
        link_centers = {id(link): center for link, center in zip(graph["links"], centers)}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="sankey-canvas" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(accessible_name, quote=True)}" style="--sankey-width:{width}px">'
        f'<title>{escape(accessible_name)}</title>'
    ]
    if standalone_style is not None:
        parts.append(f"<style>{standalone_style}</style>")
    for link in graph["links"]:
        source_node, target_node = nodes[link["source"]], nodes[link["target"]]
        start_y, end_y = link_centers[id(link)]
        source_position = positions[link["source"]]
        target_position = positions[link["target"]]
        start_x = source_position["x"] + source_position["width"]
        end_x = target_position["x"]
        if target_position.get("horizontal"):
            fraction = max(0, min(1, (start_y - source_position["y"]) / max(1, source_position["height"])))
            reverse = (graph.get("branchLayout") == "split" and
                       (target_position["x"] + target_position["width"] / 2 - start_x) *
                       (target_position["y"] + 4 - source_position["y"] - source_position["height"] / 2) > 0)
            end_x += (1 - fraction if reverse else fraction) * target_position["width"]
            end_y = target_position["y"] + target_position["height"] / 2
        control = (end_x - start_x) * (0.5 if graph.get("branchLayout") == "split" else 0.45)
        path = (
            f"M {_sankey_number(start_x)} {_sankey_number(start_y)} "
            f"C {_sankey_number((start_x + end_x) / 2)} {_sankey_number(start_y)}, "
            f"{_sankey_number(end_x)} {_sankey_number((start_y + end_y) / 2)}, "
            f"{_sankey_number(end_x)} {_sankey_number(end_y)}"
        ) if target_position.get("horizontal") else _path(start_x, start_y, end_x, end_y, control)
        color = link.get("color") or source_node.get("color") or target_node.get("color") or "#73869a"
        label = link.get("label") or _sankey_number(link["value"])
        description = f'{source_node["label"]} → {target_node["label"]}: {label} ({_sankey_number(link["value"])})'
        thickness = link["value"] * scale
        series = f' data-series="{escape(link["series"], quote=True)}"' if "series" in link else ""
        dash = ' stroke-dasharray="10 10"' if link.get("originColor") else ""
        parts.append(
            f'<path class="sankey-link"{series} data-flow-value="{_sankey_number(link["value"])}" '
            f'd="{path}" fill="none" '
            f'stroke="{color}"{dash} stroke-opacity=".48" stroke-width="{_sankey_number(thickness)}">'
            f'<title>{escape(description)}</title></path>'
        )
        if link.get("originColor"):
            parts.append(
                f'<path class="sankey-origin"{series} d="{path}" '
                f'fill="none" stroke="{link["originColor"]}" stroke-opacity=".48" '
                f'stroke-width="{_sankey_number(thickness)}" stroke-dasharray="10 10" stroke-dashoffset="10"/>'
            )
        if thickness >= 24:
            parts.append(
                f'<text class="sankey-link-label" x="{_sankey_number((start_x + end_x) / 2)}" '
                f'y="{_sankey_number((start_y + end_y) / 2 + 4)}" text-anchor="middle">'
                f'{escape(label)}</text>'
            )
    for node in graph["nodes"]:
        position = positions[node["id"]]
        node_x, node_y = position["x"], position["y"]
        node_height = position["height"]
        color = node.get("color", "#587894")
        label_x = position.get("labelX", node_x + position["width"] / 2)
        lower = not position["upper"] if position.get("horizontal") and graph.get("branchLayout") == "split" else node.get("placement") == "below"
        lines = node["label"].split("\n")
        label_y = position.get("labelY", node_y + 22 if lower else node_y - 7 - (len(lines) - 1) * 14)
        label_html = escape(node["label"])
        if graph.get("branchLayout") == "split":
            label_html = ""
            for index, line in enumerate(lines):
                label_html += (f'<tspan x="{_sankey_number(label_x)}" dy="{"1.15em" if index else "0"}">'
                               f'{escape(line)}</tspan>')
        total_in = _sankey_number(incoming[node["id"]])
        total_out = _sankey_number(outgoing[node["id"]])
        parts.append(
            f'<g class="sankey-node" data-node-id="{escape(node["id"], quote=True)}">'
            f'<rect x="{_sankey_number(node_x)}" y="{_sankey_number(node_y)}" width="{_sankey_number(position["width"])}" '
            f'height="{_sankey_number(node_height)}" rx="2" fill="{color}">'
            f'<title>{escape(node["label"])}; incoming {total_in}, outgoing {total_out}</title></rect>'
            f'<text x="{_sankey_number(label_x)}" y="{_sankey_number(label_y)}" '
            f'text-anchor="{position.get("labelAnchor", "middle")}" class="sankey-label">{label_html}'
            f'<title>{escape(node["label"])}</title></text></g>'
        )
    parts.append("</svg>")
    return "".join(parts) + ("\n" if standalone_style is not None else "")


def _path(start_x, start_y, end_x, end_y, control):
    return (
        f"M {_sankey_number(start_x)} {_sankey_number(start_y)} "
        f"C {_sankey_number(start_x + control)} {_sankey_number(start_y)}, "
        f"{_sankey_number(end_x - control)} {_sankey_number(end_y)}, "
        f"{_sankey_number(end_x)} {_sankey_number(end_y)}"
    )


def unsupported(source: str) -> InputError:
    return figure_error(source, "data", "carries neither 'sankey' nor 'traces'",
                        "Give the descriptor's data one of the two shapes obs-html draws")


def sankey_svg(descriptor: dict, style: str, source: str) -> str:
    """The Sankey descriptor's static drawing as a standalone SVG document styled by ``style``."""
    data = descriptor["data"]
    graph, nodes = _sankey_graph(data["sankey"], source)
    return _render_sankey(graph, nodes, descriptor["id"],
                          count_labels=COUNT_LABELS | data.get("countLabels", {}), standalone_style=style)


def _plot(descriptor: dict, source: str) -> dict:
    """Plotly data and layout: one x/y axis pair per panel, placed by the panel grid."""
    panels = descriptor["panels"]
    rows = max(panel["grid"]["row"] + panel["grid"]["rowSpan"] for panel in panels)
    columns = max(panel["grid"]["column"] + panel["grid"]["columnSpan"] for panel in panels)
    layout: dict[str, object] = {}
    axes: dict[str, tuple[str, str]] = {}
    for index, panel in enumerate(panels, start=1):
        panel_axes(descriptor, panel, source)
        suffix = "" if index == 1 else str(index)
        grid = panel["grid"]
        domains = {
            "x": [grid["column"] / columns, (grid["column"] + grid["columnSpan"]) / columns],
            "y": [1 - (grid["row"] + grid["rowSpan"]) / rows, 1 - grid["row"] / rows],
        }
        for letter, axis in zip("xy", panel["axes"]):
            limits = axis["limits"]
            log = axis["scale"] == "log"
            layout[f"{letter}axis{suffix}"] = {
                "title": {"text": axis["label"]}, "type": "log" if log else "linear",
                "range": [math.log10(limits["minimum"]), math.log10(limits["maximum"])] if log
                else [limits["minimum"], limits["maximum"]],
                "domain": domains[letter],
                **({"anchor": f"{'y' if letter == 'x' else 'x'}{suffix}"} if suffix else {}),
            }
        axes[panel["id"]] = (f"x{suffix}", f"y{suffix}")
    data = []
    for trace in checked_traces(descriptor, source):
        panel, x, y = trace.get("panel", panels[0]["id"]), trace["x"], trace["y"]
        data.append({
            "x": x, "y": y, "type": "scatter", "mode": trace.get("mode", "lines"),
            "name": str(trace.get("label", "")), "xaxis": axes[panel][0], "yaxis": axes[panel][1],
            "showlegend": bool(trace.get("label")),
            **({"line": {"color": trace["color"]}, "marker": {"color": trace["color"]}}
               if "color" in trace else {}),
        })
    return {"data": data, "layout": layout}


def panel_field(descriptor: dict, panel: dict) -> str:
    return f"panels[{descriptor['panels'].index(panel)}]"


def panel_axes(descriptor: dict, panel: dict, source: str) -> tuple[dict, dict]:
    """A trace panel's x and y axis, checked as this adapter draws them."""
    field = panel_field(descriptor, panel)
    if len(panel["axes"]) != 2:
        raise figure_error(source, f"{field}.axes", f"has {len(panel['axes'])} axes, but a trace panel has "
                           "an x and a y axis", "Give the panel exactly two axes, x first")
    for index, axis in enumerate(panel["axes"]):
        limits = axis["limits"]
        if axis["scale"] == "log" and (limits["minimum"] <= 0 or limits["maximum"] <= 0):
            raise figure_error(source, f"{field}.axes[{index}].limits", "are not both positive, but the axis "
                               "is logarithmic", "Give a log axis positive limits")
    return panel["axes"][0], panel["axes"][1]


def checked_traces(descriptor: dict, source: str) -> list[dict]:
    """The descriptor's ``data.traces``, each on a known panel with equally long finite x and y."""
    traces = descriptor["data"]["traces"]
    if not isinstance(traces, list) or not 1 <= len(traces) <= 64:
        raise figure_error(source, "data.traces", "is not a list of 1 to 64 series",
                           "Give the figure 1 to 64 traces")
    panels = {panel["id"] for panel in descriptor["panels"]}
    for index, trace in enumerate(traces):
        panel = trace.get("panel", descriptor["panels"][0]["id"])
        if panel not in panels:
            raise figure_error(source, f"data.traces[{index}].panel", f"is {panel!r}, which is no panel of the "
                               "descriptor", "Name one of its panels")
        x, y = trace.get("x"), trace.get("y")
        if (not isinstance(x, list) or not isinstance(y, list) or len(x) != len(y) or not x
                or not all(_finite(value) for value in x + y)):
            raise figure_error(source, f"data.traces[{index}]", "needs x and y lists of equal, nonzero length "
                               "with finite numbers", "Give the trace such x and y lists")
    return traces


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
