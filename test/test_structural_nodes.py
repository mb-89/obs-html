"""Structural nodes: every type the core's Document schema lists renders, and no node is dropped.

The structural types are the core's (``$defs/structuralType`` of ``src/obs/document.schema.json``);
the core-built Document ``fixtures/documents/structural.json`` holds each Markdown construct as the
core emits it (its vault is ``structural`` in ``fixtures/build_documents.py``).
"""
import json
import re
from pathlib import Path

import pytest

from artifacts import artifact_html
from conftest import CORE_ROOT, ROOT
from documents import chapter, document as build, paragraph, text
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render


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
    attrs = {"table-cell": {"header": False}, "field": {"name": "name"}, "section": {"level": 2},
             "list": {"ordered": False, "tight": True}}.get(kind, {})
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


def test_an_untitled_note_callout_shows_the_core_title_and_the_adapter_adds_none() -> None:
    html = _notes(STRUCTURAL)["formatting"]["html"]
    assert '<header class="content-card-title">Note</header>\n<p>Untitled note body.</p>' in html
    untitled = {"type": "callouts", "attrs": {"kind": "note", "title": ""}, "children": [paragraph("Body.")]}
    html = _notes(build("Doc", chapter("one", "One", untitled)))["one"]["html"]
    assert "content-card-title" not in html and "Note</header>" not in html
    assert '<aside class="content-card content-callout content-callout--accent" data-callout="note"' in html


def test_an_invalid_formula_names_the_chapter_the_formula_and_the_remedy() -> None:
    formula = {"type": "math", "attrs": {"display": False}, "children": [], "text": "x^"}
    with pytest.raises(InputError) as raised:
        render(build("Doc", chapter("one", "One", paragraph(formula))), CONFIG)
    assert (raised.value.source, raised.value.field) == ("chapter one", "body")
    assert "'x^'" in raised.value.problem  # The formula as authored.


def test_an_invented_node_type_raises_one_limited_function_warning_naming_it(capsys) -> None:
    def invented(value: str) -> dict:
        return {"type": "sparkle", "attrs": {}, "children": [text(value)]}

    document = build("Doc", chapter("one", "One", paragraph(invented("first")), paragraph(invented("second"))))
    document["capabilities"].remove("sparkle")
    html = render(document, CONFIG)
    notes = {note["slug"]: note for note in decode_artifact_data(html)["notes"]}
    assert '<span class="unknown-node" data-node-type="sparkle">second</span>' in notes["one"]["html"]
    limits = json.loads(re.search(r'<script id="document-limits" type="application/json">(.*?)</script>',
                                  html)[1])
    assert len(limits) == 1
    assert limits[0]["key"] == "node-sparkle"
    assert "sparkle" in limits[0]["feature"]
    assert "obs-html (src/obs_html/render.py)" in limits[0]["reason"]
    assert "chapter 'one'" in limits[0]["observation"]
    assert limits[0]["remedy"]
    warnings = [line for line in capsys.readouterr().err.splitlines() if "'sparkle'" in line]
    assert len(warnings) == 1
    assert warnings[0].split(": ")[:3] == ["Warning", "obs-html (src/obs_html/render.py)", "limited function"]
    assert warnings[0].endswith(f"{limits[0]['remedy']}")  # The remedy closes the one form.


def test_a_document_without_unknown_nodes_carries_no_limits() -> None:
    html = render(build("Doc", chapter("one", "One", paragraph("Known."))), CONFIG)
    assert '<script id="document-limits" type="application/json">[]</script>' in html


@pytest.mark.browser
def test_the_notice_center_shows_one_limited_function_warning_per_unknown_type(tmp_path: Path,
                                                                                reader_browser) -> None:
    from playwright.sync_api import expect
    from test_sandboxed_preview_browser import open_page

    def invented(value: str) -> dict:
        return {"type": "sparkle", "attrs": {}, "children": [text(value)]}

    document = build("Doc", chapter("one", "One", paragraph(invented("first")), paragraph(invented("second"))))
    document["capabilities"].remove("sparkle")
    path = tmp_path / "artifact.html"
    path.write_text(artifact_html(document), encoding="utf-8")
    errors: list[str] = []
    page = open_page(reader_browser, path, errors)
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    entries = page.locator('[data-notice-list="warning"] [data-notice]')
    expect(entries).to_have_count(1)
    expect(entries.first).to_have_attribute("data-notice", "capability-node-sparkle")
    expect(entries.first.locator("[data-notice-title]")).to_have_text(
        'Limited functionality: Node type "sparkle"')
    expect(entries.first.locator("[data-notice-details]")).to_contain_text("obs-html (src/obs_html/render.py)")
    assert page.locator('[data-notice-list="error"] [data-notice]').count() == 0
    assert errors == []


def test_display_math_inside_a_paragraph_is_phrasing_content_and_on_its_own_a_block() -> None:
    """`Text $$a^2$$ text` keeps its paragraph whole: the browser closes a <p> at a <div>."""
    inline = {"type": "math", "attrs": {"display": True}, "children": [], "text": "a^2"}
    alone = {"type": "math", "attrs": {"display": True}, "children": [], "text": "b^2"}
    html = _notes(build("Doc", chapter("one", "One", paragraph("Text ", inline, " text"), alone)))["one"]["html"]
    paragraph_html = re.search(r"<p>.*?</p>", html, re.DOTALL)[0]
    assert paragraph_html.startswith('<p>Text <span class="math block"><math ')
    assert paragraph_html.endswith("</math></span> text</p>")
    assert "<div" not in paragraph_html
    assert re.search(r'</p>\n<div class="math block"><math [^>]*display="block"[^>]*>.*<mi>b</mi>.*</math></div>\n',
                     html, re.DOTALL)
