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

from preview import open_preview

pytestmark = pytest.mark.browser
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


@pytest.mark.parametrize("width", [360, 700])
def test_a_card_metric_at_the_document_end_is_clear_of_the_next_chapter_arrow(opened, width: int) -> None:
    found = faults(opened, width, [None])
    assert [fault for fault in found if fault[0].startswith("a.record-metric-value")] == [], found


def test_a_card_quantity_link_scrolls_into_view_with_the_filter_bar_docked_aside(opened) -> None:
    found = faults(opened, 1100, [["filter", "left"], ["filter", "right"]])
    assert [fault for fault in found if fault[0].startswith("a.internal-link")] == [], found
