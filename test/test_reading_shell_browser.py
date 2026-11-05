"""The reading shell's top band, the title page and the chapter walk, in Claude's artifact viewer.

The design owners are spec/design_input/artifact-ui.md (Reading shell: the one-row top band;
Paged view: no text twice in one view) and spec/design_input/input-model.md (chapters: the table
of contents and previous/next walk the same non-hidden manifest lines). Each test opens the
artifact in the viewer fixture (test/browser/viewer.py).
"""
from pathlib import Path

import pytest
from browser.viewer import open_viewer
from documents import chapter, document, heading, paragraph

from obs_html.config import load_config
from obs_html.render import render

pytestmark = pytest.mark.browser

# Each sheet's running-header lines that its own content already shows as a heading.
REPEATED_HEADINGS = """() => [...document.querySelectorAll(".paper-sheet")].flatMap((sheet) => {
    const headings = new Set([...sheet.querySelectorAll("h1, h2, h3, h4, h5, h6")]
        .map((heading) => heading.textContent.trim()));
    return [...sheet.querySelectorAll(".paper-header > span")].map((span) => span.textContent.trim())
        .filter((line) => line && headings.has(line)).map((line) => `${sheet.dataset.pageChapter}: ${line}`);
})"""


def test_the_title_page_shows_the_document_type_once(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    artifact = render(document(
        "Product", chapter("one", "One", heading(1, "One"), paragraph("Text.")),
        metadata={"document type": "Design specification", "product": {"name": "Widget"},
                  "confidentiality": "Internal"},
    ), load_config())
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light")
    expect(frame.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "home")
    for paged, view in ((True, ".paper-sheet:has(.document-heading)"), (False, "[data-chapter-body]")):
        frame.evaluate("(paged) => globalThis.obsPages.setPaged(paged)", paged)
        text = frame.locator(view).first.inner_text()
        for shown in ("Design specification", "Widget", "Internal"):
            assert text.count(shown) == 1, (view, shown, text)
    frame.evaluate("globalThis.obsPages.setPaged(true)")
    assert frame.evaluate(REPEATED_HEADINGS) == []
    frame.evaluate("location.hash = '#one'")
    expect(frame.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "one")
    frame.evaluate("globalThis.obsArtifact.whenChapterReady()")
    assert frame.locator(".paper-sheet .paper-header").count()
    assert frame.evaluate(REPEATED_HEADINGS) == []
    assert errors == []
