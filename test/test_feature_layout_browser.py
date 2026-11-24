"""Native-browser tier: the faults the feature fixture's card group found, each at the widths it
showed at, and the Home chooser's close on a click on the menu or a docked bar.

Reader: whoever changes the card group's width, the review gutter or the breadcrumb choosers.

The design owners are spec/artifact-ui.md (card groups: within the reader and clear of the chapter
controls; Comments: the review gutter; Reading shell: the breadcrumb choosers). The artifact is the
feature fixture (test/fixtures/build_documents.py, features), whose last chapter, references, ends
with the card group. The checks run the covered-control sweep (test/browser/control-coverage.js)
on that chapter alone, in the continuous view, as test_parity_browser.py's sweep does on every
chapter; that sweep found these faults first.
"""
from pathlib import Path

import pytest

from browser import door
from preview import open_preview

COVERAGE = Path(__file__).parent / "browser" / "control-coverage.js"
CARDS = "references"


@pytest.fixture(scope="module")
def opened(tmp_path_factory, shared_reader_browser, feature_artifact: str):
    """The feature fixture opened once in a null-origin preview frame for the module's checks,
    each of which sets the width and the bars it checks; no page error may arise."""
    errors: list[str] = []
    page, frame = open_preview(tmp_path_factory.mktemp("feature-layout"), shared_reader_browser, errors,
                               feature_artifact, "null-origin")
    yield page, frame
    assert errors == []


def faults(opened, width: int, layouts: list) -> list[tuple[str, str]]:
    """Each covered control of the card group's chapter at the width, and what covers it."""
    page, frame = opened
    page.evaluate("width => document.getElementById('artifact').style.width = width", f"{width}px")
    results = frame.locator("html").evaluate(COVERAGE.read_text(encoding="utf-8"), {
        "views": ["continuous"], "layouts": layouts, "firstChapterLayouts": [], "chapters": [CARDS]})
    assert [result["chapter"] for result in results] == [CARDS] * len(layouts)
    return [(fault["control"], fault["covering"]) for result in results for fault in result["faults"]]


@pytest.mark.hot("features-cards-desktop")
@pytest.mark.browser
@pytest.mark.parametrize("width", [1100, 1600])
def test_cards_side_by_side_in_review_mode_keep_their_review_buttons_apart(opened, width: int) -> None:
    found = faults(opened, width, [["comments", "right"]])
    assert [fault for fault in found if fault[0].startswith("button.review-action")] == [], found


@pytest.mark.hot("features-cards-phone")
@pytest.mark.browser
@pytest.mark.parametrize("width", [360, 700])
def test_a_card_metric_at_the_document_end_is_clear_of_the_next_chapter_arrow(opened, width: int) -> None:
    found = faults(opened, width, [None])
    assert [fault for fault in found if fault[0].startswith("a.record-metric-value")] == [], found


@pytest.mark.hot("features-cards-desktop")
@pytest.mark.browser
def test_a_card_quantity_link_scrolls_into_view_with_the_filter_bar_docked_aside(opened) -> None:
    found = faults(opened, 1100, [["filter", "left"], ["filter", "right"]])
    assert [fault for fault in found if fault[0].startswith("a.internal-link")] == [], found


CHOOSER = ".chapter-breadcrumb-chooser"
# The browser door's state the chooser's logic test opens: the feature fixture at 1100 by 800, its card
# group's chapter opened (test/browser/expectations.yaml), as a top-level page.
STATE = "features-cards-desktop"


@pytest.mark.dom
def test_the_home_chooser_closes_on_a_click_on_the_menu_or_a_docked_bar(door_artifact, fake_page) -> None:
    """At Home, Enter on Home opens its chooser; a click on the menu button, on a menu row's dock
    direction or inside a docked bar closes it, as a click anywhere outside the breadcrumbs does.
    The fixture opens in screens, which have no Home (artifact-ui.md, Screens): shown as pages."""
    page, errors = fake_page, []
    page.on("pageerror", lambda error: errors.append(str(error)))
    door.open_recorded(page, STATE, door_artifact(STATE), through=0)
    page.evaluate("() => { obsPages.setPaged(true); obsArtifact.activateChapter('home'); }")
    home = page.locator(".chapter-home-link")
    chooser = page.locator(f"{CHOOSER}[open]")

    def open_chooser() -> None:
        home.focus()
        page.keyboard.press("Enter")
        assert chooser.count() == 1, "Enter on Home at Home opens the top-level chooser"

    open_chooser()
    page.locator("[data-menu-button]").first.click()
    assert chooser.count() == 0, "a click on the menu button closes the chooser"
    open_chooser()
    page.locator('[data-dock-bar="toc"][data-dock-direction="right"]').first.click()
    assert chooser.count() == 0, "a click on a menu row's dock direction closes the chooser"
    page.locator("[data-menu-button]").first.click()  # The menu, which overlays the bar's top, closes.
    open_chooser()
    page.locator("[data-toc-action]").first.click()
    assert chooser.count() == 0, "a click inside a docked bar closes the chooser"
    page.evaluate("() => { obsArtifact.closeBar('toc'); obsPages.setPaged(false); }")
    assert errors == []


# The left edge of each heading's text below the chapter title and of the body text beside it:
# paragraphs, lists and tables that are a chapter's or a heading section's own blocks.
EDGES = """() => {
    const body = document.querySelector('#prose .chapter-body');
    const own = ':is(.chapter-body, .heading-section-body) >';
    const left = (element) => Math.round(element.getBoundingClientRect().left * 10) / 10;
    const headings = [...body.querySelectorAll('h2, h3, h4, h5, h6')].map((heading) => {
        const range = document.createRange();
        range.selectNodeContents(heading);
        return [heading.tagName + ' ' + heading.textContent.trim(), Math.round(range.getBoundingClientRect().left * 10) / 10];
    });
    const blocks = [...body.querySelectorAll(`${own} p, ${own} ul, ${own} ol, ${own} table`)]
        .map((block) => [block.tagName + ' ' + block.textContent.trim().slice(0, 20), left(block)]);
    return {headings, blocks};
}"""


@pytest.mark.hot("features-desktop")
@pytest.mark.browser
@pytest.mark.parametrize("layout", ["screens", "scrolling"])
@pytest.mark.parametrize("width", [390, 1100])
def test_a_headings_text_starts_at_the_left_edge_of_the_body_under_it(opened, layout: str, width: int) -> None:
    """A heading's text and the paragraphs, lists and tables under it share one left edge, in the
    screens and the scrolling layout (artifact-ui.md, Content sections), so no text reads as if it
    belonged to no heading. The layout is the root's screens-mode class (pages.js, reader-startup.js),
    the only switch the stylesheets read; the feature fixture opens in screens."""
    page, frame = opened
    page.evaluate("width => document.getElementById('artifact').style.width = width", f"{width}px")
    frame.evaluate("""screens => {
        document.documentElement.classList.toggle('screens-mode', screens);
        obsArtifact.activateChapter('prose');
    }""", layout == "screens")
    edges = frame.evaluate(EDGES)
    assert {name.split()[0] for name, _ in edges["headings"]} >= {"H2"}, edges
    assert {name.split()[0] for name, _ in edges["blocks"]} >= {"P", "OL", "UL"}, edges
    body = {left for _, left in edges["blocks"]}
    assert len(body) == 1, edges
    assert [(name, left) for name, left in edges["headings"] if abs(left - next(iter(body))) > 0.5] == [], edges
