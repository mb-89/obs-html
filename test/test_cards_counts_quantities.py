"""Cards and metrics, count queries and quantities render as the interim adapter in obs rendered them.

Each test builds a contract-valid Document as the core emits it (see the core's vault.py): a
``cards-metrics`` node carries the parsed fence as ``spec``, whose card bodies stay Markdown; a
quantity note's chapter starts with ``quantities`` (its metadata) and, with a ``query``, a
``count-query`` node; every note is a record whose ``fields`` are its frontmatter.
"""
import json
from html import escape, unescape

import pytest

from obs_html.config import load_config
from obs_html.render import RenderError, render
from obs_html.artifact_data import decode_artifact_data

from documents import chapter, document as build, node, paragraph


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


def _cards(*cards: dict) -> dict:
    spec = {"version": 1, "cards": list(cards)}
    return node("cards-metrics", source=json.dumps(spec), spec=spec)


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
                        {"title": "Evidence", "body": "Unfiltered [instructions](https://example.org)."}))
    assert html.startswith('<div class="record-cards" data-record-cards>'
                           '<section class="content-card record-card" data-record-card="')
    assert '<header class="content-card-title">Service &lt;health&gt;</header>' in html
    assert ('<div class="record-metrics "><div data-record-metric="0" role="status" aria-busy="true">'
            'Calculating…</div><div data-record-metric="1" role="status" aria-busy="true">Calculating…</div></div>'
            '<p>Ordinary <strong>operations</strong>.</p>\n</section>') in html
    assert _card_payload(html) == metrics
    assert ('<section class="content-card record-card" data-record-card="[]">'
            '<header class="content-card-title">Evidence</header>'
            '<p>Unfiltered <a href="https://example.org">instructions</a>.</p>\n</section></div>\n') in html


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


def test_card_bodies_resolve_wikilinks_by_path_name_and_alias() -> None:
    html = _html(_cards({"title": "Ops", "body": "Items [[serviceCount]] ([[counts/subset]] active), "
                                                 "limit [[limit]], [[one|back]], [[gone]], `[[code]]`."}))
    assert ('<p>Items <a class="internal-link" href="#counts-total" data-quantity-reference="counts/total.md" '
            'aria-busy="true" role="status">Calculating…</a> (<a class="internal-link" href="#counts-subset" '
            'data-quantity-reference="counts/subset.md" aria-busy="true" role="status">Calculating…</a> active), '
            'limit <a class="internal-link" href="#limit">20 mm</a>, '
            '<a class="internal-link" href="#one">back</a>, '
            '<span class="unresolved" title="gone">gone</span>, <code>[[code]]</code>.</p>') in html


def test_a_compound_metric_value_is_the_primary_and_secondary_quantity_links() -> None:
    metric = {"label": "Findings (unexplained)", "from": "counts/total", "where": [],
              "secondary": "counts/subset", "secondaryLink": "#one?tableFilter=explained%3Afalse",
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
    with pytest.raises(RenderError, match=r"Chapter one: card 'Series' metric series one/groups.list .*unique"):
        _notes(source)


def test_a_capability_fence_in_a_card_body_names_the_card_and_the_remedy() -> None:
    with pytest.raises(RenderError, match=r"Chapter one: card 'Bounded' body holds a base fence.*Remedy"):
        _html(_cards({"title": "Bounded", "body": "```base\nviews: []\n```"}))


def test_a_malformed_cards_spec_names_the_chapter_and_the_remedy() -> None:
    with pytest.raises(RenderError, match=r"Chapter one: cards fence .*regenerate the Document"):
        _html(node("cards-metrics", source="", spec={"version": 1, "cards": [{"body": ""}]}))


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


@pytest.mark.parametrize(("change", "message"), [
    ({"value": None}, "needs exactly one of value or query"),
    ({"query": {"where": []}}, "needs exactly one of value or query"),
    ({"value": "20"}, "value must be a finite number"),
    ({"unit": " "}, "unit must be a non-empty string"),
    ({"aliases": ["two", "names"]}, "needs one short variable-style alias"),
    ({"source": "plain text"}, "source must .*note link"),
])
def test_invalid_quantity_metadata_names_the_chapter_and_the_remedy(change, message) -> None:
    source = _document(paragraph("Text."))
    metadata = {key: value for key, value in {**LIMIT, **change}.items() if value is not None}
    limit = next(item for item in source["chapters"] if item["id"] == "limit")
    limit["content"][1] = node("quantities", metadata=metadata)
    with pytest.raises(RenderError, match=rf"Chapter limit: quantity {message}.*Remedy"):
        render(source, CONFIG)


def test_a_count_query_without_conditions_names_the_chapter_and_the_remedy() -> None:
    source = _document(paragraph("Text."))
    total = next(item for item in source["chapters"] if item["id"] == "counts-total")
    total["content"][3] = node("count-query", query={"distinct": "identity"})
    with pytest.raises(RenderError, match=r"Chapter counts-total: count query has no where list.*regenerate"):
        render(source, CONFIG)
