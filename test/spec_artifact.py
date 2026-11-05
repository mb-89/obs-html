"""obs's spec as this adapter renders it, built once per run without the network.

Reader: a test that reads the spec artifact (the parity gate, the content-model check).

The core of this repository builds the spec Document (its capability reference first) through
the core's test/offline_obs_document.py, whose fake remote fetcher keeps every subprocess off the
network; this adapter renders it with the spec's commands executed.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import CORE_ROOT, built_once
from obs_html.cli import main as obs_html

# The core's obs-document with the core's fake remote fetcher: no subprocess reaches the network.
OFFLINE_DOCUMENT = CORE_ROOT / "test" / "offline_obs_document.py"


def run(command: list[str], cwd: Path, what: str) -> None:
    """Run a build step; on failure name the step, its command and its output."""
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, encoding="utf-8",
                            capture_output=True, timeout=900)
    if result.returncode:
        pytest.fail(f"test/spec_artifact.py: {what} failed: {' '.join(command)} (in {cwd})\n"
                    f"{result.stdout[-2000:]}{result.stderr[-2000:]}", pytrace=False)


def uv() -> str:
    found = shutil.which("uv")
    if not found:
        pytest.fail("test/spec_artifact.py: uv not found on PATH. Remedy: install uv "
                    "(https://docs.astral.sh/uv/).", pytrace=False)
    return found


def spec_artifact(tmp_path_factory) -> Path:
    """The spec artifact, built once per run and shared by every xdist worker."""
    core = CORE_ROOT

    def build(folder: Path) -> None:
        capabilities, document = folder / "capabilities.json", folder / "spec.json"
        run([uv(), "run", "--offline", "--project", str(core), "python", "-m", "obs.capabilities",
             "--notes", str(core / "spec" / "capabilities"), "--output", str(capabilities)],
            core, "building the capability reference with the core")
        run([uv(), "run", "--offline", "--project", str(core), "python", str(OFFLINE_DOCUMENT),
             "--document", str(document), "--source", str(core / "spec" / "manifest.md"),
             "--capability-reference", str(capabilities)],
            core, "building obs's spec Document with the core, without the network")
        assert obs_html([str(document), str(folder / "adapter.html"), "--execute-commands",
                         "--command-root", str(core / "spec")]) == 0, \
            "test/spec_artifact.py: obs-html could not render obs's spec Document"

    return built_once(tmp_path_factory, "spec-artifact", build) / "adapter.html"
