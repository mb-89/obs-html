"""A property editor's static projection renders from a core-built Document (obs capabilities/property-editors).

The core-built Document ``fixtures/documents/property-editor-projection.json`` (vault
``property-editor-projection`` in ``fixtures/build_documents.py``) carries the fence's projection in
the ``property-editors`` node's ``attrs.spec``; the artifact keeps it as the editor's static data.
"""
import json

from conftest import ROOT
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.render import render


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
