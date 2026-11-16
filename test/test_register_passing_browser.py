"""Native-browser tier: a view's passing rows fold into one count line (obsHtml.passing).

The owners are generic-tables.md (Query and filtering: the fold, its count line and the all-pass
sentence; Columns and cells: the footer count while folded), input-model.md (Compact declarative
table presentation: the option) and artifact-ui.md (Dock menu: a Search hit opens the fold that
holds its row). A view lists the rows that do not pass; the passing ones fold into one line under
the table, ``<p> of <t> <label>``, which one button opens in place; when every row passes, the line
is the sentence ``All <t> <label>.`` in the positive tone. The fold's pure layer, foldPassingRows and
passingCaption, is tested in Node (passing-rows.test.js).
"""
import json
import pytest

from artifacts import artifact_html
from documents import card_document, chapter, document as build, heading, node


pytestmark = pytest.mark.browser
FAILING = {7, 200}
PASSING = {"filters": 'status == "verified"', "label": "verified"}
SHELL = "[data-active-chapter] .data-table-shell"
LINE = f"{SHELL} .data-table-passing"
ROWS = f"{SHELL} tbody tr[data-row-key]"
COUNT = f"{SHELL} .data-table-count"
GROUPS = f"{SHELL} .data-table-group-row"
ORDER = ["design", "build", "commissioning"]


def _record(index: int, kind: str = "check", status: str = "verified", phase: str = "") -> dict:
    fields = {"kind": kind, "code": f"{kind}-{index:03}", "status": status, **({"phase": phase} if phase else {})}
    return {"id": f"{kind}-{index:03}", "type": "note", "path": f"{kind}-{index:03}.md", "fields": fields}


CHECKS = [_record(index, status="open" if index in FAILING else "verified") for index in range(266)]
GREEN = [_record(index, "green") for index in range(264)]
# Grouped by phase: design all passes, build has one failing row, commissioning has no row.
PHASED = [_record(0, "phased", phase="design"), _record(1, "phased", phase="design"),
          _record(2, "phased", phase="build"), _record(3, "phased", "open", "build")]


def _view(name: str = "Checks", **options: object) -> dict:
    return {"type": "table", "name": name, "order": ["code", "status"],
            "obsHtml": {"pageSize": 300, **options}}


def _register(view: dict, records: list[dict]) -> dict:
    """A register of one .base file, its one view's rows as the core selected them."""
    base = {"filters": f'kind == "{records[0]["fields"]["kind"]}"', "views": [view]}
    return node("registers", target="checks.base", heading="", base=base, view=None,
                rows=[[record["id"] for record in records]])


def _fence(view: dict, kind: str) -> dict:
    return node("bases", source="", spec={"filters": f'kind == "{kind}"', "views": [view]})


def _table_chapter(identifier: str, table: dict) -> dict:
    return chapter(identifier, identifier.title(), heading(1, identifier.title()), table)


def _grouped(**options: object) -> dict:
    return {**_view("Phased", groupOrder=ORDER, **options), "groupBy": {"property": "phase", "direction": "ASC"}}


# The metric counts the passing checks and drills down into the folded register.
METRIC = {"key": "verified", "label": "Verified", "link": "#register",
          "where": [{"field": "kind", "equals": "check"}, {"field": "status", "equals": "verified"}]}
CARD = {"title": "Checks", "metrics": [METRIC]}
CARDS = node("cards-metrics", source=json.dumps({"version": 1, "cards": [CARD]}), spec={"version": 1, "cards": [CARD]})
CARDS["children"] = [card_document(CARD, [])]

