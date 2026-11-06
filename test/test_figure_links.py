"""Links inside a figure: a figure whose body has links shows its SVG inline, non-executable, with
each resolved link a chapter link like one in prose, in the frame and in the expanded view
(artifact-ui.md, Links inside a figure; figure_links.py).

Reader: whoever changes how a figure's links are shown.
"""
import re

import pytest

from obs_html.artifact_data import decode_artifact_data, html_text
from obs_html.config import load_config
from obs_html.render import render

from documents import chapter, document as build, heading, paragraph


CONFIG = load_config()
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
       'viewBox="0 0 300 60" width="300" height="60" onload="alert(1)">'
       '<style>text{fill:#333}</style><script>alert(2)</script><foreignObject><p>html</p></foreignObject>'
       '<text x="4" y="16">See [[target]] or [[missing]].</text>'
       '<a xlink:href="drawn.md" target="_top" onclick="alert(3)"><rect class="drawn" x="4" y="30" width="60" height="24"/></a>'
       '<a href="javascript:alert(4)"><rect x="80" y="30" width="20" height="20"/></a>'
       '<a href="https://example.org/"><rect x="120" y="30" width="20" height="20"/></a>'
       '<set attributeName="href" to="javascript:alert(5)"/></svg>')


def _link(target: str, chapter_id: str | None, written: str) -> dict:
    return {"type": "wikilinks", "attrs": {"target": target, "chapter": chapter_id, "heading": "",
                                           "label": target, "svg": written}, "children": []}


def _figure(svg: str, *links: dict) -> dict:
    return {"type": "figures", "attrs": {"kind": "svg", "alt": "Linked drawing"},
            "children": [{"type": "svg", "attrs": {"svg": svg}, "children": list(links)}]}


def _document(*content: dict) -> dict:
    return build(
        "Figure links",
        chapter("chapter", "Chapter", heading(1, "Chapter"), *content),
        chapter("target", "Target", heading(1, "Target"), paragraph("The target note.")),
        chapter("drawn", "Drawn", heading(1, "Drawn"), paragraph("The drawn note.")),
        records=tuple({"id": slug, "type": "note", "path": f"{slug}.md", "fields": {}}
                      for slug in ("chapter", "target", "drawn")),
    )


LINKED = _document(_figure(SVG, _link("target", "target", "[[target]]"), _link("missing", None, "[[missing]]"),
                           _link("drawn.md", "drawn", "drawn.md")))


def _chapter_html(document: dict) -> str:
    data = decode_artifact_data(render(document, CONFIG))
    return next(note for note in data["notes"] if note["slug"] == "chapter")["html"]


def test_a_figure_with_links_shows_its_svg_inline_with_each_resolved_link_a_chapter_link() -> None:
    html = _chapter_html(LINKED)

    assert "<img" not in html
    assert '<a href="#target" class="internal-link">target</a>' in html
    assert '<tspan class="unresolved">missing</tspan>' in html
    assert re.search(r'<a (?:class="internal-link" href="#drawn"|href="#drawn" class="internal-link")>'
                     r'<rect class="drawn"', html)
    assert 'href="https://example.org/"' in html


def test_the_inline_svg_keeps_nothing_executable() -> None:
    html = _chapter_html(LINKED)
    svg = html[html.index("<svg"):html.index("</svg>")]

    assert not re.search(r"<script|<foreignObject|<set|\son\w+=|javascript:|target=", svg)


def test_the_chapter_text_shows_the_drawing_s_text_with_link_labels_and_no_style() -> None:
    assert html_text(_chapter_html(LINKED)).splitlines()[1:] == ["See target or missing."]


def test_a_block_link_inside_a_figure_links_the_figure_s_anchor() -> None:
    block = {**_link("target", "target", "[[target#^plan]]"), "attrs": {
        "target": "target", "chapter": "target", "heading": "^plan", "label": "plan", "figure": "plan",
        "svg": "[[target#^plan]]"}}
    svg = SVG.replace("[[target]]", "[[target#^plan]]")

    assert '<a href="#target/block-plan" class="internal-link">plan</a>' in _chapter_html(_document(_figure(svg, block)))


def test_a_figure_without_links_stays_an_image() -> None:
    html = _chapter_html(_document(_figure(SVG.replace("[[target]] or [[missing]]", ""))))

    assert '<img class="figure-default figure-visual"' in html and "<svg" not in html


@pytest.mark.browser
def test_a_link_inside_a_figure_shows_its_hover_card_and_navigates_in_the_frame_and_the_expanded_view(
        tmp_path, reader_browser) -> None:
    from playwright.sync_api import expect

    artifact = tmp_path / "figure-links.html"
    artifact.write_text(render(LINKED, CONFIG), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: errors.append(f"dialog {dialog.message}"))
    try:
        page.goto(artifact.as_uri() + "#chapter")
        page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('chapter')")
        figure = page.locator("[data-chapter-body] .obs-figure")
        # Playwright's own pointing misses a link inside SVG text, so the mouse goes to its box.
        box = figure.locator("a[href='#target']").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(page.locator("#hover-card .hover-card-title")).to_have_text("Target")
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(page.locator("[data-chapter-body] h1")).to_have_text("Target")

        page.evaluate("obsArtifact.activateChapter('chapter')")
        figure.locator(".figure-expand").click()
        expanded = page.locator("dialog.figure-overlay .obs-figure")
        expect(expanded.locator("svg.figure-visual")).to_be_visible()
        expanded.locator("a[href='#drawn'] rect").click()
        expect(page.locator("dialog.figure-overlay")).to_have_count(0)
        expect(page.locator("[data-chapter-body] h1")).to_have_text("Drawn")
        assert page.evaluate("obsArtifact.records.find(record => record.slug === 'chapter').text") == (
            "Chapter See target or missing.")
        assert errors == []
    finally:
        page.close()
