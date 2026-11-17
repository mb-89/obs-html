"""Native-browser tier: one line per table row (artifact.tableRowsOneLine), at 390 x 844.

The owners are generic-tables.md (Columns and cells, One line per row; Pipe tables; group captions)
and architecture.md (Rendering and runtime: the option is on as packaged by the owner's decision of
17 Nov 2026, and off a page is byte for byte as before, test_features.py and unchanged_output.py).
Built with the packaged settings, every collapsed data row of a Base table or a pipe table and every
group caption is one line high on screen, shown as pages and in the continuous view; a cut cell
keeps its whole text in the page and as its title; a row with a cut cell has a disclosure that shows
its cells in full; Search and Comments open the row that holds a hit; the print book shows every
cell in full. With the option off, rows and captions wrap as before. The decisions' pure layers are
tested in Node (table-rows-one-line.test.js).
"""
import dataclasses
import json

import pytest

from artifacts import artifact_html
from obs_html.config import load_config
from documents import chapter, document as build, field_nodes, heading, node, paragraph, text


pytestmark = pytest.mark.browser
PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 900}
SHELL = "[data-active-chapter] .data-table-shell"
BASE_ROWS = f"{SHELL} tbody tr[data-row-key]"
GROUP_ROWS = f"{SHELL} tbody tr.data-table-group-row"
PIPE = "[data-active-chapter] table[data-node-id='table-long']"
FIVE = "[data-active-chapter] table[data-node-id='table-five']"


def _long(word: str) -> str:
    """400 characters of prose whose one word ``word`` sits near its end, in the part a cut hides."""
    start = "Each rule of this register reads as one sentence that runs on past any phone's width. " * 4
    filler = (start + "x" * 400)[:400 - len(word) - 10]
    return f"{filler} {word} at end."[:400].ljust(400, ".")


BASE_WORD, PIPE_WORD = "zanzibar", "wombat"
SUMMARY = _long(BASE_WORD)
CONTENTS_SUMMARY = _long("quokka")
PIPE_TEXT = _long(PIPE_WORD)
PHASE = "a phase whose caption runs far wider than the table it groups on any phone screen at all"
RULE = {"kind": "rule", "phase": PHASE}
LINK_A = {"type": "text", "attrs": {"link": "ada"}, "children": [], "text": "Ada"}
LINK_B = {"type": "text", "attrs": {"link": "bo"}, "children": [], "text": "Bo"}
PROPERTIES = {"lead": {"displayName": "Lead", "obsHtml": {"reference": {"label": ["file.name"]}}}}


def _base(identifier: str, column: str = "summary", **view: object) -> dict:
    """Two columns, so a table fits a phone (three columns' minimum widths do not, with or without the option)."""
    spec = {"filters": 'kind == "rule"', "properties": PROPERTIES,
            "views": [{"type": "table", "name": "Rules", "order": ["file.name", column], **view}]}
    return {**node("bases", source="", spec=spec), "id": f"bases-{identifier}"}


def _table_chapter(identifier: str, base: dict) -> dict:
    return chapter(identifier, identifier.title(), heading(1, identifier.title()), base)


def _note(identifier: str, metadata: dict, body: str, fields: dict | None = None, toc: bool = False) -> dict:
    return {**chapter(identifier, identifier.title(), paragraph(body), metadata=metadata, fields=fields), "toc": toc}


def _cell(*children: str | dict, header: bool = False) -> dict:
    return {"type": "table-cell", "attrs": {"header": True} if header else {},
            "children": [text(child) if isinstance(child, str) else child for child in children]}


def _row(identifier: str, *cells: dict) -> dict:
    return {"type": "table-row", "attrs": {}, "children": list(cells), "id": identifier}


def _pipe(identifier: str, *rows: dict) -> dict:
    return {"type": "table", "attrs": {}, "children": list(rows), "id": identifier}


BREAK = {"type": "break", "attrs": {}, "children": []}
PIPES = chapter(
    "pipes", "Pipes", heading(1, "Pipes"),
    _pipe("table-long",
          _row("row-head", _cell("Key", header=True), _cell("Meaning", header=True)),
          _row("row-long", _cell("long"), _cell(PIPE_TEXT)),
          _row("row-link", _cell("link"), _cell("See ", LINK_A, BREAK, "and a second line after the hard break")),
          _row("row-short", _cell("short"), _cell("Fits."))),
    _pipe("table-five",
          _row("five-head", *(_cell(name, header=True) for name in ("Gate", "When", "Runs", "Fails", "Note"))),
          _row("five-one", *(_cell(f"{name} {SUMMARY[:120]}") for name in ("Gate", "When", "Runs", "Fails", "Note")))))
