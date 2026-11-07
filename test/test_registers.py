"""Registers: a ``registers`` node renders from its attrs alone (obs capabilities/registers, Document node).

The core-built Document ``fixtures/documents/registers.json`` (vault ``registers`` in
``fixtures/build_documents.py``) embeds ``points.base`` whole and by one view heading, and
``types.base``, which has one view per record type. The DOM tier shows each view's rows as the
reader sees them; the core selected them, and the adapter evaluates no selection.
"""
import re
import copy
import json
from pathlib import Path

import pytest

from conftest import CORE_ROOT, ROOT
from documents import chapter, document as build, node, paragraph
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from test_dom import run_artifact_dom_contract


CONFIG = load_config()
REGISTERS = json.loads((ROOT / "test" / "fixtures" / "documents" / "registers.json").read_text(encoding="utf-8"))
RECORD_TYPES = json.loads((CORE_ROOT / "src" / "obs" / "document.schema.json").read_text(encoding="utf-8"))[
    "$defs"]["record"]["properties"]["type"]["enum"]


def _inspect(document: dict, folder: Path, chapters: list[str]) -> dict:
    artifact = folder / "registers.html"
    artifact.write_text(render(document, CONFIG), encoding="utf-8")
    output = run_artifact_dom_contract(artifact, "--inspect-json", arguments=(json.dumps(chapters),))
    return json.loads(output)["chapters"]


def _register(document: dict, chapter_id: str) -> dict:
    """The first registers node of a chapter, at any depth (a register can sit in a list item or a callout)."""
    stack = list(next(item for item in document["chapters"] if item["id"] == chapter_id)["content"])
    while stack[0]["type"] != "registers":
        stack[:1] = stack[0]["children"]
    return stack[0]


@pytest.fixture(scope="module")
def inspected(tmp_path_factory) -> dict:
    return _inspect(REGISTERS, tmp_path_factory.mktemp("registers"), ["points", "second", "types"])


def test_the_registers_document_is_contract_valid(document_validator) -> None:
    document_validator.validate(REGISTERS)
    assert "registers" in REGISTERS["capabilities"]


@pytest.mark.dom
def test_a_register_embed_renders_every_view_with_the_rows_the_core_selected(inspected) -> None:
    [views] = inspected["points"]["views"]
    assert [view["name"] for view in views] == ["Labelled", "Second"]
    assert sorted(views[0]["rows"]) == ["note:a-point", "note:c-point"]
    assert views[1]["rows"] == ["note:b-point"]


@pytest.mark.dom
def test_a_view_heading_embed_renders_that_one_view_without_a_selector(inspected) -> None:
    assert inspected["second"]["views"] == [[{"name": "", "rows": ["note:b-point"], "labels": []}]]


# The view of types.base over each record type, and the rows the reader sees: the core's rows, and
# for documentMetadata also the adapter's generation provenance (generic-tables, Bases filter grammar).
TYPE_VIEWS = {
    "note": ("Notes", ["note:a-point", "note:b-point", "note:c-point", "note:d-point"]),
    "chapter": ("Chapters", ["points", "second", "types"]),
    "tag": ("Tags", ["second:risk:second_risk"]),
    "glossary": ("Glossary", ["glossary:datum"]),
    "documentMetadata": ("Metadata", ["metadata:status", "generation:timestamp", "generation:generator",
                                      "generation:target"]),
    "documentHistory": ("History", ["history:0", "history:1"]),
}


def test_a_register_renders_between_the_paragraphs_of_the_text_around_it() -> None:
    """A register's table is a block beside the paragraphs, as the core places it (obs
    capabilities/markdown#Document nodes): the text around the embed stays paragraphs, in order,
    and an embed alone leaves no empty paragraph."""
    alone = render(REGISTERS, CONFIG)
    notes = {note["slug"]: note["html"] for note in decode_artifact_data(alone)["notes"]}
    assert '<h1 id="points--points">Points</h1>\n<p>All views.</p>\n<div class="data-table-placeholder" ' \
        in notes["points"]
    register = _register(REGISTERS, "points")
    document = build("Doc", chapter(
        "one", "One", paragraph("Before "), register,
        paragraph(" after"),
    ), records=tuple(REGISTERS["records"]))
    html = next(note["html"] for note in decode_artifact_data(render(document, CONFIG))["notes"]
                if note["slug"] == "one")
    assert html.startswith('<p>Before </p>\n<div class="data-table-placeholder" data-base-table="one-base-1"></div>\n'
                           "<p> after</p>\n"), html


