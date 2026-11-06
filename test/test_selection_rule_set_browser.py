"""Native-browser tier: every live selection follows the one rule set (obs capabilities/bases#Comparisons).

The reader's filter, the counts recomputed under it, facet pills and Sankey drill-downs select
with one evaluator (query.js); the shared fixture's cases run in bases-filter-conformance.test.js.
Moved from the interim's case checks (obs test_figures_browser.py), rebuilt on Documents.
"""
import json

import pytest

from artifacts import artifact_html

from documents import chapter, document as build, heading, node


pytestmark = pytest.mark.browser
# Values and property names that differ only in case.
FLOW = (("a", "flow-record", "target", "approved"), ("b", "flow-record", "target", "Approved"),
        ("c", "Flow-Record", "Target", "APPROVED"), ("d", "flow-record", "target", "rejected"),
        ("e", "flow-record", "target", "Rejected"))
GRAPH = {
    "version": 1,
    "nodes": [
        {"id": "approved", "label": "Approved", "stage": 1,
         "records": {"where": [{"field": "target", "equals": "approved"}]}, "unique": "target"},
        {"id": "rejected", "label": "Rejected", "stage": 1},
        {"id": "request", "label": "Request", "stage": 0},
    ],
    "links": [
        {"source": "request", "target": "approved", "value": 3, "label": "Approved",
         "where": [{"field": "target", "equals": "approved"}]},
        {"source": "request", "target": "rejected", "value": 1, "label": "Rejected",
         "where": [{"field": "target", "equals": "Rejected", "matchCase": True}]},
    ],
    "data": {"where": [{"field": "kind", "equals": "flow-record"}]},
}
RETAINED = ("obsArtifact.records.filter(record => /^record-/.test(record.slug) && obsArtifact.matchesFilter(record))"
            ".map(record => record.slug.slice(7)).join('')")


def _record(identifier: str, fields: dict) -> dict:
    return {"id": identifier, "type": "note", "path": f"{identifier}.md", "fields": fields}


def _scope(kind: str) -> dict:
    """The reader's filter narrows the records of one kind, so chapters stay readable."""
    return {"obsHtml": {"query": {"scope": "records", "where": [{"field": "kind", "equals": kind}]}}}


def _sankey(graph: dict) -> dict:
    return {"type": "figures", "attrs": {"kind": "sankey"}, "children": [node("sankey", graph=graph)]}


