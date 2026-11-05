"""An HTML5 content-model check of a built artifact: no block element where only phrasing content
is allowed.

Reader: whoever changes what this adapter writes, or this check.

A browser's parser repairs such markup silently (a ``<div>`` inside a ``<p>`` closes the ``<p>``
early), so the page can still look right while its DOM is not the one written. This check reads the
markup as written: the page outside its data island, and every HTML string the island carries
(each value under a key ``html`` or ending in ``Html``), named by the chapter it belongs to.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from obs_html.artifact_data import ARTIFACT_PATTERN, decode_artifact_data

# Elements whose content model is phrasing content only (HTML Living Standard, Elements); `a` and
# the formatting elements are transparent and are held to phrasing here, as inside a paragraph.
PHRASING_ONLY = frozenset({
    "p", "span", "a", "h1", "h2", "h3", "h4", "h5", "h6", "summary", "em", "strong", "s", "b", "i",
    "u", "small", "sub", "sup", "code", "label", "button", "abbr", "cite", "q", "mark", "time",
    "pre",
})
# Flow content that is not phrasing content: it may not appear inside a phrasing-only parent.
BLOCK = frozenset({
    "address", "article", "aside", "blockquote", "details", "dialog", "div", "dl", "dd", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup",
    "hr", "li", "main", "menu", "nav", "ol", "p", "pre", "section", "table", "tbody", "thead", "tfoot",
    "tr", "td", "th", "ul",
})
# A summary may hold one heading besides its phrasing content.
ALLOWED = {"summary": frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})}
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
                  "track", "wbr"})
# Foreign content (MathML, SVG) follows its own content model.
FOREIGN = frozenset({"math", "svg"})
SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)


class _Checker(HTMLParser):
    def __init__(self, chapter: str) -> None:
        super().__init__(convert_charrefs=True)
        self.chapter, self.stack, self.violations = chapter, [], []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not any(open_tag in FOREIGN for open_tag, _ in self.stack):
            parent = self.stack[-1] if self.stack else None
            if tag in BLOCK and parent and parent[0] in PHRASING_ONLY and tag not in ALLOWED.get(parent[0], ()):
                self.violations.append(
                    f"chapter {self.chapter!r}: <{tag}{_classes(attrs)}> inside {parent[1]}: a block element "
                    f"where only phrasing content is allowed (the browser closes the <{parent[0]}> early). "
                    f"Remedy: in src/obs_html/render.py, write phrasing content there (a <span> styled "
                    f"display: block) or move the block out of the <{parent[0]}>.")
        if tag not in VOID:
            self.stack.append((tag, f"<{tag}{_classes(attrs)}>"))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


def _classes(attrs: list[tuple[str, str | None]]) -> str:
    classes = dict(attrs).get("class")
    return f' class="{classes}"' if classes else ""


def check_markup(markup: str, chapter: str) -> list[str]:
    """The content-model violations of one piece of markup, each naming the element, its parent,
    the chapter and the remedy."""
    checker = _Checker(chapter)
    checker.feed(SCRIPT.sub("", markup))
    checker.close()
    return checker.violations


def _html_strings(value: object, key: str = "") -> list[str]:
    if isinstance(value, str):
        return [value] if key == "html" or key.endswith("Html") else []
    if isinstance(value, dict):
        return [markup for name, item in value.items() for markup in _html_strings(item, name)]
    if isinstance(value, list):
        return [markup for item in value for markup in _html_strings(item, key)]
    return []


def check_artifact(artifact: str) -> list[str]:
    """The content-model violations of a built artifact: its page and every chapter's HTML."""
    data = decode_artifact_data(artifact)
    violations = check_markup(ARTIFACT_PATTERN.sub("", artifact), "page")
    for note in data["notes"]:
        violations += [violation for markup in _html_strings(note)
                       for violation in check_markup(markup, note["slug"])]
    rest = {name: value for name, value in data.items() if name != "notes"}
    violations += [violation for markup in _html_strings(rest) for violation in check_markup(markup, "page")]
    return violations
