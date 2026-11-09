"""Comments through the core's model: the island the build writes, the core ids review items carry,
and the import of a returned copy (spec/input-model.md, Comments and the core model)."""
import copy
import json
import re
from pathlib import Path

import pytest

from core_calls import import_comments, unresolved_targets, validate_overlays, with_comments
from obs_html.artifact_data import decode_artifact_data
from obs_html.comments import OWNER, extract_comments
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render

ISLAND = re.compile(r'<script id="obs-comments" type="application/json" data-comment-island>(.*?)</script>', re.S)
EMPTY = {"version": 1, "files": [], "comments": [], "decisions": []}
PARAGRAPH = {"chapter": "intro", "node": "paragraph-957766ff"}
ROOT = {"id": "c1", "author": "Alice", "created": "2026-11-09T10:00:00Z", "state": "open",
        "body": {"mediaType": "text/plain", "text": "Clarify this."},
        "target": {**PARAGRAPH, "quote": "Selected", "prefix": "", "suffix": " text", "start": 0, "end": 8}}
REPLY = {"id": "c2", "author": "Bob", "created": "2026-11-09T11:00:00Z", "state": "resolved",
         "body": {"mediaType": "text/plain", "text": "Agreed."}, "inReplyTo": "c1"}
BATCH = {"id": "c3", "author": "Alice", "created": "2026-11-09T12:00:00Z", "state": "open",
         "body": {"mediaType": "text/plain", "text": "Rework the list."}, "target": {"chapter": "intro"},
         "batch": {"scope": "chapter", "items": [{"chapter": "intro", "node": "list-item-7692c3ad"},
                                                 {"chapter": "intro", "node": "bases-cc30b281:alpha"}]}}
DECISION = {"id": "d1", "reviewer": "Alice", "created": "2026-11-09T10:05:00Z", "target": PARAGRAPH,
            "state": "accepted"}


def model(*comments: dict, decisions: tuple[dict, ...] = ()) -> dict:
    return {"version": 1, "files": ["manifest.comments.alice.json"], "comments": list(comments),
            "decisions": list(decisions)}


def island(html: str) -> object:
    return json.loads(ISLAND.search(html).group(1))


def write_artifact(path: Path, value: object) -> Path:
    path.write_text('<!doctype html><script id="obs-comments" type="application/json" data-comment-island>'
                    f"{json.dumps(value)}</script><script>throw new Error('must not execute')</script>",
                    encoding="utf-8")
    return path


def _refused(artifact: Path, field: str, overlay: Path | None = None) -> InputError:
    """Extraction fails naming the reviewed HTML, the JSON path in its comment island and the owner."""
    with pytest.raises(InputError) as failure:
        extract_comments(artifact, overlay)
    assert (failure.value.source, failure.value.field) == (str(artifact), f"script#obs-comments{field}")
    assert OWNER in failure.value.remedy
    return failure.value


def test_the_island_is_the_documents_resolved_comments_and_empty_without_them(document) -> None:
    assert island(render(document, load_config())) == EMPTY
    document["comments"] = model(ROOT, REPLY, BATCH, decisions=(DECISION,))
    assert island(render(document, load_config())) == document["comments"]


def test_every_review_element_carries_its_blocks_core_id(document) -> None:
    data = decode_artifact_data(render(document, load_config()))
    notes = {note["slug"]: note for note in data["notes"]}
    intro, appendix = notes["intro"], notes["appendix"]
    for element in ('id="mark-intro-risk-limit" data-node-id="paragraph-957766ff">', '<li data-node-id="list-item-7692c3ad">',
                    '<pre class="command-output" data-node-id="command-fences-576af4dd">'):
        assert element in intro["html"]
    assert 'data-node-id="figures-009c9499"' in appendix["html"]
    assert 'data-node-id="paragraph-043c8ce6"' in appendix["html"]  # A card body's paragraph.
    assert [table["node"] for table in intro["tables"]] == ["bases-cc30b281"]
    assert data["rowRecords"]["note:alpha"] == "alpha"
    assert data["rowRecords"]["intro"] == "chapter-intro"


def test_extract_comments_lists_anonymized_threads_deterministically(tmp_path: Path) -> None:
    artifact = write_artifact(tmp_path / "reviewed.html", model(ROOT, REPLY, decisions=(DECISION,)))
    first = extract_comments(artifact)
    assert first == extract_comments(artifact)
    assert first == (
        "comment candidates: 1\n"
        "--- c1 [open] chapter intro node paragraph-957766ff\n"
        "quote: Selected\n"
        "reviewer-1: Clarify this.\n"
        "  reviewer-2 [resolved]: Agreed.\n"
    )
    assert "Alice" not in first and "throw new Error" not in first


def test_extract_comments_lists_an_abstract_target_and_each_state_entry_under_its_comment(tmp_path: Path) -> None:
    home = {**ROOT, "target": {"abstract": True, "node": "paragraph-8254a15d"}}
    states = [{"id": "s1", "author": "Bob", "created": "2026-11-09T12:00:00Z", "target": "c1", "state": "resolved"},
              {"id": "s2", "author": "Alice", "created": "2026-11-09T13:00:00Z", "target": "c1", "state": "open"}]
    artifact = write_artifact(tmp_path / "reviewed.html", {**model(home, REPLY), "states": states})
    assert extract_comments(artifact) == (
        "comment candidates: 1\n"
        "--- c1 [open] abstract node paragraph-8254a15d\n"
        "reviewer-1: Clarify this.\n"
        "reviewer-2 set it resolved\n"
        "reviewer-1 set it open\n"
        "  reviewer-2 [resolved]: Agreed.\n"
    )


