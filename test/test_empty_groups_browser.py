"""Native-browser tier: a view's groupOrder, and the listed groups no row has (obsHtml.showEmptyGroups).

The owner is generic-tables.md (the grouping rules, the group anchor rule and pagination): groupOrder
lists a grouped property's values in display order, unlisted values following in the groupBy
direction; with obsHtml.showEmptyGroups a listed value no row has gets a muted caption with the count
(0) and no control, in its place, after the table-local and global filters. The empty groups' pure
layer, emptyGroupLabels, is tested in Node (empty-groups.test.js).
"""
import json

import pytest

from artifacts import artifact_html
from documents import chapter, document as build, heading, node


pytestmark = pytest.mark.browser
ORDER = ["design", "build", "commissioning"]
TASKS = (("t1", "design"), ("t2", "design"), ("t3", "build"), ("t4", "build"))
# Rows of another kind, whose phases groupOrder does not list.
LOOSE = (("l1", "zeta"), ("l2", "alpha"))
GROUPS = "[data-active-chapter] .data-table-group-row"


def _view(**options: object) -> dict:
    view = {"type": "table", "name": "Tasks", "order": ["file.name", "phase"],
            "groupBy": {"property": "phase", "direction": "ASC"}}
    if options:
        view["obsHtml"] = options
    return view


def _base(view: dict, *kinds: str) -> dict:
    """A Base over the records of ``kinds``, the task records by default."""
    filters = {"or": [f'kind == "{kind}"' for kind in kinds or ("task",)]}
    return node("bases", source="", spec={"filters": filters, "views": [view]})


def _record(identifier: str, kind: str, phase: str) -> dict:
    return {"id": identifier, "type": "note", "path": f"{identifier}.md", "fields": {"kind": kind, "phase": phase}}


def _table_chapter(identifier: str, base: dict) -> dict:
    return chapter(identifier, identifier.title(), heading(1, identifier.title()), base)


TABLES = build(
    "Phases",
    _table_chapter("on", _base(_view(groupOrder=ORDER, showEmptyGroups=True))),
    _table_chapter("off", _base(_view(groupOrder=ORDER))),
    _table_chapter("order", _base(_view(groupOrder=ORDER), "task", "loose")),
    _table_chapter("paged", _base(_view(groupOrder=ORDER, showEmptyGroups=True, pageSize=3))),
    _table_chapter("paged-off", _base(_view(groupOrder=ORDER, pageSize=3))),
    records=(*(_record(name, "task", phase) for name, phase in TASKS),
             *(_record(name, "loose", phase) for name, phase in LOOSE)),
    # The reader's filter narrows the task records, so the chapters stay readable.
    metadata={"obsHtml": {"query": {"scope": "records", "where": [{"field": "kind", "equals": "task"}]}}})


def _tree_chapter(identifier: str, phase: str, *children: dict) -> dict:
    return chapter(identifier, identifier.title(), heading(1, identifier.title()),
                   metadata={"phase": phase}, children=children)


# A source tree: the parent chapter's child sits under it, grouped there by its own phase.
TREE = build(
    "Tree",
    chapter("register", "Register", heading(1, "Register"), node("bases", source="", spec={
        "filters": {"or": ['phase == "design"', 'phase == "build"']}, "views": [{
            "type": "table", "name": "Chapters", "order": ["title", "phase"], "obs": {"records": "chapter"},
            "groupBy": {"property": "phase", "direction": "ASC"},
            "obsHtml": {"groupOrder": ORDER, "showEmptyGroups": True}}]})),
    _tree_chapter("parent", "design", _tree_chapter("child", "build")))


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory) -> dict[str, str]:
    folder = tmp_path_factory.mktemp("empty-groups")
    paths = {}
    for name, source in (("tables", TABLES), ("tree", TREE)):
        path = folder / f"{name}.html"
        path.write_text(artifact_html(source), encoding="utf-8")
        paths[name] = path.as_uri()
    return paths


