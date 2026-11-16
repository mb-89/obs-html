"""Native-browser tier: a two-column block stands side by side at its weights and stacks in a narrow
reader, in every layout and on paper, and the reader's tools reach the blocks in its columns.

Reader: whoever changes columns.css, render.py's _columns, or a reader tool that walks a chapter's blocks.

The design owners are obs capabilities/columns (the block) and spec/artifact-ui.md (weighted columns
stack only where the reader's width cannot hold readable columns). The artifact is the columns
fixture Document (test/fixtures/build_documents.py, columns), whose first chapter holds a 1:2 block
with a card on the left and a heading, a marked paragraph and a Base table on the right.
"""
import copy
import json

import pypdfium2 as pdfium
import pytest

from artifacts import artifact_html
from conftest import ROOT
from obs_html import cli

pytestmark = pytest.mark.browser
FIXTURE = ROOT / "test" / "fixtures" / "documents" / "columns.json"
COLUMNS = json.loads(FIXTURE.read_text(encoding="utf-8"))
BLOCK = '[data-chapter-body] [data-content-columns="1:2"]'
COLUMN_BOXES = f"""async () => {{
    await obsArtifact.activateChapter("columns");
    await obsArtifact.whenChapterReady();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return [...document.querySelector('{BLOCK}').children].map((column) => {{
        const box = column.getBoundingClientRect();
        return {{left: box.left, top: box.top, width: box.width, bottom: box.bottom}};
    }});
}}"""


def _with_layout(layout: str | None) -> dict:
    source = copy.deepcopy(COLUMNS)
    if layout:
        source["manifest"]["metadata"]["obsHtml"] = {"layout": layout}
    return source


def _open(tmp_path, browser, source: dict, width: int):
    artifact = tmp_path / "artifact.html"
    artifact.write_text(artifact_html(source), encoding="utf-8")
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    return page, errors, artifact


def _side_by_side(columns: list[dict]) -> bool:
    first, second = columns
    return abs(first["top"] - second["top"]) < 1 and first["left"] + first["width"] <= second["left"]


def _stacked(columns: list[dict]) -> bool:
    first, second = columns
    return abs(first["left"] - second["left"]) < 1 and first["bottom"] <= second["top"]


def test_a_weighted_block_stands_at_its_ratio_and_stacks_in_a_narrow_reader(tmp_path, reader_browser) -> None:
    """At 1280 px the columns are side by side at 1:2; narrowing the reader alone, the chapter scroll,
    stacks them at the same viewport; at 390 px they are stacked, first above second, and nothing scrolls
    sideways."""
    page, errors, _ = _open(tmp_path, reader_browser, COLUMNS, 1280)
    wide = page.evaluate(COLUMN_BOXES)
    page.evaluate("() => { document.querySelector('.chapter-scroll').style.width = '600px'; }")
    narrowed = page.evaluate(COLUMN_BOXES)
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("() => { document.querySelector('.chapter-scroll').style.width = ''; }")
    phone = page.evaluate(COLUMN_BOXES)
    sideways = page.evaluate("""() => [document.documentElement, document.querySelector('.chapter-scroll')]
        .map((element) => element.scrollWidth - element.clientWidth)""")

    assert _side_by_side(wide), wide
    assert wide[1]["width"] / wide[0]["width"] == pytest.approx(2, abs=0.01)
    assert _stacked(narrowed), narrowed
    assert _stacked(phone), phone
    assert sideways == [0, 0]
    assert errors == []


@pytest.mark.parametrize("layout", ["paged", "scrolling", "screens"])
def test_the_block_stands_side_by_side_in_each_layout(tmp_path, reader_browser, layout: str) -> None:
    page, errors, _ = _open(tmp_path, reader_browser, _with_layout(layout), 1280)
    columns = page.evaluate(COLUMN_BOXES)
    shown = page.evaluate(f"() => document.querySelector('{BLOCK}').checkVisibility()")

    assert shown and _side_by_side(columns), (layout, columns)
    assert errors == []


COMMENT_ON_THE_RIGHT = f"""async () => {{
    await obsArtifact.activateChapter("columns");
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const paragraph = document.querySelector('{BLOCK} > :last-child [data-mark-kind] .semantic-mark-content');
    const range = document.createRange();
    range.setStart(paragraph.firstChild, 0);
    range.setEnd(paragraph.firstChild, 8);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    await new Promise((resolve) => setTimeout(resolve, 0));
    document.querySelector("[data-comment-add]").click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return {{target: obsComments.data.annotations.at(-1).target,
             node: paragraph.closest("[data-node-id]").dataset.nodeId}};
}}"""
ANCHORED = f"""async (node) => {{
    await obsArtifact.activateChapter("columns");
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const block = document.querySelector(`[data-chapter-body] [data-node-id="${{node}}"]`);
    return {{
        column: block.closest('{BLOCK} > *') === document.querySelector('{BLOCK}').lastElementChild,
        targets: obsComments.data.annotations.map((annotation) => annotation.target),
        painted: [...CSS.highlights.get("obs-comments")].map((painted) => block.contains(painted.startContainer)),
    }};
}}"""


