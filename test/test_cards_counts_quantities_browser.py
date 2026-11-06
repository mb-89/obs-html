"""Native-browser tier: the cards runtime (cards.js) counts as the interim adapter's did.

Moved from the interim's native card and quantity checks (obs test_cards_browser.py,
test_query_quantities_browser.py), rebuilt on Documents as the core emits them.
"""
import json
from urllib.parse import quote

import pytest

from artifacts import artifact_html
from conftest import ROOT

from documents import chapter, document as build, heading, node, paragraph, text


pytestmark = pytest.mark.browser
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
    artifact.write_text(artifact_html(source), encoding="utf-8")
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


def test_a_metric_drill_down_shows_exactly_its_counted_rows(tmp_path, reader_browser) -> None:
    """A metric link names its table; its filter derives from the metric's from and where
    (obs capabilities/cards-metrics), so the table shows exactly the rows the value counts."""
    north = {"kind": "quantity", "aliases": ["northCount"], "source": "[[chapter]]",
             "query": {"where": [{"field": "region", "equals": "NORTH"}]}}
    where = [{"field": "healthy", "equals": "Yes"}]
    cards = _cards({"title": "Coverage", "body": "", "metricStyle": "pills", "metrics": [
        {"label": "Healthy", "from": "counts/north", "where": where,
         "denominator": [{"field": "kind", "equals": "service"}], "link": "#chapter"}]})
    spec = {"filters": {"and": ['kind == "service"']},
            "views": [{"type": "table", "name": "Services", "order": ["healthy", "region"]}]}
    source = build("Cards", chapter("chapter", "Chapter", heading(1, "Operations"),
                                    node("bases", source="", spec=spec)),
                   _quantity("counts/north", "North", north), abstract=(cards,),
                   records=(*_services(("four", "c", "yes", "yes", "south")),
                            _record("counts/north", north, "counts/north.md")))
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('home')")
    metric = page.locator("[data-active-chapter] .record-metrics--pills .record-metric-value").first
    expect(metric.locator("strong")).to_have_text("100.0%")
    expression = page.evaluate("obsQuery.conditionsExpression(%s)" % json.dumps(north["query"]["where"] + where))
    expect(metric).to_have_attribute("href", f"#chapter?tableFilter={quote(expression, safe='')}")
    counted = page.evaluate("obsRecordMetrics.select({from: 'counts/north', where: %s})"
                            ".map(record => `note:${record.slug}`).sort()" % json.dumps(where))
    assert len(counted) == 2
    metric.click()
    table = page.locator('[data-active-chapter] [data-data-table="chapter-base-1"]')
    expect(table.locator(".data-table-filter").first).to_have_value(expression)
    expect(table.locator("[data-row-key]")).to_have_count(len(counted))
    assert sorted(table.locator("[data-row-key]").evaluate_all(
        "rows => rows.map(row => row.dataset.rowKey)")) == counted
    assert errors == []


def test_a_metric_series_drill_down_shows_exactly_its_counted_rows(tmp_path, reader_browser) -> None:
    """A series metric selects the series' where plus its group's value, folded as every
    condition is (obs capabilities/cards-metrics#Drill-downs); its count and its drill-down
    both read that selection. A service outside where shares a label, and ``STRASSE`` folds to
    the label ``Straße``."""
    where = [{"field": "kind", "equals": "service"}]
    series = {"sourceNote": "groups", "property": "groups", "labelProperty": "name",
              "distinctProperty": "identity", "where": where, "tone": "neutral",
              "link": {"note": "chapter", "groupProperty": "region"}}
    groups = {"groups": [{"name": "north", "identity": "identity"}, {"name": "Straße", "identity": "identity"}]}
    cards = _cards({"title": "Regions", "body": "", "metricStyle": "pills", "obs": {"metricsFrom": series}})
    spec = {"views": [{"type": "table", "name": "Notes", "order": ["region"]}]}
    source = build("Cards", chapter("chapter", "Chapter", heading(1, "Operations"), node("bases", source="", spec=spec)),
                   abstract=(cards,),
                   records=(*_services(("four", "c", "yes", "yes", "STRASSE")), _record("groups", groups),
                            _record("stray", {"kind": "note", "identity": "z", "region": "north"})))
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false)")
    for index, (label, value) in enumerate((("north", "1"), ("Straße", "1"))):
        page.evaluate("obsArtifact.activateChapter('home')")
        metric = page.locator("[data-active-chapter] .record-metric-value").nth(index)
        expect(metric.locator("strong")).to_have_text(value)
        counted = page.evaluate("where => obsRecordMetrics.select({where}).map(record => `note:${record.slug}`).sort()",
                                [*where, {"field": "region", "equals": label}])
        metric.click()
        rows = page.locator('[data-active-chapter] [data-data-table="chapter-base-1"] [data-row-key]')
        expect(rows).to_have_count(len(counted))
        assert sorted(rows.evaluate_all("rows => rows.map(row => row.dataset.rowKey)")) == counted, label
    assert errors == []


