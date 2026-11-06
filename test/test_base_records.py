"""DOM tier: Base views select, show and sort the Document's note records (obs capabilities/bases)."""
from pathlib import Path

import pytest

from documents import chapter, document, node
from obs_html.config import load_config
from obs_html.render import render
from test_artifact_harness import run_harness


pytestmark = pytest.mark.dom


def record(identifier: str, path: str, ignored: bool = False, **fields: object) -> dict:
    return {"id": identifier, "type": "note", "path": path, "fields": fields,
            **({"ignored": True} if ignored else {})}


RECORDS = (
    record("items-alpha", "items/alpha.md", kind="item", status="open", rank=2),
    record("items-beta", "items/beta.md", kind="item", status="closed", rank=1),
    record("items-gamma", "items/gamma.md", kind="item", status="open", rank=3),
    record("archive-delta", "archive/delta.md", kind="item", status="open", rank=4),
)
IGNORED = record("items-hidden", "items/hidden.md", ignored=True, kind="item", status="open", rank=0)


def base(filters: object, order: list[str], sort: list[dict] | None = None) -> dict:
    view = {"type": "table", "name": "Items", "order": order, **({"sort": sort} if sort else {})}
    return node("bases", source="filters: ...\n", spec={"filters": filters, "views": [view]})


def table(tmp_path: Path, spec: dict, records: tuple[dict, ...] = RECORDS) -> dict:
    source = document("Records", chapter("items", "Items", spec), records=records)
    artifact = tmp_path / "artifact.html"
    artifact.write_text(render(source, load_config()), encoding="utf-8")
    _, result = run_harness(artifact, tmp_path, {"step": "activate", "chapter": "items"},
                            {"step": "table", "key": "items-base-1"})
    return result


def test_a_file_filter_selects_by_the_record_path(tmp_path: Path) -> None:
    result = table(tmp_path, base('file.folder == "items"', ["file.name", "file.path"],
                                  [{"property": "file.name", "direction": "ASC"}]))
    assert result["rows"] == ["note:items-alpha", "note:items-beta", "note:items-gamma"]
    assert result["cells"][0] == ["alpha", "items/alpha.md"]


def test_a_property_filter_selects_by_the_record_fields(tmp_path: Path) -> None:
    result = table(tmp_path, base({"and": ['kind == "item"', 'status == "open"']}, ["file.name", "status"],
                                  [{"property": "file.name", "direction": "ASC"}]))
    assert result["rows"] == ["note:items-alpha", "note:archive-delta", "note:items-gamma"]
    assert result["count"] == "3 of 3 items"


def test_sorting_orders_the_records(tmp_path: Path) -> None:
    result = table(tmp_path, base('kind == "item"', ["file.name", "rank"],
                                  [{"property": "rank", "direction": "DESC"}]))
    assert [cells[0] for cells in result["cells"]] == ["delta", "gamma", "alpha", "beta"]


def test_an_ignored_record_that_matches_is_neither_listed_nor_counted(tmp_path: Path) -> None:
    result = table(tmp_path, base('status == "open"', ["file.name"]), (*RECORDS, IGNORED))
    assert "note:items-hidden" not in result["rows"]
    assert result["count"] == "3 of 3 items"


def test_the_runtime_query_population_does_not_count_an_ignored_record(tmp_path: Path) -> None:
    source = document("Records", chapter("items", "Items"), records=(*RECORDS, IGNORED),
                      metadata={"obsHtml": {"query": {"scope": "records"}}})
    artifact = tmp_path / "artifact.html"
    artifact.write_text(render(source, load_config()), encoding="utf-8")
    [summary] = run_harness(artifact, tmp_path, {"step": "summary"})
    assert summary == {"records": 5, "totalRecords": 5}  # The chapter and four records.
