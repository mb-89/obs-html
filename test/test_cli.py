import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURE, ROOT
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data, encode_artifact_data


def _run(*arguments: str) -> None:
    cli.main([str(argument) for argument in arguments])


def test_help_is_the_complete_cli_reference(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run("--help")
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    for option in ("DOCUMENT", "DESTINATION", "--config", "--check",
                   "--export-pdf", "--output", "--check-rendered", "--timings", "--embed-attachments",
                   "Editions", "Exit status"):
        assert option in output


def test_installed_command_renders_through_the_adapter_contract(tmp_path) -> None:
    destination = tmp_path / "out" / "artifact.html"
    completed = subprocess.run(
        [sys.executable, "-m", "obs_html.cli", FIXTURE, destination],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source = f"Document of {fixture['manifest']['path']}"
    assert fixture["diagnostics"] and all(
        f"{item['level'].title()}: {source}: diagnostics[{index}]: {item['message']}" in completed.stderr
        for index, item in enumerate(fixture["diagnostics"]))
    assert completed.stdout == f"Generated {destination.resolve()}.\n"
    notes = decode_artifact_data(destination.read_text(encoding="utf-8"))["notes"]
    assert any('<pre class="command-output"><code>derived' in note["html"] for note in notes)
    assert not (tmp_path / "produced.txt").exists()  # Silent producers run in the core, before conversion.


def test_check_renders_without_output(tmp_path, capsys) -> None:
    _run(FIXTURE, "--check")
    assert "no output written" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def _input_error(capsys, source: object, field: str) -> None:
    """An input error names where it comes from: its message starts with the source and the field."""
    error = capsys.readouterr().err
    assert f"\n{source}: {field}: " in f"\n{error}", error


@pytest.mark.parametrize("arguments, field", [
    ([FIXTURE, "x.html", "--check"], "--check"),
    ([FIXTURE], "DESTINATION"),
    ([FIXTURE, "x.html", "--execute-commands"], "arguments"),
    ([FIXTURE, "x.html", "--output", "x.pdf"], "--output"),
    (["--export-pdf", "a.html"], "--output"),
    (["--export-pdf", "a.html", "--output", "a.html"], "--output"),
    (["--check-rendered", "a.html", FIXTURE], "DOCUMENT"),
    (["--check-rendered", "a.html", "--embed-attachments"], "--embed-attachments"),
    (["--extract-comments", "a.html", "--embed-attachments"], "--embed-attachments"),
    (["--print-chapter", "a.html", "intro", FIXTURE], "DOCUMENT"),
    (["--print-chapter", "a.html", "intro", "--vault-root", "vault"], "--vault-root"),
    (["--print-chapter", "a.html", "intro", "--embed-attachments"], "--embed-attachments"),
    (["--print-chapter", "a.html", "intro", "--extract-comments", "b.html"], "--extract-comments"),
    (["--print-chapter", "a.html", "intro", "--timings"], "--timings"),
    ([FIXTURE, "x.html", "--chapter-format", "text"], "--chapter-format"),
    ([FIXTURE, FIXTURE], "DESTINATION"),
])
def test_invalid_option_combinations_fail(arguments, field, capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run(*arguments)
    assert exit_info.value.code == 2
    _input_error(capsys, "obs-html", field)


def test_a_document_that_is_not_json_names_the_file(tmp_path, capsys) -> None:
    source = tmp_path / "document.json"
    source.write_text("{", encoding="utf-8")
    with pytest.raises(SystemExit):
        _run(source, "--check")
    _input_error(capsys, source, "top level")


def test_settings_override_merges_over_the_packaged_settings(tmp_path, capsys) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"artifact": {"print": {"paperSizes": {
        "Letter": {"widthMillimeters": 200, "heightMillimeters": 250}}}}}), encoding="utf-8")
    destination = tmp_path / "artifact.html"
    _run(FIXTURE, destination, "--config", settings)
    paper = decode_artifact_data(destination.read_text(encoding="utf-8"))["paper"]
    assert paper == {"widthMillimeters": 200, "heightMillimeters": 250, "marginMillimeters": 15.0}


@pytest.mark.parametrize("override, field", [
    ({"execution": {"renderedCheckTimeoutSeconds": 0}}, "execution.renderedCheckTimeoutSeconds"),
    ({"artifact": {"theme": "dark"}}, "artifact.theme"),
    ({"artifact": {"print": {"default": {"paper": "A4", "margin": "2mm"}}}}, "artifact.print.default.margin"),
    ({"artifact": {"print": {"default": {"paper": "B5", "margin": "20mm"}}}}, "artifact.print.default.paper"),
    ({"report": {"tablePageSize": 5}}, "report"),
    ([], "top level"),
])
def test_invalid_settings_name_the_settings_file_and_the_field(tmp_path, override, field, capsys) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(override), encoding="utf-8")
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del document["manifest"]["metadata"]["obsHtml"]  # The fixture's profile would choose its own paper.
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    destination = tmp_path / "artifact.html"
    with pytest.raises(SystemExit) as exit_info:
        _run(source, destination, "--config", settings)
    assert exit_info.value.code == 2
    _input_error(capsys, settings, field)
    assert not destination.exists()


