"""A decision figure's option short names have one owner, the core (obs input-model, Pugh decision
figures, ``shortNames``): the adapter reads them from the figure's body and keeps no rule of its own.

Reader: whoever changes how obs-html names a decision figure's options.
"""
from pathlib import Path

SOURCE = Path(__file__).parents[2] / "src" / "obs_html"


def test_neither_the_figure_nor_the_record_resolves_a_short_name_itself() -> None:
    for name in ("pugh-figure.js", "bless_record.py"):
        text = (SOURCE / name).read_text(encoding="utf-8")

        assert "SHORT_WORDS" not in text and "candidate.short" not in text, name
        assert "shortNames" in text, name