TREE = chapter("tree", "Tree", heading(1, "Tree"), {**node("bases", source="", spec={
    "filters": {"or": ['kind == "branch"']},
    "views": [{"type": "table", "name": "Branches", "order": ["title", "summary"], "obs": {"records": "chapter"}}]}),
    "id": "bases-tree"})


def _branch(identifier: str, summary: str, *children: dict) -> dict:
    return chapter(identifier, identifier.title(), heading(1, identifier.title()),
                   metadata={"kind": "branch", "summary": summary}, children=children)


def _record(identifier: str, fields: dict) -> dict:
    return {"id": identifier, "type": "note", "path": f"{identifier}.md", "fields": fields}


T1 = {**RULE, "summary": SUMMARY}
C1 = {**RULE, "summary": CONTENTS_SUMMARY}
R2 = {**RULE, "summary": "Fits.", "lead": ["[[ada]]", "[[bo]]"]}
# The two references' field nodes, links as the core parses each item.
LEADS = {"lead.0": [LINK_A], "lead.1": [LINK_B]}
DOCUMENT = build(
    "Rows",
    _table_chapter("grouped", _base("grouped", groupBy={"property": "phase", "direction": "ASC"})),
    _table_chapter("fields", _base("fields", obsHtml={"detailFields": []})),
    _table_chapter("paged", _base("paged", obsHtml={"pageSize": 2})),
    _table_chapter("references", _base("references", "lead")),
    PIPES,
    TREE,
    _branch("parent", SUMMARY, _branch("child", CONTENTS_SUMMARY)),
    _note("c1", C1, "A rule in the contents.", toc=True),
    _note("t1", T1, "The first rule's text."),
    _note("r2", R2, "The second rule's text.", LEADS),
    _note("ada", {"kind": "person"}, "Ada."),
    _note("bo", {"kind": "person"}, "Bo."),
    records=(_record("c1", C1), _record("t1", T1),
             # The two references are links, as the core parses `[[ada]], [[bo]]`.
             {**_record("r2", R2), "fieldNodes": [*field_nodes({**R2, "lead": ""}), *(
                 {"type": "field", "attrs": {"name": name}, "children": links} for name, links in LEADS.items())]},
             _record("ada", {"kind": "person"}), _record("bo", {"kind": "person"})))
DOCUMENT["links"] = [{"id": "ada", "href": "ada.md", "label": "Ada"}, {"id": "bo", "href": "bo.md", "label": "Bo"}]
DOCUMENT["comments"] = {"version": 1, "files": ["manifest.comments.alice.json"], "comments": [
    {"id": "base-comment", "author": "Alice", "created": "2026-11-17T10:00:00Z", "state": "open",
     "body": {"mediaType": "text/plain", "text": "On the cut word."},
     "target": {"chapter": "fields", "node": "bases-fields:t1", "start": 0, "end": len(BASE_WORD), "quote": BASE_WORD}},
    {"id": "pipe-comment", "author": "Alice", "created": "2026-11-17T10:01:00Z", "state": "open",
     "body": {"mediaType": "text/plain", "text": "On the cut word."},
     "target": {"chapter": "pipes", "node": "row-long", "start": 0, "end": len(PIPE_WORD), "quote": PIPE_WORD}},
], "decisions": [], "states": []}
PACKAGED = load_config()
OFF = dataclasses.replace(PACKAGED, artifact={**PACKAGED.artifact, "tableRowsOneLine": False})


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory) -> dict[str, str]:
    folder = tmp_path_factory.mktemp("table-rows-one-line")
    paths = {}
    for name, config in (("on", None), ("off", OFF)):
        path = folder / f"{name}.html"
        path.write_text(artifact_html(DOCUMENT, config), encoding="utf-8")
        paths[name] = path.as_uri()
    return paths


