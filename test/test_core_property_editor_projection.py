"""A property editor's static projection renders from a core-built Document (obs capabilities/property-editors).

The core-built Document ``fixtures/documents/property-editor-projection.json`` (vault
``property-editor-projection`` in ``fixtures/build_documents.py``) carries the fence's projection in
the ``property-editors`` node's ``attrs.spec``; the artifact keeps it as the editor's static data.
"""
import json
import re

from conftest import ROOT
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.render import render

SOURCE = ROOT / "src" / "obs_html"


DOCUMENT = json.loads((ROOT / "test" / "fixtures" / "documents" / "property-editor-projection.json")
                      .read_text(encoding="utf-8"))


def test_the_projection_of_a_core_built_document_is_the_editors_static_data() -> None:
    [editor] = [node for node in DOCUMENT["chapters"][0]["content"] if node["type"] == "property-editors"]
    html = render(DOCUMENT, load_config())

    [note] = [note for note in decode_artifact_data(html)["notes"] if note["slug"] == "finding"]
    assert note["editableProperties"]["explanation"]["projection"] == editor["attrs"]["spec"]["projection"] == {
        "blank": {"status": "finding", "accepted": "no", "outputs": []},
        "nonblank": {"status": "explained", "accepted": "yes", "outputs": ["System", "Labels"]},
    }
    assert 'data-property-field="explanation"' in note["html"]


def test_no_projection_rule_check_remains_in_the_adapter() -> None:
    """The core owns the projection rules (obs capabilities/property-editors#Projection rules):
    the adapter's Python reads a projection only as data, and its schema checks only its shape."""
    for path in SOURCE.glob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert not re.search(r"projection.*(PROTECTED_FIELDS|frontmatter|InputError)|_projection_",
                                 line), f"{path.name}:{number}: {line.strip()}"
    schema = json.loads((SOURCE / "property-editor.schema.json").read_text(encoding="utf-8"))
    assert "$ref" not in schema["$defs"]["projectionFields"]["propertyNames"]
