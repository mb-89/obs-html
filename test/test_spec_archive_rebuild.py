"""reproduce.py rebuilds obs's spec, with the adapter's References entry, from the spec's source archive.

Reader: whoever changes reproduce.py or `obs-html --build-own-spec`; input-model.md, "Optional
reproduction archive", owns the behaviour, cli.md, "Building its own specification", the command.

obs's spec names no adapter, so the test adds the References note that stands for the adapter's
specification (REFERENCE_NOTE) to a copy of obs's spec vault and builds that copy with the recorded
command (obs-document --adapter obs-html --execute-commands --embed-source). It extracts the
archive the artifact embeds and checks the steps reproduce.py composes. Their install is faked: the
core's checkout stands for obs at the recorded commit, already installed, so the rebuild step runs
with that checkout in place of the clone and the core's test/offline_obs_document.py in place of
obs-document, which serves remote images without the network. The note's producer fence writes
the run's one build of the adapter's specification (test/conftest.py, ``own_spec``, which
`obs-html --build-own-spec` builds) to the file the entry attaches, in the build and in the
rebuild, so the run builds the specification once. The rebuild runs from the extracted folder,
whose vault holds no generated file, so the file the References entry attaches is the adapter's
specification the producer put there.
"""
import io
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from conftest import CORE_ROOT
from obs_html import reproduce
from obs_html.cli import main as obs_html
from obs_html.source_archive import embedded
from spec_artifact import run, uv

OFFLINE_DOCUMENT = CORE_ROOT / "test" / "offline_obs_document.py"
"""The core's obs-document without the network."""
PRODUCED = "design_output/obs-html-specification.html"
"""What the References note's producer writes, the file its entry attaches."""
OWN_SPEC = "OBS_HTML_OWN_SPEC"
"""The environment variable naming the run's build of the adapter's specification to the producer."""
PRODUCER = (f"python -c \"import os, pathlib, shutil; target = pathlib.Path('{PRODUCED}'); "
            f"target.parent.mkdir(exist_ok=True); shutil.copyfile(os.environ['{OWN_SPEC}'], target)\"")
"""The producer fence: it writes the run's build of the adapter's specification where the entry attaches it."""
REFERENCE_NOTE = f"""---
title: obs-html specification
url: ../../../obs-html/spec/manifest.md
description: "The HTML adapter's own specification, built with the adapter."
accessed: 2026-11-22
---

This note stands for the HTML adapter's specification, which the build writes into the attached
file.

```cmd silent
{PRODUCER}
```

![obs-html specification](../../{PRODUCED})
"""
"""The note in the vault's appendix/references that stands for the adapter's specification."""
ENTRY = "appendix-references-obs-html-specification"
"""The chapter of the References entry that stands for the adapter's specification."""


def _offline(command: list[str], checkout: Path) -> list[str]:
    """The rebuild step's ``command`` with the core's checkout in place of ``checkout``, uv offline and
    the core's offline obs-document in place of obs-document."""
    command = [part.replace(str(checkout), str(CORE_ROOT)) for part in command]
    at = command.index("obs-document")
    return [*command[:2], "--offline", *command[2:at], "python", str(OFFLINE_DOCUMENT), *command[at + 1:]]


@pytest.mark.build
def test_reproduce_rebuilds_obs_spec_from_its_archive_with_the_references_entry(
        tmp_path: Path, own_spec: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv(OWN_SPEC, str(own_spec))
    vault = tmp_path / "spec"
    shutil.copytree(CORE_ROOT / "spec", vault, ignore=shutil.ignore_patterns("design_output"))
    (vault / "appendix" / "references" / "obs-html-specification.md").write_text(REFERENCE_NOTE, encoding="utf-8")
    built = tmp_path / "built" / "spec.html"
    run([uv(), "run", "--offline", "--project", str(CORE_ROOT), "python", str(OFFLINE_DOCUMENT), "--source",
         str(vault / "manifest.md"), "--adapter", "obs-html", "--destination", str(built), "--execute-commands",
         "--embed-source"], CORE_ROOT,
        "building a copy of obs's spec with its source archive")
    here = tmp_path / "extracted"
    with zipfile.ZipFile(io.BytesIO(embedded(built.read_text(encoding="utf-8"), built))) as archive:
        archive.extractall(here)
    assert not (here / "vault" / PRODUCED).exists()
    config = json.loads((here / "build-config.json").read_text(encoding="utf-8"))
    checkout = here / reproduce.CHECKOUT

    steps = reproduce.steps(config, here, config["obs"]["repository"], execute_commands=True)

    assert [step.name for step in steps] == ["clone", "checkout", "install", "rebuild"]
    rebuild = steps[-1]
    assert rebuild.command == ["uv", "run", "--frozen", "--project", str(checkout), *config["command"]]
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    environment.update({name: value.replace(str(checkout), str(CORE_ROOT))
                        for name, value in rebuild.environment.items()})
    result = subprocess.run(_offline(rebuild.command, checkout), cwd=here, env=environment, text=True,
                            encoding="utf-8", capture_output=True, timeout=900)

    assert result.returncode == 0, f"{result.stdout[-2000:]}{result.stderr[-2000:]}"
    assert "<title>obs-html</title>" in (here / "vault" / PRODUCED).read_text(encoding="utf-8")
    destination = here / config["command"][config["command"].index("--destination") + 1]
    capsys.readouterr()
    assert obs_html(["--print-chapter", str(destination), ENTRY, "--chapter-format", "text"]) == 0
    assert f"obs-html specification ({PRODUCED})" in capsys.readouterr().out
