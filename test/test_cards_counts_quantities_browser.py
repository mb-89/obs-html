"""Native-browser tier: the cards runtime (cards.js) counts as the interim adapter's did.

Moved from the interim's native card and quantity checks (obs test_cards_browser.py,
test_query_quantities_browser.py), rebuilt on Documents as the core emits them.
"""
import json
from urllib.parse import quote

import pytest

from conftest import ROOT
from obs_html.config import load_config
from obs_html.render import render

from documents import chapter, document as build, heading, node, paragraph, text


pytestmark = pytest.mark.browser
CONFIG = load_config()
SERVICES = [("one", "a", "yes", "yes", "north"), ("two", "b", "no", "no", "south"),
            ("three", "a", "yes", "yes", "north")]


def _record(identifier: str, fields: dict, path: str = "", **extra: object) -> dict:
    quantity = {"quantity": _quantity_of(fields)} if fields.get("kind") == "quantity" else {}
    return {"id": identifier, "type": "note", "path": path or f"{identifier}.md", "fields": fields,
            **quantity, **extra}


def _quantity_of(metadata: dict) -> dict:
    """A quantity as the core emits it (obs capabilities/quantities#Document node); these use mm or none."""
    if "value" not in metadata:
        return {"unit": "", "dimension": {}}
    return {"value": metadata["value"], "unit": "mm", "siValue": metadata["value"] / 1000, "dimension": {"length": 1}}


def _services(*extra: tuple[str, str, str, str, str]) -> list[dict]:
    return [_record(name, {"kind": "service", "identity": identity, "active": active,
                           "healthy": healthy, "region": region})
            for name, identity, active, healthy, region in [*SERVICES, *extra]]


def _cards(*cards: dict, bodies: tuple[list[dict], ...] = ()) -> dict:
    """The node of a cards fence; ``bodies`` holds each card's body nodes, empty by default."""
    spec = {"version": 1, "cards": list(cards)}
    result = node("cards-metrics", source=json.dumps(spec), spec=spec)
    result["children"] = [{"type": "document", "attrs": {}, "children": list(body)}
                          for body in (bodies or tuple([] for _ in cards))]
    return result


def _quantity(identifier: str, title: str, metadata: dict) -> dict:
    content = [node("quantities", metadata=metadata, quantity=_quantity_of(metadata))]
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
    {"title": "Evidence", "body": "Static instructions."},
    bodies=([paragraph("Ordinary ", {"type": "strong", "attrs": {}, "children": [text("operations")]}, ".")],
            [paragraph("Static instructions.")]),
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
                            {"field": "active", "equals": "yes"}], "distinct": "identity", "denominator": []}]},
                   bodies=([paragraph("Items ", _link("serviceCount", "counts-total"), " (",
                                      _link("activeCount", "counts-subset"), " active).")],))
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
    page.evaluate("""async () => {  // A canonical change no property editor declares: a transaction.
        const artifact = globalThis.obsArtifact;
        const notes = artifact.canonicalNotes().map(note => note.slug === 'two'
            ? {...note, frontmatter: {...note.frontmatter, active: 'yes'}} : note);
        (await artifact.stageCanonicalTransaction({expectedRevision: artifact.revision, notes,
            assetChanges: []})).commit();
    }""")
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


def test_every_metric_field_and_a_metric_series_count_as_the_interim_runtime_counts(tmp_path, reader_browser) -> None:
    """The ``cards`` vault of fixtures/build_documents.py, built by the core. Three points: a and c
    open (owners ada, lin), b closed (lin); no point has a reviewer. The expectations are the interim runtime's
    (obs cards.js): a denominator makes a percentage, the first matching tone rule wins over the
    tone, a compound value links primary and secondary, a projection counts its own fields,
    and a series makes one metric per list entry, linked to a table filtered to its label."""
    document = json.loads((ROOT / "test" / "fixtures" / "documents" / "cards.json").read_text(encoding="utf-8"))
    page, errors = _open(tmp_path, reader_browser, document)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('overview')")
    cards = page.locator("[data-active-chapter] [data-record-card]")
    outer, metrics, series = (cards.filter(has=page.locator(f":scope > .content-card-title:text-is('{title}')"))
                              for title in ("Outer", "Metrics", "Series"))
    expect(page.locator("[data-active-chapter] .record-card [data-data-table='overview-base-1'] [data-row-key]")).to_have_count(3)
    expect(outer.locator("[data-record-card] .content-card-title")).to_have_text("Inner")
    share = metrics.locator("[data-record-metric='0']")
    expect(share).to_have_class("record-metric record-metric--warning")
    expect(share.locator(".record-metric-value")).to_have_text("66.7%")
    expect(share.locator(".record-metric-value")).to_have_attribute("href", "#target")
    compound = metrics.locator("[data-record-metric='1']")
    expect(compound).to_have_class("record-metric record-metric--negative")
    expect(compound.locator(".record-metric-value")).to_have_text("3 (2)")
    expect(compound.locator("[data-quantity-reference]")).to_have_count(2)
    assert compound.locator("[data-quantity-reference]").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))") == ["#overview", "#target"]
    reviewed = metrics.locator("[data-record-metric='2']")
    expect(reviewed).to_have_class("record-metric record-metric--positive")
    expect(reviewed.locator(".record-metric-value")).to_have_text("2")
    page.evaluate("obsCards.setProjection('review', {'b-point.md': {status: 'open'}})")
    expect(reviewed.locator(".record-metric-value")).to_have_text("3")
    expect(share.locator(".record-metric-value")).to_have_text("66.7%")
    page.evaluate("obsCards.setProjection('review', null)")
    expect(reviewed.locator(".record-metric-value")).to_have_text("2")
    expect(series.locator(".record-metric-label")).to_have_text(["open", "closed"])
    expect(series.locator(".record-metric-value strong")).to_have_text(["2", "0"])
    expect(series.locator(".record-metric")).to_have_class(
        ["record-metric record-metric--positive", "record-metric record-metric--negative"])
    assert series.locator(".record-metric-value").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))") == [
        f"#overview?tableFilter={quote(f'status:/^{label}$/', safe='')}" for label in ("open", "closed")]
    assert errors == []
