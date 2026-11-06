"""The browser tests' engine (test/conftest.py, HEADLESS_SHELL): the newest headless shell
Playwright installed, or a failure that names where it looked and the remedy.

Reader: whoever changes how the browser tests find their browsers.
"""
from pathlib import Path

import pytest

from conftest import HEADLESS_SHELL, HEADLESS_SHELL_INSTALL, BrowserEngineError, headless_shell, playwright_browsers


def install(browsers: Path, revision: int) -> Path:
    revision_folder, platform, executable = HEADLESS_SHELL
    path = browsers / revision_folder.replace("*", str(revision)) / platform.replace("*", "linux64") / executable
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    return path


def test_the_newest_installed_headless_shell_is_the_engine(tmp_path: Path) -> None:
    install(tmp_path, 999)
    newest = install(tmp_path, 1243)
    (tmp_path / "chromium-1300").mkdir()  # full Chromium is never the bulk's engine

    assert headless_shell(tmp_path) == str(newest)


def test_a_missing_headless_shell_names_the_folder_and_the_remedy(tmp_path: Path) -> None:
    with pytest.raises(BrowserEngineError) as failure:
        headless_shell(tmp_path)

    message = str(failure.value)
    assert message.startswith("test/conftest.py: HEADLESS_SHELL")
    assert str(tmp_path) in message
    assert HEADLESS_SHELL_INSTALL in message


def test_playwrights_folder_is_the_one_its_variable_names(tmp_path: Path) -> None:
    assert playwright_browsers({"PLAYWRIGHT_BROWSERS_PATH": str(tmp_path)}) == tmp_path
