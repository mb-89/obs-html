"""The installed obs-html wheel renders from its own package data, never from the repository tree.

Every browser asset the adapter embeds is package data in its wheel (hatch_build.py builds the
ones that come from a lockfile). The test builds the wheels of obs and obs-html once, installs them
into a fresh virtual environment outside the checkout, with the lockfile's dependencies from uv's
cache, and renders a Document with an equation figure and a plot there, in a Python whose audit hook
records every file it opens or lists inside the checkout. It builds the adapter's own
specification there too (`obs-html --build-own-spec`), every Python process it starts (the core,
which runs the specification's command fences) recording its reads as well. A build that cannot
install a lockfile names the lockfile and the remedy. The installed core draws Mermaid and PlantUML
from its own package data the same way (the core's hatch_build.py).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from conftest import CORE_ROOT, FIXTURE, ROOT
from documents import chapter, document, heading, node

# Runs in the installed environment: argv[1] is the checkout, argv[2] the record of what the
# renderer read inside it, the rest obs-html's arguments.
RENDER = """
import json, os, sys
checkout = os.path.realpath(sys.argv[1])
reads = []
def audit(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.realpath(os.fsdecode(args[0]))
        if path == checkout or path.startswith(checkout + os.sep):
            reads.append(path)
sys.addaudithook(audit)
import obs_html
from obs_html.cli import main
code = main(sys.argv[3:])
reads.append(obs_html.__file__) if obs_html.__file__.startswith(checkout + os.sep) else None
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(reads))
sys.exit(code)
"""


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


def _uv(*arguments: str, cwd: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(["uv", *arguments], cwd=cwd, env=environment, capture_output=True, text=True)
    assert result.returncode == 0, f"uv {' '.join(arguments)}:\n{result.stderr}"


@pytest.fixture(scope="module")
def installed(tmp_path_factory) -> Path:
    """The Python of a fresh virtual environment with the obs and obs-html wheels, built once."""
    if shutil.which("uv") is None:
        pytest.fail("uv is not on PATH; install it (https://docs.astral.sh/uv/) to build the wheels")
    folder = tmp_path_factory.mktemp("wheel")
    environment = {key: value for key, value in os.environ.items() if key not in ("VIRTUAL_ENV", "PYTHONPATH")}
    environment["UV_PROJECT_ENVIRONMENT"] = str(folder / "venv")
    _uv("build", "--all-packages", "--wheel", "--offline", "--out-dir", str(folder / "dist"),
        cwd=CORE_ROOT, environment=environment)
    # The lockfile's dependencies of obs-html, from uv's cache; then the two wheels just built.
    _uv("sync", "--frozen", "--offline", "--no-dev", "--no-install-workspace", "--package", "obs-html",
        cwd=CORE_ROOT, environment=environment)
    python = folder / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _uv("pip", "install", "--offline", "--no-deps", "--python", str(python),
        *map(str, sorted((folder / "dist").glob("*.whl"))), cwd=folder, environment=environment)
    return python


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


def test_the_installed_wheel_embeds_its_packaged_assets_and_reads_nothing_from_the_tree(installed, tmp_path) -> None:
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document("Installed", chapter(
        "one", "One", heading(1, "One"), _figure("equations"), _figure("plot")))), encoding="utf-8")
    reads, output = tmp_path / "reads.json", tmp_path / "out" / "document.html"
    result = subprocess.run([str(installed), "-I", "-c", RENDER, str(CORE_ROOT), str(reads), str(source),
                             str(output)], cwd=tmp_path, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(reads.read_text(encoding="utf-8")) == []
    html = output.read_text(encoding="utf-8")
    pin = json.loads((ROOT / "maths" / "package-lock.json").read_text(encoding="utf-8"))
    version = pin["packages"]["node_modules/mathjs"]["version"]
    maths = _script(html, "maths-script")
    licence, library = maths.split("*/", 1)
    assert f"@version {version}" in licence and "Apache License" in licence and f'"{version}"' in library
    assert "plotly.js" in _script(html, "plotly-script")


# RENDER with the core's build in place of the adapter's render: the rest of argv is obs-document's.
BUILD = RENDER.replace("import obs_html\nfrom obs_html.cli import main", "import obs as obs_html\nfrom obs.document import main")
DIAGRAMS = "# Diagrams\n\n```mermaid\ngraph TD\n  Draft --> Done\n```\n\n```plantuml\n@startuml\nAuthor -> Reviewer\n@enduml\n```\n"


def test_the_installed_core_draws_mermaid_and_plantuml_from_its_package_data(installed, tmp_path) -> None:
    (tmp_path / "manifest.md").write_text("- [[chapter]]\n", encoding="utf-8")
    (tmp_path / "chapter.md").write_text(DIAGRAMS, encoding="utf-8")
    reads, output = tmp_path / "reads.json", tmp_path / "document.json"
    result = subprocess.run([str(installed), "-I", "-c", BUILD, str(CORE_ROOT), str(reads), "--source",
                             str(tmp_path / "manifest.md"), "--document", str(output)],
                            cwd=tmp_path, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(reads.read_text(encoding="utf-8")) == []
    figures = [item for part in json.loads(output.read_text(encoding="utf-8"))["chapters"]
               for item in part["content"] if item["type"] == "figures"]
    assert [figure["attrs"]["kind"] for figure in figures] == ["mermaid", "plantuml"]
    mermaid, plantuml = (figure["children"][0]["attrs"]["svg"] for figure in figures)
    assert mermaid.startswith("<svg") and "Draft" in mermaid
    assert plantuml.startswith("<svg") and "Reviewer" in plantuml


def test_the_installed_wheel_builds_its_own_spec_and_reads_nothing_from_the_tree(installed, tmp_path) -> None:
    (tmp_path / "audit").mkdir()
    (tmp_path / "audit" / "sitecustomize.py").write_text(AUDIT, encoding="utf-8")
    reads, output = tmp_path / "reads.txt", tmp_path / "out" / "obs-html-specification.html"
    reads.touch()
    environment = {key: value for key, value in os.environ.items() if key not in ("VIRTUAL_ENV", "UV_PROJECT")}
    environment.update(PYTHONPATH=str(tmp_path / "audit"), AUDIT_CHECKOUT=str(CORE_ROOT), AUDIT_RECORD=str(reads))
    result = subprocess.run([str(installed), "-c", "import sys; from obs_html.cli import main; "
                             "sys.exit(main(sys.argv[1:]))", "--build-own-spec", str(output)],
                            cwd=tmp_path, env=environment, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert reads.read_text(encoding="utf-8").splitlines() == []
    assert "<title>obs-html</title>" in output.read_text(encoding="utf-8")
    # The CLI note's command fence ran in the installed environment and shows the interim's help.
    chapter = subprocess.run([str(installed), "-I", "-c", "import sys; from obs_html.cli import main; "
                              "sys.exit(main(sys.argv[1:]))", "--print-chapter", str(output), "cli",
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


def test_a_build_without_npm_names_the_lockfile_and_the_remedy(hook, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook.shutil, "which", lambda name: None)

    with pytest.raises(hook.BuildError) as failure:
        hook.npm_ci(ROOT / "maths", tmp_path)

    assert (failure.value.source, failure.value.field) == (ROOT / "maths" / "package-lock.json", "npm ci")
    assert "Node.js" in failure.value.remedy


def test_a_failed_npm_ci_names_the_lockfile_and_what_npm_said(hook, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/fake/bin/npm")

    def npm(command, cwd, **_):
        return subprocess.CompletedProcess(command, 1, stdout="npm said why\n")

    with pytest.raises(hook.BuildError) as failure:
        hook.npm_ci(ROOT / "maths", tmp_path, run=npm)

    assert (failure.value.source, failure.value.field) == (ROOT / "maths" / "package-lock.json", "npm ci")
    assert "npm said why" in str(failure.value)
