from pathlib import Path

ROOT = Path(__file__).parents[2]


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_sharepoint_preview_points_to_the_canary_rule_instead_of_restating_it() -> None:
    note = _flat((ROOT / "spec" / "sharepoint-preview.md").read_text(encoding="utf-8"))

    for restated in ("raise Limited functionality warnings",
                     "the registry that lists the browser capabilities the artifact depends on"):
        assert restated not in note, (
            f"sharepoint-preview.md: replace '{restated}' with a link to artifact-ui.md#dock-menu (the notice center)")
    assert ("The artifact now does this itself: see [Artifact UI](artifact-ui.md#dock-menu), "
            "the notice center, for which features it includes and how their canaries report a host's limits.") in note
