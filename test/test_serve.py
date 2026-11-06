"""obs-html serve: the local answers sink (spec/cli.md, Serving answers; spec/capabilities/answers.md).

The browser test of the page posting to it is test_answers_browser.py; these tests post as a page
would, over loopback only, and every wait has a timeout (test/serving.py).
"""
import json
import socket
from pathlib import Path
from urllib.parse import urlsplit

import pytest

import serving
from obs_html.config import load_config

SOURCE = "obs-html serve"


def _artifact(tmp_path: Path) -> Path:
    artifact = tmp_path / "artifact.html"
    artifact.write_text("<!doctype html><title>Artifact</title>", encoding="utf-8")
    (tmp_path / "beside.txt").write_text("beside", encoding="utf-8")
    return artifact


def _input_error(stderr: str, field: str) -> None:
    """An error names where it comes from: ``obs-html serve: <field>: ...``."""
    assert f"\n{SOURCE}: {field}: " in f"\n{stderr}", stderr


def test_wait_writes_answers_json_beside_the_artifact_and_prints_the_payload(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    served = serving.started(artifact, "--wait", "--timeout", serving.WAIT)
    try:
        address = urlsplit(served.url)
        assert (address.scheme, address.hostname) == ("http", "127.0.0.1")
        assert address.path == "/artifact.html" and "obs-answers=" in address.query
        payload = {"verdicts": [{"id": "one", "verdict": "bless"}], "note": "Grüße"}
        status, answer = serving.post(served.url, json.dumps(payload).encode("utf-8"))
        assert (status, answer) == (200, {"written": "answers.json"})
        code, out, err = served.finished()
    finally:
        served.stop()
    assert code == 0, err
    assert json.loads(out.strip().splitlines()[-1]) == payload
    assert json.loads((tmp_path / "answers.json").read_text(encoding="utf-8")) == payload
    assert sorted(path.name for path in tmp_path.iterdir()) == ["answers.json", "artifact.html", "beside.txt"]


def test_it_serves_the_artifact_and_the_files_beside_it_and_refuses_a_post_without_its_token(tmp_path: Path) -> None:
    served = serving.started(_artifact(tmp_path), "--wait", "--timeout", serving.WAIT)
    try:
        origin = served.url.split("/artifact.html")[0]
        with serving.OPENER.open(served.url, timeout=serving.WAIT) as response:
            assert b"<title>Artifact</title>" in response.read()
        with serving.OPENER.open(f"{origin}/beside.txt", timeout=serving.WAIT) as response:
            assert response.read() == b"beside"
        status, answer = serving.post(f"{origin}/artifact.html", b"{}")
        assert status == 403 and answer["error"].startswith(f"{SOURCE}: obs-answers: ")
        status, _ = serving.post(served.url, b"{}")
        assert status == 200
        assert served.finished()[0] == 0
    finally:
        served.stop()


@pytest.mark.parametrize("body, content_type, field", [
    (b"not json", "application/json", "body"),
    (b"[1, 2]", "application/json", "body"),
    (b"\xff\xfe", "application/json", "body"),
    (b"{}", "text/plain", "Content-Type"),
], ids=["not-json", "not-an-object", "not-utf-8", "not-json-type"])
def test_a_malformed_payload_is_refused_naming_its_field_and_the_server_keeps_waiting(
        tmp_path: Path, body: bytes, content_type: str, field: str) -> None:
    served = serving.started(_artifact(tmp_path), "--wait", "--timeout", serving.WAIT)
    try:
        status, answer = serving.post(served.url, body, content_type)
        assert status in {400, 415}
        assert answer["error"].startswith(f"{SOURCE}: {field}: "), answer
        assert not (tmp_path / "answers.json").exists()
        assert serving.post(served.url, b'{"ok": true}')[0] == 200
        code, out, err = served.finished()
    finally:
        served.stop()
    assert code == 0
    # The refusal is a warning on stderr too, where the person waiting reads it.
    assert f"\nWarning: {SOURCE}: {field}: " in f"\n{err}", err
    assert json.loads(out.strip().splitlines()[-1]) == {"ok": True}


def test_a_payload_over_the_settings_limit_is_refused(tmp_path: Path) -> None:
    limit = load_config().serve_answers_max_bytes
    served = serving.started(_artifact(tmp_path), "--wait", "--timeout", serving.WAIT)
    try:
        status, answer = serving.post(served.url, b'{"a": "' + b"x" * limit + b'"}')
        assert status == 413
        assert answer["error"].startswith(f"{SOURCE}: body: ") and "execution.serveAnswersMaxBytes" in answer["error"]
    finally:
        served.stop()


def test_the_wait_times_out_naming_the_option_and_writing_nothing(tmp_path: Path) -> None:
    completed = serving.run(_artifact(tmp_path), "--wait", "--timeout", "0.2")
    assert completed.returncode == 2
    _input_error(completed.stderr, "--timeout")
    assert completed.stdout.startswith("http://127.0.0.1:")
    assert not (tmp_path / "answers.json").exists()


def test_a_port_in_use_names_the_option(tmp_path: Path) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        completed = serving.run(_artifact(tmp_path), "--port", taken.getsockname()[1], "--wait", "--timeout", "1")
    assert completed.returncode == 2
    _input_error(completed.stderr, "--port")
    assert completed.stdout == ""


@pytest.mark.parametrize("arguments, field", [
    (["missing.html"], "ARTIFACT"),
    (["{artifact}", "--timeout", "5"], "--timeout"),
    (["{artifact}", "--wait", "--timeout", "0"], "--timeout"),
    (["{artifact}", "--port", "70000"], "--port"),
], ids=["missing-artifact", "timeout-without-wait", "zero-timeout", "port-out-of-range"])
def test_invalid_arguments_name_their_field(tmp_path: Path, arguments: list[str], field: str) -> None:
    artifact = _artifact(tmp_path)
    completed = serving.run(*(str(artifact) if item == "{artifact}" else item for item in arguments))
    assert completed.returncode == 2
    _input_error(completed.stderr, field)


def test_the_serve_help_names_its_options() -> None:
    completed = serving.run("--help")
    assert completed.returncode == 0
    for option in ("ARTIFACT", "--port", "--wait", "--timeout", "answers.json", "127.0.0.1"):
        assert option in completed.stdout
