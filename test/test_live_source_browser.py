"""Native-browser tier: a Base's live source in the page (generic-tables.md, Current data).

Reader: whoever changes what the tables feature's live-source part does when the page starts.

A table that declares a live source shows exactly the rows, groups and details it shows without it.
When the page starts, the part checks each live table's declaration against the build's rows,
whether or not its chapter is shown: a register's population is the core's rows of the views its
entry carries, a fence's the note rows its Base-level filters select. A row the declaration does
not reproduce logs one console error naming the table, the note, the check and the field; rows it
reproduces log nothing. These tables declare the capability note's example with its connector
route only, which a page outside Claude's artifact viewer does not read: no page here makes a
request, the feature fixture included. The web route's reads are test_live_web_browser.py's. The build's refusals are test_live_source.py's, the pure layer is
live-data.test.js's and the --check-rendered failure test_pdf.py's.
"""
import copy
import json
import re
from pathlib import Path

import pytest
import yaml

from artifacts import artifact_html
from conftest import ROOT
from documents import chapter, document as build, heading, node, paragraph


pytestmark = pytest.mark.browser
EXAMPLE = yaml.safe_load(re.search(r"```yaml\n(.*?)```", (ROOT / "spec" / "capabilities" / "live-data.md")
                                   .read_text(encoding="utf-8"), re.S)[1])["obsHtml"]["liveSource"]
# The capability note's example with its connector route only: a file: page reads a web route
# (test_live_web_browser.py), and these checks are of the rows and the check, which read nothing.
DECLARATION = {**EXAMPLE, "changes": [route for route in EXAMPLE["changes"] if route["provider"] == "connector"]}
SHELL = "[data-active-chapter] .data-table-shell"
IN_PAGE = ("blob:", "data:")
ISSUES = {
    1: {"state": "open", "labels": ["ready"], "status": "Next"},
    2: {"state": "closed", "labels": ["running"], "status": "Done"},
    3: {"state": "open", "labels": ["running"], "status": "Running"},
    4: {"state": "open", "labels": ["planned"], "status": "Someday"},
}


def _fields(number: int, **changes: object) -> dict:
    return {"kind": "issue", "repo": "widgets", "number": number, **ISSUES[number], **changes}


def _base(live: bool) -> dict:
    view = {"type": "table", "name": "Board", "order": ["file.name", "status"], "groupBy": {"property": "status"},
            "obsHtml": {"groupOrder": ["Next", "Running", "Done", "Someday"]}}
    spec = {"filters": 'kind == "issue"', "views": [view, {"type": "table", "name": "All", "order": ["file.name"]}]}
    return {**spec, "obsHtml": {"liveSource": copy.deepcopy(DECLARATION)}} if live else spec


def _document(fields: dict[int, dict]) -> dict:
    """Two tables of the same Base, one with the live source, and a register of it; the issue
    notes sit outside the contents, so an opened row shows its note's text."""
    notes = [{**chapter(f"widgets-{number}", f"Widget {number}", paragraph(f"Issue {number}'s text."),
                        metadata=item), "toc": False} for number, item in fields.items()]
    rows = [[f"widgets-{number}" for number in fields]] * 2
    return build(
        "Tracker",
        chapter("plain", "Plain", heading(1, "Plain"), node("bases", source="", spec=_base(False))),
        chapter("live", "Live", heading(1, "Live"), node("bases", source="", spec=_base(True))),
        chapter("register", "Register", heading(1, "Register"), node(
            "registers", target="issues.base", heading="", base=_base(True), view=None, rows=rows)),
        *notes,
        records=tuple({"id": f"widgets-{number}", "type": "note", "path": f"issues/widgets-{number}.md",
                       "fields": item} for number, item in fields.items()))


GOOD = {number: _fields(number) for number in ISSUES}
# Issue 1 is labelled ready, so the declaration derives Next; its note says Running.
WRONG = {**GOOD, 1: _fields(1, status="Running")}


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory) -> dict[str, str]:
    folder = tmp_path_factory.mktemp("live-source")
    paths = {}
    for name, fields in (("good", GOOD), ("wrong", WRONG)):
        path = folder / f"{name}.html"
        path.write_text(artifact_html(_document(fields)), encoding="utf-8")
        paths[name] = path.as_uri()
    return paths


@pytest.fixture
def opened(artifacts, reader_browser):
    """Opens an artifact at its home and returns the page, its console errors and its requests:
    every one but the artifact's own file and the page's own blob: and data: URLs, which ask the
    network for nothing."""
    pages = []

    def open_(url: str):
        page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(5000)
        errors: list[str] = []
        requests: list[str] = []
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(f"Uncaught {error}"))
        page.on("request", lambda request: requests.append(request.url)
                if request.url != url and not request.url.startswith(IN_PAGE) else None)
        page.goto(url)
        page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        page.evaluate("obsPages.setPaged(false)")
        pages.append(page)
        return page, errors, requests

    return open_


def _table(page, slug: str) -> dict:
    """What the chapter's table shows: its body text, its group captions and its first row's details."""
    page.evaluate(f"obsArtifact.activateChapter({json.dumps(slug)})")
    page.locator(SHELL).wait_for()
    shown = {"rows": page.locator(f"{SHELL} tbody tr[data-row-key]").evaluate_all(
                 "rows => rows.map(row => row.dataset.rowKey + ' ' + row.innerText)"),
             "groups": page.locator(f"{SHELL} tbody").inner_text()}
    page.locator(f"{SHELL} tbody tr[data-row-key] .data-table-tree-toggle").first.click()
    shown["detail"] = page.locator(f"{SHELL} .data-table-detail-row").inner_text()
    return shown


def test_a_live_table_shows_the_rows_groups_and_details_it_shows_without_the_option(artifacts, opened) -> None:
    page, errors, requests = opened(artifacts["good"])
    plain = _table(page, "plain")
    assert plain["rows"] and "Issue 1's text." in plain["detail"]
    assert _table(page, "live") == plain
    assert _table(page, "register")["rows"] == plain["rows"]
    assert errors == []
    assert requests == []


def test_a_row_the_declaration_does_not_reproduce_logs_one_error_per_live_table_naming_its_note(
        artifacts, opened) -> None:
    """The check runs when the page starts, with no live chapter shown: the fence's and the
    register's tables each log one error, naming the table, the note, the check and the field;
    the plain table logs none, and the tables keep showing their saved rows."""
    page, errors, requests = opened(artifacts["wrong"])
    assert len(errors) == 2, errors
    for error, key in zip(sorted(errors), ["live-base-1", "register-base-1"]):
        assert f"table {key}" in error
        assert "note issues/widgets-1.md" in error and "derive check of field status" in error
        assert "Example Tracker" in error
    assert "Running" in _table(page, "live")["groups"]
    assert requests == []


def test_the_feature_fixture_carries_the_part_and_makes_no_request(feature_artifact: str, tmp_path: Path,
                                                                      opened) -> None:
    """The feature fixture's tracker table declares a connector route only (build_documents.py,
    FEATURE_LIVE_SOURCE): its check passes silently and the page asks the network for nothing."""
    assert "globalThis.obsLiveData" in feature_artifact
    path = tmp_path / "features.html"
    path.write_text(feature_artifact, encoding="utf-8")
    page, errors, requests = opened(path.as_uri())
    assert errors == []
    assert requests == []
