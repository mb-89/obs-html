"""Source file links without a browser (spec/cli.md, Source file links; source_files.py)."""
import dataclasses
import json
from importlib.resources import files
from pathlib import Path

import pytest

from conftest import FIXTURE
from documents import chapter, document, heading, paragraph
from obs_html import cli, provenance, source_files
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render

CONFIG = load_config()
OFF = dataclasses.replace(CONFIG, artifact={**CONFIG.artifact, "sourceFileLinks": False})
SCRIPT = files("obs_html").joinpath("source-file.js").read_text(encoding="utf-8")
ADDED = ("sourceFilePath", "sourceFileHref")
EPOCH = "1700000000"


def rows(html: str) -> dict[str, tuple[str | None, str | None]]:
    return {note["slug"]: (note.get("sourceFilePath"), note.get("sourceFileHref"))
            for note in decode_artifact_data(html)["notes"]}


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("link", ["notes", "../notes", "../../My Notes ü", "../.notes"])
def test_a_link_climbs_with_dots_alone_then_names_the_vault_folder(link) -> None:
    assert source_files.checked(link) == link


@pytest.mark.parametrize("link", ["", "..", ".", "../", "../..", "../a:b", "-notes", "../-notes", "a/notes",
                                  "../a\\b", "./notes", "../no\ttes", "/notes", "..//notes"])
def test_any_other_link_is_an_input_error_of_the_vault_link(link) -> None:
    with pytest.raises(InputError) as refused:
        source_files.checked(link)
    assert (refused.value.source, refused.value.field) == ("obs-html", "--vault-link")


def test_a_local_term_that_matches_the_vault_folder_drops_the_link(tmp_path) -> None:
    (tmp_path / ".public-check.local").write_text("# a comment\nsecret\n", encoding="utf-8")
    terms = provenance.local_terms(tmp_path / ".public-check.local")

    assert source_files.usable("../../Secret-notes", terms) is None
    assert source_files.usable("../notes", terms) == "../notes"
    assert source_files.usable("../secret-notes", ()) == "../secret-notes"


def test_the_link_joins_its_parts_percent_encoded() -> None:
    assert source_files.href("../My Notes", "guide/usage ü #1?.md") == \
        "../My%20Notes/guide/usage%20%C3%BC%20%231%3F.md"
    assert source_files.href("notes", "a.md") == "notes/a.md"
    assert source_files.href("../../notes", "a/b.md").isascii()


def test_each_note_the_document_names_a_path_for_gets_its_path_and_with_a_link_its_link() -> None:
    linked, plain = rows(render(fixture(), CONFIG, vault_link="../vault")), rows(render(fixture(), CONFIG))

    assert linked["home"] == ("manifest.md", "../vault/manifest.md")
    assert linked["guide-usage"] == ("guide/usage.md", "../vault/guide/usage.md")
    assert linked["intro"] == ("intro.md", "../vault/intro.md")
    assert all(path and link == f"../vault/{path}" for path, link in linked.values())
    assert plain == {slug: (path, None) for slug, (path, _) in linked.items()}


def test_a_note_with_only_the_stand_in_path_gets_neither() -> None:
    """A chapter without a note record keeps the stand-in ``{slug}.md``; one with a record gets its path."""
    source = document("Plain", chapter("one", "One", heading(1, "One"), paragraph("Text.")),
                      chapter("two", "Two", heading(1, "Two"), paragraph("Text.")),
                      records=({"type": "note", "id": "two", "path": "notes/two.md", "fields": {}},))

    assert rows(render(source, CONFIG, vault_link="../vault")) == {
        "home": ("manifest.md", "../vault/manifest.md"), "one": (None, None),
        "two": ("notes/two.md", "../vault/notes/two.md")}


def test_no_other_field_changes() -> None:
    off, on = (decode_artifact_data(render(fixture(), config, vault_link="../vault")) for config in (OFF, CONFIG))

    assert [{key: value for key, value in note.items() if key not in ADDED} for note in on["notes"]] == off["notes"]
    assert {key: value for key, value in on.items() if key not in {"notes", "document"}} == \
        {key: value for key, value in off.items() if key not in {"notes", "document"}}


def _built(tmp_path: Path, name: str, *arguments: str) -> bytes:
    destination = tmp_path / name / "document.html"
    assert cli.main([str(FIXTURE), str(destination), *arguments]) == 0
    return destination.read_bytes()


def test_with_the_option_off_a_page_is_the_same_with_or_without_the_link(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    (tmp_path / "off.json").write_text('{"artifact": {"sourceFileLinks": false}}\n', encoding="utf-8")
    off = ("--config", str(tmp_path / "off.json"))

    without, linked = _built(tmp_path, "without", *off), _built(tmp_path, "linked", "--vault-link", "../vault", *off)

    assert without == linked
    text = without.decode("utf-8")
    assert SCRIPT not in text and all(field not in text for field in ADDED)
    assert all(field not in json.dumps(decode_artifact_data(text)) for field in ADDED)


def test_the_packaged_settings_ship_the_row_and_a_page_with_links_reports_no_provenance(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    page = _built(tmp_path, "on", "--vault-link", "../vault").decode("utf-8")

    assert page.count(SCRIPT) == 1
    assert provenance.reported(provenance.findings(page)) == []


def _secret_vault(tmp_path: Path) -> Path:
    """A project whose local list names its vault folder, secret-notes, beside the page's folder."""
    project = tmp_path / "proj2"
    (project / "secret-notes").mkdir(parents=True)
    (project / ".public-check.local").write_text("secret\n", encoding="utf-8")
    (tmp_path / "refuse.json").write_text('{"artifact": {"refuseProvenance": true}}\n', encoding="utf-8")
    return project


def test_a_page_whose_local_list_names_the_vault_folder_has_no_link_and_warns_of_nothing(tmp_path, capsys) -> None:
    project = _secret_vault(tmp_path)
    destination = project / "site" / "page.html"

    assert cli.main([str(FIXTURE), str(destination), "--vault-root", str(project / "secret-notes"),
                     "--vault-link", "../secret-notes", "--config", str(tmp_path / "refuse.json")]) == 0

    assert "warning" not in capsys.readouterr().err.lower()
    assert all(link is None for _path, link in rows(destination.read_text(encoding="utf-8")).values())


def test_the_vault_list_is_found_from_the_destination_where_the_root_is_relative_to_another_folder(
        tmp_path, monkeypatch, capsys) -> None:
    project = _secret_vault(tmp_path)
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")  # The adapter runs from another folder than the user's.
    destination = project / "site" / "page.html"

    assert cli.main([str(FIXTURE), str(destination), "--vault-root", "secret-notes",
                     "--vault-link", "../secret-notes", "--config", str(tmp_path / "refuse.json")]) == 0

    assert "warning" not in capsys.readouterr().err.lower()
    assert all(link is None for _path, link in rows(destination.read_text(encoding="utf-8")).values())


def test_a_second_list_that_does_not_read_gives_no_link_and_no_error(tmp_path, capsys) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / ".public-check.local").write_text("[\n", encoding="utf-8")  # Not a regex.
    destination = tmp_path / "b" / "site" / "page.html"

    assert cli.main([str(FIXTURE), str(destination), "--vault-root", str(tmp_path / "a" / "notes"),
                     "--vault-link", "../notes"]) == 0

    assert "warning" not in capsys.readouterr().err.lower()
    assert all(link is None for _path, link in rows(destination.read_text(encoding="utf-8")).values())
