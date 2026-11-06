"""Cards and metrics, count queries and quantities render as the interim adapter in obs rendered them.

Each test builds a contract-valid Document as the core emits it (see the core's vault.py): a
``cards-metrics`` node carries the parsed fence as ``spec`` and each card's body as one
``document`` child node; a quantity note's chapter starts with ``quantities`` (its metadata) and, with a ``query``, a
``count-query`` node; every note is a record whose ``fields`` are its frontmatter.
"""
import json
from html import escape, unescape

import pytest

from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from obs_html.artifact_data import decode_artifact_data

from conftest import ROOT
from documents import chapter, document as build, node, paragraph, text


CONFIG = load_config()
TOTAL = {"kind": "quantity", "aliases": ["serviceCount"], "source": "[[one]]",
         "query": {"where": [{"field": "kind", "equals": "service"}], "distinct": "identity"}}
SUBSET = {"kind": "quantity", "aliases": ["activeCount"], "source": "[[one]]",
          "query": {"from": "counts/total", "where": [{"field": "active", "equals": "yes"}]}}
LIMIT = {"kind": "quantity", "aliases": ["staticLimit"], "source": "[[one]]", "value": 20.0, "unit": "mm"}


def _record(identifier: str, path: str, fields: dict) -> dict:
    return {"id": identifier, "type": "note", "path": path, "fields": fields}


def _quantity_chapter(identifier: str, metadata: dict) -> dict:
    content = [node("quantities", metadata=metadata)]
    if "query" in metadata:
        content += [node("queries", query=metadata["query"]), node("count-query", query=metadata["query"])]
    result = chapter(identifier, identifier.title(), *content, metadata=metadata)
    result["toc"] = False
    return result


def _document(*content: dict) -> dict:
    quantities = {"counts-total": ("counts/total.md", TOTAL), "counts-subset": ("counts/subset.md", SUBSET),
                  "limit": ("limit.md", LIMIT)}
    source = build("Doc", chapter("one", "One", *content),
                   *(_quantity_chapter(key, metadata) for key, (_, metadata) in quantities.items()),
                   records=(_record("one", "one.md", {}),
                            *(_record(key, path, metadata) for key, (path, metadata) in quantities.items())))
    return source


def _notes(source: dict) -> dict[str, dict]:
    return {note["slug"]: note for note in decode_artifact_data(render(source, CONFIG))["notes"]}


def _html(*content: dict) -> str:
    return _notes(_document(*content))["one"]["html"]


def _cards(*cards: dict, bodies: tuple[list[dict], ...] = ()) -> dict:
    """The node of a cards fence; ``bodies`` holds each card's body nodes, empty by default."""
    spec = {"version": 1, "cards": list(cards)}
    result = node("cards-metrics", source=json.dumps(spec), spec=spec)
    result["children"] = [{"type": "document", "attrs": {}, "children": list(body)}
                          for body in (bodies or tuple([] for _ in cards))]
    return result


def _strong(value: str) -> dict:
    return {"type": "strong", "attrs": {}, "children": [text(value)]}


def _fixture() -> dict:
    """The ``cards`` vault of fixtures/build_documents.py, built by the core."""
    return json.loads((ROOT / "test" / "fixtures" / "documents" / "cards.json").read_text(encoding="utf-8"))


def _link(target: str, chapter_id: str, label: str = "") -> dict:
    return node("wikilinks", target=target, chapter=chapter_id, heading="", label=label or target)


def _card_payload(html: str) -> list[dict]:
    start = html.index('data-record-card="') + len('data-record-card="')
    return json.loads(unescape(html[start:html.index('"', start)]))


def test_the_documents_are_contract_valid(document_validator) -> None:
    document_validator.validate(_document(_cards({"title": "T", "body": ""})))


def test_cards_render_titled_sections_with_metric_slots_and_markdown_bodies() -> None:
    metrics = [{"label": "Availability", "where": [{"field": "healthy", "equals": "yes"}],
                "denominator": [{"field": "kind", "equals": "service"}]},
               {"label": "Regions", "where": [{"field": "kind", "equals": "service"}], "distinct": "region"}]
    html = _html(_cards({"title": "Service <health>", "body": "Ordinary **operations**.", "metrics": metrics},
                        {"title": "Evidence", "body": "Unfiltered."},
                        bodies=([paragraph("Ordinary ", _strong("operations"), ".")], [paragraph("Unfiltered.")])))
    assert html.startswith('<div class="record-cards" data-record-cards>'
                           '<section class="content-card record-card" data-record-card="')
    assert '<header class="content-card-title">Service &lt;health&gt;</header>' in html
    assert ('<div class="record-metrics "><div data-record-metric="0" role="status" aria-busy="true">'
            'Calculating…</div><div data-record-metric="1" role="status" aria-busy="true">Calculating…</div></div>'
            '<p>Ordinary <strong>operations</strong>.</p>\n</section>') in html
    assert _card_payload(html) == metrics
    assert ('<section class="content-card record-card" data-record-card="[]">'
            '<header class="content-card-title">Evidence</header>'
            '<p>Unfiltered.</p>\n</section></div>\n') in html