def test_a_projected_metric_drill_down_selects_through_its_projection(tmp_path, reader_browser) -> None:
    """A metric with obs.projection counts the projected fields; its drill-down selects through
    the same projection (obs capabilities/cards-metrics#Drill-downs), so while the projection
    makes service two healthy and service one not, the table shows two and three."""
    where = [{"field": "healthy", "equals": "yes"}]
    cards = _cards({"title": "Review", "body": "", "metricStyle": "pills", "metrics": [
        {"label": "Healthy", "where": where, "link": "#chapter", "obs": {"projection": "review"}}]})
    spec = {"filters": {"and": ['kind == "service"']},
            "views": [{"type": "table", "name": "Services", "order": ["healthy"]}]}
    source = build("Cards", chapter("chapter", "Chapter", heading(1, "Operations"), node("bases", source="", spec=spec)),
                   abstract=(cards,), records=tuple(_services()))
    page, errors = _open(tmp_path, reader_browser, source)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('home')")
    page.evaluate("obsCards.setProjection('review', {'one.md': {healthy: 'no'}, 'two.md': {healthy: 'yes'}})")
    metric = page.locator("[data-active-chapter] .record-metric-value").first
    expect(metric.locator("strong")).to_have_text("2")
    counted = page.evaluate("where => obsRecordMetrics.select({where}, 'review').map(record => `note:${record.slug}`)"
                            ".sort()", where)
    assert counted == ["note:three", "note:two"]
    metric.click()
    rows = page.locator('[data-active-chapter] [data-data-table="chapter-base-1"] [data-row-key]')
    expect(rows).to_have_count(len(counted))
    assert sorted(rows.evaluate_all("rows => rows.map(row => row.dataset.rowKey)")) == counted
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
    and a series makes one metric per list entry, selecting the series' where plus its label
    (the drill-down derives from that selection). A
    metric link's filter derives from the conditions the metric counts, a secondary link's from
    its quantity's (the counts notes' queries in the vault)."""
    document = json.loads((ROOT / "test" / "fixtures" / "documents" / "cards.json").read_text(encoding="utf-8"))
    queries = {record["path"]: record["fields"]["query"] for record in document["records"]
               if str(record.get("path", "")).startswith("counts/")}
    points, open_points = queries["counts/points.md"]["where"], queries["counts/open.md"]["where"]
    page, errors = _open(tmp_path, reader_browser, document)

    def drill_down(link: str, where: list[dict]) -> str:
        expression = page.evaluate("where => obsQuery.conditionsExpression(where)", where)
        return f"{link}?tableFilter={quote(expression, safe='')}"

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
    expect(share.locator(".record-metric-value")).to_have_attribute(
        "href", drill_down("#target", [{"field": "status", "equals": "open"}]))
    compound = metrics.locator("[data-record-metric='1']")
    expect(compound).to_have_class("record-metric record-metric--negative")
    expect(compound.locator(".record-metric-value")).to_have_text("3 (2)")
    expect(compound.locator("[data-quantity-reference]")).to_have_count(2)
    assert compound.locator("[data-quantity-reference]").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))") == [
        drill_down("#overview", points), drill_down("#target", points + open_points)]
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
        drill_down("#overview", [{"field": "kind", "equals": "point"}, {"field": "status", "equals": label}])
        for label in ("open", "closed")]
    assert errors == []


def test_every_drill_down_shows_exactly_the_rows_its_count_counted(tmp_path, reader_browser) -> None:
    """The ``cards`` fixture Document holds every kind of count with a drill-down: card metrics,
    a projected metric (under an active projection), a count query (a secondary quantity), a
    metric series and a dynamic Sankey. Each drill-down, followed as a reader follows it, shows
    exactly the rows its count counted (obs capabilities/cards-metrics#Drill-downs)."""
    document = json.loads((ROOT / "test" / "fixtures" / "documents" / "cards.json").read_text(encoding="utf-8"))
    records = {record["path"].removesuffix(".md"): record["fields"] for record in document["records"] if "path" in record}
    page, errors = _open(tmp_path, reader_browser, document)
    from playwright.sync_api import expect
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('overview')")
    page.evaluate("obsCards.setProjection('review', {'b-point.md': {status: 'open'}})")
    select = "([query, key]) => obsRecordMetrics.select(query, key).map(record => `note:${record.slug}`).sort()"
    kinds: set[str] = set()

    def follow(kind: str, link, counted: list[str]) -> None:
        link.click()
        rows = page.locator("[data-active-chapter] [data-data-table]").first.locator("[data-row-key]")
        expect(rows).to_have_count(len(counted))
        assert sorted(rows.evaluate_all("rows => rows.map(row => row.dataset.rowKey)")) == counted, kind
        kinds.add(kind)
        page.evaluate("obsArtifact.activateChapter('overview')")

    for card in page.locator("[data-active-chapter] [data-record-card]").all():
        metrics = json.loads(card.get_attribute("data-record-card"))
        slots = card.locator(".record-metrics").first
        for index, metric in enumerate(metrics):
            slot = slots.locator(f"[data-record-metric='{index}']")
            projection = (metric.get("obs") or {}).get("projection", "")
            query = {"where": metric["where"], **({"from": metric["from"]} if "from" in metric else {})}
            if projection:
                assert page.evaluate(select, [query, projection]) != page.evaluate(select, [query, ""])
            if "link" in metric:
                link = slot.locator("[data-quantity-reference]").first if "secondary" in metric \
                    else slot.locator(".record-metric-value")
                follow("projected metric" if projection else "card metric", link,
                       page.evaluate(select, [query, projection]))
            if "secondaryLink" in metric:
                follow("count query", slot.locator("[data-quantity-reference]").nth(1),
                       page.evaluate(select, [records[metric["secondary"]]["query"], ""]))
        if series := card.get_attribute("data-record-series"):
            series = json.loads(series)
            entries = records[series["sourceNote"]]
            for part in series["property"].split("."):
                entries = entries[part]
            for index, entry in enumerate(entries, start=len(metrics)):
                where = [*series["where"], {"field": series["link"]["groupProperty"],
                                            "equals": entry[series["labelProperty"]]}]
                follow("series", slots.locator(f"[data-record-metric='{index}'] .record-metric-value"),
                       page.evaluate(select, [{"where": where}, ""]))

    figure = page.locator("[data-active-chapter] [data-figure-kind='sankey']")
    graph = json.loads(figure.get_attribute("data-figure-spec"))
    retained = ("() => obsArtifact.records.filter(record => obsArtifact.selectable(record) && "
                "obsArtifact.matchesFilter(record)).map(record => `note:${record.slug}`).sort()")
    linked = ("([population, where]) => obsArtifact.records.filter(record => obsArtifact.selectable(record) && "
              "obsQuery.compileConditions(population).match(record) && obsQuery.compileConditions(where).match(record))"
              ".map(record => `note:${record.slug}`).sort()")
    links = [{**link, "rows": page.evaluate(linked, [graph["data"]["where"], link["where"]])} for link in graph["links"]]
    assert figure.locator(".sankey-link").evaluate_all("links => links.map(link => link.dataset.flowValue)") == [
        str(len(link["rows"])) for link in links if link["rows"]]
    for node_spec in graph["nodes"]:
        incident = [link for link in links if node_spec["id"] in (link["source"], link["target"])]
        counted = sorted({row for link in incident for row in link["rows"]})
        if "records" in node_spec:
            assert counted == sorted(set(counted) & set(page.evaluate(linked, [graph["data"]["where"],
                                                                               node_spec["records"]["where"]])))
        figure.locator(f"[data-node-id='{node_spec['id']}']").click()
        page.wait_for_function(f"(counted => JSON.stringify(({retained})()) === JSON.stringify(counted))", arg=counted)
        kinds.add("sankey")
        # The reader's filter hides the overview chapter itself, so the reader returns to it.
        page.evaluate("obsFilter.setExpression(''); obsArtifact.activateChapter('overview')")
    assert kinds == {"card metric", "projected metric", "count query", "series", "sankey"}
    assert errors == []
