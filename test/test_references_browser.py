"""Native-browser tier: reference and glossary notes in the reader's link hover card.

A reduced move of the interim's test_reference_items_browser.py
(test_hover_card_shows_per_kind_content_and_the_only_external_link) onto a Document: the
guided-card, quantity and mark parts stay with the capabilities that own them.
"""
import pytest

from artifacts import artifact_html
from browser.viewer import with_stand_in

from documents import chapter, document as build, heading, node, paragraph, text


pytestmark = pytest.mark.browser
URL = "https://webstore.iec.ch/publication/1234"
REFERENCE = {"title": "IEC 1234", "url": URL, "description": "Safety of medical electrical equipment."}
TERM = {"kind": "glossary", "term": "RSS", "definition": "Root **sum** of squares."}


def _link(chapter_id: str, label: str) -> dict:
    return node("wikilinks", target=chapter_id, chapter=chapter_id, heading="", label=label)


def test_hover_card_shows_the_reference_link_and_the_glossary_definition(tmp_path, reader_browser) -> None:
    from playwright.sync_api import expect

    reference = {**REFERENCE, "kind": "reference"}
    source = build(
        "References",
        chapter("chapter", "Chapter", heading(1, "Chapter"),
                paragraph("The limit follows ", _link("iec", "iec"), ". Errors add as ", _link("rss", "rss"), ".")),
        chapter("iec", "IEC 1234", node("references", metadata=reference), metadata=reference),
        chapter("rss", "RSS", node("references", metadata=TERM), metadata=TERM, fields={"definition": [
            "Root ", {"type": "strong", "attrs": {}, "children": [text("sum")]}, " of squares."]}),
        records=tuple({"id": slug, "type": "note", "path": f"{slug}.md", "fields": fields}
                      for slug, fields in (("chapter", {}), ("iec", reference), ("rss", TERM))),
    )
    for item in source["chapters"][1:]:
        item["toc"] = False
    artifact = tmp_path / "references.html"
    artifact.write_text(with_stand_in(artifact_html(source), "window.open = () => null;"), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 800})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri() + "#chapter")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('chapter')")
    card = page.locator("#hover-card")
    assert page.locator("[data-chapter-body] a[href^='http']").count() == 0
    page.locator("[data-chapter-body] p a[href='#iec']").hover()
    expect(card).to_be_visible()
    expect(card.locator(".hover-card-title")).to_have_text("IEC 1234")
    expect(card).to_contain_text("Safety of medical electrical equipment.")
    external = card.locator("a[href^='http']")
    expect(external).to_have_count(1)
    expect(external).to_have_attribute("href", URL)
    page.locator("[data-chapter-body] p a[href='#rss']").hover()
    expect(card.locator(".hover-card-title")).to_have_text("RSS")
    expect(card).to_contain_text("Root sum of squares.")
    expect(card.locator("strong")).to_have_text("sum")
    assert errors == []
