"""The reading shell's top band, the title page and the chapter walk, in Claude's artifact viewer.

The design owners are spec/artifact-ui.md (Reading shell: the one-row top band;
Paged view: no text twice in one view; chapter navigation: a link to a whole note opens it at its
heading) and obs's spec/design_input/input-model.md (chapters: the table of contents and
previous/next walk the same non-hidden manifest lines). The band's and the self-link's checks are
hot: they open the artifact in the viewer fixture (test/browser/viewer.py) in the real Chromium,
since what they check is layout. The others run on the fake browser (test/browser/browser-door.md),
each from the recording of its state (test/browser/expectations.yaml) at desktop size; the fake has
no frames, so the artifact is the top-level page, as it is in the viewer's frame.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from artifacts import artifact_html
from browser import door
from browser.fake_page import expect
from browser.viewer import open_viewer
from conftest import CORE_ROOT, ROOT
from documents import chapter, document, heading, paragraph

from obs_html.cli import main as obs_html

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
        notices: [...document.querySelectorAll("[data-header-notices] [data-notice-icon]")]
            .filter((icon) => icon.getClientRects().length).map(box),
        menu: box(document.querySelector("[data-menu-button]")),
        arrows: [...document.querySelectorAll("[data-step]")].map(box),
        viewport: innerWidth,
    };
}"""