@pytest.fixture
def open_chapter(artifacts, reader_browser):
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    page.set_default_timeout(5000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    opened = set()

    def open_(slug: str, artifact: str = "tables"):
        if artifact not in opened:
            page.goto(artifacts[artifact])
            page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
            page.evaluate("obsPages.setPaged(false)")
            opened.add(artifact)
        page.evaluate(f"obsArtifact.activateChapter({json.dumps(slug)})")
        page.locator("[data-active-chapter] .data-table-shell").wait_for()
        return page

    yield open_
    assert errors == []


# A caption's text is the heading cell's last node, after its expand or collapse control.
CAPTION = "rows => rows.map(row => row.querySelector('th').lastChild.textContent)"


def _captions(page) -> list[str]:
    return page.locator(GROUPS).evaluate_all(CAPTION)


def _empty(page) -> list[str]:
    return page.locator(f"{GROUPS}.data-table-group-row--empty").evaluate_all(CAPTION)


def _set_table_filter(page, expression: str) -> None:
    page.locator("[data-active-chapter] .data-table-shell").evaluate(
        "(shell, expression) => shell.dispatchEvent(new CustomEvent('obs-table-set-filter', {detail: {expression}}))",
        expression)


def test_group_order_lists_its_values_first_and_unlisted_ones_follow_in_the_group_by_direction(open_chapter) -> None:
    page = open_chapter("order")
    assert _captions(page) == ["phase: design (2)", "phase: build (2)", "phase: alpha (1)", "phase: zeta (1)"]


def test_a_listed_group_no_row_has_shows_last_muted_with_a_zero_count_and_no_control(open_chapter) -> None:
    page = open_chapter("on")
    assert _captions(page) == ["phase: design (2)", "phase: build (2)", "phase: commissioning (0)"]
    assert _empty(page) == ["phase: commissioning (0)"]
    empty = page.locator(f"{GROUPS}.data-table-group-row--empty")
    assert empty.locator("button").count() == 0
    colours = page.evaluate("""() => {
        const probe = document.createElement("span");
        probe.style.color = "var(--color-text-muted)";
        document.querySelector("[data-active-chapter]").append(probe);
        const muted = getComputedStyle(probe).color;
        probe.remove();
        const caption = document.querySelector("[data-active-chapter] .data-table-group-row--empty th");
        const other = document.querySelector("[data-active-chapter] .data-table-group-row:not(.data-table-group-row--empty) th");
        return [getComputedStyle(caption).color, muted, getComputedStyle(other).color];
    }""")
    assert colours[0] == colours[1] != colours[2]


def test_without_the_option_a_listed_group_no_row_has_draws_nothing(open_chapter) -> None:
    page = open_chapter("off")
    assert _captions(page) == ["phase: design (2)", "phase: build (2)"]
    assert _empty(page) == []


def test_a_filter_that_removes_every_row_of_a_value_shows_it_with_zero_and_clearing_restores_it(open_chapter) -> None:
    page = open_chapter("on")
    rows = page.locator("[data-active-chapter] [data-row-key]")
    _set_table_filter(page, "NOT phase:build")
    assert _captions(page) == ["phase: design (2)", "phase: build (0)", "phase: commissioning (0)"]
    assert rows.count() == 2
    _set_table_filter(page, "")
    assert _captions(page) == ["phase: design (2)", "phase: build (2)", "phase: commissioning (0)"]
    assert rows.count() == 4
    # The reader's filter, the global one, does the same.
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('NOT phase:build'))")
    page.wait_for_function(f"document.querySelectorAll({json.dumps(GROUPS)})[1]?.textContent.includes('(0)')")
    assert _captions(page) == ["phase: design (2)", "phase: build (0)", "phase: commissioning (0)"]
    page.evaluate("obsArtifact.setFilter(obsQuery.compile(''))")
    page.wait_for_function(f"document.querySelectorAll({json.dumps(GROUPS)})[1]?.textContent.includes('(2)')")
    assert _captions(page) == ["phase: design (2)", "phase: build (2)", "phase: commissioning (0)"]


def test_a_reader_sort_on_the_grouped_property_orders_empty_groups_with_the_others(open_chapter) -> None:
    page = open_chapter("on")
    header = page.locator("[data-active-chapter] th[data-column-key='phase']")
    header.click()  # Ascending: the reader's sort overrides groupOrder.
    assert _captions(page) == ["phase: build (2)", "phase: commissioning (0)", "phase: design (2)"]
    header.click()
    assert _captions(page) == ["phase: design (2)", "phase: commissioning (0)", "phase: build (2)"]
    _set_table_filter(page, "NOT phase:design")
    assert _captions(page) == ["phase: design (0)", "phase: commissioning (0)", "phase: build (2)"]


