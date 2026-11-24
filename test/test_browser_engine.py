"""The browser tests' engine (test/suite.py's HEADLESS_SHELL, test/conftest.py's headless_shell): the
headless shell at the revision the installed Playwright pins, installed where it is missing, or a
failure that names where it looked and the remedy.

Reader: whoever changes how the browser tests find their browsers.
"""
import json
import subprocess
from pathlib import Path

import pytest

from conftest import BrowserEngineError, headless_shell, install_pinned_shell, pinned_revision, suite


def install(browsers: Path, revision: int | str) -> Path:
    revision_folder, platform, executable = suite.HEADLESS_SHELL
    path = browsers / revision_folder.replace("*", str(revision)) / platform.replace("*", "linux64") / executable
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    return path


def test_the_pinned_revision_is_the_one_playwrights_browsers_json_names(tmp_path: Path) -> None:
    (tmp_path / "browsers.json").write_text(json.dumps({"browsers": [
        {"name": "chromium", "revision": "1300"},
        {"name": "chromium-headless-shell", "revision": "1248"},
    ]}), encoding="utf-8")

    assert pinned_revision(tmp_path) == "1248"


def test_the_pinned_headless_shell_is_the_engine_beside_a_newer_one(tmp_path: Path) -> None:
    """A Claude Code cloud container holds a newer revision than the pinned Playwright's; the tests
    run on the pinned one, as CI does, never on the newest installed."""
    pinned = install(tmp_path, 1248)
    install(tmp_path, 1243)
    install(tmp_path, 1300)
    (tmp_path / "chromium-1248").mkdir()  # full Chromium is never the bulk's engine

    assert headless_shell(tmp_path, "1248") == str(pinned)


def test_a_missing_headless_shell_names_the_revision_the_folder_and_the_remedy(tmp_path: Path) -> None:
    install(tmp_path, 1243)
    with pytest.raises(BrowserEngineError) as failure:
        headless_shell(tmp_path, "1248")

    message = str(failure.value)
    assert message.startswith("test/conftest.py:") and "HEADLESS_SHELL" in message
    assert "1248" in message and str(tmp_path) in message
    assert " ".join(suite.BROWSER_INSTALL) in message


def test_a_missing_pinned_shell_is_installed_and_a_present_one_is_not(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("conftest.pinned_revision", lambda: "1248")
    install(tmp_path, 1243)
    calls = []

    def run(command, **_options):
        calls.append(command)
        install(tmp_path, 1248)
        return subprocess.CompletedProcess(command, 0, stdout="")

    assert install_pinned_shell(tmp_path, run) is True
    assert calls == [suite.BROWSER_INSTALL]
    assert install_pinned_shell(tmp_path, run) is False
    assert len(calls) == 1


def test_a_failed_install_names_the_command_and_its_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("conftest.pinned_revision", lambda: "1248")

    def run(command, **_options):
        return subprocess.CompletedProcess(command, 1, stdout="no network")

    with pytest.raises(suite.InstallError) as failure:
        install_pinned_shell(tmp_path, run)
    assert "exit code 1" in str(failure.value) and "no network" in str(failure.value)


def test_playwrights_folder_is_the_one_its_variable_names(tmp_path: Path) -> None:
    assert suite.playwright_browsers({"PLAYWRIGHT_BROWSERS_PATH": str(tmp_path)}) == tmp_path
