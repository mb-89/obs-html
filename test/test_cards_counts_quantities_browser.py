"""Native-browser tier: the cards runtime (cards.js) counts as the interim adapter's did.

Moved from the interim's native card and quantity checks (obs test_cards_browser.py,
test_query_quantities_browser.py), rebuilt on Documents as the core emits them.
"""
import json
from urllib.parse import quote

import pytest

from obs_html.config import load_config
from obs_html.render import render

from documents import chapter, document as build, heading, node, paragraph


pytestmark = pytest.mark.browser
CONFIG = load_config()
SERVICES = [("one", "a", "yes", "yes", "north"), ("two", "b", "no", "no", "south"),
            ("three", "a", "yes", "yes", "north")]


def _record(identifier: str, fields: dict, path: str = "", **extra: object) -> dict:
    return {"id": identifier, "type": "note", "path": path or f"{identifier}.md", "fields": fields, **extra}


def _services(*extra: tuple[str, str, str, str, str]) -> list[dict]:
    return [_record(name, {"kind": "service", "identity": identity, "active": active,
                           "healthy": healthy, "region": region})
            for name, identity, active, healthy, region in [*SERVICES, *extra]]


def _cards(*cards: dict) -> dict:
    spec = {"version": 1, "cards": list(cards)}
    return node("cards-metrics", source=json.dumps(spec), spec=spec)


def _quantity(identifier: str, title: str, metadata: dict) -> dict:
    content = [node("quantities", metadata=metadata)]
    if "query" in metadata:
        content += [node("queries", query=metadata["query"]), node("count-query", query=metadata["query"])]
    result = chapter(identifier, title, *content, metadata=metadata)
    result["toc"] = False
    return result


def _link(target: str, chapter_id: str, label: str = "") -> dict:
    return node("wikilinks", target=target, chapter=chapter_id, heading="", label=label or target)


def _open(tmp_path, reader_browser, source: dict):
    artifact = tmp_path / "artifact.html"
    artifact.write_text(render(source, CONFIG), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1440, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    return page, errors


GLOBAL_CARDS = _cards(
    {"title": "Service health", "body": "Ordinary **operations**.", "metrics": [
        {"label": "Availability", "where": [{"field": "healthy", "equals": "yes"}],
         "denominator": [{"field": "kind", "equals": "service"}]},
        {"label": "Regions", "where": [{"field": "kind", "equals": "service"}], "distinct": "region"},
    ]},
    {"title": "Evidence", "body": "Static [instructions](https://example.org)."},
)


def test_cards_follow_the_global_filter(tmp_path, reader_browser) -> None:
    source = build("Cards", chapter("chapter", "Chapter", heading(1, "Operations")),
                   abstract=(GLOBAL_CARDS,), records=tuple(_services()))
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('home')")
    card = page.locator("[data-active-chapter] [data-record-card]").first
    expect(card.locator("strong").first).to_have_text("66.7%")
    expect(card.locator("[data-record-metric='1'] strong")).to_have_text("2")
    evidence = page.locator("[data-active-chapter] [data-record-card]").nth(1).inner_text()
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('region:north'))")
    expect(card.locator("strong").first).to_have_text("100.0%")
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('region:missing'))")
    expect(card.locator("strong").first).to_have_text("-")
    expect(card.locator("[data-record-metric='1'] strong")).to_have_text("0")
    assert page.locator("[data-active-chapter] [data-record-card]").nth(1).inner_text() == evidence
    page.evaluate("obsArtifact.setFilter(obsQuery.compile(''))")
    expect(card.locator("strong").first).to_have_text("66.7%")
    assert errors == []


def test_a_metric_link_filters_the_linked_table(tmp_path, reader_browser) -> None:
    table_filter = "region:south"
    link = f"#chapter?tableFilter={quote(table_filter, safe='')}"
    cards = _cards({"title": "Coverage", "body": "", "metricStyle": "pills", "metrics": [
        {"label": "Healthy", "where": [{"field": "healthy", "equals": "yes"}],
         "denominator": [{"field": "kind", "equals": "service"}], "link": link}]})
    spec = {"filters": {"and": ['kind == "service"']},
            "views": [{"type": "table", "name": "Services", "order": ["healthy", "region"]}]}
    source = build("Cards", chapter("chapter", "Chapter", heading(1, "Operations"),
                                    node("bases", source="", spec=spec)),
                   abstract=(cards,), records=tuple(_services()))
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('home')")
    metric = page.locator("[data-active-chapter] .record-metrics--pills .record-metric-value").first
    expect(metric.locator("strong")).to_have_text("66.7%")
    expect(metric).to_have_attribute("href", link)
    expect(metric).to_have_attribute("aria-label", "66.7% Healthy")
    metric.click()
    table = page.locator('[data-active-chapter] [data-data-table="chapter-base-1"]')
    expect(table.locator(".data-table-filter").first).to_have_value(table_filter)
    expect(table.locator("[data-row-key]")).to_have_count(1)
    assert errors == []


