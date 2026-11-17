"""Local themes: a build machine's own themes, found in its local folder, laid over the style module.

The design owners are spec/configuration.md (Local themes), for where themes come from and what one
may hold, and spec/artifact-ui.md (Styling), for what a theme is in the page. A test reads only the
made-up fixture theme (test/fixtures/local-themes) or a copy of it in a temporary folder, and sets
OBS_HTML_LOCAL_FOLDER for its own call: every other test reads no folder (test/conftest.py).
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from artifacts import artifact_html
from conftest import FIXTURE, ROOT
from obs_html import cli, style_choice
from obs_html.artifact_data import decode_artifact_data
from obs_html.semantic_assets import color_variable
from obs_html.source_archive import embedded
from obs_html.style_choice import local_folder, local_style_choice

LOCAL_THEMES = ROOT / "test" / "fixtures" / "local-themes"
VARIABLE = "OBS_HTML_LOCAL_FOLDER"
LOCAL_JSON = "obs-html local folder: local.json"
CONTRAST = json.loads((LOCAL_THEMES / "themes" / "contrast" / "assets.json").read_text(encoding="utf-8"))
COLOURS = CONTRAST["assets"]["color"]["children"]
EPOCH = "1700000000"


def fixture_choice(folder: Path = LOCAL_THEMES):
    return local_style_choice({VARIABLE: str(folder)})


def copied(tmp_path: Path) -> Path:
    """A copy of the fixture folder that a test may change."""
    folder = tmp_path / "obs-html"
    shutil.copytree(LOCAL_THEMES, folder)
    return folder


def head(html: str) -> str:
    return html.split("<head>", 1)[1].split("</head>", 1)[0]


def build(tmp_path: Path, name: str, monkeypatch, folder: Path | None) -> bytes:
    """The fixture Document built through the CLI with the local folder at ``folder``, else unset."""
    if folder is None:
        monkeypatch.delenv(VARIABLE, raising=False)
    else:
        monkeypatch.setenv(VARIABLE, str(folder))
    destination = tmp_path / f"{name}.html"
    assert cli.main([str(FIXTURE), str(destination)]) == 0
    return destination.read_bytes()


def refused(capsys, tmp_path: Path, folder: Path, source: str, field: str, monkeypatch) -> None:
    """A CLI build with the local folder at ``folder`` exits 2 naming ``source`` and ``field``,
    and no message holds the folder's absolute path."""
    monkeypatch.setenv(VARIABLE, str(folder))
    with pytest.raises(SystemExit) as exit_info:
        cli.main([str(FIXTURE), str(tmp_path / "refused.html")])
    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert f"\n{source}: {field}: " in f"\n{captured.err}", captured.err
    for text in (captured.out, captured.err):
        assert str(folder) not in text and folder.as_posix() not in text and str(tmp_path) not in text
    assert not (tmp_path / "refused.html").exists()


