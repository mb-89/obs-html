"""A figure's SVG shown inline, so that the links the core resolved in it can be followed.

Reader: whoever changes how a link inside a figure is shown (artifact-ui.md, Links inside a
figure; obs capabilities/wikilinks, Links inside a figure).

An image cannot be clicked into, so a figure whose body has links shows its SVG inline. The
inline SVG is never executable: every element that runs or loads content (``script``,
``foreignObject``, embedded documents, event elements and the animation elements that could
rewrite a link), every event-handler attribute and every link that is neither a resolved note
link, a fragment of the drawing, a web or mail address nor a data image are removed. Each link
the core resolved (its ``svg`` attribute names it as the SVG holds it) becomes the same chapter
link as in prose; one whose note is missing loses its target, and its wikilink text shows its
label unlinked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree import ElementTree

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
HREFS = ("href", f"{{{XLINK}}}href")
DROPPED = frozenset({"script", "foreignObject", "iframe", "embed", "object", "handler", "listener",
                     "set", "animate", "animateMotion", "animateTransform", "discard"})
"""Elements that run or load content, or can change a link's target while the drawing shows."""
TEXTLESS = frozenset({"style", "title", "desc", "metadata"})
"""Elements whose text is not drawn, so no wikilink text in them becomes a link."""
SAFE_HREF = re.compile(r"^(?:#|https?:|mailto:|data:image/)", re.IGNORECASE)
"""A target the inline SVG keeps as authored: a fragment of the drawing, a web or mail address
or a data image."""
INTERNAL = "internal-link"
"""The class of a chapter link, as in prose (render.py, _internal_link)."""

# The inline SVG's own namespace is the default one; ElementTree's default_namespace option
# refuses the unqualified attribute names every SVG has.
ElementTree.register_namespace("", SVG)
ElementTree.register_namespace("xlink", XLINK)


@dataclass(frozen=True)
class FigureLink:
    """A link the core resolved in a figure: the chapter href it navigates to, or None for a
    missing note, and the label its wikilink text shows."""

    href: str | None
    label: str


def _local(name: str) -> str:
    return name.rpartition("}")[2]


def inline_svg(markup: str, links: dict[str, FigureLink], label: str) -> str:
    """The SVG as inline markup, made non-executable, with ``links`` (keyed by the link as the
    SVG holds it) rewritten; ``label`` is the figure's accessible name."""
    root = ElementTree.fromstring(markup)
    _sanitize(root, links)
    texts = [written for written in links if written.startswith("[[")]
    if texts:
        _link_text(root, texts, links)
    root.set("class", " ".join(filter(None, (root.get("class"), "figure-default figure-visual"))))
    root.set("role", "group")
    root.set("aria-label", label)
    return ElementTree.tostring(root, encoding="unicode")


def _sanitize(element: ElementTree.Element, links: dict[str, FigureLink]) -> None:
    for child in list(element):
        if isinstance(child.tag, str) and _local(child.tag) in DROPPED:
            element.remove(child)
        else:
            _sanitize(child, links)
    for name in [name for name in element.attrib if _local(name).lower().startswith("on")]:
        del element.attrib[name]
    written = next((element.get(name) for name in HREFS if element.get(name)), None)
    link = links.get(written) if written and _local(element.tag) == "a" else None
    if link is not None:
        for name in (*HREFS, "target", f"{{{XLINK}}}show"):
            element.attrib.pop(name, None)
        if link.href is not None:
            element.set("href", link.href)
            element.set("class", " ".join(filter(None, (element.get("class"), INTERNAL))))
        return
    for name in HREFS:
        if name in element.attrib and not SAFE_HREF.match(element.attrib[name].strip()):
            del element.attrib[name]


def _link_text(root: ElementTree.Element, texts: list[str], links: dict[str, FigureLink]) -> None:
    """Each wikilink text in a drawn text run becomes a link showing its label."""
    pattern = re.compile("|".join(map(re.escape, sorted(texts, key=len, reverse=True))))

    def split(text: str) -> tuple[str, list[ElementTree.Element]]:
        parts = pattern.split(text)
        found = pattern.findall(text)
        elements = []
        for written, tail in zip(found, parts[1:]):
            link = links[written]
            element = ElementTree.Element(f"{{{SVG}}}a" if link.href else f"{{{SVG}}}tspan")
            if link.href:
                element.set("href", link.href)
                element.set("class", INTERNAL)
            else:
                element.set("class", "unresolved")
            element.text, element.tail = link.label, tail or None
            elements.append(element)
        return parts[0], elements

    for element in list(root.iter()):
        if not isinstance(element.tag, str) or _local(element.tag) in TEXTLESS:
            continue
        children = list(element)
        if element.text and pattern.search(element.text):
            element.text, added = split(element.text)
            for index, new in enumerate(added):
                element.insert(index, new)
        for child in children:
            if child.tail and pattern.search(child.tail):
                child.tail, added = split(child.tail)
                position = list(element).index(child)
                for offset, new in enumerate(added, 1):
                    element.insert(position + offset, new)
