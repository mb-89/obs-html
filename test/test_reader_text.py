"""Reader-facing text names no kind (obs spec/design_input/artifact-ui.md, Reader-facing text).

The scan reads the strings the reader can see and fails on the words "document" or "report":

- the runtime's prose: every string literal with a space in the adapter's own JavaScript
  (src/obs_html, not vendor), since an identifier or a key holds no space;
- the page shell this adapter writes: its text and the attributes a reader sees or hears
  (labels, tooltips, hover help, placeholders), outside scripts, styles and the author's content;
- the limited-function notices written into the page, here for a node type the adapter lacks.

ALLOWED lists the only phrases that may still contain one of the words, each with its reason.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import obs_html
from obs_html.config import load_config
from obs_html.render import render

from documents import paragraph, text

RUNTIME = Path(obs_html.__file__).parent
WORDS = re.compile(r"\b(?:document|report)s?\b", re.IGNORECASE)
READER_ATTRIBUTES = frozenset({"aria-label", "aria-description", "title", "alt", "placeholder",
                               "data-hover-help"})

# phrase -> why a reader-facing string may contain it.
ALLOWED: dict[str, str] = {
    "document type": "the manifest field the author fills in; the runtime reads it by that name",
    "document.schema.json": "the core's schema file a limited-function notice names as its source",
}


def _hits(strings: dict[str, str]) -> list[str]:
    """Each string, keyed by where it is, that names a kind outside the ALLOWED phrases."""
    found = []
    for place, value in strings.items():
        rest = value
        for phrase in ALLOWED:
            rest = re.sub(re.escape(phrase), "", rest, flags=re.IGNORECASE)
        if WORDS.search(rest):
            found.append(f"{place}: {value!r}")
    return found


def _js_literals(source: str) -> list[str]:
    """The string literals of one JavaScript file: quoted strings and template-literal text, with
    comments and regular-expression literals skipped and ${...} expressions scanned as code."""
    literals: list[str] = []
    index, length = 0, len(source)
    previous = ""  # the last significant character, to tell a regular expression from a division

    def template(start: int) -> int:
        parts, cursor, part = [], start, []
        while cursor < length and source[cursor] != "`":
            if source[cursor] == "\\":
                part.append(source[cursor:cursor + 2])
                cursor += 2
            elif source.startswith("${", cursor):
                depth, end = 1, cursor + 2
                while end < length and depth:
                    depth += {"{": 1, "}": -1}.get(source[end], 0)
                    end += 1
                literals.extend(_js_literals(source[cursor + 2:end - 1]))
                parts.append("".join(part))
                part, cursor = [], end
            else:
                part.append(source[cursor])
                cursor += 1
        parts.append("".join(part))
        literals.append(" ".join(parts))
        return cursor + 1

    while index < length:
        char = source[index]
        if source.startswith("//", index):
            index = source.find("\n", index)
            index = length if index < 0 else index
        elif source.startswith("/*", index):
            index = source.find("*/", index + 2) + 2 or length
        elif char in "\"'":
            end = index + 1
            while end < length and source[end] != char:
                end += 2 if source[end] == "\\" else 1
            literals.append(source[index + 1:end])
            index, previous = end + 1, char
        elif char == "`":
            index, previous = template(index + 1), char
        elif char == "/" and (not previous or previous in "(,=:[!&|?{};+-*%<>~^"):
            end, in_class = index + 1, False
            while end < length and (in_class or source[end] != "/"):
                if source[end] == "\\":
                    end += 1
                elif source[end] == "[":
                    in_class = True
                elif source[end] == "]":
                    in_class = False
                end += 1
            index, previous = end + 1, "/"
        else:
            if not char.isspace():
                previous = char if not (char.isalnum() or char in "_$") else "a"
            index += 1
    return literals


class _Shell(HTMLParser):
    """The page shell's reader-facing text and attributes, outside scripts, styles and content."""

    SKIP = frozenset({"script", "style", "template", "title"})

    def __init__(self) -> None:
        super().__init__()
        self.strings: dict[str, str] = {}
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            if name in READER_ATTRIBUTES and value:
                self.strings[f"<{tag} {name}> #{len(self.strings)}"] = value
        if tag not in {"br", "img", "input", "meta", "link", "hr", "source", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag) -> None:
        if tag in self.stack:
            while self.stack.pop() != tag:
                pass

    def handle_data(self, data) -> None:
        if data.strip() and not self.SKIP.intersection(self.stack):
            self.strings[f"<{self.stack[-1] if self.stack else 'html'}> text #{len(self.strings)}"] = data.strip()


def _page(document: dict) -> str:
    """The fixture Document with one node type the adapter lacks, rendered."""
    unknown = {"type": "obs-test-unknown", "attrs": {}, "children": [text("plain")]}
    document["chapters"][0]["content"].append(paragraph(unknown))
    return render(document, load_config())


def test_reader_facing_text_names_no_kind(document, capsys) -> None:
    strings: dict[str, str] = {}
    for path in sorted(RUNTIME.rglob("*.js")):
        if "vendor" in path.relative_to(RUNTIME).parts:
            continue
        literals = _js_literals(path.read_text(encoding="utf-8"))
        for number, literal in enumerate(literals):
            if " " in literal.strip():
                strings[f"src/obs_html/{path.relative_to(RUNTIME).as_posix()} literal {number}"] = literal
    # The scan reads the runtime at all: a known message of the opening code is among its strings.
    assert "HTML could not be opened:  " in strings.values(), "test_reader_text.py: the JS scan found no runtime prose"

    page = _page(document)
    capsys.readouterr()
    shell = _Shell()
    shell.feed(page)
    assert any(value == "Search" for value in shell.strings.values()), \
        "test_reader_text.py: the shell scan found no bar label"
    strings.update({f"page shell {place}": value for place, value in shell.strings.items()})
    limits = re.search(r'<script id="[a-z-]*limits" type="application/json">(.*?)</script>', page, re.S)
    assert limits, "test_reader_text.py: the page carries no limited-function island"
    for limit in json.loads(limits.group(1)):
        for field in ("feature", "reason", "observation", "remedy"):
            strings[f"limited function {limit['key']} {field}"] = limit[field]

    hits = _hits(strings)
    assert not hits, ("Reader-facing text names a kind (artifact-ui.md, Reader-facing text); "
                      "say what it is without the noun, or list a phrase in ALLOWED with its reason:\n"
                      + "\n".join(hits))