def test_without_local_themes_every_page_is_as_before(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    empty = tmp_path / "empty"
    empty.mkdir()
    no_themes = tmp_path / "no-themes"
    (no_themes / "themes").mkdir(parents=True)
    pages = [build(tmp_path, name, monkeypatch, folder) for name, folder in (
        ("missing", tmp_path / "missing"), ("empty", empty), ("no-themes", no_themes))]
    monkeypatch.setattr(cli, "local_style_choice", lambda _environ: None)
    pages.append(build(tmp_path, "none", monkeypatch, LOCAL_THEMES))
    assert all(page == pages[-1] for page in pages)
    for page in pages:
        assert b"data-style" not in page and b"style-choice-styles" not in page


def test_a_local_theme_reaches_the_page_and_opens_in_default(document) -> None:
    html = artifact_html(document, style_choice=fixture_choice())
    root = re.search(r"<html [^>]*>", html)[0]
    assert root.endswith('data-layout="paged" data-style="default">'), root
    reading = decode_artifact_data(html)["reading"]
    assert reading["styles"] == ["default", "contrast"] and reading["style"] == "default"
    startup = head(html).split('<script id="reader-startup-script">', 1)[1].split("</script>", 1)[0]
    assert startup.strip().splitlines()[-1].strip() == 'document.documentElement.dataset.style = "default";'
    styles = re.findall(r'<style id="([^"]+)">', head(html))
    assert styles[-1] == "style-choice-styles", styles
    rule = head(html).split('<style id="style-choice-styles">', 1)[1].split("</style>", 1)[0]
    assert rule.startswith(':root:where([data-style="contrast"]){')
    for name, colour in COLOURS.items():
        value = colour["value"]
        assert f"{color_variable(f'color.{name}')}:light-dark({value['light']},{value['dark']});" in rule


def test_local_json_names_the_start_theme(document, tmp_path) -> None:
    folder = copied(tmp_path)
    (folder / "local.json").write_text('{"startTheme": "contrast"}', encoding="utf-8")
    html = artifact_html(document, style_choice=fixture_choice(folder))
    assert re.search(r"<html [^>]*>", html)[0].endswith('data-style="contrast">')
    assert 'document.documentElement.dataset.style = "contrast";' in head(html)
    assert decode_artifact_data(html)["reading"]["style"] == "contrast"


@pytest.mark.parametrize("text, field", [
    ("{", "top level"),
    ('["contrast"]', "top level"),
    ('{"startTheme": "contrast", "start": "contrast"}', "start"),
    ('{"startTheme": "missing"}', "startTheme"),
], ids=["not-json", "a-list", "unknown-key", "missing-theme"])
def test_a_bad_local_json_names_the_file_and_field(text, field, tmp_path, capsys, monkeypatch) -> None:
    folder = copied(tmp_path)
    (folder / "local.json").write_text(text, encoding="utf-8")
    refused(capsys, tmp_path, folder, LOCAL_JSON, field, monkeypatch)


def _theme(folder: Path, name: str, assets: dict | None = None, entry: str | None = None) -> None:
    theme = folder / "themes" / name
    theme.mkdir(parents=True, exist_ok=True)
    if assets is not None:
        (theme / "assets.json").write_text(json.dumps({"schemaVersion": 1, "assets": assets}), encoding="utf-8")
    if entry is not None:
        (theme / entry).write_text("notes", encoding="utf-8")


PAIR = {"light": "#ffffff", "dark": "#000000"}
BREAKS = {
    "a-capital": ("Contrast", None, None, "themes/Contrast", "name"),
    "default": ("default", None, None, "themes/default", "name"),
    "an-entry": ("plain", None, "notes.txt", "themes/plain", "notes.txt"),
    "an-icon": ("plain", {"color": {"children": {"canvas": {"type": "icon", "value": {"glyph": "x"}}}}}, None,
                "themes/plain/assets.json", "assets.color.children.canvas"),
    "a-single-hex": ("plain", {"color": {"children": {"canvas": {"value": "#ffffff"}}}}, None,
                     "themes/plain/assets.json", "assets.color.children.canvas"),
    "a-ref": ("plain", {"color": {"children": {"canvas": {"ref": "color.text"}}}}, None,
              "themes/plain/assets.json", "assets.color.children.canvas"),
    "an-undeclared-colour": ("plain", {"color": {"children": {"glow": {"value": PAIR}}}}, None,
                             "themes/plain/assets.json", "assets.color.children.glow"),
}


@pytest.mark.parametrize("name, assets, entry, source, field", BREAKS.values(), ids=BREAKS)
def test_a_theme_is_refused_naming_its_file_and_field(name, assets, entry, source, field, tmp_path, capsys,
                                                      monkeypatch) -> None:
    folder = copied(tmp_path)
    _theme(folder, name, assets, entry)
    refused(capsys, tmp_path, folder, f"obs-html local folder: {source}", field, monkeypatch)


def test_the_own_specification_reads_no_local_theme(tmp_path, monkeypatch) -> None:
    def core(command, **_):
        assert command[1:3] == ["-m", "obs.document"]
        shutil.copyfile(FIXTURE, command[command.index("--document") + 1])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def never(_environ):
        raise AssertionError("--build-own-spec read the local folder")
    monkeypatch.setattr(cli.subprocess, "run", core)
    monkeypatch.setattr(cli, "local_style_choice", never)
    monkeypatch.setenv(VARIABLE, str(LOCAL_THEMES))
    destination = tmp_path / "own-spec.html"
    assert cli.main(["--build-own-spec", str(destination)]) == 0
    page = destination.read_text(encoding="utf-8")
    assert "data-style" not in page and "style-choice-styles" not in page


def test_the_local_folder_per_system(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    systems = {
        ("linux", ()): home / ".config" / "obs-html",
        ("linux", (("XDG_CONFIG_HOME", str(tmp_path / "xdg")),)): tmp_path / "xdg" / "obs-html",
        ("darwin", ()): home / "Library" / "Application Support" / "obs-html",
        ("win32", (("APPDATA", str(tmp_path / "roaming")),)): tmp_path / "roaming" / "obs-html",
    }
    for (platform, environ), expected in systems.items():
        monkeypatch.setattr(sys, "platform", platform)
        assert local_folder(dict(environ)).as_posix() == expected.as_posix(), platform
        named = {**dict(environ), VARIABLE: str(tmp_path / "named")}
        assert local_folder(named).as_posix() == (tmp_path / "named").as_posix(), platform
        assert local_folder({**dict(environ), VARIABLE: ""}).as_posix() == expected.as_posix(), platform


def _archive(html: str) -> bytes:
    return re.search(r'<script id="obs-source-archive"[^>]*>.*?</script>', html, re.S)[0].encode("utf-8")


def test_the_source_archive_names_no_local_theme() -> None:
    source = json.loads((ROOT / "test" / "fixtures" / "documents" / "source-archive.json").read_text(encoding="utf-8"))
    without = artifact_html(source)
    themed = artifact_html(source, style_choice=fixture_choice())
    assert _archive(themed) == _archive(without)
    with zipfile.ZipFile(io.BytesIO(embedded(themed, "themed"))) as archive:
        for member in archive.infolist():
            assert "contrast" not in member.filename
            assert b"contrast" not in archive.read(member).lower(), member.filename


def test_tests_read_no_machine_themes() -> None:
    folder = os.environ.get(VARIABLE)
    assert folder and Path(folder).is_absolute() and not Path(folder).exists()
    assert style_choice.local_style_choice(os.environ) is None
