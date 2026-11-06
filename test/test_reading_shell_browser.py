"""The reading shell's top band, the title page and the chapter walk, in Claude's artifact viewer.

The design owners are spec/artifact-ui.md (Reading shell: the one-row top band;
Paged view: no text twice in one view; chapter navigation: a link to a whole note opens it at its
heading) and obs's spec/design_input/input-model.md (chapters: the table of contents and
previous/next walk the same non-hidden manifest lines). Each test opens the
artifact in the viewer fixture (test/browser/viewer.py).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from artifacts import artifact_html
from browser.viewer import open_viewer
from conftest import CORE_ROOT, ROOT, built_once
from documents import chapter, document, heading, paragraph

from obs_html.cli import main as obs_html

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


def assert_contents_and_walk(tmp_path: Path, reader_browser, artifact: str, chapters: list[str]) -> None:
    """The contents list exactly ``chapters``, and previous/next walk them both ways from Home."""
    from playwright.sync_api import expect

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
    assert contents == chapters
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


def band_artifact() -> str:
    return artifact_html(document(
        "Band",
        chapter("one", LONG, heading(1, LONG), paragraph("Parent text."), children=(
            chapter("one-a", LONG + " too", heading(1, "Child"), paragraph("Child text."),
                    metadata={"status": "draft"}),
        )),
        chapter("two", "Two", heading(1, "Two"), paragraph("Second chapter text.")),
    ))


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

    artifact = artifact_html(document(
        "Product", chapter("one", "One", heading(1, "One"), paragraph("Text.")),
        metadata={"document type": "Design specification", "product": {"name": "Widget"},
                  "confidentiality": "Internal"},
    ))
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
    unlisted = {**chapter("secret", "Secret", paragraph("Reached by link only.")), "toc": False}
    artifact = artifact_html(document(
        "Walk",
        chapter("one", "One", paragraph("One."), children=(
            chapter("one-a", "One A", paragraph("One A.")),
            unlisted,
            chapter("one-b", "One B", paragraph("One B.")),
        )),
        chapter("two", "Two", paragraph("Two.")),
    ))
    assert_contents_and_walk(tmp_path, reader_browser, artifact, ["one", "one-a", "one-b", "two"])


@pytest.fixture(scope="module")
def commented_manifest_artifact(tmp_path_factory) -> str:
    """A vault whose manifest comments lines out, built by obs-document and rendered by obs-html, once per run."""
    def build(folder: Path) -> None:
        vault = folder / "vault"
        vault.mkdir()
        (vault / "manifest.md").write_text(
            "---\ntitle: Walk\n---\n- [[one]]\n  - [[one-a]]\n  %% - [[secret]] %%\n  - [[one-b]]\n"
            "%%\n- [[gone]]\n%%\n- [[two]]\n", encoding="utf-8",
        )
        for name in ("one", "one-a", "one-b", "two"):
            (vault / f"{name}.md").write_text(f"{name} body.\n", encoding="utf-8")
        built, capabilities = folder / "document.json", folder / "capabilities.json"
        subprocess.run([sys.executable, "-m", "obs.capabilities", "--notes",
                        str(CORE_ROOT / "spec" / "capabilities"), "--output", str(capabilities)], check=True)
        subprocess.run([sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"),
                        "--document", str(built), "--capability-reference", str(capabilities)], check=True)
        assert obs_html([str(built), str(folder / "artifact.html")]) == 0

    return (built_once(tmp_path_factory, "commented-manifest-artifact", build) / "artifact.html").read_text(
        encoding="utf-8")


def test_a_manifest_with_commented_lines_walks_its_visible_chapters_end_to_end(
    tmp_path: Path, reader_browser, commented_manifest_artifact: str,
) -> None:
    """The same walk through obs-document and obs-html: the core hides the `%%` manifest lines,
    so the contents and previous/next walk one, one-a, one-b and two."""
    assert_contents_and_walk(
        tmp_path, reader_browser, commented_manifest_artifact, ["one", "one-a", "one-b", "two"],
    )


# Where the reader shows the chapter heading's text: the scroller's offsets and the text's box
# against the scroller's visible box.
HEADING_IN_VIEW = """() => {
    const scroller = document.querySelector(".chapter-scroll");
    const range = document.createRange();
    range.selectNodeContents(document.querySelector("[data-chapter-body] h1"));
    const text = range.getBoundingClientRect(), view = scroller.getBoundingClientRect();
    return {chapter: document.querySelector("[data-active-chapter]").dataset.chapter,
            scrollTop: scroller.scrollTop, scrollLeft: scroller.scrollLeft,
            inView: text.left >= view.left && text.right <= view.right &&
                text.top >= view.top && text.bottom <= view.bottom};
}"""


def test_a_whole_note_self_link_scrolls_back_to_its_heading(tmp_path: Path, reader_browser) -> None:
    """The self-link fixture with the Comments bar docked right: review mode makes the body wider
    than the reader, so the reader scrolls down and sideways to the note's link to itself. Clicking it shows the heading; activating it again at the top moves nothing."""
    artifact = artifact_html(json.loads((ROOT / "test" / "fixtures" / "documents" / "self-link.json")
                                 .read_text(encoding="utf-8")))
    errors: list[str] = []
    page, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light")
    frame.evaluate("""async () => {
        obsPages.setPaged(false);
        await obsArtifact.activateChapter("long");
        await obsArtifact.whenChapterReady();
        obsArtifact.openBar("comments", "right");
    }""")
    link = frame.locator('[data-chapter-body] a.internal-link[href="#long"]')
    # Scrolled down and sideways to the link, past the heading's start.
    link.evaluate("""(link) => link.scrollIntoView({block: "center", inline: "center", behavior: "instant"})""")
    assert frame.evaluate(HEADING_IN_VIEW)["scrollLeft"] > 0, "the fixture no longer makes the reader scroll sideways"
    box = link.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    frame.evaluate("globalThis.obsArtifact.whenChapterReady()")
    at_heading = {"chapter": "long", "scrollTop": 0, "scrollLeft": 0, "inView": True}
    assert frame.evaluate(HEADING_IN_VIEW) == at_heading
    link.evaluate("(link) => link.click()")
    frame.evaluate("globalThis.obsArtifact.whenChapterReady()")
    assert frame.evaluate(HEADING_IN_VIEW) == at_heading
    assert frame.locator("[data-floating-window]:visible").count() == 0
    assert errors == []
