"""The installed obs-html wheel renders from its own package data, never from the repository tree.

Every browser asset the adapter embeds is package data in its wheel (hatch_build.py builds the
ones that come from a lockfile). The tests use the wheels of obs and obs-html built once per run
and installed into a fresh virtual environment outside the checkout (conftest.py,
``installed_wheels``). One audit, a sitecustomize module on PYTHONPATH (AUDIT), records every file
that any Python process of that environment opens or lists inside the checkout: the render of a
Document with an equation figure and a plot, and the adapter's own specification
(`obs-html --build-own-spec`) with the core, which runs the specification's command fences. A build that cannot
install a lockfile names the lockfile and the remedy. The installed core draws Mermaid and PlantUML
from its own package data the same way (the core's hatch_build.py).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

from conftest import CORE_ROOT, FIXTURE, ROOT
from documents import chapter, document, heading, node

# The audit of every Python process of the installed environment: a sitecustomize module on
# PYTHONPATH appends to the file AUDIT_RECORD names each path inside AUDIT_CHECKOUT it opens or lists.
AUDIT = """
import os, sys
checkout = os.path.realpath(os.environ["AUDIT_CHECKOUT"])
def audit(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.realpath(os.fsdecode(args[0]))
        if path == checkout or path.startswith(checkout + os.sep):
            with open(os.environ["AUDIT_RECORD"], "a", encoding="utf-8") as record:
                record.write(path + "\\n")
sys.addaudithook(audit)
"""


def audited(installed: Path, tmp_path: Path, code: str, *arguments: str) -> tuple[subprocess.CompletedProcess, list[str]]:
    """Run ``code`` with ``arguments`` in the installed environment with AUDIT on PYTHONPATH, so every
    Python process it starts records its reads too; the result and each path read inside the checkout."""
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    (audit / "sitecustomize.py").write_text(AUDIT, encoding="utf-8")
    reads = tmp_path / "reads.txt"
    reads.write_text("", encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if key not in ("VIRTUAL_ENV", "UV_PROJECT")}
    environment.update(PYTHONPATH=str(audit), AUDIT_CHECKOUT=str(CORE_ROOT), AUDIT_RECORD=str(reads))
    result = subprocess.run([str(installed), "-c", code, *arguments], cwd=tmp_path, env=environment,
                            capture_output=True, text=True)
    return result, reads.read_text(encoding="utf-8").splitlines()


ADAPTER = "import sys; from obs_html.cli import main; sys.exit(main(sys.argv[1:]))"
CORE = "import sys; from obs.document import main; sys.exit(main(sys.argv[1:]))"


def test_the_audit_records_what_a_process_and_its_children_read_inside_the_checkout(installed_wheels, tmp_path) -> None:
    """The audit is not vacuous: a read of the checkout, in the process or in a Python it starts, is recorded."""
    read = f"open({str(CORE_ROOT / 'README.md')!r}).read()"
    result, reads = audited(installed_wheels, tmp_path, f"import subprocess, sys; {read}; "
                            f"subprocess.run([sys.executable, '-c', {read!r}], check=True)")

    assert result.returncode == 0, result.stderr
    assert reads == [str((CORE_ROOT / "README.md").resolve())] * 2


def _figure(kind: str) -> dict:
    """The fixture Document's first figure of ``kind`` (figures.py, FIGURE_KINDS)."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    body = next(item["children"][0]["attrs"] for part in fixture["chapters"] for item in part["content"]
                if item["type"] == "figures" and item["attrs"]["kind"] == kind)
    return {"type": "figures", "attrs": {"kind": kind}, "children": [node(kind, **body)]}


def _script(html: str, element: str) -> str:
    """The text of the artifact's script element with id ``element``."""
    found = re.search(rf'<script id="{element}"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert found, f"the artifact has no script element {element}"
    return found.group(1)


def test_the_installed_wheel_embeds_its_packaged_assets_and_reads_nothing_from_the_tree(installed_wheels, tmp_path) -> None:
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document("Installed", chapter(
        "one", "One", heading(1, "One"), _figure("equations"), _figure("plot")))), encoding="utf-8")
    output = tmp_path / "out" / "document.html"
    result, reads = audited(installed_wheels, tmp_path, ADAPTER, str(source), str(output))

    assert result.returncode == 0, result.stderr
    assert reads == []
    html = output.read_text(encoding="utf-8")
    pin = json.loads((ROOT / "maths" / "package-lock.json").read_text(encoding="utf-8"))
    version = pin["packages"]["node_modules/mathjs"]["version"]
    maths = _script(html, "maths-script")
    licence, library = maths.split("*/", 1)
    assert f"@version {version}" in licence and "Apache License" in licence and f'"{version}"' in library
    assert "plotly.js" in _script(html, "plotly-script")