def open_state(fake_page, door_artifact, state: str, errors: list[str]):
    """The state's artifact as the top-level page of the fake browser, opened from its recording;
    ``errors`` collects page errors and console errors, as the viewer fixture's do."""
    fake_page.on("pageerror", lambda error: errors.append(str(error)))
    fake_page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    door.open_recorded(fake_page, state, door_artifact(state))
    expect(fake_page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    return fake_page


def assert_contents_and_walk(fake_page, door_artifact, state: str, chapters: list[str]) -> None:
    """The contents list exactly ``chapters``, and previous/next walk them both ways from Home."""
    errors: list[str] = []
    frame = open_state(fake_page, door_artifact, state, errors)
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


@pytest.mark.hot
@pytest.mark.browser
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

    squares = [band["home"], *band["notices"], band["menu"]]
    assert len(band["notices"]) == 3
    size = band["menu"]["height"]
    assert [(round(item["width"]), round(item["height"])) for item in squares] == [(round(size),) * 2] * 5
    assert {round(item["top"]) for item in [*squares, band["crumbs"]]} == {round(band["menu"]["top"])}
    assert round(band["crumbs"]["height"]) == round(size)
    assert band["offRow"] == []
    # The notice icons sit directly left of the menu, in severity order.
    lefts = [item["left"] for item in band["notices"]]
    assert lefts == sorted(lefts)
    assert 0 <= band["menu"]["left"] - band["notices"][-1]["right"] <= size / 4
    assert band["crumbs"]["right"] <= lefts[0]
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


def title_page_document() -> dict:
    """The state reading-shell-title-page's Document: a document type, a product and a confidentiality."""
    return document(
        "Product", chapter("one", "One", heading(1, "One"), paragraph("Text.")),
        metadata={"document type": "Design specification", "product": {"name": "Widget"},
                  "confidentiality": "Internal"},
    )


@pytest.mark.dom
def test_the_title_page_shows_the_document_type_once(door_artifact, fake_page) -> None:
    errors: list[str] = []
    frame = open_state(fake_page, door_artifact, "reading-shell-title-page", errors)
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


def walk_document() -> dict:
    """The state reading-shell-walk's Document, as the core emits a manifest with a hidden line."""
    unlisted = {**chapter("secret", "Secret", paragraph("Reached by link only.")), "toc": False}
    return document(
        "Walk",
        chapter("one", "One", paragraph("One."), children=(
            chapter("one-a", "One A", paragraph("One A.")),
            unlisted,
            chapter("one-b", "One B", paragraph("One B.")),
        )),
        chapter("two", "Two", paragraph("Two.")),
    )


@pytest.mark.dom
def test_the_contents_and_previous_next_walk_the_same_chapters(door_artifact, fake_page) -> None:
    """The Document as the core emits a manifest with a hidden line: the hidden line is no chapter,
    and a note the manifest does not list is a `toc: false` chapter, reachable only by its link."""
    assert_contents_and_walk(fake_page, door_artifact, "reading-shell-walk", ["one", "one-a", "one-b", "two"])


def commented_manifest_artifact() -> str:
    """The state reading-shell-commented-manifest's artifact: a vault whose manifest comments lines
    out, built by obs-document and rendered by obs-html in the current folder."""
    folder = Path.cwd()
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
    assert obs_html([str(built), str(folder / "commented.html")]) == 0
    return (folder / "commented.html").read_text(encoding="utf-8")


@pytest.mark.dom
def test_a_manifest_with_commented_lines_walks_its_visible_chapters_end_to_end(door_artifact, fake_page) -> None:
    """The same walk through obs-document and obs-html: the core hides the `%%` manifest lines,
    so the contents and previous/next walk one, one-a, one-b and two."""
    assert_contents_and_walk(fake_page, door_artifact, "reading-shell-commented-manifest",
                             ["one", "one-a", "one-b", "two"])


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


@pytest.mark.hot
@pytest.mark.browser
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


# The active chapter's heading entries in the contents, its collapsible headings, and the text of its
# shown copies (artifact-ui.md, Content sections).
CHAPTER_HEADINGS = """async (slug) => {
    obsPages.setPaged(false);
    await obsArtifact.activateChapter(slug);
    await obsArtifact.whenChapterReady();
    const body = document.querySelector("[data-chapter-body]");
    return {
        contents: [...document.querySelectorAll(`[data-toc-tree] a[href^="#${slug}/"]`)]
            .map((link) => link.getAttribute("href")),
        collapsible: [...body.querySelectorAll("[data-heading-toggle]")].map((button) => button.dataset.label),
        copies: [...body.querySelectorAll("div.embed")].map((copy) => copy.textContent.replace(/\\s+/g, " ").trim()),
    };
}"""


def shown_document(shown: bool) -> dict:
    """m1, with an embed of vision's section Pitch where ``shown``, whose heading has a subheading."""
    pitch = [{**heading(2, "Pitch"), "id": "section-pitch"}, paragraph("For owners."),
             {**heading(3, "Detail"), "id": "section-detail"}, paragraph("Detail of the pitch.")]
    embed = {"type": "embeds", "attrs": {"target": "vision", "chapter": "vision", "heading": "Pitch",
                                         "block": "section-pitch"}, "children": []}
    return document(
        "Shown", chapter("m1", "Milestone 1", heading(1, "Milestone 1"), heading(2, "Own"), paragraph("Own."),
                         *([embed] if shown else []), heading(2, "Next"), paragraph("Next.")),
        chapter("vision", "Vision", heading(1, "Vision"), *pitch))


def without_section_document() -> dict:
    """The state reading-shell-without-section's Document."""
    return shown_document(False)


def shown_section_document() -> dict:
    """The state reading-shell-shown-section's Document."""
    return shown_document(True)


@pytest.mark.dom
def test_a_shown_section_adds_no_heading_to_its_embedding_chapter(door_artifact, fake_page) -> None:
    """m1 with and without an embed of vision's section Pitch, whose heading has a subheading:
    the copy shows, and m1's contents and collapsible headings are the same."""
    seen = []
    for state in ("reading-shell-without-section", "reading-shell-shown-section"):
        errors: list[str] = []
        frame = open_state(fake_page, door_artifact, state, errors)
        seen.append(frame.evaluate(CHAPTER_HEADINGS, "m1"))
        assert errors == []
    without, shown = seen
    assert without["copies"] == [] and shown["copies"] == ["Pitch For owners. Detail Detail of the pitch. Vision"]
    assert shown["contents"] == without["contents"] == ["#m1/own", "#m1/next"]
    assert shown["collapsible"] == without["collapsible"] == ["Own", "Next"]