def test_a_metric_style_classes_the_metric_row_without_changing_metric_links() -> None:
    html = _html(_cards({"title": "Coverage", "body": "", "metricStyle": "pills",
                         "metrics": [{"label": "Covered", "where": [], "link": "#one"}]}))
    assert 'class="record-metrics record-metrics--pills"' in html
    assert _card_payload(html)[0]["link"] == "#one"


def test_the_cards_runtime_ships_only_with_cards_or_query_quantities() -> None:
    with_cards = render(_document(_cards({"title": "T", "body": ""})), CONFIG)
    assert 'id="cards-script"' in with_cards
    plain = build("Plain", chapter("one", "One", paragraph("Text.")))
    assert 'id="cards-script"' not in render(plain, CONFIG)


def test_card_bodies_render_their_nodes_with_quantity_links() -> None:
    html = _html(_cards({"title": "Ops", "body": "Items [[serviceCount]], limit [[limit]], [[one|back]]."},
                        bodies=([paragraph("Items ", _link("serviceCount", "counts-total"), ", limit ",
                                           _link("staticLimit", "limit"), ", ", _link("one", "one", "back"), ".")],)))
    assert ('<p>Items <a class="internal-link" href="#counts-total" data-quantity-reference="counts/total.md" '
            'aria-busy="true" role="status">Calculating…</a>, limit <a class="internal-link" href="#limit">20 mm</a>, '
            '<a class="internal-link" href="#one">back</a>.</p>\n</section>') in html


def test_a_core_built_card_body_renders_its_base_table_and_its_nested_card() -> None:
    """A capability fence in a card body is a node like any other: the Base is a table
    placeholder of the chapter, the nested cards fence a card inside the outer card."""
    document = _fixture()
    assert {"bases", "cards-metrics", "wikilinks"} <= set(document["capabilities"])
    overview = next(note for note in decode_artifact_data(render(document, CONFIG))["notes"]
                    if note["slug"] == "overview")
    html = overview["html"]
    assert ('<header class="content-card-title">Outer</header><p>Points as a table:</p>\n'
            '<div class="data-table-placeholder" data-base-table="overview-base-1"></div>\n'
            '<div class="record-cards" data-record-cards><section class="content-card record-card" '
            'data-record-card="[]"><header class="content-card-title">Inner</header>'
            '<p>Nested <strong>body</strong> with <a class="internal-link" href="#target">Target</a>.</p>\n'
            '</section></div>\n</section>') in html
    assert [table["key"] for table in overview["tables"]] == ["overview-base-1"]
    assert overview["tables"][0]["definition"]["views"][0]["order"] == ["file.name", "status"]


def test_the_metric_contract_reaches_the_runtime_as_the_interim_adapter_ships_it() -> None:
    """Every metric field and the metric series reach cards.js unchanged, as the interim's
    render_cards ships them; only the compound value's links are this adapter's own."""
    from obs_html_interim.cards import render_cards

    document = _fixture()
    fence = next(item for item in next(chapter for chapter in document["chapters"] if chapter["id"] == "overview")
                 ["content"] if item["type"] == "cards-metrics")
    groups = next(record for record in document["records"] if record["id"] == "groups")["fields"]
    # The interim refuses a nested cards fence, so it renders the cards with metrics alone.
    # The interim reads the core's card keys in its own namespace (obs input-model#Core and adapter namespaces).
    metric_cards = [card for card in fence["attrs"]["spec"]["cards"] if card.get("metrics") or card.get("obs")]
    reference = render_cards(json.dumps({"version": 1, "cards": metric_cards}).replace('"obs":', '"obsHtml":'),
                             lambda source: "", "overview.md", lambda note: groups)
    html = next(note for note in decode_artifact_data(render(document, CONFIG))["notes"]
                if note["slug"] == "overview")["html"]

    def cards(markup: str) -> list[tuple[list[dict], str | None]]:
        result = []
        for section in markup.split('<section class="content-card record-card" ')[1:]:
            payload = [{key: value for key, value in metric.items() if key != "valueHtml"}
                       for metric in _card_payload(section)]
            series = section.split('data-record-series="')[1].split('"')[0] if "data-record-series" in section else None
            result.append((payload, series))
        return result

    shipped = cards(html)
    assert [payload for payload, _ in shipped if payload] == [
        [*card["metrics"]] for card in fence["attrs"]["spec"]["cards"] if card.get("metrics")]
    assert {"key", "denominator", "link", "tone", "toneRules", "secondaryLink", "obs"} <= {
        field for payload, _ in shipped for metric in payload for field in metric}
    assert shipped[-1][1] is not None and json.loads(unescape(shipped[-1][1])) == \
        fence["attrs"]["spec"]["cards"][2]["obs"]["metricsFrom"]
    reference_cards = [([{"obs" if key == "obsHtml" else key: value for key, value in metric.items()}
                         for metric in payload], series) for payload, series in cards(reference)]
    assert [card for card in shipped if card[0] or card[1]] == [card for card in reference_cards if card[0] or card[1]]


