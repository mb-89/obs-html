import json
from pathlib import Path

import pytest

from obs_html.comments import extract_comments
from obs_html.errors import InputError
from obs_html.config import load_config
from obs_html.render import render


def write_artifact(path: Path, island: object) -> None:
    path.write_text(
        '<!doctype html><script id="obs-comments" type="application/json">'
        f"{json.dumps(island)}"
        "</script><script>throw new Error('must not execute')</script>",
        encoding="utf-8",
    )


def _refused(artifact: Path, field: str) -> None:
    """Extraction fails naming the reviewed HTML and the JSON path in its comment island."""
    with pytest.raises(InputError) as failure:
        extract_comments(artifact)
    assert (failure.value.source, failure.value.field) == (str(artifact), f"script#obs-comments{field}")


def test_extract_comments_preserves_scoped_batch_association(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    annotation = {
        "id": "c1", "target": {"chapter": "one"}, "text": "One reason", "author": "Alice",
        "batch": {"scope": "document", "items": [
            {"chapter": "one", "item": "item-1"},
            {"chapter": "two", "item": "row-table:key"},
        ]},
    }
    write_artifact(artifact, {"version": 2, "annotations": [annotation]})
    extracted = extract_comments(artifact)
    assert "[Full document]" in extracted
    assert "one item-1" in extracted
    assert "two row-table:key" in extracted
    assert extracted.count("One reason") == 1


@pytest.mark.parametrize("batch, field", [
    (None, "scope"), ({}, "scope"), ({"scope": [], "items": []}, "scope"),
    ({"scope": "other", "items": []}, "scope"),
    ({"scope": "section", "items": []}, "items"), ({"scope": "chapter", "items": [None]}, "items[0]"),
    ({"scope": "chapter", "items": [{"chapter": "", "item": "item-1"}]}, "items[0].chapter"),
    ({"scope": "chapter", "items": [{"chapter": "one", "item": "bad"}]}, "items[0].item"),
    ({"scope": "section", "items": [{"chapter": "one", "item": "item-1"}] * 2}, "items[1]"),
])
def test_extract_comments_rejects_malformed_batch(tmp_path: Path, batch, field) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(artifact, {"version": 2, "annotations": [{
        "id": "c1", "target": {"chapter": "one"}, "text": "", "batch": batch,
    }]})
    _refused(artifact, f".annotations[0].batch.{field}")


def test_extract_comments_lists_anonymized_candidates_deterministically(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(
        artifact,
        {
            "version": 2,
            "annotations": [
                {
                    "id": "c1",
                    "target": {"chapter": "one", "quote": "Selected text", "start": 3, "end": 16},
                    "status": "open",
                    "author": "Alice",
                    "text": "Clarify this.",
                    "replies": [
                        {"id": "c2", "author": "Bob", "text": "Agreed.", "status": "open", "replies": []}
                    ],
                }
            ],
        },
    )

    first = extract_comments(artifact)
    second = extract_comments(artifact)

    assert first == second
    assert first == (
        "comment candidates: 1\n"
        "--- c1 [open] chapter one\n"
        "quote: Selected text\n"
        "reviewer-1: Clarify this.\n"
        "  reviewer-2 [open]: Agreed.\n"
    )
    assert "Alice" not in first
    assert "throw new Error" not in first


def test_extract_comments_rejects_multiple_islands(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    island = '<script id="obs-comments" type="application/json">{"version":2,"annotations":[]}</script>'
    artifact.write_text(island + island, encoding="utf-8")

    _refused(artifact, "")


def test_extract_comments_rejects_invalid_replies(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(
        artifact,
        {
            "version": 2,
            "annotations": [
                {
                    "id": "c1",
                    "target": {"chapter": "one"},
                    "author": "Reviewer",
                    "text": "Review this.",
                    "replies": {},
                }
            ],
        },
    )

    _refused(artifact, ".annotations[0].replies")


def test_generated_artifact_comment_island_round_trips_to_extractor(tmp_path: Path, document) -> None:
    generated = render(document, load_config())
    reviewed_island = {
        "version": 2,
        "annotations": [
            {
                "id": "c1",
                "target": {"chapter": "one"},
                "status": "resolved",
                "author": "Reviewer",
                "text": "Looks good.",
                "replies": [],
            }
        ],
    }
    reviewed = tmp_path / "reviewed.html"
    reviewed.write_text(
        generated.replace(
            '{"version":2,"annotations":[],"reviewers":[],"reviews":[]}',
            json.dumps(reviewed_island, separators=(",", ":")),
            1,
        ),
        encoding="utf-8",
    )

    assert extract_comments(reviewed) == (
        "comment candidates: 1\n"
        "--- c1 [resolved] chapter one\n"
        "reviewer-1: Looks good.\n"
    )


def test_extract_comments_supports_recursive_comment_replies(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(
        artifact,
        {
            "version": 2,
            "annotations": [
                {
                    "id": "c1",
                    "target": {"chapter": "one", "quote": "Review me"},
                    "author": "Alice",
                    "text": "Clarify this.",
                    "status": "open",
                    "replies": [
                        {
                            "id": "c2",
                            "author": "Bob",
                            "text": "I will.",
                            "status": "resolved",
                            "replies": [],
                        }
                    ],
                }
            ],
        },
    )

    assert extract_comments(artifact) == (
        "comment candidates: 1\n"
        "--- c1 [open] chapter one\n"
        "quote: Review me\n"
        "reviewer-1: Clarify this.\n"
        "  reviewer-2 [resolved]: I will.\n"
    )


def test_extract_comments_accepts_an_empty_editable_draft(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(
        artifact,
        {
            "version": 2,
            "annotations": [
                {
                    "id": "draft",
                    "target": {"chapter": "one", "quote": "Review me"},
                    "author": "Reviewer",
                    "text": "",
                    "status": "open",
                    "replies": [],
                }
            ],
        },
    )

    assert "reviewer-1: \n" in extract_comments(artifact)


def test_extract_comments_validates_review_decisions(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(
        artifact,
        {
            "version": 2,
            "annotations": [],
            "reviewers": ["Alice", "Bob"],
            "reviews": [
                {
                    "chapter": "one",
                    "item": "item-1",
                    "reviewer": "Alice",
                    "state": "accepted",
                }
            ],
        },
    )

    assert extract_comments(artifact) == "comment candidates: 0\n"


def test_extract_comments_accepts_row_reviews_and_detail_selection_targets(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(artifact, {
        "version": 2,
        "reviews": [{
            "chapter": "glossary", "item": "row-glossary%3Abase1:glossary%3Aterm",
            "reviewer": "Alice", "state": "accepted",
        }],
        "annotations": [{
            "id": "c1", "author": "Alice", "text": "Detail comment", "status": "open",
            "replies": [],
            "target": {
                "chapter": "glossary", "table": "glossary:base1", "row": "glossary:term",
                "detail": True, "start": 0, "end": 5, "quote": "Words",
                "column": "roles.requirement",
            },
        }],
    })
    assert "Detail comment" in extract_comments(artifact)


@pytest.mark.parametrize("scope, field", [
    ({"table": "t", "detail": True}, "row"),
    ({"table": "t", "row": "r", "detail": "yes"}, "detail"),
    ({"row": "r", "detail": True}, "table"),
    ({"column": "subject"}, "table"),
    ({"table": "t", "row": "r", "detail": False, "column": "subject"}, "column"),
    ({"table": "t", "row": "r", "detail": True, "column": ""}, "column"),
    ({"table": "t", "row": "r", "detail": True, "column": 1}, "column"),
])
def test_extract_comments_rejects_invalid_table_selection_scopes(tmp_path: Path, scope, field) -> None:
    artifact = tmp_path / "reviewed.html"
    write_artifact(artifact, {
        "version": 2,
        "annotations": [{
            "id": "c1", "text": "", "replies": [],
            "target": {"chapter": "one", **scope},
        }],
    })
    _refused(artifact, f".annotations[0].target.{field}")


def test_extract_comments_rejects_duplicate_review_decisions(tmp_path: Path) -> None:
    artifact = tmp_path / "reviewed.html"
    decision = {
        "chapter": "one",
        "item": "item-1",
        "reviewer": "Alice",
        "state": "accepted",
    }
    write_artifact(
        artifact,
        {
            "version": 2,
            "annotations": [],
            "reviewers": ["Alice"],
            "reviews": [decision, decision],
        },
    )

    _refused(artifact, ".reviews[1]")