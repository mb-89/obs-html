"""Byte-stable standalone SVG files from the Document's FigureDescriptors.

The same descriptor always gives the same bytes: the drawing follows the descriptor's lists in
order, never a dict's or set's order, formats every number one way, derives every id from the
descriptor's own ids and carries no time or random value. ``traces`` descriptors are drawn
here as static plots on their panels' bounds and axes; ``sankey`` descriptors reuse the artifact's
static Sankey drawing.
"""
from __future__ import annotations

import math
from html import escape
from typing import Iterator

from .figures import checked_traces, figure_error, panel_axes, panel_field, sankey_svg, unsupported

STYLE = ("text{font:12px sans-serif;fill:#1f2933}.figure-tick{font-size:11px;fill:#52606d}"
         ".sankey-label,.sankey-link-label{font:12px sans-serif;fill:#1f2933}")
# Plotly's default colorway, so a static export colours traces as the interactive artifact does.
COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
          "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf")
MARGIN = {"left": 64, "right": 16, "top": 16, "bottom": 48}
HOME = "home"


def document_figures(document: dict) -> Iterator[tuple[str, dict, str]]:
    """Each FigureDescriptor in Document order, named like its anchor in the HTML artifact, with
    the note of its figure fence (as an error names it)."""
    paths = {record["id"]: record["path"] for record in document["records"] if record["type"] == "note"}

    def walk(nodes: list[dict], chapter: str, source: str) -> Iterator[tuple[str, dict, str]]:
        for node in nodes:
            if node["type"] == "figure-descriptor":
                descriptor = node["attrs"]["descriptor"]
                yield f"{chapter}--figure-{descriptor['id']}", descriptor, source
            yield from walk(node.get("children", []), chapter, source)

    yield from walk(document["manifest"]["abstract"], HOME, document["manifest"]["path"])
    stack = list(reversed(document["chapters"]))
    while stack:
        chapter = stack.pop()
        yield from walk(chapter["content"], chapter["id"], paths.get(chapter["id"], f"chapter {chapter['id']}"))
        stack.extend(reversed(chapter["children"]))


def figure_svg(descriptor: dict, source: str) -> str:
    """One FigureDescriptor as a standalone SVG document; ``source`` is the note of its fence."""
    data = descriptor["data"]
    if "sankey" in data:
        return sankey_svg(descriptor, STYLE, source)
    if "traces" in data:
        return _plot_svg(descriptor, source)
    raise unsupported(source)


def _number(value: float) -> str:
    text = format(float(value), ".6g")
    return "0" if text == "-0" else text


def _plot_svg(descriptor: dict, source: str) -> str:
    name = descriptor["id"]
    panels = descriptor["panels"]
    traces = checked_traces(descriptor, source)
    width = max(panel["bounds"]["x"] + panel["bounds"]["width"] for panel in panels)
    height = max(panel["bounds"]["y"] + panel["bounds"]["height"] for panel in panels)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_number(width)}" height="{_number(height)}" '
        f'viewBox="0 0 {_number(width)} {_number(height)}" role="img" aria-label="{escape(name, quote=True)}">'
        f"<title>{escape(name)}</title><style>{STYLE}</style>"
        f'<rect width="{_number(width)}" height="{_number(height)}" fill="#ffffff"/>'
    ]
    for panel in panels:
        on_panel = [(index, trace) for index, trace in enumerate(traces)
                    if trace.get("panel", panels[0]["id"]) == panel["id"]]
        parts.append(_panel(descriptor, panel, on_panel, source))
    parts.append("</svg>\n")
    return "".join(parts)


class _Scale:
    """Maps an axis's values onto a pixel range, linearly or in decades."""

    def __init__(self, axis: dict, field: str, start: float, end: float, source: str) -> None:
        self.log = axis["scale"] == "log"
        self.low, self.high = axis["limits"]["minimum"], axis["limits"]["maximum"]
        if self.low == self.high:
            raise figure_error(source, f"{field}.limits", "have a minimum equal to their maximum",
                               "Widen the axis's limits")
        self.start, self.end = start, end

    def _t(self, value: float) -> float:
        return math.log10(value) if self.log else value

    def drawable(self, value: float) -> bool:
        return value > 0 if self.log else True

    def __call__(self, value: float) -> float:
        fraction = (self._t(value) - self._t(self.low)) / (self._t(self.high) - self._t(self.low))
        return self.start + (self.end - self.start) * fraction

    def ticks(self) -> list[float]:
        low, high = sorted((self.low, self.high))
        if self.log:
            first, last = math.ceil(math.log10(low) - 1e-9), math.floor(math.log10(high) + 1e-9)
            ticks = [10.0 ** power for power in range(first, last + 1)]
            return ticks if len(ticks) >= 2 else [low, high]
        raw = (high - low) / 5
        magnitude = 10.0 ** math.floor(math.log10(raw))
        step = next(factor * magnitude for factor in (1, 2, 5, 10) if factor * magnitude >= raw)
        first, last = math.ceil(low / step - 1e-9), math.floor(high / step + 1e-9)
        return [index * step for index in range(first, last + 1)]