def test_a_compound_metric_value_is_the_primary_and_secondary_quantity_links() -> None:
    metric = {"label": "Findings (unexplained)", "from": "counts/total", "where": [],
              "secondary": "counts/subset", "secondaryLink": "#one",
              "toneRules": [{"value": "secondary", "when": "positive", "tone": "negative"}]}
    html = _html(_cards({"title": "Coverage", "body": "", "metricStyle": "lines", "metrics": [metric]}))
    [payload] = _card_payload(html)
    assert payload == {**metric, "valueHtml": (
        '<a class="internal-link" href="#counts-total" data-quantity-reference="counts/total.md" '
        'aria-busy="true" role="status">Calculating…</a> (<a class="internal-link" href="#counts-subset" '
        'data-quantity-reference="counts/subset.md" aria-busy="true" role="status">Calculating…</a>)')}
    assert 'class="record-metrics record-metrics--lines"' in html


def test_a_metric_series_names_its_source_list_and_checks_its_labels() -> None:
    series = {"sourceNote": "one", "property": "groups.list", "labelProperty": "name",
              "distinctProperty": "key", "where": []}
    source = _document(_cards({"title": "Series", "body": "", "obs": {"metricsFrom": series}}))
    source["records"][0]["fields"] = {"groups": {"list": [{"name": "A", "key": "a"}, {"name": "B", "key": "b"}]}}
    html = _notes(source)["one"]["html"]
    assert f'data-record-series="{escape(json.dumps(series), quote=True)}"' in html
    assert '<div class="record-metrics ">' in html
    source["records"][0]["fields"] = {"groups": {"list": [{"name": "A", "key": "a"}, {"name": "A", "key": "b"}]}}
    with pytest.raises(InputError) as failure:
        _notes(source)
    assert (failure.value.source, failure.value.field) == (source["records"][0]["path"], "groups.list[1]")


def test_unaliased_quantity_links_render_their_value_or_a_pending_count() -> None:
    html = _html(paragraph("Total ", _link("serviceCount", "counts-total"), ", limit ",
                           _link("staticLimit", "limit"), ", explicit ",
                           _link("serviceCount", "counts-total", "all services"), "."))
    assert html == (
        '<p>Total <a class="internal-link" href="#counts-total" data-quantity-reference="counts/total.md" '
        'aria-busy="true" role="status">Calculating…</a>, limit <a class="internal-link" href="#limit">'
        '20 mm</a>, explicit <a class="internal-link" href="#counts-total">all services</a>.</p>\n')


def test_a_static_quantity_note_carries_its_value_label_for_its_hover_card() -> None:
    notes = _notes(_document(paragraph("Text.")))
    assert notes["limit"]["valueLabel"] == "20 mm"
    assert "valueLabel" not in notes["counts-total"]
    assert notes["counts-total"]["frontmatter"]["query"] == TOTAL["query"]


@pytest.mark.parametrize("change", [{"aliases": ["two", "names"]}, {"source": "plain text"}])
def test_the_core_owns_the_quantity_contract_so_the_adapter_renders_what_it_receives(change) -> None:
    """The core refuses an invalid quantity note (obs capabilities/quantities, input.py
    validate_quantity) before a Document exists; the adapter trusts a contract-valid Document."""
    source = _document(paragraph("Text."))
    limit = next(item for item in source["chapters"] if item["id"] == "limit")
    limit["content"][1] = node("quantities", metadata={**LIMIT, **change})
    assert "limit" in _notes(source)


def test_the_core_owns_the_count_query_contract_so_the_adapter_renders_what_it_receives() -> None:
    """The core refuses a count query without conditions (input.py validate_count_query)."""
    source = _document(paragraph("Text."))
    total = next(item for item in source["chapters"] if item["id"] == "counts-total")
    total["content"][3] = node("count-query", query={"distinct": "identity"})
    assert "counts-total" in _notes(source)
