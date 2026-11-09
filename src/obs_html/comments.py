"""The adapter's side of the core's comments: the island the build writes and the import of a
returned copy (input-model#Comments and the core model).

The core owns the format, the review semantics and the block ids (obs input-model, Comments and
reviews); the island holds the core's model unchanged, and the one mapping onto the Comments bar's
threads is the browser's (comment-model.js). Extraction reads the island as untrusted data and
exports it in the core's format, a file per author; the core writes each into a principal's overlay file.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import cache
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from obs_html.errors import InputError, field_path, schema_error


ISLAND = "script#obs-comments"
"""The comment island as a message's field names it; its JSON paths follow."""
OWNER = "input-model#Comments and the core model"
SCHEMA = json.loads(files("obs").joinpath("comments.schema.json").read_text(encoding="utf-8"))
"""The core's format, read as the core's package data: the adapter imports no core module."""
VERSION = SCHEMA["properties"]["version"]["const"]
PRINCIPAL = re.compile(SCHEMA["$defs"]["principal"]["pattern"])
"""The core's principal pattern, which an author's file-name form must match."""
KINDS = {"comments": "author", "decisions": "reviewer", "states": "author"}
"""Each kind of entry and the field that names its author; a reply's inReplyTo and a state entry's
target name a comment."""


def island_model(document: dict[str, Any]) -> dict[str, Any]:
    """What the build writes into the island: the Document's resolved comments, or an empty model."""
    return document.get("comments") or {"version": VERSION, "files": [], "comments": [], "decisions": []}


@cache
def _resolved() -> Draft202012Validator:
    """The core's schema of a resolved model (comments.schema.json, ``$defs/resolved``)."""
    return Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/resolved"})




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
        raise _error(artifact_path, ["version"], "is 2: a comments island from an older obs-html, whose review "
                     "items (item-N) are positions no Document resolves", "Print its comments with obs-html "
                     "1.14.0 or earlier (--extract-comments), add them again in a copy built now, and save that")
    error = schema_error(list(_resolved().iter_errors(raw)), artifact_path, OWNER, ISLAND)
    if error:
        raise error
    return raw


def extract_comments(artifact_path: Path, output: Path | None = None) -> str:
    """The returned copy's threads as a deterministic text list; with ``output``, also write its
    entries in the core's format, one file per author beside ``output``, and list the
    ``obs-document --import-comments`` call of each in an order the core accepts."""
    model = read_island(artifact_path)
    text = _format_candidates(model)
    if output is None:
        return text
    lines = []
    for author, form in _authors(artifact_path, model):
        path = output.with_name(f"{output.stem}.{form}.json")
        split: dict[str, Any] = {"version": model["version"], "files": model["files"], "names": [author]}
        for kind, name in KINDS.items():
            entries = [entry for entry in model.get(kind, []) if entry[name] == author]
            if entries or kind != "states":
                split[kind] = entries
        path.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines.append(f"import: obs-document --source MANIFEST --import-comments {path} --principal {form}\n")
    return text + "".join(lines)


def file_name_form(author: str) -> str:
    """An author's file-name form, the principal its import names (spec/input-model.md, Comments and
    the core model): without accents, lower-cased, other characters runs of ``-``."""
    plain = "".join(char for char in unicodedata.normalize("NFKD", author) if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _authors(source: Path, model: dict[str, Any]) -> list[tuple[str, str]]:
    """Each author of the copy's entries with its file-name form, each after the authors whose
    comments its replies and state entries name, otherwise in the order they first appear."""
    by_comment = {comment["id"]: comment["author"] for comment in model["comments"]}
    forms: dict[str, str] = {}
    needs: dict[str, set[str]] = {}
    for kind, name in KINDS.items():
        for index, entry in enumerate(model.get(kind, [])):
            author = entry[name]
            if author not in forms:
                form = file_name_form(author)
                taken = next((other for other, known in forms.items() if known == form), None)
                if not PRINCIPAL.fullmatch(form) or taken is not None:
                    problem = (f"is {author!r}, which shares the file name form {form!r} with {taken!r}"
                               if taken is not None else f"is {author!r}, which has no file name form "
                               f"matching {PRINCIPAL.pattern}")
                    raise _error(source, [kind, index, name], problem, "Save the copy with each reader named "
                                 "by letters or digits, a name no other reader's differs from only in case "
                                 "or punctuation")
                forms[author] = form
            named = {"comments": entry.get("inReplyTo"), "states": entry.get("target")}.get(kind)
            needs.setdefault(author, set()).update({by_comment.get(named)} - {author, None})
    ordered: list[str] = []
    while len(ordered) < len(forms):
        waiting = [author for author in forms if author not in ordered]
        ordered.append(next((author for author in waiting if needs[author] <= set(ordered)), waiting[0]))
    return [(author, forms[author]) for author in ordered]


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
    changes: dict[str, list[dict[str, Any]]] = {}
    for entry in model.get("states", []):
        changes.setdefault(entry["target"], []).append(entry)
    roots = [comment for comment in model["comments"] if "inReplyTo" not in comment]
    lines = [f"comment candidates: {len(roots)}"]

    def append_comment(comment: dict[str, Any], depth: int) -> None:
        status = f" [{comment['state']}]" if depth else ""
        lines.append(f"{'  ' * depth}{role(comment['author'])}{status}: {comment['body']['text']}")
        # A comment's state entries, in the model's order; the latest gives its state (obs.comments.comment_state).
        lines.extend(f"{'  ' * depth}{role(entry['author'])} set it {entry['state']}"
                     for entry in changes.get(comment["id"], []))
        for reply in replies.get(comment["id"], []):
            append_comment(reply, depth + 1)

    for root in roots:
        target = root["target"]
        place = " abstract" * ("abstract" in target) + "".join(
            f" {key} {target[key]}" for key in ("chapter", "node", "field") if key in target)
        lines.append(f"--- {root['id']} [{root['state']}]{place or ' document'}")
        if target.get("quote"):
            lines.append(f"quote: {target['quote']}")
        if batch := root.get("batch"):
            lines.append(f"[Full {batch['scope']}]")
            lines.extend(f"item: {item.get('chapter', '')} {item.get('node', '')}".rstrip() for item in batch["items"])
        append_comment(root, 0)
    return "\n".join(lines) + "\n"
