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


# The declared style: the installed style component the Document's ``style`` names
# (spec/configuration.md, Declared style).

HOUSE_CSS = ":root { --declared-style: house; }\n"


def _declaring(document: dict, folder: Path, name: str = "house") -> dict:
    document["style"] = {"name": name, "folder": str(folder)}
    return document


def _installed(root: Path) -> Path:
    folder = root / "components" / "house"
    folder.mkdir(parents=True)
    (folder / "style.css").write_text(HOUSE_CSS, encoding="utf-8")
    return folder


def test_a_declared_style_is_laid_over_the_packaged_base_in_place_of_the_generic_module(
        document, tmp_path: Path) -> None:
    document["cssSnippets"] = [{"name": "late", "path": ".obsidian/snippets/late.css", "text": "p { --snippet: 1; }"}]
    document["manifest"].setdefault("metadata", {})["obsHtml"] = {"cssSnippets": ["late"]}

    artifact = render(_declaring(document, _installed(tmp_path)), CONFIG)

    assert artifact.index(".paper-sheet") < artifact.index("--declared-style: house") < artifact.index("--snippet: 1")
    assert 'font-content: Georgia, "Times New Roman", serif' not in artifact


def test_style_option_wins_over_the_declared_style(document, tmp_path: Path) -> None:
    override = _style(tmp_path, ":root { --one-off: chosen; }")

    artifact = render(_declaring(document, _installed(tmp_path)), CONFIG, style_folder=override)

    assert "--one-off: chosen" in artifact and "--declared-style" not in artifact


def test_a_declared_folder_without_a_stylesheet_names_the_style_folder_and_the_install_command(
        document, tmp_path: Path) -> None:
    with pytest.raises(InputError) as failure:
        render(_declaring(document, tmp_path / "elsewhere"), CONFIG)

    assert (failure.value.source, failure.value.field) == (f"Document of {document['manifest']['path']}", "style.folder")
    assert "obs-components install house" in failure.value.remedy


def test_obs_html_fetches_no_style() -> None:
    from conftest import ROOT

    assert not (ROOT / "src" / "obs_html" / "declared_style.py").exists()
    assert "git" not in (ROOT / "src" / "obs_html" / "styles.py").read_text(encoding="utf-8").split()


# A style module's cover.html (spec/artifact-ui.md, Styling).

from obs_html.artifact_data import decode_artifact_data  # noqa: E402


def _home(document: dict, style: Path | None = None) -> str:
    return decode_artifact_data(render(document, CONFIG, style_folder=style))["notes"][0]["html"]


def _covered(root: Path, template: str) -> Path:
    style = _style(root, "")
    (style / "cover.html").write_text(template, encoding="utf-8")
    return style


def test_a_style_cover_shows_the_title_and_the_present_metadata_as_the_packaged_cover_does(
        document, tmp_path: Path) -> None:
    style = _covered(tmp_path, '<h1 class="document-title">{{ title }}</h1><p>{{metadata.organization}}</p>'
                               "<p>{{ metadata.authors }}</p><p>{{ metadata.product.name }}</p>"
                               "<b>{{ metadata.copyright }}</b><i>{{ metadata.obsHtml.layout }}</i>")
    document["manifest"]["title"] = '<Title & "quoted">'
    packaged = _home(document)

    home = _home(document, style)

    assert home.startswith('<header class="document-heading"><h1 class="document-title">&lt;Title &amp; ')
    assert "<p>Example org</p><p>Ada, Lin</p><p>Widget</p><b></b><i></i></header>" in home
    assert "cover-band" not in home
    assert home.split("</header>", 1)[1] == packaged.split("</header>", 1)[1]


def test_a_style_cover_gives_nothing_for_an_explicitly_empty_title_and_keeps_its_other_markup(
        document, tmp_path: Path) -> None:
    style = _covered(tmp_path, '<h1 class="document-title">{{ title }}</h1><p>{{ metadata.organization }}</p>')
    document["manifest"]["title"] = ""

    model = decode_artifact_data(render(document, CONFIG, style_folder=style))

    assert model["notes"][0]["html"].startswith(
        '<header class="document-heading"><h1 class="document-title"></h1><p>Example org</p></header>')
    assert model["notes"][0]["title"] != ""


@pytest.mark.parametrize("template, placeholder", [
    ("{{ unknown }}", "{{ unknown }}"), ("{{ metadata['organization'] }}", "{{ metadata['organization'] }}"),
    ("{{ title.__class__ }}", "{{ title.__class__ }}"), ("{{ metadata.organization | safe }}",
                                                        "{{ metadata.organization | safe }}"),
    ("<p>{{ title</p>", "{{"), ("<p>title }}</p>", "}}"),
])
def test_a_cover_placeholder_that_is_no_title_or_metadata_path_fails_every_build_naming_it(
        document, tmp_path: Path, template: str, placeholder: str) -> None:
    style = _covered(tmp_path, template)
    document["manifest"]["metadata"]["obsHtml"]["heading"] = "compact"

    with pytest.raises(InputError) as failure:
        render(document, CONFIG, style_folder=style)
    assert (failure.value.source, failure.value.field) == (str((style / "cover.html").resolve()), placeholder)


def test_the_compact_heading_and_a_style_without_cover_html_keep_the_packaged_heading(
        document, tmp_path: Path) -> None:
    plain = _style(tmp_path, "")
    assert _home(document, plain) == _home(document)
    (plain / "cover.html").write_text("<p>{{ title }}</p>", encoding="utf-8")
    document["manifest"]["metadata"]["obsHtml"]["heading"] = "compact"

    assert _home(document, plain) == _home(document)
    assert "document-heading--compact" in _home(document, plain)
