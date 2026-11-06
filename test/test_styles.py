from pathlib import Path

import pytest

from obs_html.cli import main
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render


CONFIG = load_config()


def _style(root: Path, css: str, assets: str | None = None) -> Path:
    style = root / "style"
    style.mkdir()
    (style / "style.css").write_text(css, encoding="utf-8")
    if assets is not None:
        (style / "assets.json").write_text(assets, encoding="utf-8")
    return style


def test_default_style_is_packaged_generic_and_has_no_external_module(document) -> None:
    artifact = render(document, CONFIG)

    assert 'font-content: Georgia, "Times New Roman", serif' in artifact
    assert ".paper-sheet" in artifact  # The base stylesheet always precedes the module overlay.
    assert "file:///" not in artifact
    assert '<link rel="stylesheet"' not in artifact


def test_explicit_style_module_overrides_the_default(document, tmp_path: Path) -> None:
    style = _style(tmp_path, ":root { --module-style: selected; }")

    artifact = render(document, CONFIG, style_folder=style)

    assert "--module-style: selected" in artifact
    assert 'font-content: Georgia, "Times New Roman", serif' not in artifact
    assert ".paper-sheet" in artifact


@pytest.mark.parametrize("geometry", ["@page { size: A4; }", ":root { --paper-width: 1mm; }"])
def test_style_module_cannot_declare_page_geometry(document, tmp_path: Path, geometry: str) -> None:
    style = _style(tmp_path, geometry)

    with pytest.raises(InputError) as failure:
        render(document, CONFIG, style_folder=style)
    assert failure.value.source == str((style / "style.css").resolve())
    assert failure.value.field == geometry.split()[0 if geometry.startswith("@") else 2].rstrip(":")


def test_style_module_must_be_a_folder_with_a_stylesheet(document, tmp_path: Path) -> None:
    with pytest.raises(InputError) as failure:
        render(document, CONFIG, style_folder=tmp_path / "missing")
    assert (failure.value.source, failure.value.field) == (str((tmp_path / "missing").resolve()), "top level")
    (tmp_path / "empty").mkdir()
    with pytest.raises(InputError) as failure:
        render(document, CONFIG, style_folder=tmp_path / "empty")
    assert (failure.value.source, failure.value.field) == (str((tmp_path / "empty").resolve()), "style.css")


def test_cli_style_option_selects_an_external_style_folder(document, tmp_path: Path) -> None:
    import json
    style = _style(tmp_path, ":root { --cli-style: chosen; }")
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "artifact.html"

    assert main([str(source), str(output), "--style", str(style)]) == 0
    assert "--cli-style: chosen" in output.read_text(encoding="utf-8")