TABLES = build(
    "Passing",
    chapter("overview", "Overview", heading(1, "Overview"), CARDS),
    _table_chapter("register", _register(_view(passing=PASSING), CHECKS)),
    _table_chapter("green", _fence(_view("Green", passing=PASSING), "green")),
    _table_chapter("plain", _register(_view(), CHECKS)),
    _table_chapter("paged", _register(_view(passing=PASSING, pageSize=20), CHECKS)),
    _table_chapter("phased", _fence(_grouped(passing=PASSING, showEmptyGroups=True), "phased")),
    _table_chapter("empty", _fence(_view("Empty", passing=PASSING), "none")),
    records=(*CHECKS, *GREEN, *PHASED),
    # The reader's Filter narrows the check records: the global Filter of the counts' test.
    metadata={"obsHtml": {"query": {"scope": "records", "where": [{"field": "kind", "equals": "check"}]}}})


@pytest.fixture(scope="module")
def artifact(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("passing") / "passing.html"
    path.write_text(artifact_html(TABLES), encoding="utf-8")
    return path.as_uri()


@pytest.fixture
def open_chapter(artifact, reader_browser):
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    page.set_default_timeout(5000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact)
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false)")

    def open_(slug: str, table: bool = True):
        page.evaluate(f"obsArtifact.activateChapter({json.dumps(slug)})")
        if table:
            page.locator(f"{SHELL} tbody").wait_for(state="attached")
        return page

    yield open_
    assert errors == []


def _keys(page) -> list[str]:
    return page.locator(ROWS).evaluate_all("rows => rows.filter(row => !row.hidden).map(row => row.dataset.rowKey)")


def _state(page) -> tuple[int, str, str, str]:
    """The listed rows, the footer count, the line and its aria-expanded state."""
    line = page.locator(LINE)
    return (len(_keys(page)), page.locator(COUNT).inner_text(), line.inner_text(), line.get_attribute("aria-expanded"))


# The rows the print book holds for the register chapter, over all its sheets.
PRINTED = """book => [...book.querySelectorAll(
    "[data-page-chapter='register'] table[data-review-table] tbody tr[data-row-key]")].map(row => row.dataset.rowKey)"""
# A caption's text is the heading cell's last node, after its expand or collapse control.
CAPTION = "rows => rows.map(row => row.querySelector('th').lastChild.textContent)"


def test_a_register_lists_its_failing_rows_and_folds_the_passing_ones_into_one_line(open_chapter) -> None:
    page = open_chapter("register")
    assert _state(page) == (2, "2 of 2 items", "264 of 266 verified", "false")
    assert _keys(page) == ["note:check-007", "note:check-200"]
    assert page.locator(LINE).evaluate("line => line.tagName") == "BUTTON"
    page.locator(LINE).click()
    assert _state(page) == (266, "266 of 266 items", "264 of 266 verified", "true")
    # Back in their sorted place: the view's source order, the failing rows among them.
    assert _keys(page)[7] == "note:check-007" and _keys(page)[0] == "note:check-000"
    page.locator(LINE).click()
    assert _state(page) == (2, "2 of 2 items", "264 of 266 verified", "false")


def test_the_line_opens_and_closes_from_the_keyboard(open_chapter) -> None:
    page = open_chapter("register")
    page.locator(LINE).focus()
    page.keyboard.press("Enter")
    assert _state(page)[::3] == (266, "true")
    page.keyboard.press("Space")
    assert _state(page)[::3] == (2, "false")


def test_the_counts_follow_a_table_local_filter(open_chapter) -> None:
    page = open_chapter("register")
    page.evaluate(f"""document.querySelector({json.dumps(SHELL)}).dispatchEvent(new CustomEvent(
        "obs-table-set-filter", {{detail: {{expression: "NOT code: /^check-000$/"}}}}))""")
    page.locator(LINE).click()  # the set-filter event opened the fold; fold it again
    assert _state(page) == (2, "2 of 2 items", "263 of 265 verified", "false")
    # The reader's own typing, as the filter input's input event delivers it: the fold stays.
    page.locator(f"{SHELL} input[aria-label='Filter table']").evaluate(
        "input => { input.value = 'NOT code: /^check-001$/'; input.dispatchEvent(new Event('input')); }")
    assert _state(page) == (2, "2 of 2 items", "263 of 265 verified", "false")
    page.locator(LINE).click()
    assert _state(page) == (265, "265 of 266 items", "263 of 265 verified", "true")


