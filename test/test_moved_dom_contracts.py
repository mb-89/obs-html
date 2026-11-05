"""The interim adapter's remaining DOM contracts (test/browser/artifact-ui.cjs modes), on Documents.

Each contract runs on a Document the obs core built from the interim test's vault
(test/fixtures/build_documents.py owns the vaults and says how to regenerate them). Moved from
obs: test_browser.py (test_complete_document_dom_interactions), test_artifact_changes.py
(test_artifact_change_owner_controlled_save_boundaries), test_record_projections.py and
test_table_help_browser.py (test_table_help_reuses_shared_rich_hover_dom).
"""
import json
from importlib.resources import files
from pathlib import Path

import pytest

from conftest import ROOT
from obs_html.render import render
from obs_html.artifact_data import decode_artifact_data
from test_dom import CONFIG, run_artifact_dom_contract


DOCUMENTS = ROOT / "test" / "fixtures" / "documents"


def _document(name: str) -> dict:
    return json.loads((DOCUMENTS / f"{name}.json").read_text(encoding="utf-8"))


def _artifact(tmp_path: Path, name: str) -> Path:
    artifact = tmp_path / f"{name}.html"
    artifact.write_text(render(_document(name), CONFIG), encoding="utf-8")
    return artifact


@pytest.mark.parametrize("name", sorted(path.stem for path in DOCUMENTS.glob("*.json")))
def test_fixture_documents_are_contract_valid(name, document_validator) -> None:
    document_validator.validate(_document(name))


def test_the_complete_document_uses_references_and_a_callout_without_an_extension() -> None:
    capabilities = _document("complete")["capabilities"]
    assert {"references", "callouts"} <= set(capabilities)
    assert "extensions" not in capabilities


@pytest.mark.dom
def test_complete_document_dom_interactions(tmp_path: Path) -> None:
    package = files("obs_html")
    run_artifact_dom_contract(_artifact(tmp_path, "complete"), "", package / "bars" / "comments.js",
                            package / "bars" / "settings.js", package / "storage.js")


@pytest.mark.dom
def test_artifact_change_owner_controlled_save_boundaries(tmp_path: Path) -> None:
    package = files("obs_html")
    output = run_artifact_dom_contract(_artifact(tmp_path, "artifact-change"), "--artifact-change-only",
                                     package / "bars" / "filter.js", package / "bars" / "comments.js",
                                     package / "storage.js")
    assert output.startswith("PASS artifact/review dirty")


@pytest.fixture(scope="module")
def projected(tmp_path_factory) -> dict:
    artifact = _artifact(tmp_path_factory.mktemp("projections"), "projections")
    notes = decode_artifact_data(artifact.read_text(encoding="utf-8"))["notes"]
    inspected = json.loads(run_artifact_dom_contract(artifact, "--inspect-json", arguments=(json.dumps(["registers"]),)))
    return {"notes": {note["sourcePath"]: note["slug"] for note in notes}, **inspected}


@pytest.mark.dom
def test_record_projections_select_the_same_notes_in_generator_and_browser(projected) -> None:
    slugs = projected["notes"]
    assert sorted(slugs) == [
        "draft-term.md", "extra/elsewhere.md", "extra/located.md", "glossary.md", "home.md", "manifest.md",
        "marked.md", "registers.md", "slugged.md",
    ]
    assert projected["chapters"]["registers"]["tables"] == [
        [f"glossary:{slugs['glossary.md']}"],
        [f"note:{slugs['extra/located.md']}"],
        [],
        [f"note:{slugs['slugged.md']}"],
        [f"{slugs['marked.md']}:open_point:datum_watch"],
        [f"note:{slugs['slugged.md']}"],
        [f"{slugs['registers.md']}:risk:register_check"],
    ]


@pytest.mark.dom
def test_filter_attributes_come_from_the_single_flattened_frontmatter(projected) -> None:
    record = next(item for item in projected["records"] if item["slug"] == projected["notes"]["slugged.md"])
    assert [entry[:2] for entry in record["metadataEntries"]] == [
        ["kind", "evidence"], ["slug", "custom"], ["tags", "a, b"], ["nested.owner", "Ann"],
        ["empty", "[]"], ["blank", "{}"], ["items.0.name", "x"], ["items.1.name", "y"],
    ]
    assert record["filterAttributes"] == {
        "title": ["Slugged"], "slug": ["custom"], "depth": ["0"], "mark": [],
        "kind": ["evidence"], "tags": ["a", "b"], "nested.owner": ["Ann"], "empty": [],
        "items.0.name": ["x"], "items.1.name": ["y"],
    }


@pytest.mark.dom
def test_marked_paragraph_and_tag_table_row_have_unique_ids(projected) -> None:
    assert projected["chapters"]["registers"]["duplicateIds"] == []


@pytest.mark.dom
def test_table_help_reuses_shared_rich_hover_dom(tmp_path: Path) -> None:
    output = run_artifact_dom_contract(_artifact(tmp_path, "table-help"), "--table-help-only")
    assert output.startswith("PASS: shared table help")
