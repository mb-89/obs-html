"""The adapter's part of obs's mixed notes: how this adapter presents the cover, History and
reviewed copies (spec/input-model.md)."""
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _section(heading: str) -> str:
    model = (ROOT / "spec" / "input-model.md").read_text(encoding="utf-8")
    return " ".join(model.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0].split())


def test_the_cover_and_history_presentation_is_here() -> None:
    section = _section("Cover metadata and history")

    for presentation in ("These values populate the cover", "displayed on the cover and page frame",
                         "In document view it occupies its own section"):
        assert presentation in section


def test_the_reviewed_copy_runtime_is_here_with_its_owner_links() -> None:
    section = _section("Reviewed copy")

    for adapter in ("`obs-comments`", "File System Access", "Comments and the core model",
                    "[[artifact-ui#What counts as a change]] owns whether reader state marks"):
        assert adapter in section
