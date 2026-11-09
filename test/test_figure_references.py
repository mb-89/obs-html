"""Figure numbers and references: a block link to a figure shows its current label and number,
and adjacent references merge (obs input-model, Figure captions and references;
artifact-ui.md One figure frame). The Document is the core-built ``figure-references`` fixture
(fixtures/build_documents.py). EXPECTED_TEXT holds every number and paragraph the fixture shows,
as the interim adapter showed them on the same vault until obs#3 deleted it.

Reader: whoever changes figure numbering or how a reference to a figure renders.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import ROOT
from documents import without_node_ids
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render


FIXTURE = ROOT / "test" / "fixtures" / "documents" / "figure-references.json"


def _document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _notes(document: dict, config=None) -> dict[str, str]:
    data = decode_artifact_data(render(document, config or load_config()))
    return {note["slug"]: without_node_ids(note["html"]) for note in data["notes"]}


def _paragraph(html: str, start: str) -> str:
    return next(paragraph for paragraph in re.findall(r"<p>(.*?)</p>", html, re.S) if paragraph.startswith(start))


def _link(name: str, text: str) -> str:
    return f'<a class="internal-link" href="#two/block-{name}">{text}</a>'


def _figures(document: dict, **profile: str) -> dict:
    document["manifest"]["metadata"]["obsHtml"]["figures"] = profile
    return document


def test_references_show_the_number_and_adjacent_ones_merge() -> None:
    notes = _notes(_document())

    two = notes["two"]
    assert _paragraph(two, "Single") == f"Single {_link('d', 'Figure 2.4')}."
    assert _paragraph(two, "Pair") == f"Pair Figures {_link('d', '2.4')} and {_link('e', '2.5')}."
    assert _paragraph(two, "Run") == f"Run Figures {_link('d', '2.4')}–{_link('f', '2.6')}."
    assert _paragraph(two, "Mixed") == (
        f"Mixed Figures {_link('a', '2.1')}–{_link('c', '2.3')}, and {_link('e', '2.5')} or "
        f"{_link('b', 'the second')} {_link('c', 'Figure 2.3')}.")
    assert _paragraph(two, "Siehe") == f"Siehe Figures {_link('a', '2.1')} und {_link('b', '2.2')}."
    assert _paragraph(two, "Broken") == f"Broken {_link('d', 'Figure 2.4')}<br>\n{_link('e', 'Figure 2.5')}."
    assert _paragraph(notes["one"], "Across") == f"Across {_link('b', 'Figure 2.2')}."
    assert '<span class="figure-number">Figure 2.4:</span> Figure d.' in two
    assert 'id="two--block-d"' in two


def test_label_plural_and_document_numbering_come_from_the_manifest() -> None:
    two = _notes(_figures(_document(), numbering="document", label="Abb.", labelPlural="Abb."))["two"]

    assert _paragraph(two, "Siehe") == f"Siehe Abb. {_link('a', '1')} und {_link('b', '2')}."
    assert '<span class="figure-number">Abb. 1:</span>' in two


def test_conjunctions_come_from_the_configuration() -> None:
    config = load_config()
    config.artifact["figureReferences"] = {"conjunctions": ["plus"]}

    two = _notes(_document(), config)["two"]
    assert _paragraph(two, "See") == (
        f"See Figures {_link('a', '2.1')} plus {_link('b', '2.2')} and {_link('c', 'Figure 2.3')}.")


def _settings(tmp_path: Path, conjunctions: list[str]) -> Path:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"artifact": {"figureReferences": {"conjunctions": conjunctions}}}),
                        encoding="utf-8")
    return settings


@pytest.mark.parametrize("between", [" as well as ", " as well\nas "])
def test_a_conjunction_may_be_a_phrase(tmp_path, between) -> None:
    """A phrase joins references as the interim's did: its words apart by single spaces, a soft
    line break reading as one."""
    document = _document()
    see = next(node for node in document["chapters"][1]["content"] if "See " in json.dumps(node))
    next(child for child in see["children"] if child.get("text") == " plus ")["text"] = between

    two = _notes(document, load_config(_settings(tmp_path, ["as well as"])))["two"]
    assert _paragraph(two, "See") == (
        f"See Figures {_link('a', '2.1')}{between}{_link('b', '2.2')} and {_link('c', 'Figure 2.3')}.")


def test_more_than_64_conjunctions_are_refused(tmp_path) -> None:
    settings = _settings(tmp_path, [f"word{index}" for index in range(65)])

    with pytest.raises(InputError) as failure:
        load_config(settings)

    assert failure.value.source == str(settings)
    assert failure.value.field == "artifact.figureReferences.conjunctions"
    assert "cfg.schema.json" in failure.value.remedy


def test_a_labelled_reference_needs_no_number() -> None:
    document = _figures(_document(), numbering="none")
    document["chapters"][1]["content"] = [node for node in document["chapters"][1]["content"]
                                          if node["type"] != "paragraph" or "Labelled" in json.dumps(node)]
    document["chapters"][0]["content"] = []

    two = _notes(document)["two"]
    assert _paragraph(two, "Labelled") == f"Labelled {_link('a', 'the first')}."
    assert "figure-number" not in two


@pytest.mark.parametrize("numbered", [False, True])
def test_an_unlabelled_reference_to_an_unnumbered_figure_is_an_input_error(numbered) -> None:
    """Without numbering every figure is unnumbered; with it, an uncaptioned one is."""
    document = _document() if numbered else _figures(_document(), numbering="none")
    figure = next(node for node in document["chapters"][1]["content"] if node["type"] == "figures")
    if numbered:
        del figure["attrs"]["caption"]
    document["chapters"][0]["content"] = []

    with pytest.raises(InputError) as failure:
        _notes(document)

    assert failure.value.source == "Document of manifest.md"
    assert failure.value.field.startswith("chapters[1].content["), failure.value.field
    assert "input-model#Figure captions and references" in failure.value.remedy


def _text(html: str) -> list[str]:
    """Each paragraph's text and its links' targets, as a reader sees them."""
    return [re.sub(r"<[^>]+>", "", paragraph) + " " + " ".join(re.findall(r'href="([^"]+)"', paragraph))
            for paragraph in re.findall(r"<p>(.*?)</p>", html, re.S)]


# Per note: its figure numbers in order, and each paragraph's text and link targets (_text).
EXPECTED_TEXT = {
    "one": {"numbers": [], "text": ["Across Figure 2.2. #two/block-b"]},
    "two": {
        "numbers": [f"Figure 2.{index}" for index in range(1, 7)],
        "text": [
            "Single Figure 2.4. #two/block-d",
            "Pair Figures 2.4 and 2.5. #two/block-d #two/block-e",
            "Run Figures 2.4–2.6. #two/block-d #two/block-f",
            "Mixed Figures 2.1–2.3, and 2.5 or the second Figure 2.3. "
            "#two/block-a #two/block-c #two/block-e #two/block-b #two/block-c",
            "Siehe Figures 2.1 und 2.2. #two/block-a #two/block-b",
            "See Figure 2.1 plus Figures 2.2 and 2.3. #two/block-a #two/block-b #two/block-c",
            "Labelled the first. #two/block-a",
            "Broken Figure 2.4\nFigure 2.5. #two/block-d #two/block-e",
        ],
    },
}


def test_every_number_and_reference_reads_as_expected() -> None:
    """The fixture's Document rendered by this adapter: every figure number and every paragraph's
    text and link targets are EXPECTED_TEXT's."""
    ours = _notes(_document())
    number = re.compile(r'data-figure-number="([^"]+)"')
    for slug, expected in EXPECTED_TEXT.items():
        assert number.findall(ours[slug]) == expected["numbers"], slug
        assert _text(ours[slug]) == expected["text"], slug