def test_the_counts_follow_the_global_filter(open_chapter) -> None:
    page = open_chapter("register")
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('NOT code: /^check-00[0-4]$/'))")
    page.wait_for_function(f"document.querySelector({json.dumps(LINE)}).textContent.startsWith('259')")
    assert _state(page) == (2, "2 of 2 items", "259 of 261 verified", "false")
    page.locator(LINE).click()
    assert _state(page) == (261, "261 of 261 items", "259 of 261 verified", "true")


def test_an_all_passing_view_shows_one_positive_sentence_and_no_rows(open_chapter) -> None:
    page = open_chapter("green")
    assert page.locator(f"{SHELL} tbody tr").count() == 0
    line = page.locator(LINE)
    assert line.inner_text() == "All 264 verified."
    tone = page.evaluate(f"""() => {{
        const probe = document.createElement("span");
        probe.style.color = "var(--color-positive)";
        document.body.append(probe);
        const expected = getComputedStyle(probe).color;
        probe.remove();
        return [getComputedStyle(document.querySelector({json.dumps(LINE)})).color, expected];
    }}""")
    assert tone[0] == tone[1]
    line.click()
    assert _state(page)[::3] == (264, "true")


def test_no_row_and_no_count_line_takes_the_positive_tone(open_chapter) -> None:
    page = open_chapter("register")
    page.locator(LINE).click()
    positive = page.evaluate("""() => {
        const probe = document.createElement("span");
        probe.style.color = "var(--color-positive)";
        document.body.append(probe);
        const color = getComputedStyle(probe).color;
        probe.remove();
        return color;
    }""")
    colors = page.locator(f"{ROWS} td, {LINE}").evaluate_all("cells => cells.map(cell => getComputedStyle(cell).color)")
    assert colors and positive not in colors


def test_a_search_for_a_folded_row_opens_the_fold_and_highlights_it(open_chapter) -> None:
    page = open_chapter("green")
    page.evaluate("obsArtifact.openBar('search')")
    page.locator("[data-search-input]").fill("green-150")
    page.keyboard.press("F3")
    page.locator(f"{SHELL} tr[data-row-key='note:green-150'] .search-highlight").wait_for()
    assert page.locator(LINE).get_attribute("aria-expanded") == "true"
    page_label = page.locator(f"{SHELL} .data-table-footer").inner_text()
    assert "264 of 264 items" in page_label


def test_activating_a_search_hit_on_a_folded_row_opens_the_fold_on_the_page_that_holds_it(open_chapter) -> None:
    page = open_chapter("paged")
    assert _state(page) == (2, "2 of 2 items", "264 of 266 verified", "false")
    page.evaluate("obsArtifact.openBar('search')")
    page.locator("[data-search-input]").fill("check-150")
    index = page.evaluate("obsSearch.hits.findIndex(hit => hit.slug === 'paged')")
    assert index >= 0
    page.locator(f"[data-search-hit='{index}']").click()
    page.locator(f"{SHELL} tr[data-row-key='note:check-150'] .search-highlight").wait_for()
    footer = page.locator(f"{SHELL} .data-table-footer").inner_text()
    assert "266 of 266 items" in footer and "Page 8 of 14" in footer


def test_a_metric_drill_down_into_a_folded_view_shows_exactly_the_rows_it_counted(open_chapter) -> None:
    page = open_chapter("overview", table=False)
    counted = page.evaluate("""query => obsRecordMetrics.select(query, "")
        .map(record => `note:${record.slug}`).sort()""", {"where": METRIC["where"]})
    assert len(counted) == 264
    page.locator("[data-active-chapter] [data-record-metric='0'] .record-metric-value").click()
    page.locator(f"{SHELL} tbody tr[data-row-key]").first.wait_for()
    assert sorted(_keys(page)) == counted
    assert page.locator(LINE).get_attribute("aria-expanded") == "true"


