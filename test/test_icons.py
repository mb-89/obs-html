"""Named icons and the semantic asset index: packaged, overlaid by a style module's assets.json."""
import base64
import json
from pathlib import Path

import pytest

from obs_html.cli import main
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import RenderError, render
from obs_html.artifact_data import decode_artifact_data
from obs_html.semantic_assets import SemanticAssets


CONFIG = load_config()
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8xoAAAAASUVORK5CYII="
)


def write_index(path: Path, definitions: dict) -> None:
    assets: dict = {}
    for name, value in definitions.items():
        parts = name.split(".")
        nodes = assets
        for segment in parts[:-1]:
            nodes = nodes.setdefault(segment, {}).setdefault("children", {})
        nodes[parts[-1]] = {"type": "icon", "value": value}
    path.write_text(json.dumps({"schemaVersion": 1, "assets": assets}), encoding="utf-8")


def style_with_icons(root: Path, definitions: dict) -> Path:
    style = root / "style"
    style.mkdir(parents=True)
    (style / "style.css").write_text(":root { --icon-style: on; }", encoding="utf-8")
    write_index(style / "assets.json", definitions)
    return style


def with_icon_column(document: dict, name: str) -> dict:
    base = next(node for node in document["chapters"][0]["content"] if node["type"] == "bases")
    base["attrs"]["spec"]["properties"]["evidence"] = {"obsHtml": {"icon": {
        "name": name, "label": "Evidence instructions", "help": "Select replacement evidence."}}}
    return document


def test_packaged_icons_resolve_in_the_shell_and_the_island(document) -> None:
    html = render(document, CONFIG)
    assert 'data-icon="menu" aria-hidden="true">☰</span>' in html
    assert '<style id="semantic-asset-styles">:root{' in html and "--color-canvas:var(" in html
    data = decode_artifact_data(html)
    assert data["assets"]["icon.menu"]["value"] == {"glyph": "☰"}


def test_style_catalog_overrides_framework_icons_and_reaches_base_columns(document, tmp_path) -> None:
    style = style_with_icons(tmp_path, {
        "project.evidence": {"glyph": "\U0001f9ea"},
        "icon.menu": {"glyph": "CAT"},
        "icon.mark-risk": {"glyph": "RSK"},
    })
    html = render(with_icon_column(document, "project.evidence"), CONFIG,
                  style_folder=style)
    data = decode_artifact_data(html)
    assert data["assets"]["project.evidence"]["value"] == {"glyph": "\U0001f9ea"}
    assert 'data-icon="menu" aria-hidden="true">CAT</span>' in html
    intro = next(note for note in data["notes"] if note["slug"] == "intro")
    assert 'data-icon="mark.risk" aria-hidden="true">RSK</span>' in intro["html"]
    definition = intro["tables"][0]["definition"]
    assert definition["properties"]["evidence"]["obsHtml"]["icon"]["name"] == "project.evidence"


def test_unknown_base_icons_name_the_note_and_the_obshtml_key(document) -> None:
    with pytest.raises(InputError) as failure:
        render(with_icon_column(document, "project.evidence"), CONFIG)
    assert (failure.value.source, failure.value.field) == ("intro.md", "properties.evidence.obsHtml.icon.name")


@pytest.mark.parametrize("case,expected", [
    ("invalid-json", "Invalid semantic asset index"),
    ("invalid-entry", "does not match"),
    ("missing-asset", "Missing icon resource"),
    ("escape", "escapes its boundary"),
    ("remote", "does not match"),
    ("script", "Unsupported icon SVG element"),
    ("malformed-svg", "Invalid icon SVG"),
])
def test_invalid_style_catalogs_fail_the_cli(document, tmp_path, capsys, case, expected) -> None:
    style = style_with_icons(tmp_path, {})
    catalog = style / "assets.json"
    if case == "invalid-json":
        catalog.write_text("{", encoding="utf-8")
    elif case == "invalid-entry":
        write_index(catalog, {"project.evidence": {"glyph": ""}})
    elif case == "missing-asset":
        write_index(catalog, {"project.evidence": {"asset": "absent.png"}})
    elif case == "escape":
        (tmp_path / "outside.png").write_bytes(PIXEL)
        write_index(catalog, {"project.evidence": {"asset": "../outside.png"}})
    elif case == "remote":
        write_index(catalog, {"project.evidence": {"asset": "https://example.invalid/icon.png"}})
    else:
        write_index(catalog, {"project.evidence": {"asset": "bad.svg"}})
        (style / "bad.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
            if case == "script" else "<svg", encoding="utf-8",
        )
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "artifact.html"
    with pytest.raises(SystemExit) as failure:
        main([str(source), str(output), "--style", str(style)])
    assert failure.value.code == 2
    assert expected in capsys.readouterr().err
    assert not output.exists()


def test_semantic_hierarchy_alias_and_state_merge(tmp_path) -> None:
    (tmp_path / "pixel.png").write_bytes(PIXEL)
    index = {"schemaVersion": 1, "assets": {
        "icon": {"children": {
            "unavailable": {"type": "icon", "value": {"glyph": "IN"}},
            "snapshot": {"value": {"asset": "pixel.png"}},
            "source": {"value": {"glyph": "ACT"}},
        }},
        "color": {"children": {
            "action": {"type": "color", "value": "#123456"},
            "text-muted": {"value": "#654321"},
        }},
        "project": {
            "type": "appearance", "defaultState": "active",
            "color": {"ref": "color.accent"},
            "states": {
                "active": {"color": {"ref": "color.action"}},
                "inactive": {"icon": {"ref": "icon.unavailable"}, "color": {"ref": "color.text-muted"}},
            },
            "children": {"evidence": {
                "color": {"ref": "color.failure"},
                "children": {
                    "snapshot": {"states": {"active": {"icon": {"ref": "icon.snapshot"}}}},
                    "source": {"states": {"active": {"icon": {"ref": "icon.source"}}}},
                },
            }},
        },
        "snapshotAlias": {"ref": "project.evidence.snapshot"},
    }}
    (tmp_path / "assets.json").write_text(json.dumps(index), encoding="utf-8")
    assets = SemanticAssets(tmp_path / "assets.json")
    assert assets.icon("snapshotAlias", "active")["asset"].startswith("obs-asset:")
    assert assets.icon("snapshotAlias", "inactive") == {"glyph": "IN", "color": "color.text-muted"}
    assert assets.icon("project.evidence.source", "active") == {"glyph": "ACT", "color": "color.action"}
    assert assets.entry("color.action")["value"] == "#123456"
    # The packaged filter icon comes from the package, not from the style module's folder.
    packaged = assets.icon("filter")["asset"].split(":")[1]
    assert assets.embedded_assets[packaged].startswith("data:image/svg+xml;")
    with pytest.raises(ValueError, match="state=unknown"):
        assets.icon("snapshotAlias", "unknown")
    assert "#123456" in assets.css()