DIAGRAMS = "# Diagrams\n\n```mermaid\ngraph TD\n  Draft --> Done\n```\n\n```plantuml\n@startuml\nAuthor -> Reviewer\n@enduml\n```\n"


def test_the_installed_core_draws_mermaid_and_plantuml_from_its_package_data(installed_wheels, tmp_path) -> None:
    (tmp_path / "manifest.md").write_text("- [[chapter]]\n", encoding="utf-8")
    (tmp_path / "chapter.md").write_text(DIAGRAMS, encoding="utf-8")
    output = tmp_path / "document.json"
    result, reads = audited(installed_wheels, tmp_path, CORE, "--source", str(tmp_path / "manifest.md"),
                            "--document", str(output))

    assert result.returncode == 0, result.stderr
    assert reads == []
    figures = [item for part in json.loads(output.read_text(encoding="utf-8"))["chapters"]
               for item in part["content"] if item["type"] == "figures"]
    assert [figure["attrs"]["kind"] for figure in figures] == ["mermaid", "plantuml"]
    mermaid, plantuml = (figure["children"][0]["attrs"]["svg"] for figure in figures)
    assert mermaid.startswith("<svg") and "Draft" in mermaid
    assert plantuml.startswith("<svg") and "Reviewer" in plantuml


def test_the_installed_wheel_builds_its_own_spec_and_reads_nothing_from_the_tree(installed_wheels, tmp_path) -> None:
    output = tmp_path / "out" / "obs-html-specification.html"
    result, reads = audited(installed_wheels, tmp_path, ADAPTER, "--build-own-spec", str(output))

    assert result.returncode == 0, result.stderr
    assert reads == []
    assert "<title>obs-html</title>" in output.read_text(encoding="utf-8")
    # The CLI note's command fence ran in the installed environment and shows the interim's help.
    chapter = subprocess.run([str(installed_wheels), "-I", "-c", ADAPTER, "--print-chapter", str(output), "cli",
                              "--chapter-format", "text"], cwd=tmp_path, capture_output=True, text=True)
    assert chapter.returncode == 0, chapter.stderr
    assert "usage: obs-html-interim" in chapter.stdout


@pytest.fixture
def hook(monkeypatch):
    """hatch_build.py, imported without hatchling, which only the package's build environment holds."""
    interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")
    interface.BuildHookInterface = object
    monkeypatch.setitem(sys.modules, "hatchling.builders.hooks.plugin.interface", interface)
    spec = importlib.util.spec_from_file_location("obs_html_build_hook", ROOT / "hatch_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MATHS_LOCKFILE = ROOT / "maths" / "package-lock.json"


def test_a_build_without_npm_names_the_lockfile_and_the_remedy(hook, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook.shutil, "which", lambda name: None)

    with pytest.raises(hook.BuildError) as failure:
        hook.maths(ROOT, tmp_path, tmp_path)

    assert (failure.value.source, failure.value.field) == (MATHS_LOCKFILE, "npm pack")
    assert "Node.js" in failure.value.remedy


def test_a_failed_npm_pack_names_the_lockfile_and_what_npm_said(hook, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/fake/bin/npm")
    commands = []

    def npm(command, cwd, **_):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="npm said why\n")

    with pytest.raises(hook.BuildError) as failure:
        hook.pinned_files(ROOT / "maths", [f"mathjs/{path}" for path in hook.MATHS_FILES.values()], tmp_path, run=npm)

    assert (failure.value.source, failure.value.field) == (MATHS_LOCKFILE, "npm pack")
    assert "npm said why" in str(failure.value)
    # Only the pinned mathjs tarball, not its dependencies: npm ci installed them all.
    version = json.loads(MATHS_LOCKFILE.read_text(encoding="utf-8"))["packages"]["node_modules/mathjs"]["version"]
    assert [argument for argument in commands[0] if "@" in argument] == [f"mathjs@{version}"]


def test_a_tarball_that_is_not_the_pinned_one_names_its_integrity(hook, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/fake/bin/npm")

    def npm(command, cwd, **_):
        (Path(command[command.index("--pack-destination") + 1]) / "mathjs.tgz").write_bytes(b"not it")
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([{"filename": "mathjs.tgz"}]), stderr="")

    with pytest.raises(hook.BuildError) as failure:
        hook.pinned_files(ROOT / "maths", ["mathjs/LICENSE"], tmp_path, run=npm)

    assert (failure.value.source, failure.value.field) == (MATHS_LOCKFILE, "packages.node_modules/mathjs.integrity")