def test_quantities_count_through_their_selection_chain_and_refresh(tmp_path, reader_browser) -> None:
    total = {"kind": "quantity", "aliases": ["serviceCount"], "source": "[[chapter]]",
             "query": {"where": [{"field": "kind", "equals": "service"}], "distinct": "identity"}}
    subset = {"kind": "quantity", "aliases": ["activeCount"], "source": "[[chapter]]",
              "query": {"from": "counts/total", "where": [{"field": "active", "equals": "yes"}],
                        "distinct": "identity"}}
    limit = {"kind": "quantity", "value": 20, "unit": "mm", "aliases": ["staticLimit"], "source": "[[chapter]]"}
    cards = _cards({"title": "Operations", "body": "Items [[serviceCount]] ([[activeCount]] active).",
                    "metrics": [
                        {"label": "Same selection", "from": "counts/total", "where": [], "distinct": "identity"},
                        {"label": "Active share", "from": "counts/total", "where": [
                            {"field": "active", "equals": "yes"}], "distinct": "identity", "denominator": []}]})
    source = build(
        "Quantities",
        chapter("chapter", "Chapter", heading(1, "Operations"), cards,
                paragraph("Limit ", _link("staticLimit", "limit"), ", explicit ",
                          _link("serviceCount", "counts-total", "services"), ".")),
        _quantity("counts-total", "Total", total), _quantity("counts-subset", "Subset", subset),
        _quantity("limit", "Limit", limit),
        records=(_record("chapter", {}), _record("counts-total", total, "counts/total.md"),
                 _record("counts-subset", subset, "counts/subset.md"), _record("limit", limit),
                 *_services(), _record("other", {"kind": "operator", "identity": "z"})),
        metadata={"obsHtml": {"query": {
            "scope": "records", "where": [{"field": "kind", "equals": "service"}]}}})
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('chapter')")
    summary = page.locator("[data-active-chapter] .record-card p")
    expect(summary).to_have_text("Items 2 (1 active).")
    expect(page.locator("[data-active-chapter] .record-metric strong")).to_have_text(["2", "50.0%"])
    expect(page.locator("[data-active-chapter] a").filter(has_text="20 mm")).to_have_count(1)
    expect(page.locator("[data-active-chapter] a").filter(has_text="services")).to_have_count(1)
    assert page.evaluate("""() => obsRecordMetrics.select({from:'counts/total', where:[]})
        .every(record => obsArtifact.records.includes(record))""")
    page.evaluate("""() => {
        window.aggregatePopulationPasses = 0;
        const previous = obsArtifact.matchesFilter;
        obsArtifact.matchesFilter = record => {aggregatePopulationPasses++; return previous(record);};
        const clone = document.querySelector('[data-quantity-reference]').cloneNode(true);
        clone.dataset.transientView = '';
        clone.id = 'cached-quantity-clone';
        document.body.append(clone);
        document.dispatchEvent(new CustomEvent('obs-chapter-change'));
    }""")
    expect(page.locator("#cached-quantity-clone")).to_have_text("2")
    assert page.evaluate("aggregatePopulationPasses") == 0
    before_filter = page.evaluate("JSON.stringify(obsArtifact.canonicalNotes())")
    before_revision = page.evaluate("obsArtifact.revision")
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('identity:b'))")
    expect(summary).to_have_text("Items 1 (0 active).")
    assert page.evaluate("JSON.stringify(obsArtifact.canonicalNotes())") == before_filter
    assert page.evaluate("obsArtifact.revision") == before_revision
    page.evaluate("obsArtifact.commitCanonicalProjection([{slug:'two', fields:{active:'yes'}}])")
    expect(summary).to_have_text("Items 1 (1 active).")
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('identity:missing'))")
    expect(summary).to_have_text("Items 0 (0 active).")
    page.evaluate("obsArtifact.setFilter(obsQuery.compile('identity:b')); obsPages.setPaged(true)")
    page.wait_for_function("""() => [...document.querySelectorAll('.paged-reader [data-quantity-reference]')]
        .length > 0 && [...document.querySelectorAll('.paged-reader [data-quantity-reference]')]
        .every(link => link.textContent === '1')""")
    saved = tmp_path / "reviewed.html"
    saved.write_text(page.evaluate("obsComments.reviewedHtml()"), encoding="utf-8")
    page.goto(saved.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('chapter')")
    expect(page.locator("[data-active-chapter] .record-card p")).to_have_text("Items 1 (1 active).")
    assert page.evaluate("""() => obsArtifact.canonicalNotes().filter(note =>
        note.frontmatter.kind === 'quantity' && note.frontmatter.query)
        .every(note => !Object.hasOwn(note.frontmatter, 'value'))""")
    assert errors == []


def test_ignored_notes_are_never_counted(tmp_path, reader_browser) -> None:
    total = {"kind": "quantity", "aliases": ["serviceCount"], "source": "[[chapter]]",
             "query": {"where": [{"field": "kind", "equals": "service"}], "distinct": "identity"}}
    ignored = _record("four", {"kind": "service", "identity": "c", "active": "yes", "healthy": "yes",
                               "region": "east"}, ignored=True)
    source = build(
        "Ignored",
        chapter("chapter", "Chapter", heading(1, "Operations"),
                paragraph("Services ", _link("serviceCount", "counts-total"), ".")),
        _quantity("counts-total", "Total", total),
        abstract=(GLOBAL_CARDS,),
        records=(_record("chapter", {}), _record("counts-total", total, "counts/total.md"), *_services(), ignored))
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('home')")
    card = page.locator("[data-active-chapter] [data-record-card]").first
    expect(card.locator("strong").first).to_have_text("66.7%")
    expect(card.locator("[data-record-metric='1'] strong")).to_have_text("2")
    page.evaluate("obsArtifact.activateChapter('chapter')")
    expect(page.locator("[data-active-chapter] [data-quantity-reference]")).to_have_text("2")
    assert errors == []
