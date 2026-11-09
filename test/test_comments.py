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


IMPORT = re.compile(r"^import: obs-document --source MANIFEST((?: --import-comments \S+ --principal \S+)+)$", re.M)


def _pairs(printed: str) -> list[tuple[str, str]]:
    """The file and principal pairs of the one import call the export printed, in its order."""
    calls = IMPORT.findall(printed)
    assert len(calls) <= 1, printed
    return re.findall(r" --import-comments (\S+) --principal (\S+)", calls[0]) if calls else []


def _vaults(tmp_path: Path, *names: str) -> list[Path]:
    """Vaults whose manifest lists the chapter intro, as the core imports into."""
    folders = [tmp_path / name for name in names]
    for folder in folders:
        folder.mkdir()
        (folder / "manifest.md").write_text("- [[intro]]\n", encoding="utf-8")
        (folder / "intro.md").write_text("# Intro\n\nText.\n", encoding="utf-8")
    return folders


def _import_printed(printed: str, vault: Path, tmp_path: Path) -> list[tuple[str, str]]:
    """Run the import call the export printed through the core's CLI; it refuses nothing."""
    pairs = _pairs(printed)
    import_comments(vault / "manifest.md", [(Path(file), principal) for file, principal in pairs],
                    tmp_path / "document.json")
    return pairs


def test_extraction_exports_one_file_per_author_in_the_cores_format(tmp_path: Path) -> None:
    island_value = {**model(ROOT, REPLY, BATCH, decisions=(DECISION,)), "names": ["Bob"]}
    printed = extract_comments(write_artifact(tmp_path / "reviewed.html", island_value), tmp_path / "returned.json")
    assert not (tmp_path / "returned.json").exists()
    assert json.loads((tmp_path / "returned.alice.json").read_text(encoding="utf-8")) == {
        "version": 1, "files": ["manifest.comments.alice.json"], "names": ["Alice"], "comments": [ROOT, BATCH],
        "decisions": [DECISION]}
    assert json.loads((tmp_path / "returned.bob.json").read_text(encoding="utf-8")) == {
        "version": 1, "files": ["manifest.comments.alice.json"], "names": ["Bob"], "comments": [REPLY],
        "decisions": []}
    assert _pairs(printed) == [(str(tmp_path / "returned.alice.json"), "alice"),
                               (str(tmp_path / "returned.bob.json"), "bob")]


def test_a_single_authors_copy_is_one_file_of_that_author_and_an_empty_copy_none(tmp_path: Path) -> None:
    printed = extract_comments(write_artifact(tmp_path / "reviewed.html", model(ROOT)), tmp_path / "returned.json")
    assert sorted(path.name for path in tmp_path.glob("returned*")) == ["returned.alice.json"]
    assert _pairs(printed) == [(str(tmp_path / "returned.alice.json"), "alice")]
    assert "import:" not in extract_comments(write_artifact(tmp_path / "empty.html", EMPTY), tmp_path / "e.json")
    assert not list(tmp_path.glob("e.*"))


def test_an_authors_file_name_is_its_principal_form(tmp_path: Path) -> None:
    named = {**ROOT, "author": "Zoë  Müller-Smith!"}
    extract_comments(write_artifact(tmp_path / "reviewed.html", model(named)), tmp_path / "returned.json")
    assert json.loads((tmp_path / "returned.zoe-muller-smith.json").read_text(encoding="utf-8"))["names"] == [
        "Zoë  Müller-Smith!"]


@pytest.mark.parametrize("author, other", [("", None), ("李", None), ("bob", "Bob")])
def test_an_author_without_a_file_name_of_its_own_is_refused_at_its_entry(tmp_path: Path, author, other) -> None:
    comments = [ROOT, {**REPLY, "author": author}] if other is None else [{**ROOT, "author": other},
                                                                          {**REPLY, "author": author}]
    artifact = write_artifact(tmp_path / "reviewed.html", model(*comments))
    _refused(artifact, ".comments[1].author", tmp_path / "returned.json")
    assert not list(tmp_path.glob("returned*"))


def test_a_copy_two_readers_worked_on_imports_as_two_principals_into_both_readers_entries(
        tmp_path: Path, document) -> None:
    """R3: a copy Alice and Bob worked on in turn, none of it imported yet, exports to a file per reader.
    The printed import, through the core's CLI, refuses nothing, and its union is what both readers
    did, though each reader's entries name the other's: Bob replies to and resolves Alice's comment,
    and Alice replies to his reply."""
    early = {"id": "c0", "author": "Bob", "created": "2026-11-09T09:00:00Z", "state": "open",
             "body": {"mediaType": "text/plain", "text": "Name the source."}, "target": PARAGRAPH}
    resolve = {"id": "s1", "author": "Bob", "created": "2026-11-09T11:05:00Z", "target": "c1", "state": "resolved"}
    reopen = {"id": "s2", "author": "Alice", "created": "2026-11-09T11:10:00Z", "target": "c1", "state": "open"}
    answer = {"id": "c4", "author": "Alice", "created": "2026-11-09T11:20:00Z", "state": "open",
              "body": {"mediaType": "text/plain", "text": "The figure's caption."}, "inReplyTo": "c2"}
    did, returned = _vaults(tmp_path, "did", "returned")
    for principal, name, comments, decisions, states in (("alice", "Alice", [ROOT, answer], [DECISION], [reopen]),
                                                         ("bob", "Bob", [early, REPLY], [], [resolve])):
        (did / f"manifest.comments.{principal}.json").write_text(json.dumps(
            {"version": 1, "principal": principal, "names": [name], "comments": comments, "decisions": decisions,
             "states": states}), encoding="utf-8")
    both = with_comments(copy.deepcopy(document), did / "manifest.md")["comments"]
    artifact = write_artifact(tmp_path / "reviewed.html", {**both, "names": ["Bob"]})
    printed = extract_comments(artifact, tmp_path / "returned.json")
    assert [principal for _, principal in _import_printed(printed, returned, tmp_path)] == ["bob", "alice"]
    assert with_comments(copy.deepcopy(document), returned / "manifest.md")["comments"] == both
    for principal in ("alice", "bob"):
        assert (json.loads((returned / f"manifest.comments.{principal}.json").read_text(encoding="utf-8"))
                == json.loads((did / f"manifest.comments.{principal}.json").read_text(encoding="utf-8")))


def test_core_overlays_to_artifact_to_overlays_keep_every_field(tmp_path: Path, document) -> None:
    """At the build's seam: the overlays two principals wrote, through the Document, the island and the
    export, are the overlays the core's imports write back."""
    written = {"alice": {"version": 1, "principal": "alice", "names": ["Alice"], "comments": [ROOT, BATCH],
                         "decisions": [DECISION]},
               "bob": {"version": 1, "principal": "bob", "names": ["Bob"], "comments": [REPLY], "decisions": []}}
    vault, returned = _vaults(tmp_path, "vault", "returned")
    for principal, overlay in written.items():
        (vault / f"manifest.comments.{principal}.json").write_text(json.dumps(overlay), encoding="utf-8")
    document = with_comments(document, vault / "manifest.md")
    artifact = tmp_path / "reviewed.html"
    artifact.write_text(render(document, load_config()), encoding="utf-8")
    _import_printed(extract_comments(artifact, tmp_path / "returned.json"), returned, tmp_path)
    for principal, overlay in written.items():
        assert json.loads((returned / f"manifest.comments.{principal}.json").read_text(encoding="utf-8")) == overlay


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
