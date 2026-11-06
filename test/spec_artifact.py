"""obs's spec as this adapter renders it, built once per run without the network.

Reader: a test that reads the spec artifact (the parity gate, the content-model check).

The spec's Document is the run's one shared build, which the core's test/spec_build.py owns
(it builds the capability reference first and runs the spec's commands offline); this adapter
renders that Document.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import CORE_ROOT, built_once, spec_build
from obs_html.cli import main as obs_html

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
    """The spec artifact, rendered once per run from the shared Document and shared by every xdist worker."""
    document = spec_build.built(spec_build.base(tmp_path_factory), "document") / spec_build.DOCUMENT

    def build(folder: Path) -> None:
        assert obs_html([str(document), str(folder / "adapter.html")]) == 0, \
            "test/spec_artifact.py: obs-html could not render obs's spec Document"

    return built_once(tmp_path_factory, "spec-artifact", build) / "adapter.html"
