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


# The declared style: the style module the Document's ``style`` names (spec/configuration.md, Declared style).

from style_fetchers import FakeFetcher, fake_styles  # noqa: E402
from obs_html.declared_style import GitFetcher, user_cache  # noqa: E402

DECLARED = {"url": "https://example.invalid/house-style.git", "ref": "0123456789abcdef0123456789abcdef01234567",
            "path": "styles/house"}
HOUSE = {"styles/house/style.css": ":root { --declared-style: house; }\n", "README.md": "House style\n"}


def _declaring(document: dict, **style: str) -> dict:
    document["style"] = {**DECLARED, **style}
    return document


def test_a_declared_style_is_fetched_and_laid_over_the_packaged_base_in_place_of_the_generic_module(
        document, tmp_path: Path) -> None:
    styles = fake_styles(tmp_path / "cache", {(DECLARED["url"], DECLARED["ref"]): HOUSE})
    document["cssSnippets"] = [{"name": "late", "path": ".obsidian/snippets/late.css", "text": "p { --snippet: 1; }"}]
    document["manifest"].setdefault("metadata", {})["obsHtml"] = {"cssSnippets": ["late"]}

    artifact = render(_declaring(document), CONFIG, styles=styles)

    assert styles.fetcher.calls == [(DECLARED["url"], DECLARED["ref"])]
    assert artifact.index(".paper-sheet") < artifact.index("--declared-style: house") < artifact.index("--snippet: 1")
    assert 'font-content: Georgia, "Times New Roman", serif' not in artifact


def test_style_option_wins_over_the_declared_style_and_fetches_nothing(document, tmp_path: Path) -> None:
    styles = fake_styles(tmp_path / "cache", {(DECLARED["url"], DECLARED["ref"]): HOUSE})
    override = _style(tmp_path, ":root { --one-off: chosen; }")

    artifact = render(_declaring(document), CONFIG, style_folder=override, styles=styles)

    assert "--one-off: chosen" in artifact and "--declared-style" not in artifact
    assert styles.fetcher.calls == []


def test_the_cache_fetches_each_commit_once_across_builds(document, tmp_path: Path) -> None:
    trees = {(DECLARED["url"], DECLARED["ref"]): HOUSE}
    first, second = fake_styles(tmp_path / "cache", trees), fake_styles(tmp_path / "cache", trees)

    render(_declaring(document), CONFIG, styles=first)
    render(_declaring(document), CONFIG, styles=first)
    artifact = render(_declaring(document), CONFIG, styles=second)

    assert len(first.fetcher.calls) == 1 and second.fetcher.calls == []
    assert "--declared-style: house" in artifact
    assert [entry.name for entry in (tmp_path / "cache").iterdir()] == [DECLARED["ref"]]


def test_a_style_that_cannot_be_fetched_names_its_url_and_ref_and_caches_nothing(document, tmp_path: Path) -> None:
    styles = fake_styles(tmp_path / "cache")

    with pytest.raises(InputError) as failure:
        render(_declaring(document), CONFIG, styles=styles)

    assert (failure.value.source, failure.value.field) == (f"Document of {document['manifest']['path']}", "style")
    assert DECLARED["url"] in failure.value.problem and DECLARED["ref"] in failure.value.problem
    assert list((tmp_path / "cache").iterdir()) == []


@pytest.mark.parametrize("path", ["../outside", "styles/../../outside", "/etc", "C:/styles"])
def test_a_style_path_that_leaves_the_fetched_tree_is_refused_before_any_fetch(document, tmp_path: Path,
                                                                               path: str) -> None:
    styles = fake_styles(tmp_path / "cache", {(DECLARED["url"], DECLARED["ref"]): HOUSE})

    with pytest.raises(InputError) as failure:
        render(_declaring(document, path=path), CONFIG, styles=styles)

    assert (failure.value.source, failure.value.field) == (f"Document of {document['manifest']['path']}", "style.path")
    assert styles.fetcher.calls == []


def test_a_style_path_without_a_stylesheet_names_the_style_path(document, tmp_path: Path) -> None:
    styles = fake_styles(tmp_path / "cache", {(DECLARED["url"], DECLARED["ref"]): HOUSE})

    with pytest.raises(InputError) as failure:
        render(_declaring(document, path="styles"), CONFIG, styles=styles)

    assert (failure.value.source, failure.value.field) == (f"Document of {document['manifest']['path']}", "style.path")


def test_the_default_cache_is_a_user_cache_folder_outside_the_checkout() -> None:
    from conftest import ROOT

    assert user_cache().parts[-2:] == ("obs-html", "styles")
    assert not user_cache().is_relative_to(ROOT.parents[1])


def _repository(folder: Path) -> tuple[str, str]:
    """A local Git repository holding HOUSE at one commit: its path, as a clone URL, and the commit."""
    import subprocess
    folder.mkdir()
    for name, text in HOUSE.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
    git = ["git", "-C", str(folder), "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
    for command in (["init", "--quiet"], ["add", "."], ["commit", "--quiet", "-m", "house"]):
        subprocess.run([*git, *command], check=True)
    commit = subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    return folder.as_uri(), commit


@pytest.mark.parametrize("kind", ["fake", "git"])
def test_every_fetcher_fetches_a_commit_s_tree_and_fails_on_an_unknown_commit(tmp_path: Path, kind: str) -> None:
    """The contract the fake and the real fetcher share; the real one reads a local repository only."""
    url, commit = _repository(tmp_path / "repository")
    fetcher = FakeFetcher({(url, commit): HOUSE}) if kind == "fake" else GitFetcher()
    (tmp_path / "tree").mkdir()

    assert fetcher.fetch(url, commit, tmp_path / "tree") is None
    assert (tmp_path / "tree" / "styles/house/style.css").read_text(encoding="utf-8") == HOUSE["styles/house/style.css"]
    (tmp_path / "missing").mkdir()
    assert fetcher.fetch(url, "f" * 40, tmp_path / "missing")
