import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURE, ROOT
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data


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
    diagnostics = json.loads(FIXTURE.read_text(encoding="utf-8"))["diagnostics"]
    assert diagnostics and all(f"{item['level'].title()}: {item['message']}" in completed.stderr
                               for item in diagnostics)
    assert completed.stdout == f"Generated {destination.resolve()}.\n"
    notes = decode_artifact_data(destination.read_text(encoding="utf-8"))["notes"]
    assert any('<pre class="command-output">derived' in note["html"] for note in notes)
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
