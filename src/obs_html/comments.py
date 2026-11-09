"""The adapter's side of the core's comments: the island the build writes and the import of a
returned copy (input-model#Comments and the core model).

The core owns the format, the review semantics and the block ids (obs input-model, Comments and
reviews); the island holds the core's model unchanged, and the one mapping onto the Comments bar's
threads is the browser's (comment-model.js). Importing reads the island as untrusted data and,
for an overlay file, keeps what no other principal's file of the manifest already holds.
"""
from __future__ import annotations

import json
from functools import cache
from glob import escape
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from obs_html.errors import InputError, field_path, schema_error


ISLAND = "script#obs-comments"
"""The comment island as a message's field names it; its JSON paths follow."""
OWNER = "input-model#Comments and the core model"
CORE_OWNER = "obs input-model#Comments and reviews"
SCHEMA = json.loads(files("obs").joinpath("comments.schema.json").read_text(encoding="utf-8"))
"""The core's format, read as the core's package data: the adapter imports no core module."""
VERSION = SCHEMA["properties"]["version"]["const"]
KIND = ".comments."
"""What an overlay file's name holds between its manifest's stem and its principal (obs
input-model#Overlay files owns the naming)."""


def island_model(document: dict[str, Any]) -> dict[str, Any]:
    """What the build writes into the island: the Document's resolved comments, or an empty model."""
    return document.get("comments") or {"version": VERSION, "files": [], "comments": [], "decisions": []}


@cache
def _resolved() -> Draft202012Validator:
    """The core's schema of a resolved model (comments.schema.json, ``$defs/resolved``)."""
    return Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/resolved"})


@cache
def _overlay() -> Draft202012Validator:
    """The core's schema of one principal's overlay file, which the core checks again when it reads it."""
    return Draft202012Validator(SCHEMA)


class _IslandParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.islands: list[str] = []
        self._chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "obs-comments":
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._chunks is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._chunks is not None:
            self.islands.append("".join(self._chunks))
            self._chunks = None


def _error(source: Path, parts: list[object], problem: str, remedy: str) -> InputError:
    return InputError(source, field_path(parts, ISLAND), problem, f"{remedy}; see {OWNER}")


def read_island(artifact_path: Path) -> dict[str, Any]:
    """The core's comments a returned copy holds, once the core's schema accepts them."""
    parser = _IslandParser()
    try:
        parser.feed(artifact_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as error:
        raise InputError(artifact_path, "", f"cannot be read as UTF-8 HTML ({error})",
                         "Name the reviewed HTML file the artifact saved") from error
    parser.close()
    remedy = "Extract from the HTML the artifact saved after review, unedited; its Comments bar writes the island"
    if len(parser.islands) != 1:
        raise _error(artifact_path, [], f"occurs {len(parser.islands)} times, not once", remedy)
    try:
        raw = json.loads(parser.islands[0])
    except json.JSONDecodeError as error:
        raise _error(artifact_path, [], f"is not JSON ({error.msg} at line {error.lineno}, column {error.colno})",
                     remedy) from error
    if isinstance(raw, dict) and raw.get("version") == 2:
        raise _error(artifact_path, ["version"], "is 2, a copy saved before comments went through the core, whose "
                     "review items (item-N) are positions no Document resolves",
                     "Copy its comments into a copy built now, and save that")
    error = schema_error(list(_resolved().iter_errors(raw)), artifact_path, OWNER, ISLAND)
    if error:
        raise error
    return raw


def extract_comments(artifact_path: Path, overlay: Path | None = None) -> str:
    """The returned copy's threads as a deterministic text list; with ``overlay``, also write that
    principal's overlay file: every entry no other overlay file of the manifest holds as it is."""
    model = read_island(artifact_path)
    if overlay is not None:
        _write_overlay(model, artifact_path, overlay)
    return _format_candidates(model)


def _write_overlay(model: dict[str, Any], artifact_path: Path, overlay: Path) -> None:
    stem, _, principal = overlay.name.removesuffix(".json").rpartition(KIND)
    held: dict[str, tuple[Path, object]] = {}
    for path in sorted(overlay.parent.glob(f"{escape(stem)}{KIND}*.json")):
        if path.name == overlay.name:
            continue
        other = json.loads(path.read_text(encoding="utf-8"))
        for kind in ("comments", "decisions"):
            for entry in other.get(kind, []):
                held[entry["id"]] = (path, entry)
    written: dict[str, list[dict[str, Any]]] = {"comments": [], "decisions": []}
    for kind, entries in written.items():
        for index, entry in enumerate(model[kind]):
            known = held.get(entry["id"])
            if known is None:
                entries.append(entry)
            elif known[1] != entry:
                raise _error(artifact_path, [kind, index], f"changes {entry['id']!r}, which {known[0]} holds; a "
                             "principal changes only its own file", "Give the changed entry a new id, or keep "
                             "the other principal's entry as it is")
    result = {"version": VERSION, "principal": principal, **written}
    error = schema_error(list(_overlay().iter_errors(result)), overlay, f"{CORE_OWNER} (Overlay files)")
    if error:
        raise error
    overlay.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_candidates(model: dict[str, Any]) -> str:
    roles: dict[str, str] = {}

    def role(author: str) -> str:
        if not author:
            return "reviewer"
        if author not in roles:
            roles[author] = f"reviewer-{len(roles) + 1}"
        return roles[author]

    replies: dict[str, list[dict[str, Any]]] = {}
    for comment in model["comments"]:
        if "inReplyTo" in comment:
            replies.setdefault(comment["inReplyTo"], []).append(comment)
    roots = [comment for comment in model["comments"] if "inReplyTo" not in comment]
    lines = [f"comment candidates: {len(roots)}"]

    def append_comment(comment: dict[str, Any], depth: int) -> None:
        status = f" [{comment['state']}]" if depth else ""
        lines.append(f"{'  ' * depth}{role(comment['author'])}{status}: {comment['body']['text']}")
        for reply in replies.get(comment["id"], []):
            append_comment(reply, depth + 1)

    for root in roots:
        target = root["target"]
        place = "".join(f" {key} {target[key]}" for key in ("chapter", "node", "field") if key in target)
        lines.append(f"--- {root['id']} [{root['state']}]{place or ' document'}")
        if target.get("quote"):
            lines.append(f"quote: {target['quote']}")
        if batch := root.get("batch"):
            lines.append(f"[Full {batch['scope']}]")
            lines.extend(f"item: {item.get('chapter', '')} {item.get('node', '')}".rstrip() for item in batch["items"])
        append_comment(root, 0)
    return "\n".join(lines) + "\n"
