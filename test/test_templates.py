"""Templates render as obs capabilities/templates asks: guidance apart from each slot, and a filled
document naming its template.

Reader: whoever changes how obs-html renders a ``templates`` node (render.py, _template_part;
templates.css).

The cases read the committed ``template`` and ``filled`` fixture Documents, which the core built
from the worked example of its note spec/capabilities/templates.md (test/fixtures/build_documents.py);
the core's own cases are obs's test/test_templates.py.
"""
import json
import re

import pytest

from artifacts import artifact_html
from conftest import CORE_ROOT, ROOT
from documents import chapter, document, paragraph
from fixtures import build_documents
from obs_html.artifact_data import decode_artifact_data
from obs_html.errors import InputError
from obs_html.features import feature_source


DOCUMENTS = ROOT / "test" / "fixtures" / "documents"
TEMPLATE = json.loads((DOCUMENTS / "template.json").read_text(encoding="utf-8"))
FILLED = json.loads((DOCUMENTS / "filled.json").read_text(encoding="utf-8"))
FENCE = re.compile(r"^```text (?P<file>\S+)\n(?P<body>.*?)^```$", re.M | re.S)


def _notes(source: dict) -> dict[str, dict]:
    return {note["slug"]: note for note in decode_artifact_data(artifact_html(source))["notes"]}


def test_the_fixture_vaults_are_the_worked_example_of_the_core_note() -> None:
    note = (CORE_ROOT / build_documents.TEMPLATE_NOTE).read_text(encoding="utf-8")
    example = {match["file"]: match["body"] for match in FENCE.finditer(note)}

    assert {f"template/{name}": text for name, text in build_documents.TEMPLATE.items()} | {
        f"document/{name}": text for name, text in build_documents.FILLED.items()} == example


def test_each_template_node_shows_its_guidance_apart_from_its_empty_slot() -> None:
    notes = _notes(TEMPLATE)

    for slug, gate in (("purpose", "mandatory"), ("scope", "mandatory"), ("risks", "judgment")):
        html = notes[slug]["html"]
        [guidance] = re.findall(r'<aside class="template-guidance".*?</aside>', html, re.S)
        assert f'data-template-gate="{gate}"' in guidance and f'<span class="template-gate">{gate}</span>' in guidance
        assert html.index("template-guidance") < html.index('<div class="template-slot" data-template-part="slot"')
        assert re.search(r'<div class="template-slot"[^>]*></div>', html)  # Empty: the author fills it in.
        assert "<p>" not in guidance and "{{slot}}" not in html
    purpose = notes["purpose"]["html"]
    assert re.findall(r"<dt>(\w+)</dt>", purpose) == ["Contents", "Motivation", "Form", "Sources"]
    assert '<dd data-guidance-field="form">One paragraph of at most five sentences.</dd>' in purpose
    assert re.findall(r"<dt>(\w+)</dt>", notes["scope"]["html"]) == ["Contents", "Form"]


def test_the_template_manifest_names_its_template_with_the_documents_metadata() -> None:
    home = _notes(TEMPLATE)["home"]["html"]

    [facts] = re.findall(r'<dl class="template-facts" data-template-part="template">.*?</dl>', home)
    assert re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", facts) == [
        ("Template", "requirements"), ("Version", "2"), ("Source", "an exported requirements template")]
    assert home.index('class="document-heading"') < home.index("template-facts")


def test_the_filled_document_names_its_template_and_holds_no_guidance() -> None:
    notes = _notes(FILLED)

    [facts] = re.findall(r'<dl class="template-facts" data-template-part="derived-from">.*?</dl>',
                         notes["home"]["html"])
    assert re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", facts) == [
        ("Derived from template", "requirements"), ("Version", "2")]
    for slug in ("purpose", "scope", "risks"):
        assert "template-guidance" not in notes[slug]["html"] and "template-slot" not in notes[slug]["html"]
    assert "The pump controller keeps the tank level" in notes["purpose"]["html"]


def test_the_rules_ship_only_with_a_template_part() -> None:
    rule = ".template-guidance {"

    assert rule in artifact_html(TEMPLATE) and rule in artifact_html(FILLED)
    assert rule not in artifact_html(document("Plain", chapter("plain", "Plain", paragraph("Text."))))
    assert rule in feature_source("templates.css")


def test_an_unknown_part_fails_at_its_node() -> None:
    source = document("Plain", chapter("plain", "Plain", {"type": "templates", "attrs": {"part": "draft"}, "children": []}))
    source["capabilities"].append("templates")

    with pytest.raises(InputError) as failure:
        artifact_html(source)

    assert "draft" in failure.value.problem and "template parts" in failure.value.problem
