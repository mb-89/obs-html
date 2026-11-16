"""Two-column blocks render as the interim adapter in obs rendered them (its test_columns.py).

Reader: whoever changes how obs-html renders a ``columns`` node (render.py, _columns; columns.css).

The cases read the committed ``columns`` fixture Document, which the core built from the columns
vault (test/fixtures/build_documents.py); the core's own cases are obs's test/test_columns.py.
"""
import json
import re

import pytest

from artifacts import artifact_html
from conftest import ROOT
from documents import chapter, document, paragraph
from obs_html.artifact_data import decode_artifact_data
from obs_html.errors import InputError
from obs_html.features import feature_source


COLUMNS = json.loads((ROOT / "test" / "fixtures" / "documents" / "columns.json").read_text(encoding="utf-8"))


def _notes(source: dict) -> dict[str, dict]:
    return {note["slug"]: note for note in decode_artifact_data(artifact_html(source))["notes"]}


def _block(left: str = "Left.", right: str = "Right.", weights: object = (1, 1)) -> dict:
    return {"type": "columns", "attrs": {"weights": list(weights) if isinstance(weights, tuple) else weights},
            "children": [{"type": "document", "attrs": {}, "children": [paragraph(text)]} for text in (left, right)]}


def test_a_weighted_block_renders_its_two_columns_at_their_weights_without_inline_styles() -> None:
    html = _notes(COLUMNS)["columns"]["html"]
    [block] = re.findall(r'<div class="content-columns" data-content-columns="1:2">.*?</div></div>\n', html, re.S)

    assert re.findall(r'class="(content-column [^"]*)"', block) == [
        "content-column content-column--weight-1", "content-column content-column--weight-2"]
    assert "style=" not in block
    assert html.count('class="content-columns"') == 2
    assert html.count('data-record-cards') == 1 and html.count('data-base-table=') == 1
    assert 'href="#columns/details"' in html and 'id="columns--details"' in html
    assert 'data-mark-kind="open_point"' in block
    assert "|||" not in html.replace("<code>|||</code>", "").split("<pre", 1)[0]


def test_delimiters_in_code_and_prose_stay_text_and_tables_end_at_a_delimiter() -> None:
    notes = _notes(COLUMNS)
    html = notes["columns"]["html"]

    assert '<code class="language-text">|||\n|||\n|||\n</code></pre>' in html
    assert "<code>|||\n</code></pre>" in html
    assert "inline ||| stays prose" in html
    tables = html.split('data-content-columns="1:1"')[1]
    assert tables.count("<table ") == 2 and tables.count("<tr") == 4
    more = notes["more"]["html"]
    assert more.count('class="content-columns"') == 2 and more.count('class="content-column ') == 4
    assert "<code>|||</code>" in more


def test_a_block_in_the_manifest_home_holds_its_one_base_table() -> None:
    home = _notes(COLUMNS)["home"]

    assert home["html"].count('class="content-column ') == 2
    assert home["html"].count('data-base-table="home-base-1"') == 1
    assert len(home["tables"]) == 1


def test_the_column_rules_ship_only_with_a_block() -> None:
    rules = feature_source("columns.css").strip()
    plain = document("Plain", chapter("one", "One", paragraph("Text.")))

    assert rules in artifact_html(COLUMNS)
    assert rules not in artifact_html(plain)
    assert ".content-column" not in artifact_html(plain)


@pytest.mark.parametrize(("block", "field"), [
    (_block(weights=[0, 2]), "attrs.weights"),
    (_block(weights=[1]), "attrs.weights"),
    ({**_block(), "children": _block()["children"][:1]}, "children"),
])
def test_a_block_the_core_does_not_write_is_refused_naming_its_field(block: dict, field: str) -> None:
    with pytest.raises(InputError) as raised:
        artifact_html(document("Stale", chapter("one", "One", block)))

    assert f"[0].{field}" in str(raised.value) or field in str(raised.value)
