from structure.naming import ROOT, says_document_presentation

NOTE = "spec/capabilities/artifact-presentation.md"


def test_no_capability_id_heading_or_link_says_document_presentation() -> None:
    assert says_document_presentation(NOTE) == []


def test_the_capability_is_artifact_presentation() -> None:
    text = (ROOT / NOTE).read_text(encoding="utf-8")

    assert "  id: artifact-presentation\n" in text
    assert not (ROOT / "spec/capabilities/document-presentation.md").exists()
