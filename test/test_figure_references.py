"""Figure numbers and references: a block link to a figure shows its current label and number,
and adjacent references merge (obs input-model, Figure captions and references;
artifact-ui.md One figure frame). The Document is the core-built ``figure-references`` fixture
(fixtures/build_documents.py); its figure fences are the syntax the interim reference reads too,
so the parity test renders the same vault both ways.

Reader: whoever changes figure numbering or how a reference to a figure renders.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import CORE_ROOT, ROOT, built_once
from fixtures.build_documents import figure_references
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from spec_artifact import run, uv


FIXTURE = ROOT / "test" / "fixtures" / "documents" / "figure-references.json"


def _document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _notes(document: dict, config=None) -> dict[str, str]:
    data = decode_artifact_data(render(document, config or load_config()))
    return {note["slug"]: note["html"] for note in data["notes"]}


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


def test_numbers_and_references_match_the_interim_reference(tmp_path_factory) -> None:
    """The fixture's vault rendered by the interim reference (obs-html-interim of the obs checkout
    this adapter sits in) and its Document by this adapter: every figure number and every
    paragraph's text and link targets agree."""
    if not (CORE_ROOT / "src" / "obs_html_interim" / "cli.py").is_file():
        pytest.fail(f"test/test_figure_references.py: no interim reference at {CORE_ROOT / 'src' / 'obs_html_interim'}. "
                    "Remedy: remove this parity test once obs no longer carries the interim adapter.", pytrace=False)

    def build(folder: Path) -> None:
        (folder / "vault").mkdir()
        figure_references(folder / "vault")
        run([uv(), "run", "--offline", "--project", str(CORE_ROOT), "obs-html-interim", "--source",
             str(folder / "vault" / "manifest.md"), "--output", str(folder / "reference.html")],
            CORE_ROOT, "rendering the figure-references vault with the interim reference")

    folder = built_once(tmp_path_factory, "figure-references-interim", build)
    data = decode_artifact_data((folder / "reference.html").read_text(encoding="utf-8"))
    reference = {note["slug"]: note["html"] for note in data["notes"]}
    ours = _notes(_document())

    number = re.compile(r'data-figure-number="([^"]+)"')
    assert number.findall(ours["two"]) == [f"Figure 2.{index}" for index in range(1, 7)]
    for slug in ("one", "two"):
        assert number.findall(ours[slug]) == number.findall(reference[slug]), slug
        assert _text(ours[slug]) == _text(reference[slug]), slug
