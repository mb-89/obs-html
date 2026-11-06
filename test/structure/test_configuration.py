from structure.naming import says_document_presentation


def test_no_heading_or_link_says_document_presentation() -> None:
    assert says_document_presentation("spec/configuration.md") == []
