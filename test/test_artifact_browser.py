"""Native-browser tier: the fixture artifact's presentation runs in Chromium."""

import pytest

from conftest import FIXTURE, PIXEL
from obs_html import cli


pytestmark = pytest.mark.browser


@pytest.fixture
def artifact_page(fixture_artifact, reader_browser):
    artifact = fixture_artifact
    page = reader_browser.new_page(viewport={"width": 1200, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: message.type == "error" and errors.append(message.text))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    yield page
    page.close()
    assert errors == []


def test_figures_draw_their_plot_and_sankey(artifact_page) -> None:
    artifact_page.evaluate("obsArtifact.activateChapter('appendix')")
    artifact_page.wait_for_selector("#appendix--figure-response.figure-plot-ready")
    assert artifact_page.locator("#appendix--figure-response .scatterlayer .trace").count() == 2
    assert artifact_page.locator("#appendix--figure-flow .sankey-node").count() == 3


def test_base_tables_evaluate_document_records_and_marks_show_their_icon(artifact_page) -> None:
    artifact_page.evaluate("obsArtifact.activateChapter('intro')")
    rows = artifact_page.locator('[data-data-table="intro-base-1"] tbody tr[data-row-key]')
    rows.first.wait_for()
    assert [row.get_attribute("data-row-key") for row in rows.all()] == ["note:beta", "note:alpha"]
    assert artifact_page.locator(".semantic-mark-icon--risk .resource-icon").inner_text() == "!"


def test_the_print_book_holds_every_front_page_and_chapter(artifact_page) -> None:
    artifact_page.evaluate("window.print = () => {}; globalThis.obsPages.exportPDF()")
    text = artifact_page.locator(".print-book").inner_text()
    for expected in ("Fixture document", "Contents", "Abstract", "Intro", "Usage", "Appendix"):
        assert expected in text


def test_everything_on_the_title_page_is_centered(tmp_path, reader_browser) -> None:
    import json
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["manifest"]["metadata"]["subtitle"] = "Bridge ![A](https://badges.test/a.png)"
    document["assets"].append({"id": "a", "href": "https://badges.test/a.png", "mediaType": "image/png",
                               "data": PIXEL})
    document["manifest"]["metadata"]["confidentiality"] = "Internal"
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    artifact = tmp_path / "artifact.html"
    cli.main([str(source), str(artifact)])
    page = reader_browser.new_page(viewport={"width": 1200, "height": 1000})
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    offsets = page.evaluate("""() => {
        const heading = document.querySelector('[data-chapter-body] .document-heading');
        const sheet = heading.getBoundingClientRect();
        const middle = sheet.left + sheet.width / 2;
        const boxes = [];
        const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (!node.textContent.trim()) continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            const box = range.getBoundingClientRect();
            if (box.width) boxes.push([node.textContent.trim(), box.left + box.width / 2 - middle]);
        }
        heading.querySelectorAll('img').forEach(image => {
            const box = image.getBoundingClientRect();
            boxes.push(['img', box.left + box.width / 2 - middle]);
        });
        // The title sheet's running header repeats nothing the cover shows: it holds no text.
        boxes.push(['header: ' + heading.closest('.paper-sheet').querySelector('.paper-header').textContent.trim(), 0]);
        return boxes;
    }""")
    page.close()
    texts = [text for text, _offset in offsets]
    for expected in ("Example org", "Fixture document", "Specification", "Bridge", "img", "Ada, Lin"):
        assert any(expected in text for text in texts), (expected, texts)
    assert [text for text in texts if text.startswith("header:")] == ["header: "]
    off_center = [(text, round(offset)) for text, offset in offsets
                  if abs(offset) > 2 and text not in {"Bridge", "img"}]
    assert off_center == []
    # The subtitle's text and badges are centered together as one line.
    line = [offset for text, offset in offsets if text in {"Bridge", "img"}]
    assert abs(sum(line) / len(line)) < 40


@pytest.mark.parametrize("width, side", [(700, "right"), (700, "left"), (1100, "right"), (1100, "top")])
def test_a_resized_bar_follows_the_pointer(artifact_page, width, side) -> None:
    """A narrow screen insets an overlaid bar beside the chapter arrows; dragging its edge still
    puts that edge under the pointer, as it does for a docked bar."""
    artifact_page.set_viewport_size({"width": width, "height": 800})
    artifact_page.evaluate(f"obsArtifact.openBar('filter', '{side}')")
    handle = artifact_page.locator(f'[data-dock-region="{side}"] [data-dock-resize]')
    start = handle.bounding_box()
    x, y = start["x"] + start["width"] / 2, start["y"] + start["height"] / 2
    shift = {"right": (-40, 0), "left": (40, 0), "top": (0, 40)}[side]
    artifact_page.mouse.move(x, y)
    artifact_page.mouse.down()
    artifact_page.mouse.move(x + shift[0], y + shift[1], steps=4)
    artifact_page.mouse.up()
    edge = artifact_page.locator(f'[data-dock-region="{side}"]').bounding_box()
    inner = {"right": edge["x"], "left": edge["x"] + edge["width"], "top": edge["y"] + edge["height"]}[side]
    pointer = x + shift[0] if side != "top" else y + shift[1]
    assert abs(inner - pointer) <= 1, f"test/test_artifact_browser.py: the {side} bar's edge is at {inner}, the pointer at {pointer}"


@pytest.mark.parametrize("paged", [False, True])
def test_review_gutters_stay_clear_of_the_previous_arrow(artifact_page, paged) -> None:
    """Review mode's gutters (Accept, Reject, Reset) start beyond Previous's pointer area, so
    neither covers the other wherever an item scrolls."""
    artifact_page.set_viewport_size({"width": 1100, "height": 800})
    artifact_page.evaluate(f"obsPages.setPaged({str(paged).lower()}); obsArtifact.openBar('comments', 'right')")
    artifact_page.wait_for_selector(".review-mode .review-gutter")
    arrow = artifact_page.locator(".chapter-nav-zone--previous").bounding_box()
    gutters = artifact_page.eval_on_selector_all(
        ".review-gutter", "gutters => gutters.filter((gutter) => gutter.checkVisibility())"
        ".map((gutter) => gutter.getBoundingClientRect().left)")
    assert gutters, "test/test_artifact_browser.py: the fixture shows no review gutter"
    reach = arrow["x"] + arrow["width"]
    assert min(gutters) >= reach - 0.5, (
        f"test/test_artifact_browser.py: a review gutter starts at {min(gutters)}px, inside "
        f"Previous's pointer area, which ends at {reach}px")