def _panel(descriptor: dict, panel: dict, traces: list[tuple[int, dict]], source: str) -> str:
    x_axis, y_axis = panel_axes(descriptor, panel, source)
    field = panel_field(descriptor, panel)
    bounds = panel["bounds"]
    left, right = bounds["x"] + MARGIN["left"], bounds["x"] + bounds["width"] - MARGIN["right"]
    top, bottom = bounds["y"] + MARGIN["top"], bounds["y"] + bounds["height"] - MARGIN["bottom"]
    if right <= left or bottom <= top:
        raise figure_error(source, f"{field}.bounds", "are too small to draw the panel",
                           f"Give its bounds at least {MARGIN['left'] + MARGIN['right'] + 1} by "
                           f"{MARGIN['top'] + MARGIN['bottom'] + 1}")
    x, y = (_Scale(x_axis, f"{field}.axes[0]", left, right, source),
            _Scale(y_axis, f"{field}.axes[1]", bottom, top, source))
    clip = f"{descriptor['id']}-{panel['id']}-plot"
    n = _number
    parts = [
        f'<g class="figure-panel" data-panel="{panel["id"]}">'
        f'<clipPath id="{clip}"><rect x="{n(left)}" y="{n(top)}" width="{n(right - left)}" '
        f'height="{n(bottom - top)}"/></clipPath>'
    ]
    for value in x.ticks():
        position = n(x(value))
        parts.append(
            f'<line x1="{position}" y1="{n(top)}" x2="{position}" y2="{n(bottom)}" stroke="#e4e7eb"/>'
            f'<text class="figure-tick" x="{position}" y="{n(bottom + 16)}" text-anchor="middle">'
            f"{n(value)}</text>")
    for value in y.ticks():
        position = n(y(value))
        parts.append(
            f'<line x1="{n(left)}" y1="{position}" x2="{n(right)}" y2="{position}" stroke="#e4e7eb"/>'
            f'<text class="figure-tick" x="{n(left - 6)}" y="{n(y(value) + 4)}" text-anchor="end">'
            f"{n(value)}</text>")
    parts.append(
        f'<rect x="{n(left)}" y="{n(top)}" width="{n(right - left)}" height="{n(bottom - top)}" '
        f'fill="none" stroke="#9aa5b1"/>'
        f'<text x="{n((left + right) / 2)}" y="{n(bottom + 38)}" text-anchor="middle">'
        f'{escape(x_axis["label"])}</text>'
        f'<text x="{n(bounds["x"] + 16)}" y="{n((top + bottom) / 2)}" text-anchor="middle" '
        f'transform="rotate(-90 {n(bounds["x"] + 16)} {n((top + bottom) / 2)})">'
        f'{escape(y_axis["label"])}</text>'
        f'<g clip-path="url(#{clip})">')
    for index, trace in traces:
        color = escape(str(trace.get("color", COLORS[index % len(COLORS)])), quote=True)
        mode = trace.get("mode", "lines")
        points = [(x(px), y(py)) for px, py in zip(trace["x"], trace["y"])
                  if x.drawable(px) and y.drawable(py)]
        if "lines" in mode and len(points) > 1:
            parts.append(
                f'<polyline points="{" ".join(f"{n(px)},{n(py)}" for px, py in points)}" '
                f'fill="none" stroke="{color}" stroke-width="2"/>')
        if "markers" in mode:
            parts.extend(f'<circle cx="{n(px)}" cy="{n(py)}" r="3" fill="{color}"/>' for px, py in points)
    parts.append("</g>")
    labelled = [(index, trace) for index, trace in traces if trace.get("label")]
    for row, (index, trace) in enumerate(labelled):
        color = escape(str(trace.get("color", COLORS[index % len(COLORS)])), quote=True)
        line_y = top + 14 + row * 18
        parts.append(
            f'<line x1="{n(right - 120)}" y1="{n(line_y)}" x2="{n(right - 100)}" y2="{n(line_y)}" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="{n(right - 94)}" y="{n(line_y + 4)}">{escape(str(trace["label"]))}</text>')
    parts.append("</g>")
    return "".join(parts)
