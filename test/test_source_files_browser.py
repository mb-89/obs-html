"""The source file row of a note's front matter card in a browser (artifact-ui.md, Comments bar;
cli.md, Source file links).

The shared feature fixture, built with ``--vault-link ../vault`` (conftest.py, feature_artifact),
is written to a folder with its notes in ``../vault`` and opened as a file; the same Document built
without the link shows plain paths, and in the viewer fixture (test/browser/viewer.py) the row shows.
"""
import json
from pathlib import Path

import pytest

from artifacts import artifact_html
from browser.viewer import open_viewer
from conftest import FEATURE_FIXTURE

pytestmark = pytest.mark.browser

PLAIN = "overview"  # A note without frontmatter.
FIELDS = "prose"  # A note with frontmatter.

CARD = """async (slug) => {
    await obsArtifact.activateChapter(slug);
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    const card = document.querySelector(`[data-comment-list] > [data-metadata-card="frontmatter:${slug}"]`);
    const rows = [...(card?.querySelectorAll("[data-metadata-field], [data-metadata-source-file]") || [])];
    const link = card?.querySelector("[data-metadata-source-file] a");
    return {
        card: Boolean(card),
        rows: rows.map((row) => [row.querySelector(".comment-key").textContent,
            row.querySelector(".comment-value").textContent]),
        sourceRows: card ? card.querySelectorAll("[data-metadata-source-file]").length : 0,
        link: link && {href: link.getAttribute("href"), target: link.target, rel: link.rel},
    };
}"""
SOURCE_LINK = f"[data-metadata-card='frontmatter:{PLAIN}'] [data-metadata-source-file] a"


def _site(tmp_path: Path, artifact: str) -> Path:
    """``artifact`` written to ``site/artifact.html`` with each note the Document names in ``vault``."""
    source = json.loads(FEATURE_FIXTURE.read_text(encoding="utf-8"))
    paths = [source["manifest"]["path"], *(record["path"] for record in source["records"]
                                           if record.get("type") == "note" and record.get("path"))]
    for path in paths:
        note = tmp_path / "vault" / path
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(f"The note {path}.\n", encoding="utf-8")
    page = tmp_path / "site" / "artifact.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(artifact, encoding="utf-8")
    return page


def _open(reader_browser, path: Path):
    page = reader_browser.new_page(viewport={"width": 1200, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: message.type == "error" and errors.append(message.text))
    page.goto(path.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsArtifact.whenChapterReady()")
    return page, errors


def test_every_note_has_a_front_matter_card_with_its_source_file_link_last(tmp_path, reader_browser,
                                                                           feature_artifact: str) -> None:
    page, errors = _open(reader_browser, _site(tmp_path, feature_artifact))

    plain = page.evaluate(CARD, PLAIN)
    assert plain["card"] and plain["rows"] == [["Source file", f"{PLAIN}.md"]]
    assert plain["link"] == {"href": f"../vault/{PLAIN}.md", "target": "_blank", "rel": "noopener noreferrer"}
    fields = page.evaluate(CARD, FIELDS)
    assert fields["card"] and len(fields["rows"]) > 1 and fields["sourceRows"] == 1
    assert fields["rows"][-1] == ["Source file", f"{FIELDS}.md"]
    assert errors == []


def test_the_link_opens_the_note_in_a_new_page_and_the_page_stays(tmp_path, reader_browser,
                                                                  feature_artifact: str) -> None:
    path = _site(tmp_path, feature_artifact)
    page, errors = _open(reader_browser, path)
    page.evaluate(CARD, PLAIN)

    with page.context.expect_page() as opened:
        page.locator(SOURCE_LINK).click()
    note = opened.value
    try:
        note.wait_for_load_state()
        assert note.url == (tmp_path / "vault" / f"{PLAIN}.md").as_uri()
        assert f"The note {PLAIN}.md." in note.locator("body").inner_text()
    finally:
        note.close()
    assert page.url.split("#", 1)[0] == path.as_uri()
    assert page.locator("[data-active-chapter]").get_attribute("data-chapter") == PLAIN
    assert page.locator(SOURCE_LINK).is_visible()
    assert errors == []


def test_a_saved_copy_shows_exactly_the_active_notes_row(tmp_path, reader_browser, feature_artifact: str) -> None:
    page, errors = _open(reader_browser, _site(tmp_path, feature_artifact))
    page.evaluate(CARD, PLAIN)
    copy = tmp_path / "site" / "reviewed.html"
    copy.write_text(page.evaluate("obsComments.reviewedHtml()"), encoding="utf-8")

    reopened, reopened_errors = _open(reader_browser, copy)
    for slug in (PLAIN, FIELDS):
        shown = reopened.evaluate(CARD, slug)
        assert shown["sourceRows"] == 1 and shown["rows"][-1] == ["Source file", f"{slug}.md"]
        assert [label for label, _value in shown["rows"]].count("Source file") == 1
    assert errors == reopened_errors == []


def test_without_the_link_the_row_shows_the_plain_path(tmp_path, reader_browser) -> None:
    source = json.loads(FEATURE_FIXTURE.read_text(encoding="utf-8"))
    page, errors = _open(reader_browser, _site(tmp_path, artifact_html(source)))

    plain = page.evaluate(CARD, PLAIN)
    assert plain["card"] and plain["rows"] == [["Source file", f"{PLAIN}.md"]] and plain["link"] is None
    assert errors == []


def test_in_the_viewer_the_row_shows_and_the_page_has_no_error(tmp_path, reader_browser,
                                                               feature_artifact: str) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, feature_artifact, "light")

    shown = frame.locator("html").evaluate(f"(_root) => ({CARD})({json.dumps(PLAIN)})")
    assert shown["card"] and shown["rows"] == [["Source file", f"{PLAIN}.md"]]
    assert errors == []
