import json
from pathlib import Path
from structure.naming import says_document_presentation


def test_no_heading_or_link_says_document_presentation() -> None:
    assert says_document_presentation("spec/configuration.md") == []


def test_config_references_existing_json_schema() -> None:
    """The packaged settings name the JSON Schema that holds their limits (configuration.md)."""
    config_path = Path(__file__).parents[2] / "src" / "obs_html" / "cfg.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    schema = json.loads((config_path.parent / config["$schema"]).read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
