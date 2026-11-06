"""The build hook of the adapter's package: it writes the browser assets built from lockfiles and
copies the adapter's specification into the package.

Reader: whoever changes how the adapter is built or what its package ships.

Each build of the `obs-html` distribution, editable (`uv sync`) or not, fills every folder that
PACKAGED names inside `src/obs_html` and ships its files as package data; the renderer and
`obs-html --build-own-spec` read them through `importlib.resources`. The folders are generated, so they are ignored and never edited;
`[tool.uv] cache-keys` in pyproject.toml makes uv build again when the hook or a lockfile changes.
spec/architecture.md, Packaged browser assets, owns the design.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

PACKAGE = Path("src") / "obs_html"
MATHS = Path("maths")
SPEC = Path("spec")
# The maths library's files the renderer embeds, by their path in the installed mathjs package.
MATHS_FILES = {"math.js": "lib/browser/math.js", "math.js.LICENSE.txt": "lib/browser/math.js.LICENSE.txt",
               "LICENSE": "LICENSE"}


class BuildError(Exception):
    """A packaged folder could not be built: ``source`` is its input, ``remedy`` how to fix it."""

    def __init__(self, source: Path, field: str, problem: str, remedy: str):
        self.source, self.field, self.remedy = source, field, remedy
        super().__init__(f"obs-html build (hatch_build.py): {source}: {field}: {problem}. Remedy: {remedy}.")


def npm_ci(package: Path, work: Path, run=subprocess.run) -> Path:
    """Install the npm package folder ``package`` from its lockfile into ``work``; its node_modules."""
    lockfile = package / "package-lock.json"
    remedy = f"install Node.js and check that npm reaches its registry, then build again; {lockfile} pins it"
    npm = shutil.which("npm")
    if npm is None:
        raise BuildError(lockfile, "npm ci", "npm is not on PATH", remedy)
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(package / name, work / name)
    result = run([npm, "ci", "--ignore-scripts", "--prefer-offline", "--no-audit", "--no-fund"], cwd=work,
                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise BuildError(lockfile, "npm ci", f"failed (exit code {result.returncode}):\n{result.stdout}", remedy)
    return work / "node_modules"


def maths(root: Path, work: Path, folder: Path) -> None:
    """The maths library, math.js, with its licences, from its lockfile ``maths/package-lock.json``."""
    installed = npm_ci(root / MATHS, work) / "mathjs"
    for name, path in MATHS_FILES.items():
        shutil.copy2(installed / path, folder / name)


def spec(root: Path, work: Path, folder: Path) -> None:
    """The adapter's specification vault, ``spec/``, without hidden files, which obs-html --build-own-spec builds."""
    shutil.copytree(root / SPEC, folder, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".*", "__pycache__"))


# Each generated folder of the package, relative to PACKAGE, and what fills it:
# fill(checkout root, an empty work folder, an empty folder to fill).
PACKAGED: dict[str, Callable[[Path, Path, Path], None]] = {"vendor/maths": maths, "spec": spec}


def build(root: Path) -> list[str]:
    """Fill every PACKAGED folder; the files written, relative to ``root``, for the wheel.

    Each file is replaced atomically and stale files are removed afterwards, so a process reading
    the package while it is built (an editable install's renderer) never finds a file missing."""
    written = []
    for name, fill in PACKAGED.items():
        folder = root / PACKAGE / name
        with tempfile.TemporaryDirectory(prefix="obs-html-build-") as work:
            filled = Path(work) / "packaged"
            (Path(work) / "work").mkdir()
            filled.mkdir()
            fill(root, Path(work) / "work", filled)
            files = sorted(path.relative_to(filled) for path in filled.rglob("*") if path.is_file())
            for relative in files:
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                staged = target.with_name(f".{target.name}.{os.getpid()}")
                shutil.copy2(filled / relative, staged)
                os.replace(staged, target)
        # A dot file is another build's file being staged.
        for path in folder.rglob("*"):
            if path.is_file() and not path.name.startswith(".") and path.relative_to(folder) not in files:
                path.unlink()
        written += [(PACKAGE / name / relative).as_posix() for relative in files]
    return written


class PackagedAssetsHook(BuildHookInterface):
    PLUGIN_NAME = "packaged-assets"

    def initialize(self, version: str, build_data: dict) -> None:
        build_data["artifacts"].extend(build(Path(self.root)))