def _open(tmp_path, reader_browser, source: dict, start: str = "flow"):
    artifact = tmp_path / "artifact.html"
    artifact.write_text(artifact_html(source), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate(f"obsPages.setPaged(false); obsArtifact.activateChapter({json.dumps(start)})")
    return page, errors


@pytest.fixture
def flow_page(tmp_path, reader_browser):
    records = tuple(_record(f"record-{name}", {"kind": kind, key: target}) for name, kind, key, target in FLOW)
    source = build("Flow", chapter("flow", "Flow", heading(1, "Flow"), _sankey(GRAPH)), records=records,
                   metadata=_scope("flow-record"))
    page, errors = _open(tmp_path, reader_browser, source)
    yield page
    assert errors == []


def test_sankey_drill_down_shows_exactly_the_rows_its_count_counted(flow_page) -> None:
    page = flow_page
    svg = page.locator("[data-active-chapter] .figure-sankey svg")
    links = svg.locator(".sankey-link")
    assert [links.nth(index).get_attribute("data-flow-value") for index in range(2)] == ["3", "1"]
    assert "3 records" in svg.locator('[data-node-id="approved"]').text_content()
    svg.locator('[data-node-id="approved"]').click()
    page.wait_for_function(f"({RETAINED}) === 'abc'")
    page.evaluate("obsFilter.setExpression('')")
    page.wait_for_function(f"({RETAINED}) === 'abcde'")
    svg.locator('[data-node-id="rejected"]').click()
    page.wait_for_function(f"({RETAINED}) === 'e'")


@pytest.mark.parametrize("expression, where, expected", [
    ("target: approved", [{"field": "target", "equals": "approved"}], "abc"),
    ("TARGET: /^approved$/", [{"field": "target", "equals": "approved"}], "abc"),
    ("target: /^Rejected$/c", [{"field": "target", "equals": "Rejected", "matchCase": True}], "e"),
])
def test_reader_filter_and_where_equals_select_the_same_rows(flow_page, expression, where, expected) -> None:
    page = flow_page
    counted = page.evaluate(
        "where => obsArtifact.records.filter(record => /^record-/.test(record.slug) && "
        "obsQuery.compileConditions(where).match(record)).map(record => record.slug.slice(7)).join('')",
        where,
    )
    page.evaluate(f"obsFilter.setExpression({json.dumps(expression)})")
    page.wait_for_function(f"({RETAINED}) === {json.dumps(expected)}")
    assert counted == expected


def test_a_distinct_count_reads_its_property_as_conditions_do(tmp_path, reader_browser) -> None:
    """A distinct count resolves its property's name and reads its text like a condition: a
    slug is the reader's own field, no property, so it counts nothing."""
    spec = {"version": 1, "cards": [{"title": "Flow", "metrics": [
        {"label": "Targets", "where": [{"field": "KIND", "equals": "FLOW-RECORD"}], "distinct": "TARGET"},
        {"label": "Owners", "where": [{"field": "kind", "equals": "flow-record"}], "distinct": "Owner.Name"},
        {"label": "Slugs", "where": [{"field": "kind", "equals": "flow-record"}], "distinct": "slug"},
        {"label": "Exact", "where": [{"field": "target", "equals": "Rejected", "matchCase": True}]},
    ]}]}
    cards = node("cards-metrics", source=json.dumps(spec), spec=spec)
    cards["children"] = [{"type": "document", "attrs": {}, "children": []}]
    owners = {"a": "Ann", "b": "Ann", "c": "Bob", "d": "Bob", "e": "Eve"}
    records = tuple(_record(f"record-{name}", {"kind": kind, key: target, "owner": {"name": owners[name]}})
                    for name, kind, key, target in FLOW)
    source = build("Cards", chapter("flow", "Flow", heading(1, "Flow")), abstract=(cards,), records=records)
    page, errors = _open(tmp_path, reader_browser, source, "home")
    from playwright.sync_api import expect
    card = page.locator("[data-active-chapter] [data-record-card]").first
    # Distinct texts: approved, Approved, APPROVED, rejected, Rejected.
    expect(card.locator("[data-record-metric='0'] strong")).to_have_text("5")
    expect(card.locator("[data-record-metric='1'] strong")).to_have_text("3")
    expect(card.locator("[data-record-metric='2'] strong")).to_have_text("0")
    expect(card.locator("[data-record-metric='3'] strong")).to_have_text("1")
    assert errors == []


def test_a_facet_pill_retains_exactly_the_rows_it_counts(tmp_path, reader_browser) -> None:
    """A pill counts one spelling; values differing only in case are other pills."""
    statuses = ["open", "open", "open", "Open", "Open", "closed"]
    records = tuple(_record(f"item-{index}", {"kind": "item", "status": status})
                    for index, status in enumerate(statuses))
    source = build("Facets", chapter("flow", "Flow", heading(1, "Flow")), records=records,
                   metadata=_scope("item"))
    page, errors = _open(tmp_path, reader_browser, source, "home")
    from playwright.sync_api import expect
    page.evaluate("obsArtifact.openBar('filter')")
    page.locator(".filter-field-button", has_text="status").click()
    pill = page.locator('[role="menuitemcheckbox"][data-filter-value="open"]')
    expect(pill.locator("small")).to_have_text("3")
    pill.click()
    page.wait_for_function(
        "obsArtifact.records.filter(record => /^item-/.test(record.slug) && obsArtifact.matchesFilter(record))"
        ".map(record => record.slug.slice(5)).join('') === '012'"
    )
    assert errors == []