def test_extract_comments_keeps_a_batch_scope_and_its_items(tmp_path: Path) -> None:
    extracted = extract_comments(write_artifact(tmp_path / "reviewed.html", model(BATCH)))
    assert "[Full chapter]" in extracted
    assert "item: intro list-item-7692c3ad\nitem: intro bases-cc30b281:alpha\n" in extracted


def test_an_island_of_the_retired_version_2_is_refused_at_its_version(tmp_path: Path) -> None:
    artifact = write_artifact(tmp_path / "reviewed.html", {"version": 2, "annotations": [], "reviews": [
        {"chapter": "intro", "item": "item-1", "reviewer": "Alice", "state": "accepted"}]})
    _refused(artifact, ".version")


@pytest.mark.parametrize("change, field", [
    (lambda value: value["comments"][0].update(state="done"), ".comments[0].state"),
    (lambda value: value["comments"][0].pop("created"), ".comments[0].created"),
    (lambda value: value["decisions"][0]["target"].update(node="item 1"), ".decisions[0].target.node"),
    (lambda value: value["comments"][1].update(target=PARAGRAPH), ".comments[1]"),
])
def test_an_island_the_cores_schema_refuses_names_its_field(tmp_path: Path, change, field) -> None:
    value = model(copy.deepcopy(ROOT), copy.deepcopy(REPLY), decisions=(copy.deepcopy(DECISION),))
    change(value)
    _refused(write_artifact(tmp_path / "reviewed.html", value), field)


def test_extract_comments_requires_exactly_one_island(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    one = f'<script id="obs-comments" type="application/json">{json.dumps(EMPTY)}</script>'
    artifact.write_text(one + one, encoding="utf-8")
    _refused(artifact, "")


def test_extraction_exports_the_islands_comments_in_the_cores_format(tmp_path: Path) -> None:
    island_value = model(ROOT, REPLY, BATCH, decisions=(DECISION,))
    output = tmp_path / "returned.json"
    extract_comments(write_artifact(tmp_path / "reviewed.html", island_value), output)
    assert json.loads(output.read_text(encoding="utf-8")) == island_value


def test_core_overlay_to_artifact_to_overlay_keeps_every_field(tmp_path: Path, document) -> None:
    """R3 at the build's seam: the overlay a principal wrote, through the Document, the island and the
    export, is the overlay the core's import writes back. The build's island names no reader; the
    Comments bar adds the reader's names when it saves, as here."""
    written = {"version": 1, "principal": "alice", "names": ["Alice", "Bob"], "comments": [ROOT, REPLY, BATCH],
               "decisions": [DECISION]}
    vault, returned = tmp_path / "vault", tmp_path / "returned"
    for folder in (vault, returned):
        folder.mkdir()
        (folder / "manifest.md").write_text("- [[intro]]\n", encoding="utf-8")
        (folder / "intro.md").write_text("# Intro\n\nText.\n", encoding="utf-8")
    (vault / "manifest.comments.alice.json").write_text(json.dumps(written), encoding="utf-8")
    document = with_comments(document, vault / "manifest.md")
    artifact = tmp_path / "reviewed.html"
    artifact.write_text(render(document, load_config()), encoding="utf-8")
    extract_comments(artifact, tmp_path / "returned.json")
    saved = json.loads((tmp_path / "returned.json").read_text(encoding="utf-8"))
    (tmp_path / "returned.json").write_text(json.dumps({**saved, "names": ["Alice", "Bob"]}), encoding="utf-8")
    import_comments(returned / "manifest.md", tmp_path / "returned.json", "alice", tmp_path / "document.json")
    assert json.loads((returned / "manifest.comments.alice.json").read_text(encoding="utf-8")) == written


MAPPED = """
const fs = require("node:fs"), vm = require("node:vm");
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const {fixtures} = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
console.log(JSON.stringify(Object.fromEntries(Object.entries(fixtures).map(
    ([name, native]) => [name, globalThis.obsCommentModel.toCore(native)]))));
"""


@pytest.mark.dom
def test_every_native_thread_fixture_maps_onto_core_targets_the_core_accepts(document) -> None:
    """The browser's mapping (comment-model.js) of each native fixture is an overlay the core's schema
    accepts, and each target is a block of the fixture Document (test/fixtures/comment-threads.json)."""
    import shutil
    import subprocess
    from importlib.resources import files

    result = subprocess.run(
        [shutil.which("node"), "-e", MAPPED, str(files("obs_html") / "comment-model.js"),
         str(Path(__file__).parent / "fixtures" / "comment-threads.json")],
        capture_output=True, text=True, check=True)
    mapped = json.loads(result.stdout)
    assert len(mapped) == 9
    validate_overlays([{"version": 1, "principal": "alice", "names": core["names"], "comments": core["comments"],
                        "decisions": core["decisions"], "states": core["states"]} for core in mapped.values()],
                      Path("manifest.comments.alice.json"))
    entries = [entry for core in mapped.values() for entry in [*core["comments"], *core["decisions"]]]
    targets = [entry["target"] for entry in entries if "target" in entry]
    targets += [item for entry in entries for item in entry.get("batch", {}).get("items", [])]
    assert {"abstract": True, "node": "paragraph-8254a15d"} in targets
    assert unresolved_targets(targets, document) == []
