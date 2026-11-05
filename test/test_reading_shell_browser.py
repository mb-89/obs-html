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

LONG = "A chapter title long enough to need more room than a narrow top band has"
WIDTHS = {"desktop": 1100, "narrow": 390}

# Each top control's box, in the order the band shows them.
TOP_BAND = """() => {
    const box = (element) => {
        const r = element.getBoundingClientRect();
        return {top: r.top, left: r.left, right: r.right, width: r.width, height: r.height};
    };
    const crumbs = document.querySelector(".chapter-breadcrumbs");
    const links = [...crumbs.querySelectorAll(":scope > a:not(.chapter-home-link)")];
    return {
        home: box(document.querySelector(".chapter-home-link")),
        crumbs: box(crumbs),
        // Crumbs that leave the band's one line, above or below it.
        offRow: [...crumbs.children].filter((item) => item.getClientRects().length).filter((item) => {
            const r = item.getBoundingClientRect(), row = crumbs.getBoundingClientRect();
            return r.top < row.top - 1 || r.bottom > row.bottom + 1;
        }).map((item) => item.textContent || item.className),
        truncated: links.filter((link) => link.scrollWidth > link.clientWidth)
            .map((link) => ({text: link.textContent, title: link.title})),
        chevron: box(document.querySelector("[data-frontmatter-toggle]")),
        notices: [...document.querySelectorAll("[data-header-notices] [data-notice-icon]")]
            .filter((icon) => icon.getClientRects().length).map(box),
        menu: box(document.querySelector("[data-menu-button]")),
        arrows: [...document.querySelectorAll("[data-step]")].map(box),
        viewport: innerWidth,
    };
}"""


def band_artifact() -> str:
    return render(document(
        "Band",
        chapter("one", LONG, heading(1, LONG), paragraph("Parent text."), children=(
            chapter("one-a", LONG + " too", heading(1, "Child"), paragraph("Child text."),
                    metadata={"status": "draft"}),
        )),
        chapter("two", "Two", heading(1, "Two"), paragraph("Second chapter text.")),
    ), load_config())


@pytest.mark.parametrize("width", WIDTHS)
def test_every_top_control_is_one_square_size_in_one_row(tmp_path: Path, reader_browser, width: str) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, band_artifact(), "light",
                               width=WIDTHS[width])
    frame.evaluate("location.hash = '#one-a'")
    expect(frame.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "one-a")
    frame.evaluate("""() => ["error", "warning", "information"].forEach((severity) =>
        globalThis.obsNotices.post({id: severity, severity, title: severity}))""")
    band = frame.evaluate(TOP_BAND)

    squares = [band["home"], band["chevron"], *band["notices"], band["menu"]]
    assert len(band["notices"]) == 3
    size = band["menu"]["height"]
    assert [(round(item["width"]), round(item["height"])) for item in squares] == [(round(size),) * 2] * 6
    assert {round(item["top"]) for item in [*squares, band["crumbs"]]} == {round(band["menu"]["top"])}
    assert round(band["crumbs"]["height"]) == round(size)
    assert band["offRow"] == []
    # The notice icons sit directly left of the menu, in severity order.
    lefts = [item["left"] for item in band["notices"]]
    assert lefts == sorted(lefts)
    assert 0 <= band["menu"]["left"] - band["notices"][-1]["right"] <= size / 4
    assert band["crumbs"]["right"] <= band["chevron"]["left"] <= band["chevron"]["right"] <= lefts[0]
    # Previous and next stay at the viewport edges, below the band.
    previous, following = band["arrows"]
    # Next keeps its inset clear of a scrollbar (base.css --chapter-nav-inset-end, 1rem).
    assert previous["left"] == 0 and 0 <= band["viewport"] - following["right"] <= 16
    assert min(previous["top"], following["top"]) >= band["menu"]["top"] + size
    if width == "narrow":
        assert band["truncated"], "the long crumbs do not truncate at narrow width"
        assert all(item["title"] == item["text"] for item in band["truncated"])
    assert errors == []


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


def test_the_contents_and_previous_next_walk_the_same_chapters(tmp_path: Path, reader_browser) -> None:
    """The Document as the core emits a manifest with a hidden line: the hidden line is no chapter,
    and a note the manifest does not list is a `toc: false` chapter, reachable only by its link."""
    from playwright.sync_api import expect

    unlisted = {**chapter("secret", "Secret", paragraph("Reached by link only.")), "toc": False}
    artifact = render(document(
        "Walk",
        chapter("one", "One", paragraph("One."), children=(
            chapter("one-a", "One A", paragraph("One A.")),
            unlisted,
            chapter("one-b", "One B", paragraph("One B.")),
        )),
        chapter("two", "Two", paragraph("Two.")),
    ), load_config())
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light")
    contents = frame.evaluate("""() => [...document.querySelectorAll("[data-toc-tree] [data-toc-link]")]
        .map((link) => link.getAttribute("href").slice(1))""")
    walk = []
    following = frame.locator('[data-step="1"]')
    while following.is_enabled():
        following.click()
        frame.evaluate("globalThis.obsArtifact.whenChapterReady()")
        walk.append(frame.locator("[data-active-chapter]").get_attribute("data-chapter"))
    assert contents == ["one", "one-a", "one-b", "two"]
    assert walk == contents
    backwards = []
    previous = frame.locator('[data-step="-1"]')
    while previous.is_enabled():
        previous.click()
        frame.evaluate("globalThis.obsArtifact.whenChapterReady()")
        backwards.append(frame.locator("[data-active-chapter]").get_attribute("data-chapter"))
    assert backwards == [*reversed(contents[:-1]), "home"]
    expect(frame.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "home")
    assert errors == []
