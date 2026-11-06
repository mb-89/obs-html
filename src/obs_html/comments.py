from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from obs_html.errors import InputError, field_path


ISLAND = "script#obs-comments"
"""The comment island as a message's field names it; its JSON paths follow."""
REMEDY = ("Extract from the HTML the artifact saved after review, unedited; its comment panel writes "
          "the island")


class _Island:
    """Where a comment-island error is: the reviewed HTML file and a JSON path in its island."""

    def __init__(self, source: Path) -> None:
        self.source = source

    def error(self, parts: list[object], problem: str, remedy: str = REMEDY) -> InputError:
        return InputError(self.source, field_path(parts, ISLAND), problem, remedy)

    def text(self, value: Any, parts: list[object]) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self.error(parts, "must be non-empty text")
        return value.strip()


class _CommentIslandParser(HTMLParser):
    def __init__(self, island: _Island) -> None:
        super().__init__(convert_charrefs=False)
        self.island = island
        self.islands: list[str] = []
        self._chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == "obs-comments":
            if self._chunks is not None:
                raise self.island.error([], "is nested inside another comment island")
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._chunks is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._chunks is not None:
            self.islands.append("".join(self._chunks))
            self._chunks = None


def extract_comments(artifact_path: Path) -> str:
    island = _Island(artifact_path)
    parser = _CommentIslandParser(island)
    try:
        parser.feed(artifact_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as error:
        raise InputError(artifact_path, "", f"cannot be read as UTF-8 HTML ({error})",
                         "Name the reviewed HTML file the artifact saved") from error
    parser.close()
    if len(parser.islands) != 1:
        raise island.error([], f"occurs {len(parser.islands)} times, not once", REMEDY)
    try:
        raw = json.loads(parser.islands[0])
    except json.JSONDecodeError as error:
        raise island.error([], f"is not JSON ({error.msg} at line {error.lineno}, column {error.colno})") \
            from error
    annotations = _validate_island(raw, island)
    return _format_candidates(annotations)


def _validate_island(raw: Any, island: _Island) -> list[dict[str, Any]]:
    if not isinstance(raw, dict) or raw.get("version") != 2:
        raise island.error(["version"], "is not 2, the version of a comment island obs-html reads")
    annotations = raw.get("annotations")
    if not isinstance(annotations, list):
        raise island.error(["annotations"], "must be a list")
    _validate_review_data(raw, island)
    normalized = []
    seen_ids: set[str] = set()
    for index, annotation in enumerate(annotations):
        where: list[object] = ["annotations", index]
        if not isinstance(annotation, dict):
            raise island.error(where, "must be a mapping")
        comment_id = island.text(annotation.get("id"), [*where, "id"])
        if comment_id in seen_ids:
            raise island.error([*where, "id"], f"is {comment_id!r}, the id of an earlier comment")
        seen_ids.add(comment_id)
        target = _validate_target(annotation.get("target"), [*where, "target"], island)
        node = _validate_node(annotation, where, seen_ids, island, known_id=comment_id)
        batch = {"batch": _validate_batch(annotation["batch"], [*where, "batch"], island)} \
            if "batch" in annotation else {}
        normalized.append({**node, "target": target, **batch})
    return normalized


def _validate_review_data(raw: dict[str, Any], island: _Island) -> None:
    reviewers = raw.get("reviewers", [])
    if not isinstance(reviewers, list):
        raise island.error(["reviewers"], "must be a list")
    normalized_reviewers = [island.text(reviewer, ["reviewers", index]) for index, reviewer in enumerate(reviewers)]
    if len(normalized_reviewers) != len(set(normalized_reviewers)):
        raise island.error(["reviewers"], "names a reviewer twice")

    reviews = raw.get("reviews", [])
    if not isinstance(reviews, list):
        raise island.error(["reviews"], "must be a list")
    seen: set[tuple[str, str, str]] = set()
    for index, review in enumerate(reviews):
        where: list[object] = ["reviews", index]
        if not isinstance(review, dict):
            raise island.error(where, "must be a mapping")
        chapter = island.text(review.get("chapter"), [*where, "chapter"])
        item = island.text(review.get("item"), [*where, "item"])
        if not _is_review_item(item):
            raise island.error([*where, "item"], f"is {item!r}, not a review item identifier (item-N or row-TABLE:KEY)")
        reviewer = island.text(review.get("reviewer"), [*where, "reviewer"])
        state = review.get("state")
        if state not in {"accepted", "rejected"}:
            raise island.error([*where, "state"], f"is {state!r}, not accepted or rejected")
        key = (chapter, item, reviewer)
        if key in seen:
            raise island.error(where, f"repeats the decision of {reviewer} on {chapter} {item}")
        seen.add(key)


def _is_review_item(item: str) -> bool:
    return (
        item.startswith("item-") and item.removeprefix("item-").isdigit()
        or item.startswith("row-") and len(item.split(":", 1)) == 2
        and all(item.removeprefix("row-").split(":", 1))
    )


def _validate_batch(raw: Any, where: list[object], island: _Island) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("scope") not in ("section", "chapter", "document"):
        raise island.error([*where, "scope"], "is not section, chapter or document")
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        raise island.error([*where, "items"], "must be a non-empty list")
    normalized = []
    seen = set()
    for index, identity in enumerate(items):
        place = [*where, "items", index]
        if not isinstance(identity, dict):
            raise island.error(place, "must be a mapping")
        chapter = island.text(identity.get("chapter"), [*place, "chapter"])
        item = island.text(identity.get("item"), [*place, "item"])
        if not _is_review_item(item):
            raise island.error([*place, "item"], f"is {item!r}, not a review item identifier (item-N or row-TABLE:KEY)")
        if (chapter, item) in seen:
            raise island.error(place, f"repeats {chapter} {item}")
        seen.add((chapter, item))
        normalized.append({"chapter": chapter, "item": item})
    return {"scope": raw["scope"], "items": normalized}


def _validate_node(
    raw: dict[str, Any],
    where: list[object],
    seen_ids: set[str],
    island: _Island,
    *,
    known_id: str | None = None,
) -> dict[str, Any]:
    comment_id = known_id or island.text(raw.get("id"), [*where, "id"])
    if known_id is None:
        if comment_id in seen_ids:
            raise island.error([*where, "id"], f"is {comment_id!r}, the id of an earlier comment")
        seen_ids.add(comment_id)
    status = raw.get("status", "open")
    if status not in {"open", "resolved"}:
        raise island.error([*where, "status"], f"is {status!r}, not open or resolved")
    author = raw.get("author", "")
    if not isinstance(author, str):
        raise island.error([*where, "author"], "must be text")
    text = raw.get("text")
    if not isinstance(text, str):
        raise island.error([*where, "text"], "must be text")
    raw_replies = raw.get("replies", [])
    if not isinstance(raw_replies, list):
        raise island.error([*where, "replies"], "must be a list")
    replies = []
    for index, reply in enumerate(raw_replies):
        if not isinstance(reply, dict):
            raise island.error([*where, "replies", index], "must be a mapping")
        replies.append(_validate_node(reply, [*where, "replies", index], seen_ids, island))
    return {
        "id": comment_id,
        "status": status,
        "author": author.strip(),
        "text": text,
        "replies": replies,
    }


def _validate_target(raw: Any, where: list[object], island: _Island) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise island.error(where, "must be a mapping")
    target: dict[str, Any] = {"chapter": island.text(raw.get("chapter"), [*where, "chapter"])}
    for key in ("quote", "prefix", "suffix"):
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise island.error([*where, key], "must be text")
        if value:
            target[key] = value
    for key in ("start", "end"):
        value = raw.get(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise island.error([*where, key], f"is {value!r}, not a non-negative whole number")
            target[key] = value
    if "table" in raw or "row" in raw or "detail" in raw or "column" in raw:
        target["table"] = island.text(raw.get("table"), [*where, "table"])
        target["row"] = island.text(raw.get("row"), [*where, "row"])
        if not isinstance(raw.get("detail"), bool):
            raise island.error([*where, "detail"], "must be true or false")
        target["detail"] = raw["detail"]
        if "column" in raw:
            if not raw["detail"]:
                raise island.error([*where, "column"], "needs detail: true")
            target["column"] = island.text(raw["column"], [*where, "column"])
    if "start" in target or "end" in target:
        if "start" not in target or "end" not in target or target["end"] < target["start"]:
            raise island.error([*where, "end"], "needs a start and an end no smaller than it")
    return target


def _format_candidates(annotations: list[dict[str, Any]]) -> str:
    roles: dict[str, str] = {}

    def role(author: str) -> str:
        if not author:
            return "reviewer"
        if author not in roles:
            roles[author] = f"reviewer-{len(roles) + 1}"
        return roles[author]

    lines = [f"comment candidates: {len(annotations)}"]

    def append_comment(comment: dict[str, Any], depth: int) -> None:
        marker = "  " * depth
        status = f" [{comment['status']}]" if depth else ""
        lines.append(f"{marker}{role(comment['author'])}{status}: {comment['text']}")
        for reply in comment["replies"]:
            append_comment(reply, depth + 1)

    for annotation in annotations:
        target = annotation["target"]
        lines.append(
            f"--- {annotation['id']} [{annotation['status']}] chapter {target['chapter']}"
        )
        if target.get("quote"):
            lines.append(f"quote: {target['quote']}")
        if batch := annotation.get("batch"):
            lines.append(f"[Full {batch['scope']}]")
            lines.extend(f"item: {item['chapter']} {item['item']}" for item in batch["items"])
        append_comment(annotation, 0)
    return "\n".join(lines) + "\n"