def test_the_record_type_views_cover_every_record_type_of_the_core_schema() -> None:
    assert sorted(TYPE_VIEWS) == sorted(RECORD_TYPES)


@pytest.mark.dom
@pytest.mark.parametrize("record_type", sorted(TYPE_VIEWS))
def test_a_view_over_each_record_type_renders_the_rows_the_core_selected(inspected, record_type: str) -> None:
    name, rows = TYPE_VIEWS[record_type]
    [views] = inspected["types"]["views"]
    view = next(view for view in views if view["name"] == name)
    assert sorted(view["rows"]) == sorted(rows)


def test_records_other_than_notes_do_not_become_notes() -> None:
    slugs = {note["slug"] for note in decode_artifact_data(render(REGISTERS, CONFIG))["notes"]}
    assert {"a-point", "datum", "points"} <= slugs
    assert not slugs & {record["id"] for record in REGISTERS["records"] if record["type"] != "note"}


@pytest.mark.dom
def test_views_with_different_members_show_the_core_rows_in_member_order_with_their_labels(inspected) -> None:
    [views] = inspected["points"]["views"]
    assert views[0] == {"name": "Labelled", "rows": ["note:c-point", "note:a-point"], "labels": ["C", "A"]}


@pytest.mark.dom
def test_members_label_the_core_rows_in_the_order_received_without_sorting_them(tmp_path: Path) -> None:
    """The core emits a members view's rows in member order (obs generic-tables); the adapter keeps
    the order it receives, so rows the core sent in another order stay in it."""
    document = copy.deepcopy(REGISTERS)
    _register(document, "points")["attrs"]["rows"][0] = ["a-point", "c-point"]
    [views] = _inspect(document, tmp_path, ["points"])["points"]["views"]
    assert views[0] == {"name": "Labelled", "rows": ["note:a-point", "note:c-point"], "labels": ["A", "C"]}


@pytest.mark.dom
def test_the_adapter_shows_the_core_rows_and_evaluates_no_selection(tmp_path: Path) -> None:
    """Rows the filter and members would not select show when the core names them, in its order, and
    no others."""
    document = copy.deepcopy(REGISTERS)
    _register(document, "second")["attrs"]["rows"][1] = ["d-point", "a-point"]
    assert _inspect(document, tmp_path, ["second"])["second"]["views"][0][0]["rows"] == ["note:d-point",
                                                                                          "note:a-point"]


def test_no_members_evaluation_remains_in_the_adapter() -> None:
    runtime = "".join((ROOT / "src" / "obs_html" / name).read_text(encoding="utf-8")
                      for name in ("artifact.js", "tables.js"))
    assert "definition.obs?.members" not in runtime
    assert "Missing Bases member note" not in runtime


def test_a_register_row_the_records_do_not_hold_fails_naming_the_register_and_the_remedy() -> None:
    document = copy.deepcopy(REGISTERS)
    _register(document, "second")["attrs"]["rows"][1] = ["gone"]
    with pytest.raises(InputError) as failure:
        render(document, CONFIG)
    assert failure.value.source == "Document of manifest.md"
    assert re.fullmatch(r"chapters\[\d+\]\.content\[\d+\]\.attrs\.rows\[1\]", failure.value.field), failure.value.field
    assert "obs-document" in failure.value.remedy


def test_a_base_fence_with_members_fails_naming_the_field_and_the_remedy() -> None:
    spec = {"views": [{"type": "table", "order": ["file.name"],
                       "obs": {"members": [{"path": "a.md", "label": "A"}]}}]}
    with pytest.raises(InputError) as failure:
        render(build("Doc", chapter("one", "One", node("bases", source="", spec=spec))), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", "base.views[0].obs.members")


def test_the_base_schema_leaves_the_cores_keys_to_the_core() -> None:
    """records and members are the core's (obs input-model#Core and adapter namespaces): the core's
    schema owns them, and the adapter's own namespace has no place for them."""
    schema = json.loads((ROOT / "src" / "obs_html" / "base.schema.json").read_text(encoding="utf-8"))
    view = schema["properties"]["views"]["items"]["properties"]
    for namespace in (schema["properties"]["obsHtml"], view["obsHtml"]):
        assert not {"records", "members"} & set(namespace["properties"])
    assert schema["properties"]["obs"] == view["obs"] == {"$ref": "#/$defs/core"}
