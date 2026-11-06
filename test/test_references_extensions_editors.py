"""References, syntax extensions and property editors render as the interim adapter in obs did.

Documents are built as the core emits them (its vault.py): a glossary or reference note
carries a ``references`` node with its frontmatter, and a ``property-editor`` fence a
``property-editors`` node with its mapping in ``attrs.spec``. The property-editor cases are the interim's
test_property_editors.py on Documents.
"""
import json

import pytest

from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from obs_html.artifact_data import decode_artifact_data

from documents import chapter, document as build, heading, node, paragraph, text


CONFIG = load_config()


def _notes(source: dict) -> dict[str, dict]:
    html = render(source, CONFIG)
    return {note["slug"]: note for note in decode_artifact_data(html)["notes"]} | {"": {"html": html}}


def _editor(fence: dict, metadata: dict) -> dict:
    return build("Doc", chapter("one", "One", heading(1, "One"), node("property-editors", source=json.dumps(fence),
                                                                      spec=fence), metadata=metadata))


def test_a_glossary_note_carries_its_definition_for_hover_cards_and_registers() -> None:
    term = {"kind": "glossary", "term": "Datum", "definition": "A **reference**, see [[one]]."}
    notes = _notes(build("Doc", chapter("one", "One", heading(1, "One")),
                         chapter("datum", "Datum", node("references", metadata=term), metadata=term, fields={
                             "term": ["Datum"],
                             "definition": ["A ", {"type": "strong", "attrs": {}, "children": [text("reference")]},
                                            ", see ", node("wikilinks", target="one", chapter="one", heading="",
                                                           label="one"), "."]}),
                         records=({"id": "one", "type": "note", "path": "one.md", "fields": {}},)))
    assert notes["datum"]["definitionHtml"] == (
        'A <strong>reference</strong>, see <a class="internal-link" href="#one">One</a>.')
    assert notes["one"]["definitionHtml"] == ""


def test_a_glossary_record_without_a_chapter_carries_its_definition_from_its_field_nodes() -> None:
    fields = {"kind": "glossary", "term": "Term", "definition": "Said *once* & <b>twice</b>."}
    record = {"id": "term", "type": "note", "path": "term.md", "fields": fields, "fieldNodes": [
        {"type": "field", "attrs": {"name": "kind"}, "children": [text("glossary")]},
        {"type": "field", "attrs": {"name": "term"}, "children": [text("Term")]},
        {"type": "field", "attrs": {"name": "definition"}, "children": [
            text("Said "), {"type": "emphasis", "attrs": {}, "children": [text("once")]}, text(" & <b>twice</b>.")]}]}
    notes = _notes(build("Doc", chapter("one", "One"), records=(record,)))
    assert notes["term"]["definitionHtml"] == "Said <em>once</em> &amp; &lt;b&gt;twice&lt;/b&gt;."


def test_a_reference_note_keeps_its_url_for_the_hover_card() -> None:
    reference = {"kind": "reference", "url": "https://example.org/spec", "description": "The spec."}
    notes = _notes(build("Doc", chapter("spec", "Spec", node("references", metadata=reference),
                                        metadata=reference)))
    assert notes["spec"]["frontmatter"]["url"] == "https://example.org/spec"


