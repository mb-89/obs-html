import json
import re
from pathlib import Path

import pytest

from conftest import FIXTURE
from obs_html import cli, exposure
from obs_html.artifact_data import decode_artifact_data, encode_artifact_data


def _with_command(tmp_path: Path, attrs: dict[str, object]) -> Path:
    """The fixture Document with its rendering command node's attributes replaced."""
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    text = json.dumps(document).replace(
        json.dumps({"source": "echo derived\n", "output": "derived\n"}), json.dumps(attrs))
    source = tmp_path / "document.json"
    source.write_text(text, encoding="utf-8")
    return source


def _command_output(destination: Path) -> str:
    notes = decode_artifact_data(destination.read_text(encoding="utf-8"))["notes"]
    return "".join(note["html"] for note in notes if "command-output" in note["html"])


def test_a_command_node_renders_the_output_the_core_captured_without_running_it(tmp_path) -> None:
    destination = tmp_path / "artifact.html"
    source = _with_command(tmp_path, {"source": "exit 7\n", "output": "<b>captured</b>\n"})

    assert cli.main([str(source), str(destination)]) == 0

    output = _command_output(destination)
    assert '<pre class="command-output">&lt;b&gt;captured&lt;/b&gt;\n</pre>' in output
    assert output.count('class="command-output"') == 1  # The fixture's silent producer renders nothing.


def test_a_command_node_without_output_fails_naming_the_node_and_the_remedy(tmp_path, capsys) -> None:
    destination = tmp_path / "artifact.html"
    source = _with_command(tmp_path, {"source": "echo derived\n"})

    with pytest.raises(SystemExit) as exit_info:
        cli.main([str(source), str(destination)])

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "command-fences node" in error and "attrs.output" in error
    assert "obs-document --execute-commands" in error
    assert not destination.exists()


def test_a_artifact_exposing_the_build_machine_fails_naming_where_and_the_remedy(
        tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home" / "builder"
    home.mkdir(parents=True)
    (tmp_path / "vault").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    text = FIXTURE.read_text(encoding="utf-8")
    leaked = json.dumps(f"see {home / 'notes'}")[1:-1]
    source = tmp_path / "document.json"
    source.write_text(text.replace("Intro", leaked, 1), encoding="utf-8")
    destination = tmp_path / "artifact.html"
    with pytest.raises(SystemExit) as exit_info:
        cli.main([str(source), str(destination)])
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert f"the build machine's home folder '{home}'" in error
    assert re.search(r"in artifact-data notes\[\d+\]\.title\. Remedy: ", error)
    assert not destination.exists()


def test_the_exposure_check_finds_the_user_name(monkeypatch) -> None:
    monkeypatch.setattr(exposure, "_user_name", lambda: "builder")
    artifact = encode_artifact_data({"notes": [{"html": "<p>/mnt/builder/a.md</p>"}]})
    with pytest.raises(exposure.ExposureError, match=r"user name 'builder' .* artifact-data notes\[0\]\.html"):
        exposure.check_artifact(artifact)
    with pytest.raises(exposure.ExposureError, match=r"user name 'builder' .* HTML line 1"):
        exposure.check_artifact("<p>/mnt/builder/x</p>")
    exposure.check_artifact("<p>builder https://example.com/builder/x</p>")
