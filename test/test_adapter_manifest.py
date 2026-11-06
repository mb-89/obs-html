import ast
import json
import re
import tomllib
from pathlib import Path

from jsonschema import Draft202012Validator

from conftest import CORE_ROOT, FIXTURE, ROOT
from obs_html.render import CAPABILITIES


def _manifest() -> dict[str, object]:
    return json.loads((ROOT / "adapter.json").read_text(encoding="utf-8"))


def test_adapter_manifest_validates_against_the_core_schema(core_root: Path) -> None:
    schema = json.loads((core_root / "src" / "obs" / "adapter.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(_manifest())


def test_adapter_manifest_declares_exactly_the_rendered_capabilities() -> None:
    assert _manifest()["capabilities"] == sorted(CAPABILITIES)


def test_declared_capabilities_exist_in_the_core_reference(core_root: Path) -> None:
    notes = core_root / "spec" / "capabilities"
    for capability in _manifest()["capabilities"]:
        note = (notes / f"{capability}.md").read_text(encoding="utf-8")
        assert re.search(rf"^  id: {re.escape(capability)}$", note, re.MULTILINE), capability


def test_adapters_configuration_names_the_cli_as_the_executable() -> None:
    adapters = json.loads((CORE_ROOT / "adapters.json").read_text(encoding="utf-8"))
    assert adapters == {"adapters": {"html": "adapters/html/adapter.json"}}
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert _manifest()["command"] == ["uv", "run", "obs-html"]
    assert scripts["obs-html"] == "obs_html.cli:main"  # Other scripts, such as obs-html-inspect, are tools.


def test_fixture_is_a_contract_valid_document_using_every_capability(
        document, document_validator, core_root: Path) -> None:
    """The fixture, which the core builds from its vault, uses every capability a Document can
    list: an adapter behavior (kind adapter-behavior) is no Document capability, and no vault
    yields an extensions node, which has no input-model contract yet (capabilities/extensions)."""
    document_validator.validate(document)
    notes = core_root / "spec" / "capabilities"
    listed = [capability for capability in _manifest()["capabilities"] if capability != "extensions"
              and re.search(r"^kind: capability$", (notes / f"{capability}.md").read_text(encoding="utf-8"),
                            re.MULTILINE)]
    assert document["capabilities"] == listed


def test_no_module_imports_the_core_package() -> None:
    offenders = []
    for path in sorted([*(ROOT / "src").rglob("*.py"), *(ROOT / "test").rglob("*.py")]):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            offenders += [f"{path.relative_to(ROOT)}: {name}" for name in names
                          if name == "obs" or name.startswith("obs.")]
    assert offenders == []