def test_unreadable_settings_name_the_settings_file(tmp_path, capsys) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{", encoding="utf-8")
    with pytest.raises(SystemExit):
        _run(FIXTURE, "--check", "--config", settings)
    _input_error(capsys, settings, "top level")


def test_identical_output_is_not_rewritten(tmp_path, monkeypatch) -> None:
    destination = tmp_path / "artifact.html"
    arguments = (FIXTURE, destination)
    _run(*arguments)
    writes = []
    original = Path.replace
    monkeypatch.setattr(Path, "replace", lambda self, target: writes.append(target) or original(self, target))
    _run(*arguments)
    assert writes == []


def test_failed_write_preserves_the_previous_output(tmp_path, monkeypatch) -> None:
    destination = tmp_path / "artifact.html"
    destination.write_text("previous", encoding="utf-8")

    def fail(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(SystemExit):
        _run(FIXTURE, destination)
    assert destination.read_text(encoding="utf-8") == "previous"
    assert [path.name for path in tmp_path.iterdir()] == ["artifact.html"]


def test_timings_print_one_line_per_stage(tmp_path, capsys) -> None:
    _run(FIXTURE, tmp_path / "artifact.html", "--timings")
    stages = [line.split()[1] for line in capsys.readouterr().out.splitlines() if line.startswith("Timing:")]
    assert stages == ["render", "figures", "write", "total"]


def test_trusted_runtime_is_embedded_only_when_named(tmp_path) -> None:
    runtime = tmp_path / "runtime.js"
    runtime.write_text("globalThis.trustedFixture = '</script>';", encoding="utf-8")
    plain, trusted = tmp_path / "plain.html", tmp_path / "trusted.html"
    _run(FIXTURE, plain)
    _run(FIXTURE, trusted,
         "--trusted-runtime-bundle", f"fixture-v1={runtime}")
    assert "trusted-application-runtime" not in plain.read_text(encoding="utf-8")
    html = trusted.read_text(encoding="utf-8")
    assert '<meta name="obs-trusted-runtime" content="fixture-v1">' in html
    assert "globalThis.trustedFixture = '<\\/script>';" in html


@pytest.mark.parametrize("bundle", ["no-separator", "Bad=runtime.js", "fixture-v1=runtime.txt",
                                    "fixture-v1=missing.js"])
def test_trusted_runtime_bundles_are_validated(tmp_path, monkeypatch, capsys, bundle) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runtime.txt").write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        _run(FIXTURE, tmp_path / "out.html",
             "--trusted-runtime-bundle", bundle)
    _input_error(capsys, "obs-html", "--trusted-runtime-bundle")


def test_extract_comments_reads_a_returned_artifact(tmp_path, capsys) -> None:
    artifact = tmp_path / "reviewed.html"
    island = {"version": 2, "annotations": [
        {"id": "c1", "target": {"chapter": "intro"}, "text": "Tighten this.", "author": "Ada"}]}
    artifact.write_text('<!doctype html><script id="obs-comments" type="application/json">'
                      f"{json.dumps(island)}</script>", encoding="utf-8")
    _run("--extract-comments", artifact)
    assert "Tighten this." in capsys.readouterr().out
    with pytest.raises(SystemExit):
        _run(FIXTURE, "--extract-comments", artifact)


def test_print_chapter_prints_the_stored_html_by_id(fixture_artifact, capsys) -> None:
    notes = decode_artifact_data(fixture_artifact.read_text(encoding="utf-8"))["notes"]
    stored = next(note["html"] for note in notes if note["slug"] == "intro")
    assert cli.main(["--print-chapter", str(fixture_artifact), "intro"]) == 0
    assert capsys.readouterr().out == stored


def test_print_chapter_finds_a_chapter_by_its_title(fixture_artifact, capsys) -> None:
    cli.main(["--print-chapter", str(fixture_artifact), "intro"])
    by_id = capsys.readouterr().out
    cli.main(["--print-chapter", str(fixture_artifact), "Intro"])
    assert capsys.readouterr().out == by_id


def test_print_chapter_prints_plain_text_one_line_per_block(fixture_artifact, capsys) -> None:
    cli.main(["--print-chapter", str(fixture_artifact), "intro", "--chapter-format", "text"])
    text = capsys.readouterr().out
    assert text.endswith("\n") and "<p" not in text and "</" not in text


def test_an_unknown_chapter_names_it_and_lists_the_available_ids(fixture_artifact, capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run("--print-chapter", fixture_artifact, "missing-chapter")
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert f"\n{fixture_artifact}: --print-chapter: " in f"\n{error}", error
    notes = decode_artifact_data(fixture_artifact.read_text(encoding="utf-8"))["notes"]
    assert "missing-chapter" in error
    assert all(note["slug"] in error for note in notes)


def test_print_chapter_names_an_unreadable_artifact(tmp_path, capsys) -> None:
    with pytest.raises(SystemExit):
        _run("--print-chapter", tmp_path / "absent.html", "intro")
    _input_error(capsys, tmp_path / "absent.html", "HTML")


def test_a_title_two_chapters_share_lists_their_ids(tmp_path, capsys) -> None:
    artifact = tmp_path / "artifact.html"
    notes = [{"slug": "appendix-references", "title": "References", "html": "<p>a</p>"},
             {"slug": "capabilities-references", "title": "References", "html": "<p>b</p>"}]
    artifact.write_text(encode_artifact_data({"notes": notes}, "none"), encoding="utf-8")
    with pytest.raises(SystemExit):
        _run("--print-chapter", artifact, "References")
    error = capsys.readouterr().err
    assert f"\n{artifact}: --print-chapter: " in f"\n{error}", error
    assert "appendix-references" in error and "capabilities-references" in error
