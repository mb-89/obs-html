"""Links inside a figure: a figure whose body has links shows its SVG inline, non-executable, with
each resolved link a chapter link like one in prose, in the frame and in the expanded view
(artifact-ui.md, Links inside a figure; figure_links.py).

Reader: whoever changes how a figure's links are shown.
"""
import re

import pytest

from artifacts import artifact_html
from obs_html.artifact_data import decode_artifact_data, html_text
from obs_html.config import load_config
from obs_html.render import render

from documents import chapter, document as build, heading, paragraph


CONFIG = load_config()
AUTHORED = "rect{fill:red}svg{--figure-frame-border-block:9px solid red}"
"""The drawing's own style: its rects, and a frame token set inside it."""
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
       'viewBox="0 0 300 60" width="300" height="60" onload="alert(1)">'
       f'<style>text{{fill:#333}}{AUTHORED}</style><script>alert(2)</script><foreignObject><p>html</p></foreignObject>'
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
        "target": "target", "chapter": "target", "heading": "^plan", "label": "plan", "block": "plan",
        "svg": "[[target#^plan]]"}}
    svg = SVG.replace("[[target]]", "[[target#^plan]]")

    assert '<a href="#target/block-plan" class="internal-link">plan</a>' in _chapter_html(_document(_figure(svg, block)))


def _figure_warnings(capsys) -> list[str]:
    return [line for line in capsys.readouterr().err.splitlines() if line.startswith("Warning: chapter.md: figure.style:")]


def test_an_inline_figure_s_style_applies_only_inside_its_own_figure() -> None:
    html = _chapter_html(LINKED)

    assert ("<style>:where(#chapter--figure-1) text{fill:#333}:where(#chapter--figure-1) rect{fill:red}"
            ":where(#chapter--figure-1) svg{--figure-frame-border-block:9px solid red}</style>") in html


def test_every_selector_and_nested_rule_is_scoped_and_keyframes_are_renamed() -> None:
    style = ("a:hover, :is(g, .x) > rect{fill:blue}@media (min-width: 1px){@supports (fill: red){circle{fill:red}}}"
             "@keyframes pulse{from{opacity:0}to{opacity:1}}rect{animation:pulse 1s;animation-name:pulse}")
    html = _chapter_html(_document(_figure(SVG.replace(AUTHORED, style), _link("target", "target", "[[target]]"))))
    scope = ":where(#chapter--figure-1)"

    assert (f"{scope} a:hover,{scope} :is(g, .x) &gt; rect{{fill:blue}}"
            f"@media (min-width: 1px){{@supports (fill: red){{{scope} circle{{fill:red}}}}}}"
            f"@keyframes chapter--figure-1--pulse{{from{{opacity:0}}to{{opacity:1}}}}"
            f"{scope} rect{{animation:chapter--figure-1--pulse 1s;animation-name:chapter--figure-1--pulse}}") in html


def test_global_at_rules_are_dropped_with_a_warning_naming_the_figure(capsys) -> None:
    style = ("@import url(https://example.org/a.css);@font-face{font-family:x;src:url(x.woff)}"
             "@property --figure-frame-border-block{syntax:'*';inherits:false}rect, {fill:red}")
    html = _chapter_html(_document(_figure(SVG.replace(AUTHORED, style), _link("target", "target", "[[target]]"))))
    warnings = _figure_warnings(capsys)

    assert "<style>:where(#chapter--figure-1) text{fill:#333}</style>" in html
    assert len(warnings) == 3 and all("chapter--figure-1" in warning for warning in warnings)


def test_page_selectors_are_dropped_and_frame_tokens_set_inside_stay_inside(capsys) -> None:
    style = (":root, html rect, body > g, :is(:root) rect, svg{--figure-frame-border-block:4px solid red}"
             "html{--figure-frame-background:red}")
    html = _chapter_html(_document(_figure(SVG.replace(AUTHORED, style), _link("target", "target", "[[target]]"))))
    warnings = _figure_warnings(capsys)

    assert ("<style>:where(#chapter--figure-1) text{fill:#333}:where(#chapter--figure-1) :is(:root) rect,"
            ":where(#chapter--figure-1) svg{--figure-frame-border-block:4px solid red}</style>") in html
    assert len(warnings) == 2 and all("chapter--figure-1" in warning for warning in warnings)


def test_a_diagram_s_own_style_is_left_as_drawn() -> None:
    style = "#mermaid-1 rect{fill:red}@keyframes dash{to{stroke-dashoffset:0}}"
    figure = _figure(SVG.replace("text{fill:#333}" + AUTHORED, style), _link("target", "target", "[[target]]"))
    figure["attrs"]["kind"] = "mermaid"

    assert f"<style>{style}</style>" in _chapter_html(_document(figure))


def test_a_figure_without_links_stays_an_image() -> None:
    html = _chapter_html(_document(_figure(SVG.replace("[[target]] or [[missing]]", ""))))

    assert '<img class="figure-default figure-visual"' in html and "<svg" not in html


@pytest.mark.browser
def test_a_link_inside_a_figure_shows_its_hover_card_and_navigates_in_the_frame_and_the_expanded_view(
        tmp_path, reader_browser) -> None:
    from playwright.sync_api import expect

    artifact = tmp_path / "figure-links.html"
    artifact.write_text(artifact_html(LINKED), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: errors.append(f"dialog {dialog.message}"))
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
    # The figure's style reaches its own rects only, never one elsewhere on the page, and the
    # frame tokens it sets inside the drawing leave the frame's border as the page sets it.
    assert page.evaluate("""() => {
        const outside = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        outside.innerHTML = '<rect width="4" height="4"/>';
        document.querySelector("[data-chapter-body]").append(outside);
        const fill = element => getComputedStyle(element).fill;
        const frame = document.querySelector("dialog.figure-overlay .obs-figure");
        const result = [fill(outside.firstChild), fill(frame.querySelector("rect.drawn")),
                        getComputedStyle(frame).borderTopWidth !== "9px"];
        outside.remove();
        return result;
    }""") == ["rgb(0, 0, 0)", "rgb(255, 0, 0)", True]
    expanded.locator("a[href='#drawn'] rect").click()
    expect(page.locator("dialog.figure-overlay")).to_have_count(0)
    expect(page.locator("[data-chapter-body] h1")).to_have_text("Drawn")
    assert page.evaluate("obsArtifact.records.find(record => record.slug === 'chapter').text") == (
        "Chapter See target or missing.")
    assert errors == []
