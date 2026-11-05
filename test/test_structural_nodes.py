"""Structural nodes: every type the core's Document schema lists renders, and no node is dropped.

The structural types are the core's (``$defs/structuralType`` of ``src/obs/document.schema.json``);
the core-built Document ``fixtures/documents/structural.json`` holds each Markdown construct as the
core emits it (its vault is ``structural`` in ``fixtures/build_documents.py``).
"""
import json
import re
from pathlib import Path

import pytest

from conftest import CORE_ROOT, ROOT
from documents import chapter, document as build, node, paragraph, text
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.render import RenderError, render


CONFIG = load_config()
SCHEMA = json.loads((CORE_ROOT / "src" / "obs" / "document.schema.json").read_text(encoding="utf-8"))
STRUCTURAL_TYPES = SCHEMA["$defs"]["structuralType"]["enum"]
STRUCTURAL = json.loads((ROOT / "test" / "fixtures" / "documents" / "structural.json").read_text(encoding="utf-8"))


def _notes(document: dict) -> dict:
    return {note["slug"]: note for note in decode_artifact_data(render(document, CONFIG))["notes"]}


def _word(kind: str) -> str:
    return "word" + kind.replace("-", "")


def _structural_node(kind: str) -> dict:
    """A node of a structural type carrying the word ``word<kind>`` (letters only, which math keeps as
    letters), as text or as a text child."""
    word = _word(kind)
    if kind in {"text", "code", "math"}:
        return {"type": kind, "attrs": {"display": False} if kind == "math" else {}, "children": [], "text": word}
    attrs = {"table-cell": {"header": False}, "field": {"name": "name"}, "section": {"level": 2}}.get(kind, {})
    return {"type": kind, "attrs": attrs, "children": [] if kind == "rule" else [text(word)]}


@pytest.mark.parametrize("kind", STRUCTURAL_TYPES)
def test_every_structural_type_of_the_core_schema_renders_its_text(kind: str, capsys) -> None:
    html = _notes(build("Doc", chapter("one", "One", _structural_node(kind))))["one"]["html"]
    if kind == "rule":
        assert html == "<hr>\n"  # The one type without text.
    else:
        assert _word(kind) in re.sub(r"<[^>]+>", "", html), html
    assert "unknown-node" not in html
    assert capsys.readouterr().err == ""


def test_the_adapter_reads_the_structural_types_from_the_core_schema() -> None:
    from obs_html.render import STRUCTURAL as adapter_types

    assert sorted(adapter_types) == sorted(STRUCTURAL_TYPES)


def test_a_core_built_document_renders_every_markdown_construct(document_validator) -> None:
    document_validator.validate(STRUCTURAL)
    note = _notes(STRUCTURAL)["formatting"]
    html = note["html"]
    assert ("<p>Plain, <strong>strong <em>emphasis inside</em> and <s>struck</s></strong>, "
            "<em>emphasis <strong>strong inside</strong></em>, "
            "<s>struck <strong>strong <em>all three</em></strong></s> and inline "
            '<span class="math inline"><math') in html
    assert "<msup><mi>x</mi><mn>2</mn></msup>" in html
    assert re.search(r'<div class="math block"><math [^>]*display="block"[^>]*>.*<mi>E</mi>.*</math></div>\n', html)
    assert "<blockquote>\n<p>A quoted <strong>line</strong>.</p>\n</blockquote>\n" in html
    assert ("<table>\n<thead>\n<tr>"
            '<th style="text-align:left">Left</th><th style="text-align:center">Center</th>'
            '<th style="text-align:right">Right</th></tr>\n</thead>\n<tbody>\n<tr>'
            '<td style="text-align:left">a</td><td style="text-align:center"><em>b</em></td>'
            '<td style="text-align:right">3</td></tr>\n</tbody>\n</table>\n') in html
    assert "<hr>\n" in html
    # Frontmatter fields render from their field nodes, by dotted path; data-only values stay data.
    assert note["frontmatterHtml"] == {"owner.name": "<em>Ada</em> <strong>Lovelace</strong>",
                                       "tags": "<s>old</s>, plain", "count": "3"}


def test_an_invalid_formula_names_the_chapter_the_formula_and_the_remedy() -> None:
    formula = {"type": "math", "attrs": {"display": False}, "children": [], "text": "x^"}
    with pytest.raises(RenderError) as raised:
        render(build("Doc", chapter("one", "One", paragraph(formula))), CONFIG)
    message = str(raised.value)
    assert message.startswith("Chapter one: math formula 'x^'")
    assert "Remedy:" in message