@pytest.fixture
def reader(artifacts, reader_browser):
    """Opens a build at 390 x 844 (or ``viewport``), shown as pages or in the continuous view."""
    pages, errors = [], []

    def open_(build: str = "on", paged: bool = True, viewport: dict = PHONE):
        page = reader_browser.new_page(viewport=viewport)
        page.set_default_timeout(5000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(artifacts[build])
        page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        page.evaluate(f"obsPages.setPaged({json.dumps(paged)})")
        pages.append(page)
        return page

    yield open_
    assert errors == []


def _show(page, slug: str, selector: str = SHELL) -> None:
    page.evaluate(f"obsArtifact.activateChapter({json.dumps(slug)})")
    page.evaluate("obsArtifact.whenChapterReady()")
    page.locator(selector).first.wait_for()
    _settle(page)


def _settle(page) -> None:
    """Two frames, so the resize observers have measured the laid-out rows."""
    page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


# Each row's height and its one-line bound: the larger of its first cell's line height (measured on
# one line where it is `normal`) and its disclosure's height, plus that cell's vertical padding and
# borders, plus 1 px.
HEIGHTS = """rows => rows.filter(row => row.getClientRects().length).map(row => {
    const cell = row.cells[0];
    const style = getComputedStyle(cell);
    let line = parseFloat(style.lineHeight);
    if (Number.isNaN(line)) {
        const probe = document.createElement("span");
        probe.textContent = "x";
        probe.style.whiteSpace = "nowrap";
        cell.append(probe);
        line = probe.getBoundingClientRect().height;
        probe.remove();
    }
    const toggle = cell.querySelector(".disclosure-toggle");
    const chrome = ["paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth"]
        .reduce((sum, name) => sum + parseFloat(style[name]), 0);
    return {key: row.dataset.rowKey || row.dataset.nodeId || row.textContent.slice(0, 20),
        height: row.getBoundingClientRect().height,
        bound: Math.max(line, toggle ? toggle.getBoundingClientRect().height : 0) + chrome + 1};
})"""


def _over(page, selector: str) -> list[dict]:
    """The rows of ``selector`` higher than one line."""
    return [row for row in page.locator(selector).evaluate_all(HEIGHTS) if row["height"] > row["bound"]]


def _closed(selector: str) -> str:
    return f"{selector}:not([data-row-open]):not([data-pipe-row-open])"


def _scrolls_sideways(page) -> list[str]:
    return page.evaluate("""() => [
        ...[...document.querySelectorAll("[data-active-chapter] .data-table-scroll")]
            .filter(scroller => scroller.scrollWidth > scroller.clientWidth + 1).map(() => "base"),
        ...[...document.querySelectorAll("[data-active-chapter] table[data-node-id]")]
            .filter(table => table.offsetWidth > table.parentElement.clientWidth + 1).map(table => table.dataset.nodeId),
        ...[document.querySelector("[data-chapter-scroll]")]
            .filter(reader => reader.scrollWidth > reader.clientWidth + 1).map(() => "reader")]""")


def _cell_state(locator) -> dict:
    """A cell's whole text, its title and whether its content is cut (a clamp box overflowing)."""
    return locator.evaluate("""cell => ({
        text: cell.textContent.replace(/\\s+/g, " "), title: (cell.title || "").replace(/\\s+/g, " "),
        cut: [...cell.querySelectorAll(".data-table-clamp, .pipe-table-box")]
            .some(box => box.scrollHeight > box.clientHeight + 1 || box.scrollWidth > box.clientWidth + 1)})""")


def _base_row(page, record: str):
    return page.locator(f"{SHELL} tbody tr[data-row-key='note:{record}']")


def _pipe_row(page, identifier: str):
    return page.locator(f"[data-active-chapter] tr[data-node-id='{identifier}']")


@pytest.mark.parametrize("paged", [True, False], ids=["pages", "continuous"])
def test_collapsed_rows_and_captions_of_both_kinds_are_one_line_at_390_px(reader, paged: bool) -> None:
    page = reader(paged=paged)
    for slug in ("grouped", "fields", "paged"):
        _show(page, slug)
        assert _over(page, _closed(BASE_ROWS)) == [], slug
        assert _over(page, GROUP_ROWS) == [], slug
        assert _scrolls_sideways(page) == [], slug
    _show(page, "grouped")
    caption = page.locator(GROUP_ROWS).first
    label = caption.locator(".data-table-group-label")
    assert caption.locator(".data-table-group-count").is_visible()
    assert PHASE in label.get_attribute("title") and PHASE in caption.text_content()
    long_cell = _base_row(page, "t1").locator("td").nth(1)
    assert _cell_state(long_cell) == {"text": SUMMARY, "title": SUMMARY, "cut": True}
    _show(page, "references")
    assert _over(page, _closed(BASE_ROWS)) == [] and _scrolls_sideways(page) == []
    references = _base_row(page, "r2").locator("td").nth(1)
    assert references.locator("a").count() == 2 and _cell_state(references)["cut"]
    assert _cell_state(references)["title"] == "ada bo"
    _show(page, "pipes", PIPE)
    assert _over(page, _closed(f"{PIPE} tbody tr")) == []
    assert _over(page, _closed(f"{FIVE} tbody tr")) == []
    assert _scrolls_sideways(page) == []
    assert _cell_state(_pipe_row(page, "row-long").locator("td").nth(1)) == {
        "text": PIPE_TEXT, "title": PIPE_TEXT, "cut": True}
    linked = _pipe_row(page, "row-link").locator("td").nth(1)
    assert _cell_state(linked)["cut"] and linked.locator("a").count() == 1
    assert _pipe_row(page, "row-short").locator("[data-pipe-row-toggle]").count() == 0
    assert _pipe_row(page, "row-long").locator("td").first.locator(":scope > [data-pipe-row-toggle]").count() == 1


def test_the_pipe_header_row_is_as_without_the_option(reader) -> None:
    headers = []
    for build in ("on", "off"):
        page = reader(build)
        _show(page, "pipes", PIPE)
        headers.append([page.locator(f"{table} thead").evaluate("head => head.outerHTML") for table in (PIPE, FIVE)])
    assert headers[0] == headers[1]


def _cells_in_full(row) -> bool:
    return row.evaluate("""row => [...row.querySelectorAll(".data-table-clamp, .pipe-table-box")]
        .every(box => box.scrollHeight <= box.clientHeight + 1 && box.scrollWidth <= box.clientWidth + 1)""")


def test_opening_a_row_shows_its_cells_in_full_and_closing_cuts_them_again(reader) -> None:
    page = reader()
    _show(page, "grouped")
    note = _base_row(page, "t1")
    note.locator(".data-table-tree-toggle").click()
    page.locator(f"{SHELL} tr[data-detail-owner='note:t1']").wait_for()
    assert note.get_attribute("data-row-open") == "" and _cells_in_full(note)
    contents = _base_row(page, "c1")
    toggle = contents.locator("[data-table-cut-toggle]")
    assert toggle.get_attribute("aria-label").startswith("Expand ")
    details = page.locator(f"{SHELL} tr[data-detail-owner]").count()
    toggle.click()
    _settle(page)
    assert _base_row(page, "c1").get_attribute("data-row-open") == "" and _cells_in_full(_base_row(page, "c1"))
    assert page.locator(f"{SHELL} tr[data-detail-owner]").count() == details
    _show(page, "pipes", PIPE)
    long_row = _pipe_row(page, "row-long")
    long_row.locator("[data-pipe-row-toggle]").click()
    _settle(page)
    assert long_row.get_attribute("aria-expanded") is None
    assert long_row.locator("[data-pipe-row-toggle]").get_attribute("aria-expanded") == "true"
    assert _cells_in_full(long_row)
    long_row.locator("[data-pipe-row-toggle]").click()
    _settle(page)
    assert not _cells_in_full(long_row) and _over(page, _closed(f"{PIPE} tbody tr")) == []
    assert _pipe_row(page, "row-link").locator("td a").evaluate("link => link.href").endswith("#ada")


def _cut_rows_have_disclosures(page) -> list[str]:
    """The rows with a cut cell that lack a disclosure."""
    return page.locator(BASE_ROWS).evaluate_all("""rows => rows.filter(row => [...row.cells].some(cell =>
        [...cell.querySelectorAll(".data-table-clamp")].some(box => box.scrollHeight > box.clientHeight + 1))
        && !row.querySelector(".data-table-tree-toggle")).map(row => row.dataset.rowKey)""")


def _one_line_after(page, label: str) -> None:
    _settle(page)
    assert _over(page, _closed(BASE_ROWS)) == [], label
    assert _cut_rows_have_disclosures(page) == [], label


def test_rows_stay_one_line_after_a_sort_a_grouping_a_page_a_parent_and_new_rows(reader) -> None:
    page = reader()
    _show(page, "fields")
    page.locator(f"{SHELL} thead th[data-column-key='summary']").click()
    _one_line_after(page, "sort")
    assert _base_row(page, "c1").locator("[data-table-cut-toggle]").count() == 1
    page.locator(f"{SHELL} .data-table-options-toggle").click()
    page.locator(f"{SHELL} .data-table-options button.filter-pill", has_text="Group").click()
    page.locator(f"{SHELL} .data-table-options [data-group-field='phase'], "
                 f"{SHELL} .data-table-options button.filter-pill:has-text('phase')").first.click()
    page.keyboard.press("Escape")
    page.locator(GROUP_ROWS).first.wait_for()
    _one_line_after(page, "grouping")
    assert _over(page, GROUP_ROWS) == []
    _show(page, "paged")
    page.locator(f"{SHELL} .data-table-footer button[aria-label='Next table page']").click()
    _one_line_after(page, "page")
    _show(page, "tree")
    parent = page.locator(f"{SHELL} tbody tr[data-row-key='parent']")
    parent.locator(".data-table-tree-toggle").click()
    _one_line_after(page, "parent closed")
    parent.locator(".data-table-tree-toggle").click()
    page.locator(f"{SHELL} tbody tr[data-row-key='child']").wait_for()
    _one_line_after(page, "parent opened")
    assert _cells_in_full(parent)
    page.evaluate("document.dispatchEvent(new CustomEvent('obs-canonical-property-change'))")
    _one_line_after(page, "rows set anew")


def _search(page, query: str) -> list[dict]:
    page.evaluate("obsArtifact.openBar('search')")
    page.locator("[data-search-input]").fill(query)
    page.wait_for_function("obsSearch.hits.length > 0")
    return page.evaluate("obsSearch.hits.map(hit => ({slug: hit.slug, kind: hit.kind}))")


def test_search_and_comments_open_the_row_that_holds_a_hit_in_a_cut_cell(reader) -> None:
    page = reader()
    hits = _search(page, BASE_WORD)
    page.locator(f"[data-search-hit='{hits.index({'slug': 'grouped', 'kind': 'row'})}']").click()
    page.locator(f"{SHELL} tr[data-row-key='note:t1'][data-row-open] .search-highlight").wait_for()
    assert page.locator(f"{SHELL} tr[data-row-key='note:t1'] .search-highlight").first.is_visible()
    assert page.locator(f"{SHELL} tr[data-detail-owner='note:t1']").count() == 0
    hits = _search(page, PIPE_WORD)
    page.locator(f"[data-search-hit='{[hit['slug'] for hit in hits].index('pipes')}']").click()
    page.locator("[data-active-chapter] tr[data-node-id='row-long'][data-pipe-row-open] .search-highlight").wait_for()
    assert page.locator("[data-active-chapter] tr[data-node-id='row-long'] .search-highlight").first.is_visible()

    page = reader()
    page.evaluate("obsArtifact.openBar('comments', 'right')")
    for comment, row in (("base-comment", "tr[data-row-key='note:t1']"), ("pipe-comment", "tr[data-node-id='row-long']")):
        page.locator(f"[data-comment-id='{comment}'] .comment-target").click()
        page.locator(f"[data-active-chapter] {row}[data-row-open], "
                     f"[data-active-chapter] {row}[data-pipe-row-open]").wait_for()
        if comment == "base-comment":
            # A reveal opens the row's cells, not its details (generic-tables.md, One line per row).
            assert page.locator(f"{SHELL} tr[data-detail-owner='note:t1']").count() == 0


def test_the_print_book_shows_every_cell_and_caption_in_full(reader) -> None:
    page = reader()
    page.evaluate("dispatchEvent(new Event('beforeprint'))")
    page.emulate_media(media="print")
    book = page.evaluate("""() => {
        const book = document.querySelector(".print-book");
        const cells = [...book.querySelectorAll("td, th")];
        return {
            boxes: book.querySelectorAll(".pipe-table-box, .data-table-clamp, [data-pipe-row-toggle], [data-table-cut-toggle]").length,
            clipped: cells.filter(cell => cell.scrollHeight > cell.clientHeight + 1).length,
            text: book.textContent.replace(/\\s+/g, " "),
            tall: cells.filter(cell => cell.textContent.includes("at end.")).map(cell => cell.getBoundingClientRect().height),
            caption: [...book.querySelectorAll(".data-table-group-row th")].map(th => th.getBoundingClientRect().height),
        };
    }""")
    page.emulate_media(media="screen")
    page.evaluate("dispatchEvent(new Event('afterprint'))")
    assert book["boxes"] == 0 and book["clipped"] == 0
    assert SUMMARY in book["text"] and PIPE_TEXT in book["text"] and PHASE in book["text"]
    assert book["tall"] and min(book["tall"]) > 60
    assert book["caption"] and min(book["caption"]) > 30


def test_with_the_option_off_rows_and_captions_wrap_as_before(reader) -> None:
    page = reader("off")
    _show(page, "grouped")
    assert page.locator(f"{SHELL}[data-rows-one-line], {SHELL} .data-table-clamp, {SHELL} [data-table-cut-toggle]").count() == 0
    assert {row["key"] for row in _over(page, BASE_ROWS)} >= {"note:t1", "note:c1"}
    assert len(_over(page, GROUP_ROWS)) == 1
    _show(page, "pipes", PIPE)
    assert page.locator("[data-active-chapter] .pipe-table-box, [data-pipe-row-toggle]").count() == 0
    assert len(_over(page, f"{PIPE} tbody tr")) == 2