def test_a_folded_table_prints_its_line_and_no_passing_rows(open_chapter) -> None:
    page = open_chapter("register")
    page.evaluate("window.print = () => {}; obsPages.exportPDF()")
    book = page.locator(".print-book")
    book.locator(".data-table-passing").first.wait_for(state="attached")
    printed = book.evaluate(PRINTED)
    assert sorted(printed) == ["note:check-007", "note:check-200"]
    assert book.locator("[data-page-chapter='register'] .data-table-passing").inner_text() == "264 of 266 verified"


def test_a_table_the_reader_opened_prints_its_rows(open_chapter) -> None:
    page = open_chapter("register")
    page.locator(LINE).click()
    page.evaluate("window.print = () => {}; obsPages.exportPDF()")
    book = page.locator(".print-book")
    book.locator("table[data-review-table]").first.wait_for(state="attached")
    assert len(book.evaluate(PRINTED)) == 266


def test_a_declared_group_whose_rows_all_pass_folds_with_them_and_a_true_hole_shows_zero(open_chapter) -> None:
    """With obsHtml.showEmptyGroups, a value no row has still shows (0); a value whose rows all pass
    has rows, folded into the line, so it draws no caption while folded (no false hole)."""
    page = open_chapter("phased")
    assert page.locator(GROUPS).evaluate_all(CAPTION) == ["phase: build (1)", "phase: commissioning (0)"]
    assert _keys(page) == ["note:phased-003"]
    assert page.locator(LINE).inner_text() == "3 of 4 verified"
    page.locator(LINE).click()
    assert page.locator(GROUPS).evaluate_all(CAPTION) == [
        "phase: design (2)", "phase: build (2)", "phase: commissioning (0)"]


def test_a_view_with_no_rows_keeps_todays_empty_result_without_a_line(open_chapter) -> None:
    page = open_chapter("empty")
    assert page.locator(f"{SHELL} tbody tr").count() == 0
    assert page.locator(LINE).is_hidden()
    assert page.locator(COUNT).inner_text() == "0 of 0 items"


def test_a_view_without_the_option_lists_every_row_and_draws_no_line(open_chapter) -> None:
    page = open_chapter("plain")
    assert len(_keys(page)) == 266
    assert page.locator(COUNT).inner_text() == "266 of 266 items"
    assert page.locator(f"{SHELL} .data-table-passing").count() == 0


def test_the_query_view_reports_a_bad_passing_filter_and_keeps_the_last_valid_rows(open_chapter) -> None:
    page = open_chapter("green")
    spec = {"filters": 'kind == "green"', "views": [_view("Green", passing={**PASSING, "filters": "status > 3"})]}
    page.locator(f"{SHELL} .data-table-options-toggle").click()
    page.locator(f"{SHELL} .data-table-options .filter-pill", has_text="Query view").click()
    editor = page.locator(f"{SHELL} .data-table-query-editor")
    editor.fill(json.dumps(spec))
    editor.blur()
    alert = page.locator(f"{SHELL} [role='alert']", has_text="passing")
    assert "views.0.obsHtml.passing.filters: unsupported definition value." in alert.inner_text()
    missing = {"filters": 'kind == "green"', "views": [_view("Green", passing={"filters": PASSING["filters"]})]}
    editor.fill(json.dumps(missing))
    editor.blur()
    assert "views.0.obsHtml.passing: missing label." in page.locator(
        f"{SHELL} [role='alert']", has_text="missing label").inner_text()
    if page.locator(f"{SHELL} .data-table-options").is_hidden():
        page.locator(f"{SHELL} .data-table-options-toggle").click()
    page.locator(f"{SHELL} .data-table-options .filter-pill", has_text="Query view").click()
    assert page.locator(LINE).inner_text() == "All 264 verified."