def test_a_comment_on_a_block_in_the_right_column_anchors_to_it_after_a_reload(tmp_path, reader_browser) -> None:
    page, errors, artifact = _open(tmp_path, reader_browser, COLUMNS, 1280)
    made = page.evaluate(COMMENT_ON_THE_RIGHT)
    reviewed = tmp_path / "reviewed.html"
    reviewed.write_text(page.evaluate("obsComments.reviewedHtml()"), encoding="utf-8")
    reopened = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    reopened.on("pageerror", lambda error: errors.append(str(error)))
    reopened.goto(reviewed.as_uri())
    reopened.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    shown = reopened.evaluate(ANCHORED, made["node"])

    assert made["target"]["chapter"] == "columns" and made["target"]["node"] == made["node"]
    assert made["target"]["quote"] == "Question"
    assert shown["column"]
    assert [target["node"] for target in shown["targets"]] == [made["node"]]
    assert shown["painted"] == [True]
    assert errors == []


SEARCH_AND_FILTER = """async () => {
    const input = document.querySelector("[data-search-input]");
    obsArtifact.openBar("search");
    input.value = "Second right";
    input.dispatchEvent(new Event("input", {bubbles: true}));
    await new Promise((resolve) => setTimeout(resolve, 0));
    const results = [...document.querySelectorAll("[data-search-result]")].map((link) => link.dataset.searchResult);
    await obsArtifact.activateSearchResult("more", obsQuery.compile(input.value), {kind: "chapter"});
    const hits = [...document.querySelectorAll("[data-chapter-body] .search-highlight")]
        .map((hit) => [hit.textContent, Boolean(hit.closest(".content-column"))]);
    obsFilter.setExpression("mark.open_point: columns");
    const marked = obsArtifact.documentRecords().filter((record) => obsArtifact.matchesFilter(record))
        .map((record) => record.slug);
    obsFilter.setExpression("");
    return {results, hits, marked};
}"""


def test_search_finds_a_columns_text_and_the_filter_reads_its_marked_paragraph(tmp_path, reader_browser) -> None:
    page, errors, _ = _open(tmp_path, reader_browser, COLUMNS, 1280)
    found = page.evaluate(SEARCH_AND_FILTER)

    assert found["results"] == ["more"]
    assert ["Second", True] in found["hits"] and ["right", True] in found["hits"]
    assert found["marked"] == ["columns"]
    assert errors == []


@pytest.fixture(scope="module")
def printed(pdf_browser, tmp_path_factory):
    """The columns fixture printed once by this adapter's own PDF path."""
    pdf = tmp_path_factory.mktemp("columns-printed") / "columns.pdf"
    assert cli.main([str(FIXTURE), str(pdf)]) == 0
    return pdf


def _box(document, text: str) -> tuple[int, tuple[float, float, float, float]]:
    """The page index and the box (left, bottom, right, top, in points) of the first ``text``."""
    for index in range(len(document)):
        page = document[index].get_textpage()
        found = page.search(text, match_case=True, match_whole_word=True).get_next()
        if found:
            return index, page.get_charbox(found[0])
    raise AssertionError(f"{text!r} is on no page of the printed PDF")


def test_a_printed_block_stays_side_by_side(printed) -> None:
    """On paper the card's title, left, and the right column's marked paragraph stand side by side: the
    paragraph starts right of the card and above the card's end."""
    document = pdfium.PdfDocument(str(printed))
    (left_page, left), (right_page, right) = _box(document, "Coverage"), _box(document, "Question")
    _, below = _box(document, "See")  # The card body's link, the card's last line.

    assert left_page == right_page
    assert right[0] > left[2] + 72  # The right column starts well right of the card's title.
    assert right[1] > below[1]  # The paragraph stands higher on the page than the card's last line.


def test_in_review_mode_the_columns_stand_one_below_the_other(tmp_path, reader_browser) -> None:
    """The one review gutter left of the prose column holds every item's controls, so the columns stack
    there, as card groups do, and their review buttons never share a line."""
    page, errors, _ = _open(tmp_path, reader_browser, COLUMNS, 1280)
    reading = page.evaluate(COLUMN_BOXES)
    page.evaluate("obsArtifact.openBar('comments', 'right')")
    reviewing = page.evaluate(COLUMN_BOXES)

    assert _side_by_side(reading), reading
    assert _stacked(reviewing), reviewing
    assert errors == []
