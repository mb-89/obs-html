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
                   "--export-pdf", "--output", "--check-rendered", "--timings", "Exit status"):
        assert option in output


def test_installed_command_renders_through_the_adapter_contract(tmp_path) -> None:
    destination = tmp_path / "out" / "artifact.html"
    completed = subprocess.run(
        [sys.executable, "-m", "obs_html.cli", FIXTURE, destination],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Warning: Fixture diagnostic." in completed.stderr
    assert completed.stdout == f"Generated {destination.resolve()}.\n"
    notes = decode_artifact_data(destination.read_text(encoding="utf-8"))["notes"]
    assert any('<pre class="command-output">derived' in note["html"] for note in notes)
    assert not (tmp_path / "produced.txt").exists()  # Silent producers run in the core, before conversion.


def test_check_renders_without_output(tmp_path, capsys) -> None:
    _run(FIXTURE, "--check")
    assert "no output written" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("arguments, message", [
    ([FIXTURE, "x.html", "--check"], "--check cannot be combined"),
    ([FIXTURE], "DESTINATION is required"),
    ([FIXTURE, "x.html", "--execute-commands"], "unrecognized arguments: --execute-commands"),
    ([FIXTURE, "x.html", "--output", "x.pdf"], "--output is only used with --export-pdf"),
    (["--export-pdf", "a.html"], "requires --output file.pdf"),
    (["--export-pdf", "a.html", "--output", "a.html"], "requires --output file.pdf"),
    (["--check-rendered", "a.html", FIXTURE], "separate operations"),
    ([FIXTURE, FIXTURE], "must not overwrite"),
])
def test_invalid_option_combinations_fail(arguments, message, capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run(*arguments)
    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err


def test_settings_override_merges_over_the_packaged_settings(tmp_path, capsys) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"artifact": {"print": {"paperSizes": {
        "Letter": {"widthMillimeters": 200, "heightMillimeters": 250}}}}}), encoding="utf-8")
    destination = tmp_path / "artifact.html"
    _run(FIXTURE, destination, "--config", settings)
    paper = decode_artifact_data(destination.read_text(encoding="utf-8"))["paper"]
    assert paper == {"widthMillimeters": 200, "heightMillimeters": 250, "marginMillimeters": 15.0}


@pytest.mark.parametrize("override, message", [
    ({"execution": {"renderedCheckTimeoutSeconds": 0}}, "execution.renderedCheckTimeoutSeconds"),
    ({"artifact": {"theme": "dark"}}, "Additional properties"),
    ({"artifact": {"print": {"default": {"paper": "A4", "margin": "2mm"}}}}, "out of range"),
    ({"artifact": {"print": {"default": {"paper": "B5", "margin": "20mm"}}}}, "must be one of"),
])
def test_invalid_settings_fail(tmp_path, override, message, capsys) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(override), encoding="utf-8")
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del document["manifest"]["metadata"]["obsHtml"]  # The fixture's profile would choose its own paper.
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SystemExit):
        _run(source, "--check", "--config", settings)
    assert message in capsys.readouterr().err


def test_an_old_report_settings_key_names_the_new_key_and_the_file(tmp_path, capsys) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"report": {"tablePageSize": 5}}), encoding="utf-8")
    destination = tmp_path / "artifact.html"
    with pytest.raises(SystemExit) as exit_info:
        _run(FIXTURE, destination, "--config", settings)
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert f"{settings}: settings key 'report' was renamed to 'artifact'" in error
    assert "rename the key in that file" in error
    assert not destination.exists()


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


@pytest.mark.parametrize("bundle, message", [
    ("no-separator", "ID=PATH"), ("Bad=runtime.js", "ID=PATH"),
    ("fixture-v1=runtime.txt", "regular .js file"), ("fixture-v1=missing.js", "regular .js file"),
])
def test_trusted_runtime_bundles_are_validated(tmp_path, monkeypatch, capsys, bundle, message) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runtime.txt").write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        _run(FIXTURE, tmp_path / "out.html",
             "--trusted-runtime-bundle", bundle)
    assert message in capsys.readouterr().err


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
