"""Every committed fixture Document is what the current core builds from its vault.

The tests read committed Documents (test/fixtures/documents), so a core change could hide behind
them. Each run builds every vault of test/fixtures/build_documents.py with this repository's core,
once, and compares. A vault the core refuses fails naming the vault and the core's message; a
stale Document fails naming the first JSON path that differs and the command that rebuilds it.
"""
import json
import subprocess

import pytest

from conftest import CORE_ROOT, ROOT, built_once
from fixtures import build_documents

DOCUMENTS = ROOT / "test" / "fixtures" / "documents"
REBUILD = "uv run python test/fixtures/build_documents.py <obs checkout> {name}"


@pytest.fixture(scope="session")
def rebuilt(tmp_path_factory):
    """Every vault built by the current core, once per run: the folder, the core's refusals and the
    processes the build started."""
    def build(folder):
        processes = []

        def run(command, **options):
            processes.append(command[:command.index("python") + 1] if "python" in command else command)
            return subprocess.run(command, **options)

        refused = build_documents.build(CORE_ROOT, [], folder, offline=True, run=run)
        (folder / "refused.json").write_text(json.dumps(refused), encoding="utf-8")
        (folder / "processes.json").write_text(json.dumps(processes), encoding="utf-8")

    folder = built_once(tmp_path_factory, "fixture-documents", build)
    return (folder, json.loads((folder / "refused.json").read_text(encoding="utf-8")),
            json.loads((folder / "processes.json").read_text(encoding="utf-8")))


def first_difference(committed, built, path="$"):
    """The first JSON path where the two values differ, with both sides; None when equal."""
    if type(committed) is not type(built):
        return f"{path}: committed {committed!r:.80}, built {built!r:.80}"
    if isinstance(committed, dict):
        for key in sorted(committed.keys() | built.keys()):
            if key not in committed or key not in built:
                return f"{path}.{key}: {'only built' if key in built else 'only committed'}"
            found = first_difference(committed[key], built[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(committed, list):
        for index, (one, other) in enumerate(zip(committed, built)):
            found = first_difference(one, other, f"{path}[{index}]")
            if found:
                return found
        if len(committed) != len(built):
            return f"{path}: committed {len(committed)} items, built {len(built)}"
        return None
    return None if committed == built else f"{path}: committed {committed!r:.80}, built {built!r:.80}"


@pytest.mark.parametrize("name", list(build_documents.VAULTS))
def test_the_committed_document_is_what_the_current_core_builds(rebuilt, name: str) -> None:
    folder, refused, _processes = rebuilt
    assert name not in refused, (
        f"test/fixtures/build_documents.py: the core refuses the {name} vault: {refused.get(name)}\n"
        f"Remedy: change the vault in build_documents.py as the core's message says, then run "
        f"{REBUILD.format(name=name)}.")
    committed = json.loads((DOCUMENTS / f"{name}.json").read_text(encoding="utf-8"))
    built = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    difference = first_difference(committed, built)
    assert difference is None, (
        f"test/fixtures/documents/{name}.json is stale: the current core builds another Document from "
        f"its vault ({difference}). Remedy: run {REBUILD.format(name=name)} and fix what the new "
        "Document breaks.")


def test_every_vault_is_built_in_one_core_process(rebuilt) -> None:
    """Each core process costs its imports (about 0.3 s of CPU); the capability reference and every
    vault's Document are built in one."""
    _folder, _refused, processes = rebuilt
    assert processes == [["uv", "run", "--offline", "--project", str(CORE_ROOT), "python"]]


def test_a_stale_document_names_the_first_differing_path() -> None:
    assert first_difference({"a": [1, {"b": 2}]}, {"a": [1, {"b": 3}]}) == "$.a[1].b: committed 2, built 3"
    assert first_difference({"a": [1]}, {"a": [1, 2]}) == "$.a: committed 1 items, built 2"
    assert first_difference({"a": 1}, {"a": 1}) is None


def test_the_build_machines_fields_are_normalised_in_one_place() -> None:
    """A committed Document cannot hold the commit, paths or times of the machine that built it;
    build_documents.normalised sets each such field (MACHINE_FIELDS) to the value a fixture carries."""
    built = {"sourceArchive": {"files": [], "build": {"commit": "1" * 40, "lockfiles": {"uv.lock": {"obs": "9"}}}},
             "manifest": {"path": "manifest.md"}}

    assert build_documents.normalised(built) == {
        "sourceArchive": {"files": [], "build": build_documents.FIXTURE_BUILD}, "manifest": {"path": "manifest.md"}}
    assert build_documents.normalised({"manifest": {}}) == {"manifest": {}}