def test_a_link_to_an_empty_group_lands_on_its_caption(open_chapter) -> None:
    page = open_chapter("on")
    key = page.locator("[data-active-chapter] .data-table-shell").get_attribute("data-data-table")
    anchor = f"table-group--{key}--phase--commissioning"
    page.evaluate("""() => {
        window.revealed = [];
        const reveal = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function (options) {
            window.revealed.push(this.id || this.dataset.dataTable || this.tagName);
            return reveal.call(this, options);
        };
    }""")
    page.evaluate(f"obsArtifact.activateChapter({json.dumps('on/@' + anchor)})")
    page.wait_for_function("window.revealed.length > 0")
    assert page.evaluate("window.revealed") == [anchor]
    assert page.locator(f"#{anchor}").get_attribute("class") == "data-table-group-row data-table-group-row--empty"


def test_an_empty_caption_takes_no_page_slot_and_shows_on_the_page_of_the_row_before_it(open_chapter) -> None:
    def pages(page) -> list[tuple[str, str, list[str]]]:
        """Each page's footer count and page label, and its group captions."""
        footer = page.locator("[data-active-chapter] .data-table-footer")
        shown = []
        while True:
            shown.append((footer.locator(".data-table-count").inner_text(),
                          footer.locator(".data-table-page").inner_text(), _captions(page)))
            following = footer.locator("[aria-label='Next table page']")
            if following.is_disabled():
                return shown
            following.click()

    without = pages(open_chapter("paged-off"))
    with_option = pages(open_chapter("paged"))
    # The same pages and counts as without the option: the caption takes no slot and no item.
    assert [(count, label) for count, label, _ in with_option] == [(count, label) for count, label, _ in without] == [
        ("4 of 4 items", "Page 1 of 2"), ("4 of 4 items", "Page 2 of 2")]
    # Three rows on page one, the fourth (build) on page two, with the empty caption after it.
    assert [captions for _, _, captions in with_option] == [
        ["phase: design (2)", "phase: build (2)"], ["phase: build (2)", "phase: commissioning (0)"]]
    # With nothing before it, an empty caption shows on page one.
    page = open_chapter("paged")
    _set_table_filter(page, "NOT phase:design")
    assert _captions(page) == ["phase: design (0)", "phase: build (2)", "phase: commissioning (0)"]


def test_a_source_tree_parent_never_gets_empty_siblings_and_removing_the_level_draws_none(open_chapter) -> None:
    page = open_chapter("register", "tree")
    assert _captions(page) == ["phase: design (1)", "phase: build (1)", "phase: build (0)", "phase: commissioning (0)"]
    child = page.locator(f"{GROUPS}").nth(1)
    assert "--row--" in child.get_attribute("id") and not child.evaluate(
        "row => row.classList.contains('data-table-group-row--empty')")
    assert _empty(page) == ["phase: build (0)", "phase: commissioning (0)"]
    page.locator("[data-active-chapter] .data-table-options-toggle").click()
    page.locator("[data-active-chapter] .data-table-options .filter-pill", has_text="Group / Sort").click()
    page.locator("[data-active-chapter] [title='Remove group by phase']").click()
    assert _captions(page) == []


def test_the_query_view_refuses_the_option_without_group_order_and_keeps_the_last_valid_table(open_chapter) -> None:
    page = open_chapter("on")
    spec = {"filters": {"or": ['kind == "task"']}, "views": [_view(showEmptyGroups=True)]}
    page.locator("[data-active-chapter] .data-table-options-toggle").click()
    page.locator("[data-active-chapter] .data-table-options .filter-pill", has_text="Query view").click()
    editor = page.locator("[data-active-chapter] .data-table-query-editor")
    editor.fill(json.dumps(spec))
    editor.blur()
    alert = page.locator("[data-active-chapter] [role='alert']", has_text="showEmptyGroups")
    assert "obsHtml.showEmptyGroups requires obsHtml.groupOrder." in alert.inner_text()
    assert _captions(page) == ["phase: design (2)", "phase: build (2)", "phase: commissioning (0)"]
