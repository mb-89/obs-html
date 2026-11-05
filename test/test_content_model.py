"""The adapter writes valid HTML: no block element where only phrasing content is allowed.

The check (test/content_model.py) reads obs's spec artifact (test/spec_artifact.py) and the
artifact of every fixture Document as written, the page and each chapter's HTML, and fails naming
each block element inside a phrasing-only parent, that parent, its chapter and the remedy.
"""
from pathlib import Path

import pytest

from conftest import ROOT
from content_model import check_artifact, check_markup
from documents import chapter, document as build, paragraph
from obs_html.cli import main as obs_html
from obs_html.config import load_config
from obs_html.render import render
from spec_artifact import spec_artifact

FIXTURES = sorted([ROOT / "test" / "fixtures" / "document.json",
                   *(ROOT / "test" / "fixtures" / "documents").glob("*.json")])


def _report(name: str, violations: list[str]) -> str:
    return f"{name}: {len(violations)} content-model violation(s):\n" + "\n".join(violations)


def test_the_spec_artifact_writes_no_block_element_inside_phrasing_content(tmp_path_factory) -> None:
    violations = check_artifact(spec_artifact(tmp_path_factory).read_text(encoding="utf-8"))
    assert not violations, _report("obs's spec artifact", violations)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_every_fixture_artifact_writes_no_block_element_inside_phrasing_content(fixture: Path, tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.html"
    assert obs_html([str(fixture), str(artifact), "--execute-commands", "--command-root", str(tmp_path)]) == 0
    violations = check_artifact(artifact.read_text(encoding="utf-8"))
    assert not violations, _report(f"test/fixtures/{fixture.relative_to(ROOT / 'test' / 'fixtures').as_posix()}",
                                   violations)


def test_the_check_names_the_element_its_parent_the_chapter_and_the_remedy() -> None:
    [violation] = check_markup('<p>Text <div class="math block">x</div> text</p>', "one")
    assert violation.startswith("chapter 'one': <div class=\"math block\"> inside <p>:")
    assert "Remedy:" in violation
    # Foreign content and a summary's heading are allowed; a block inside a span is not.
    assert check_markup("<p><math><mrow><mi>x</mi></mrow></math></p><summary><h2>T</h2></summary>", "one") == []
    [violation] = check_markup('<span class="a"><a href="#"><ul><li>x</li></ul></a></span>', "one")
    assert violation.startswith('chapter \'one\': <ul> inside <a>:')


def test_text_with_display_math_renders_no_block_element_inside_its_paragraph() -> None:
    formula = {"type": "math", "attrs": {"display": True}, "children": [], "text": "a^2"}
    artifact = render(build("Doc", chapter("one", "One", paragraph("Text ", formula, " text"))), load_config())
    assert check_artifact(artifact) == []