@pytest.mark.parametrize("metadata,field", [
    ({"kind": "glossary", "term": "Datum"}, "definition"),
    ({"kind": "reference", "url": "file:///home/me/spec.pdf"}, "url"),
])
def test_invalid_reference_notes_fail_naming_the_note_and_the_field(metadata, field) -> None:
    with pytest.raises(InputError) as failure:
        render(build("Doc", chapter("bad", "Bad", node("references", metadata=metadata), metadata=metadata)),
               CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter bad", field)


@pytest.mark.parametrize("syntax", ["callout", "diagram"])
def test_a_syntax_extension_fails_naming_the_syntax_its_source_and_the_remedy(syntax) -> None:
    """No syntax extension has an input-model contract yet (the core's extensions.md), so the core
    emits none; a callout is a ``callouts`` node, never an ``extensions`` marker."""
    with pytest.raises(InputError) as failure:
        render(build("Doc", chapter("one", "One", node("extensions", syntax=syntax))), CONFIG)
    assert (failure.value.source, failure.value.field) == ("Document of manifest.md", "chapters[0].content[0].attrs.syntax")
    assert "obs-document" in failure.value.remedy and "extensions.md" in failure.value.problem


def test_property_editor_is_explicit_and_canonical() -> None:
    notes = _notes(_editor({"version": 1, "field": "explanation", "label": "Review explanation"},
                           {"explanation": "Original", "identifier": "R-1"}))
    one = notes["one"]
    assert one["editableProperties"] == {"explanation": {"label": "Review explanation", "maxLength": 4096}}
    assert ('<textarea data-property-editor data-property-note="one" data-property-field="explanation" '
            'maxlength="4096" aria-label="Review explanation" rows="2"></textarea>') in one["html"]
    assert one["frontmatter"] == {"explanation": "Original", "identifier": "R-1"}
    assert 'id="property-editor-script"' in notes[""]["html"]


def test_a_artifact_without_editors_carries_no_editor_script() -> None:
    assert "property-editor-script" not in render(build("Doc", chapter("one", "One")), CONFIG)


def test_property_editor_projection_is_preserved_as_static_data() -> None:
    projection = {"blank": {"status": "finding", "accepted": "no", "sink": "path"},
                  "nonblank": {"status": "explained", "accepted": "yes", "sink": "finding"}}
    notes = _notes(_editor({"version": 1, "field": "explanation", "label": "Review", "projection": projection},
                           {"explanation": "Original", "status": "explained", "accepted": "yes", "sink": "finding"}))
    assert notes["one"]["editableProperties"]["explanation"]["projection"] == projection


def test_property_editor_projection_preserves_supported_arrays() -> None:
    projection = {"blank": {"outputs": []}, "nonblank": {"outputs": ["System", "Labels"]}}
    notes = _notes(_editor({"version": 1, "field": "explanation", "label": "Review", "projection": projection},
                           {"explanation": "Original", "outputs": ["System"]}))
    assert notes["one"]["editableProperties"]["explanation"]["projection"] == projection


@pytest.mark.parametrize("field", [
    "title", "kind", "aliases", "term", "definition",
    "__proto__", "constructor", "prototype", "Title", "KiNd",
])
@pytest.mark.parametrize("branch", ["blank", "nonblank"])
def test_property_editor_projection_rejects_protected_fields(field, branch) -> None:
    value, replacement = (["Original"], ["Changed"]) if field == "aliases" else ("Original", "Changed")
    projection = {"blank": {field: replacement} if branch == "blank" else {"status": "Initial"},
                  "nonblank": {field: replacement} if branch == "nonblank" else {"status": "Initial"}}
    with pytest.raises(InputError) as failure:
        render(_editor({"version": 1, "field": "explanation", "label": "Review", "projection": projection},
                       {"explanation": "Original", "status": "Initial", field: value}), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", f"property-editor.projection.{branch}.{field}")


@pytest.mark.parametrize("field,value", [("missing", "text"), ("explanation", 42), ("title", "semantic")])
def test_property_editor_rejects_missing_nontext_or_semantic_fields(field, value) -> None:
    with pytest.raises(InputError) as failure:
        render(_editor({"version": 1, "field": field, "label": "Review"},
                       {"explanation": value, "title": value}), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", "property-editor.field")


@pytest.mark.parametrize("projection", [
    {"blank": {"missing": "value"}, "nonblank": {"status": "ok"}},
    {"blank": {"explanation": "replaced"}, "nonblank": {"status": "ok"}},
    {"blank": {"status": {"nested": "value"}}, "nonblank": {"status": "ok"}},
    {"blank": {"status": ["mixed", 2]}, "nonblank": {"status": "ok"}},
    {"blank": {"status": 5}, "nonblank": {"status": "ok"}},
])
def test_property_editor_rejects_unsafe_or_type_mismatched_projection(projection) -> None:
    with pytest.raises(InputError) as failure:
        render(_editor({"version": 1, "field": "explanation", "label": "Review", "projection": projection},
                       {"explanation": "Original", "status": "explained", "accepted": "yes"}), CONFIG)
    [name] = projection["blank"]
    assert (failure.value.source, failure.value.field) == ("chapter one", f"property-editor.projection.blank.{name}")


@pytest.mark.parametrize("fence,field", [
    ({"version": 2, "field": "explanation", "label": "Review"}, "property-editor.version"),
    ({"version": 1, "field": "explanation", "label": "Review", "maxLength": 3}, "explanation"),
])
def test_invalid_or_oversized_editors_fail_naming_the_note_and_the_field(fence, field) -> None:
    with pytest.raises(InputError) as failure:
        render(_editor(fence, {"explanation": "Original"}), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", field)


def test_a_field_has_one_editor_and_home_has_none() -> None:
    fence = node("property-editors", source="version: 1\nfield: explanation\nlabel: Review\n",
                 spec={"version": 1, "field": "explanation", "label": "Review"})
    with pytest.raises(InputError) as failure:
        render(build("Doc", chapter("one", "One", fence, fence, metadata={"explanation": "x"})), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", "property-editor.field")
    with pytest.raises(InputError) as failure:
        render(build("Doc", abstract=(fence,)), CONFIG)
    assert (failure.value.source, failure.value.field) == ("manifest.md", "property-editor.field")


def test_a_markdown_link_to_a_note_is_an_internal_link_in_prose_and_metadata() -> None:
    source = build("Doc", chapter("one", "One", paragraph({"type": "text", "attrs": {"link": "cite"},
                                                          "children": [], "text": "1"})),
                   chapter("reference", "Reference", metadata={"document": "[Source](reference.md)"},
                           fields={"document": [{"type": "text", "attrs": {"link": "cite"}, "children": [],
                                                 "text": "Source"}]}),
                   records=({"id": "reference", "type": "note", "path": "reference.md", "fields": {}},))
    source["links"] = [{"id": "cite", "href": "reference.md", "label": "1"},
                       {"id": "web", "href": "https://example.org/a.md", "label": "web"}]
    notes = _notes(source)
    assert '<a class="internal-link" href="#reference">1</a>' in notes["one"]["html"]
    assert notes["reference"]["frontmatterHtml"]["document"] == \
        '<a class="internal-link" href="#reference">Source</a>'


def test_external_and_unresolved_markdown_links_stay_ordinary_links() -> None:
    source = build("Doc", chapter("one", "One", paragraph(
        {"type": "text", "attrs": {"link": "web"}, "children": [], "text": "web"},
        {"type": "text", "attrs": {"link": "gone"}, "children": [], "text": "gone"})))
    source["links"] = [{"id": "web", "href": "https://example.org/a.md", "label": "web"},
                       {"id": "gone", "href": "missing.md", "label": "gone"}]
    html = _notes(source)["one"]["html"]
    assert '<a href="https://example.org/a.md">web</a>' in html
    assert '<a href="missing.md">gone</a>' in html
