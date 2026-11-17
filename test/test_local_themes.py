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
            assert b"trebuchet" not in archive.read(member).lower(), member.filename


def test_tests_read_no_machine_themes() -> None:
    folder = os.environ.get(VARIABLE)
    assert folder and Path(folder).is_absolute() and not Path(folder).exists()
    assert style_choice.local_style_choice(os.environ) is None


STYLE_CSS = "obs-html local folder: themes/contrast/style.css"
STYLE_BREAKS = {
    "page-geometry": (":root {\n    --paper-width: 10cm;\n}\n", "--paper-width"),
    "page": ("@page {\n    margin: 1cm;\n}\n", "@page"),
    "import": ('@import "late.css";\n', "@import"),
    "font-face": ('@font-face {\n    font-family: "Late";\n    src: local("Late");\n}\n', "@font-face"),
    "layer": ("@layer theme {\n    p { margin: 0; }\n}\n", "@layer"),
    "container": ("@container (min-width: 30rem) { p { margin: 0; } }\n", "@container"),
    "remote-url": (".cover-organization {\n    mask-image: url(https://example.invalid/logo.svg);\n}\n", "url"),
    "image-set": ('.cover-organization {\n    mask-image: image-set("data:image/png;base64,AA" 1x);\n}\n', "url"),
    "parse-error": ('p {\n    margin: 0;\n    content: "open\n}\n', "line 3"),
    "style-end": ('p {\n    margin: 0;\n}\np::after {\n    content: "</style>";\n}\n', "line 5"),
    "hex": ("p {\n    margin: 0;\n    border-color: #ff0000;\n}\n", "line 3"),
    "named-colour": ("p {\n    color: rebeccapurple;\n}\n", "line 2"),
    "color-mix-literal": ("p {\n    color: color-mix(in srgb, red 40%, var(--color-text));\n}\n", "line 2"),
    "rgb": ("p {\n    color: light-dark(#ffffff, #000000);\n    background: rgb(0 0 0);\n}\n", "line 3"),
    "color-scheme": (":root {\n    color-scheme: dark;\n}\n", "color-scheme"),
    "prefers-color-scheme": ("@media (prefers-color-scheme: dark) {\n    p { margin: 0; }\n}\n",
                             "prefers-color-scheme"),
}


def with_style(tmp_path: Path, css: str) -> Path:
    """A copy of the fixture folder whose theme contrast holds ``css`` as its style.css."""
    folder = copied(tmp_path)
    (folder / "themes" / "contrast" / "style.css").write_text(css, encoding="utf-8")
    return folder


@pytest.mark.parametrize("css, field", STYLE_BREAKS.values(), ids=STYLE_BREAKS)
def test_a_theme_rule_is_refused_naming_its_file_and_field(css, field, tmp_path, capsys, monkeypatch) -> None:
    refused(capsys, tmp_path, with_style(tmp_path, css), STYLE_CSS, field, monkeypatch)


ACCEPTED = """#cover .cover-organization {
    mask-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>");
    background-color: var(--color-text);
    border-color: light-dark(#123456, #abcdef);
    color: currentcolor;
    outline-color: transparent;
    text-decoration-color: color-mix(in srgb, var(--color-text) 40%, transparent);
}
"""


def test_theme_colours_as_pairs_and_variables_are_read(tmp_path) -> None:
    [theme] = fixture_choice(with_style(tmp_path, ACCEPTED)).extras
    css = theme.css()
    for kept in ("light-dark(#123456, #abcdef)", "var(--color-text)", "currentcolor", "transparent",
                 "color-mix(in srgb, var(--color-text) 40%, transparent)",
                 "data:image/svg+xml", ':where(:root[data-style="contrast"]) #cover .cover-organization{'):
        assert kept in css, css


SCOPED = """/* planted-theme-comment */
:root {
    --font-content: "Trebuchet MS", sans-serif;
}
html body p { margin: 0; }
:root.paged .chapter { margin: 0; }
.chapter h1, .chapter h2 { margin: 0; }
@media print {
    :root { --font-code: "Courier New", monospace; }
    .chapter-body p { margin: 0; }
}
@supports (display: grid) {
    html { margin: 0; }
}
"""


def test_theme_rules_keep_their_specificity_and_follow_default(document, tmp_path) -> None:
    document["cssSnippets"] = [{"name": "late", "path": ".obsidian/snippets/late.css", "text": "p { --snippet: 1; }"}]
    document["manifest"].setdefault("metadata", {})["obsHtml"] = {"cssSnippets": ["late"]}
    html = artifact_html(document, style_choice=fixture_choice(with_style(tmp_path, SCOPED)))
    styles = head(html).split('<style id="style-choice-styles">', 1)[1].split("</style>", 1)[0]
    colours, rules = styles.split("}", 1)
    assert colours.startswith(':root:where([data-style="contrast"]){') and color_variable("color.canvas") in colours
    name = '[data-style="contrast"]'
    for selector in (f":root:where({name}){{", f"html:where({name}) body p{{",
                     f":root:where({name}).paged .chapter{{",
                     f":where(:root{name}) .chapter h1,:where(:root{name}) .chapter h2{{",
                     f"@media print{{:root:where({name}){{", f":where(:root{name}) .chapter-body p{{",
                     f"@supports (display: grid){{html:where({name}){{"):
        assert selector in rules, rules
    assert rules.index('"Trebuchet MS"') < rules.index("@media print") < rules.index("@supports")
    assert html.index('<style id="style-choice-styles">') < html.index('<style data-css-snippet="late">')
    assert html.index('<style id="semantic-asset-styles">') < html.index('<style id="style-choice-styles">')
    assert "planted-theme-comment" not in html
