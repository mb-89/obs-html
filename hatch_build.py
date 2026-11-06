"""The build hook of the adapter's package: it writes the browser assets built from lockfiles and
copies the adapter's specification into the package.

Reader: whoever changes how the adapter is built or what its package ships.

Each build of the `obs-html` distribution, editable (`uv sync`) or not, fills every folder that
PACKAGED names inside `src/obs_html` and ships its files as package data; the renderer and
`obs-html --build-own-spec` read them through `importlib.resources`. The folders are generated, so they are ignored and never edited;
`[tool.uv] cache-keys` in pyproject.toml makes uv build again when the hook or a lockfile changes.
spec/architecture.md, Packaged browser assets, owns the design.
"""
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
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


def _lockfile_packages(lockfile: Path) -> dict:
    """The lockfile's ``packages``: each installed package by its path, with its version and integrity."""
    return json.loads(lockfile.read_text(encoding="utf-8"))["packages"]


def pinned_files(package: Path, files: list[str], work: Path, run=subprocess.run) -> Path:
    """Unpack ``files``, paths below node_modules, from the tarballs of the npm packages they belong
    to, at the versions the lockfile of ``package`` pins, into ``work``; the node_modules folder.

    Only those packages' own tarballs are fetched (one ``npm pack``, from npm's cache where it has
    them), not their dependencies, and each is checked against the lockfile's integrity."""
    lockfile = package / "package-lock.json"
    remedy = f"install Node.js and check that npm reaches its registry, then build again; {lockfile} pins it"
    pinned = _lockfile_packages(lockfile)
    names = sorted({_npm_package(file) for file in files})
    for name in names:
        if f"node_modules/{name}" not in pinned:
            raise BuildError(lockfile, f"packages.node_modules/{name}", "the lockfile pins no such package",
                             f"add {name} to {package / 'package.json'} and run npm install there")
    npm = shutil.which("npm")
    if npm is None:
        raise BuildError(lockfile, "npm pack", "npm is not on PATH", remedy)
    tarballs = work / "tarballs"
    tarballs.mkdir()
    result = run([npm, "pack", "--json", "--prefer-offline", "--pack-destination", str(tarballs),
                  *(f"{name}@{pinned[f'node_modules/{name}']['version']}" for name in names)], cwd=work,
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise BuildError(lockfile, "npm pack", f"failed (exit code {result.returncode}):\n{result.stderr}{result.stdout}",
                         remedy)
    installed = work / "node_modules"
    for name, packed in zip(names, json.loads(result.stdout)):
        tarball = (tarballs / packed["filename"]).read_bytes()
        integrity = pinned[f"node_modules/{name}"]["integrity"]
        if f"sha512-{base64.b64encode(hashlib.sha512(tarball).digest()).decode()}" != integrity:
            raise BuildError(lockfile, f"packages.node_modules/{name}.integrity",
                             f"the tarball npm fetched, {packed['filename']}, is not the one the lockfile pins",
                             "clear npm's cache with `npm cache clean --force`, then build again")
        with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
            members = {member.name.removeprefix("package/"): member for member in archive.getmembers()
                       if member.isfile()}
            for file in files:
                member = members.get(file.removeprefix(f"{name}/")) if _npm_package(file) == name else None
                if member is not None:
                    target = installed / file
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
    return installed


def _npm_package(file: str) -> str:
    """The npm package a path below node_modules belongs to: its first segment, two where scoped."""
    parts = file.split("/")
    return "/".join(parts[:2] if parts[0].startswith("@") else parts[:1])


def maths(root: Path, work: Path, folder: Path) -> None:
    """The maths library, math.js, with its licences, from its lockfile ``maths/package-lock.json``."""
    installed = pinned_files(root / MATHS, [f"mathjs/{path}" for path in MATHS_FILES.values()], work)
    for name, path in MATHS_FILES.items():
        if not (installed / "mathjs" / path).is_file():
            raise BuildError(root / MATHS / "package-lock.json", f"mathjs/{path}",
                             "its pinned tarball holds no such file",
                             "pin a version that has it, or change MATHS_FILES in hatch_build.py to its new path")
        shutil.copy2(installed / "mathjs" / path, folder / name)


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
