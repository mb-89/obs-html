from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_input_model_points_to_obs_for_the_chapter_sequence() -> None:
    flat = " ".join((ROOT / "spec" / "input-model.md").read_text(encoding="utf-8").split())

    assert "Left and right controls walk the chapter sequence (obs's input model, Manifest contract)." in flat
    for restatement in ("Left and right controls move through all items in depth-first manifest order.",
                        "Previous and next navigation follows that sequence in depth-first order."):
        assert restatement not in flat
