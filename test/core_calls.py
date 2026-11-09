"""The core's comment and block-id functions, for the adapter's tests, each run in a process of its own.

Reader: a test of this adapter that checks its output against what the core decides.

The adapter imports no module of the core (test/test_adapter_manifest.py); these calls cross the
same boundary the adapter does, a process, so a test holds the adapter to the core's own resolver,
schema check and build instead of a copy of them.
"""
import json
import subprocess
import sys
from pathlib import Path

_CALL = """
import json, sys
from pathlib import Path
from obs.comments import apply_comments, unresolved, validate_overlay
from obs.node_ids import assign_ids, chapter_targets
request = json.load(sys.stdin)
if request["call"] == "targets":
    result = {chapter: sorted(ids) for chapter, ids in chapter_targets(request["document"]).items()}
elif request["call"] == "unresolved":
    nodes = {chapter: set(ids) for chapter, ids in request["targets"].items()}
    result = [target for target in request["list"] if unresolved(target, nodes)]
elif request["call"] == "ids":
    result = request["document"]
    assign_ids(result)
elif request["call"] == "validate":
    for overlay in request["overlays"]:
        validate_overlay(overlay, Path(request["path"]))
    result = None
else:
    document = request["document"]
    apply_comments(document, Path(request["manifest"]))
    result = document
json.dump(result, sys.stdout)
"""


def _call(**request) -> object:
    done = subprocess.run([sys.executable, "-c", _CALL], input=json.dumps(request), capture_output=True,
                          text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def chapter_targets(document: dict) -> dict[str, set[str]]:
    """``obs.node_ids.chapter_targets``: each chapter's block ids and keyed rows."""
    return {chapter: set(ids) for chapter, ids in _call(call="targets", document=document).items()}


def unresolved_targets(targets: list[dict], nodes: dict[str, set[str]]) -> list[dict]:
    """The targets ``obs.comments.unresolved`` finds no node for."""
    return _call(call="unresolved", list=targets, targets={chapter: sorted(ids) for chapter, ids in nodes.items()})


def with_ids(document: dict) -> dict:
    """The Document with ``obs.node_ids.assign_ids`` applied, as the core's build gives every block its id."""
    return _call(call="ids", document=document)


def validate_overlays(overlays: list[dict], path: Path) -> None:
    """``obs.comments.validate_overlay`` on each overlay as the file ``path``; it fails the test where
    the core refuses one."""
    _call(call="validate", overlays=overlays, path=str(path))


def with_comments(document: dict, manifest: Path) -> dict:
    """The Document with ``obs.comments.apply_comments`` applied: the union of the manifest's overlay files."""
    return _call(call="apply", document=document, manifest=str(manifest))


def import_comments(manifest: Path, returned: Path, principal: str, document: Path) -> None:
    """``obs-document --source MANIFEST --import-comments RETURNED --principal PRINCIPAL``: the core writes
    the principal's overlay file, then builds the Document into ``document``."""
    done = subprocess.run([sys.executable, "-m", "obs.document", "--source", str(manifest), "--import-comments",
                           str(returned), "--principal", principal, "--document", str(document)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
