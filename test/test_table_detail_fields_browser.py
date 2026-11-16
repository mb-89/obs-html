"""Native-browser tier: a view chooses the fields an opened row shows (obsHtml.detailFields).

The owners are input-model.md (Compact declarative table presentation: the option, its omission
rules and its field path) and generic-tables.md (the note detail row). With the option, an opened
row shows only the listed fields, in the listed order, above its note's text; an empty list shows
no field block; a blank field stays omitted; the tabs of ``details: columns`` keep their reference
metadata; and a value that is not a list of unique non-blank names fails the view's validation at
``views.<i>.obsHtml.detailFields``. Without the option a row opens as before (the part strips:
test_features.py). The choice's pure layer, chosenDetailEntries, is tested in Node
(detail-fields.test.js).
"""
import json

import pytest

from artifacts import artifact_html
from documents import chapter, document as build, heading, node, paragraph


pytestmark = pytest.mark.browser
SHELL = "[data-active-chapter] .data-table-shell"
DETAIL = f"{SHELL} .data-table-detail-row"
# A task's frontmatter, in the note's order; blocker is blank, so it is never shown.
FIELDS = {"kind": "task", "status": "Needs you", "date": "2026-11-16", "blocker": "", "lead": "[[ada]]"}
LEAD = {"kind": "person", "role": "lead", "team": "core"}


def _note(identifier: str, metadata: dict, text: str, fields: dict | None = None) -> dict:
    """A note outside the contents: a table row opens it in place."""
    return {**chapter(identifier, identifier.title(), paragraph(text), metadata=metadata, fields=fields),
            "toc": False}


def _view(**options: object) -> dict:
    view = {"type": "table", "name": "Tasks", "order": ["file.name", "status"]}
    if options:
        view["obsHtml"] = options
    return view


def _base(view: dict, **properties: dict) -> dict:
    spec = {"filters": 'kind == "task"', "views": [view], **({"properties": properties} if properties else {})}
    return node("bases", source="", spec=spec)


def _table_chapter(identifier: str, base: dict) -> dict:
    return chapter(identifier, identifier.title(), heading(1, identifier.title()), base)


LINK = {"type": "text", "attrs": {"link": "ada"}, "children": [], "text": "Ada"}
REFERENCE = {"lead": {"displayName": "Lead", "obsHtml": {"detail": True, "reference": {"label": ["file.name"]}}}}
COLUMNS = {"type": "table", "name": "Leads", "order": ["file.name", "lead"]}
TABLES = build(
    "Details",
    _table_chapter("plain", _base(_view())),
    _table_chapter("text-only", _base(_view(detailFields=[]))),
    _table_chapter("date", _base(_view(detailFields=["date"]))),
    _table_chapter("ordered", _base(_view(detailFields=["date", "blocker", "missing", "status"]))),
    _table_chapter("columns", _base({**COLUMNS, "obsHtml": {"details": "columns"}}, **REFERENCE)),
    _table_chapter("columns-chosen", _base({**COLUMNS, "obsHtml": {"details": "columns", "detailFields": []}},
                                           **REFERENCE)),
    _note("t1", FIELDS, "The first task's text.", {"lead": [LINK]}),
    _note("ada", LEAD, "Ada leads the tasks."),
    records=({"id": "t1", "type": "note", "path": "t1.md", "fields": FIELDS},
             {"id": "ada", "type": "note", "path": "ada.md", "fields": LEAD}))
TABLES["links"] = [{"id": "ada", "href": "ada.md", "label": "Ada"}]


@pytest.fixture(scope="module")
def artifact(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("detail-fields") / "tables.html"
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

    def open_(slug: str):
        page.evaluate(f"obsArtifact.activateChapter({json.dumps(slug)})")
        page.locator(SHELL).wait_for()
        return page

    yield open_
    assert errors == []


def _open_row(page):
    """Opens the table's one row and returns its detail row."""
    page.locator(f"{SHELL} tbody tr[data-row-key] .data-table-tree-toggle").first.click()
    detail = page.locator(DETAIL)
    detail.wait_for()
    return detail


def _terms(detail) -> list[str]:
    return detail.locator(".note-detail-metadata dt").evaluate_all("terms => terms.map(term => term.textContent)")


def test_a_view_without_the_option_opens_a_row_with_every_filled_in_field(open_chapter) -> None:
    detail = _open_row(open_chapter("plain"))
    assert _terms(detail) == ["kind", "status", "date", "lead"]
    assert "The first task's text." in detail.inner_text()


def test_an_empty_list_opens_a_row_with_its_text_and_no_field_block(open_chapter) -> None:
    detail = _open_row(open_chapter("text-only"))
    assert detail.locator(".note-detail-metadata").count() == 0
    assert detail.locator(".data-table-detail-subject").inner_text().strip() == "The first task's text."


def test_a_listed_field_is_the_only_one_an_opened_row_shows(open_chapter) -> None:
    detail = _open_row(open_chapter("date"))
    assert _terms(detail) == ["date"]
    assert detail.locator(".note-detail-metadata dd").inner_text() == "2026-11-16"
    assert "The first task's text." in detail.inner_text()


def test_the_listed_order_holds_and_a_blank_or_missing_field_stays_omitted(open_chapter) -> None:
    detail = _open_row(open_chapter("ordered"))
    assert _terms(detail) == ["date", "status"]


def test_the_option_leaves_the_tabs_of_column_details_as_they_are(open_chapter) -> None:
    page = open_chapter("columns")
    plain = _open_row(page).locator(".data-table-detail-panel").first.inner_html()
    assert "lead" in plain and "core" in plain
    chosen = _open_row(open_chapter("columns-chosen")).locator(".data-table-detail-panel").first.inner_html()
    assert chosen == plain


@pytest.mark.parametrize("value", ["date", ["date", "date"], [" "]])
def test_the_query_view_refuses_a_value_that_is_no_list_of_unique_names_at_its_field(open_chapter, value) -> None:
    page = open_chapter("date")
    spec = {"filters": 'kind == "task"', "views": [_view(detailFields=value)]}
    page.locator("[data-active-chapter] .data-table-options-toggle").click()
    page.locator("[data-active-chapter] .data-table-options .filter-pill", has_text="Query view").click()
    editor = page.locator("[data-active-chapter] .data-table-query-editor")
    editor.fill(json.dumps(spec))
    editor.blur()
    alert = page.locator("[data-active-chapter] [role='alert']", has_text="detailFields")
    # Matched by its field path (the item's own path for a blank name), not by its wording.
    assert alert.inner_text().startswith("root.views.0.obsHtml.detailFields")
    # The last valid table stays.
    assert page.locator(f"{SHELL} tbody tr[data-row-key]").count() == 1
