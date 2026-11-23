"""Whether a change leaves obs's reference pages byte for byte as they were, and what changed in the others.

Reader: a worker whose change must leave the other pages as they were (architecture.md, Rendering
and runtime), who quotes this command's output in the field report. From this repository's root:

    uv run python test/unchanged_output.py [--base REF] [--head REF] [--keep FOLDER]

It builds the reference set twice with ``SOURCE_DATE_EPOCH`` fixed (EPOCH): at the base, by default
the merge base of ``HEAD`` and ``origin/main``, and at the head, by default the working tree. A
side's root is a checkout of obs-html. A REF is built in a detached worktree of its own whose
folder starts with PREFIX, removed again however the run ends. Each side builds with its own code:
every command is ``uv run`` in that side's root (UV_PROJECT), without the caller's
``VIRTUAL_ENV``, so a worktree gets its own ``.venv`` on first use, and the core it runs is the
release that side's lockfile pins. The core finds that side's checkout as the component ``html``
of a machine folder of the side's own (OBS_LOCAL_FOLDER), as test/conftest.py installs it, so no
build reads the machine's installed components. The pages go to a temporary folder, or to
``FOLDER/base`` and ``FOLDER/head``, each with its side's machine folder in it (MACHINE).

The set (``reference_set``) holds, in this order:

- the decks: ``phone-deck`` from the side (DECKS) and ``bless-deck`` from the core (CORE_DECKS),
  each built through the core as a deck is built (``obs-document --source <manifest> --adapter obs-html``);
- the fixture Documents, every ``*.json`` in the side's DOCUMENTS, each built with ``obs-html DOCUMENT``;
- obs's spec (OBS_SPEC) from the core, built from a copy of its vault with ``--execute-commands``,
  which fetches its remote images;
- the adapter's specification (ADAPTER_SPEC) from the side, ``obs-html --build-own-spec``.

The core is obs's checkout at the tag pyproject.toml pins, beside this repository as ``../obs`` or
where ``OBS_CORE_ROOT`` names it (CORE_ROOT, as test/conftest.py reads it; README, Core). Its pages
come from one checkout, so they are the same input on both sides, and only the side's code makes
them differ.

For each page, in the set's order, it prints ``same NAME``, or ``differs NAME`` with the report of
test/compare_builds.py's ``compare`` under it, indented by two spaces, or ``added NAME`` or
``removed NAME`` for a page only the head or only the base has, which differs too. The last line
is ``N same, M differ``. It exits 0 where every page is the same, 1 where any differs, and 2 where
a build fails, naming the page, the side and the last line of the command's error, or where a
worktree cannot be made.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import style_component
from compare_builds import IDENTICAL, compare

ADAPTER = Path(__file__).resolve().parents[1]
# The core's checkout, as test/conftest.py reads it (README, Core).
CORE_ROOT = Path(os.environ.get("OBS_CORE_ROOT") or ADAPTER.parent / "obs").resolve()
# What every build of both sides is given, so that two builds of one source are equal.
EPOCH = "1700000000"
# The start of each worktree's folder name.
PREFIX = "obs-unchanged-output-"
# The machine folder of a side's builds, in that side's output folder (machine_folder).
MACHINE = ".machine"
# The commit every side's adapter component records, so a build records the same component on both sides
# where their versions agree, as test/conftest.py records it.
COMMIT = "0" * 40
SIDES = ("base", "head")
# What a side holds, relative to its root: the fixture Documents and its deck.
DOCUMENTS = PurePosixPath("test/fixtures/documents")
DECKS = {"phone-deck": PurePosixPath("test/fixtures/phone-deck/manifest.md")}
# What the core holds, relative to CORE_ROOT: its deck.
CORE_DECKS = {"bless-deck": PurePosixPath("spec/examples/bless-deck/manifest.md")}
# obs's spec, from the core, and the adapter's specification, from the side.
OBS_SPEC, OBS_SPEC_SOURCE = "obs-spec", PurePosixPath("spec/manifest.md")
ADAPTER_SPEC, ADAPTER_SPEC_SOURCE = "adapter-spec", PurePosixPath("spec/manifest.md")
# The set's order: decks, then fixture Documents, then the two specifications.
KINDS = ("deck", "document", "spec", "adapter-spec")
# Where a page's source is: the side's root or CORE_ROOT.
SIDE, CORE = "side", "core"


@dataclass(frozen=True)
class Page:
    """One page of the set: its name, its kind (KINDS), its source relative to its origin's root and
    its origin, SIDE or CORE."""
    name: str
    kind: str
    source: PurePosixPath
    origin: str = SIDE


class BuildError(Exception):
    """A page could not be built on a side; ``detail`` is the last line of the command's error."""

    def __init__(self, page: str, side: str, detail: str):
        super().__init__(f"unchanged_output.py: {page} could not be built on the {side} side: {detail}")
        self.page, self.side, self.detail = page, side, detail


def _order(page: Page) -> tuple[int, str]:
    return KINDS.index(page.kind), page.name


def reference_set(files: Iterable[PurePosixPath], core: Iterable[PurePosixPath] = ()) -> list[Page]:
    """The pages a side's ``files`` and the core's ``core`` (paths relative to each root) give, in
    the set's order."""
    files, core = set(files), set(core)
    pages = [Page(name, "deck", source) for name, source in DECKS.items() if source in files]
    pages += [Page(name, "deck", source, CORE) for name, source in CORE_DECKS.items() if source in core]
    pages += [Page(file.stem, "document", file) for file in files if file.parent == DOCUMENTS and file.suffix == ".json"]
    pages += [Page(OBS_SPEC, "spec", OBS_SPEC_SOURCE, CORE)] if OBS_SPEC_SOURCE in core else []
    pages += [Page(ADAPTER_SPEC, "adapter-spec", ADAPTER_SPEC_SOURCE)] if ADAPTER_SPEC_SOURCE in files else []
    return sorted(pages, key=_order)


def side_files(root: Path) -> list[PurePosixPath]:
    """The files of a side's ``root`` that ``reference_set`` reads."""
    found = [source for source in [*DECKS.values(), ADAPTER_SPEC_SOURCE] if (root / source).is_file()]
    return found + [DOCUMENTS / path.name for path in (root / DOCUMENTS).glob("*.json")]


def core_files(core: Path) -> list[PurePosixPath]:
    """The files of the core's checkout ``core`` that ``reference_set`` reads."""
    return [source for source in [*CORE_DECKS.values(), OBS_SPEC_SOURCE] if (core / source).is_file()]


def paired(base: list[Page], head: list[Page]) -> list[tuple[str, Page | None, Page | None]]:
    """Each page either side has, in the set's order, with its base and its head page (None where
    that side has none)."""
    old, new = {page.name: page for page in base}, {page.name: page for page in head}
    pages = sorted({page.name: page for page in [*base, *head]}.values(), key=_order)
    return [(page.name, old.get(page.name), new.get(page.name)) for page in pages]


def report(pairs: Iterable[tuple[str, str | None, str | None]]) -> tuple[list[str], int]:
    """The report's lines and the exit code for each page's base and head HTML (None where that side
    has no such page)."""
    lines, same, differ = [], 0, 0
    for name, before, after in pairs:
        if before is None or after is None:
            lines.append(f"{'added' if before is None else 'removed'} {name}")
        else:
            shown = compare(before, after, names=(f"base/{name}.html", f"head/{name}.html"))
            if shown == [IDENTICAL]:
                lines.append(f"same {name}")
                same += 1
                continue
            lines += [f"differs {name}", *(f"  {line}" for line in shown)]
        differ += 1
    lines.append(f"{same} same, {differ} differ")
    return lines, 1 if differ else 0


def component(root: Path) -> str:
    """The adapter component the side's checkout ``root`` is: the name its adapter.json declares,
    obs-html, or html on a side from before the component took its repository's name. A
    ``KeyError``, an ``OSError`` or a ``ValueError`` names a side without one."""
    return json.loads((root / "adapter.json").read_text(encoding="utf-8"))["name"]


def machine_folder(root: Path, folder: Path) -> Path:
    """The machine folder in ``folder`` whose installed components are the side's checkout ``root``,
    as the adapter component its adapter.json names (component), and the default style component
    obs-html-style-generic, as test/conftest.py installs them: the adapter at the version the side's
    pyproject.toml holds, with the commit COMMIT (obs's spec/design_input/components.md, Installed
    components), the style from test/style_component.py's cache. A ``KeyError``, an ``OSError`` or a
    ``ValueError`` names a side without that version or that name."""
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    name = component(root)
    machine = folder / MACHINE
    (machine / "components").mkdir(parents=True, exist_ok=True)
    link = machine / "components" / name
    if not link.is_symlink():
        link.symlink_to(root.resolve(), target_is_directory=True)
    entry = {"name": name, "kind": "adapter", "version": version, "commit": COMMIT}
    style = style_component.install_into(machine, CORE_ROOT)
    (machine / "components.json").write_text(json.dumps({"components": [entry, style]}), encoding="utf-8")
    return machine


def _environment(root: Path, machine: Path) -> dict[str, str]:
    """A side's environment: the caller's without ``VIRTUAL_ENV``, with the fixed instant, with the
    side's machine folder (machine_folder) as the core's, so no build reads the machine's installed
    components, and with obs-html's local folder at one that nothing creates, so a build on a
    machine with local themes equals one on CI (spec/configuration.md, Local themes)."""
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    environment.update(SOURCE_DATE_EPOCH=EPOCH, UV_PROJECT=str(root), OBS_LOCAL_FOLDER=str(machine),
                       OBS_HTML_LOCAL_FOLDER=str(root / ".no-local-folder"))
    return environment


def _run(command: list[str], cwd: Path, root: Path, machine: Path, page: Page, side: str) -> None:
    result = subprocess.run(command, cwd=cwd, env=_environment(root, machine), text=True, encoding="utf-8",
                            errors="replace", capture_output=True)
    if result.returncode:
        lines = [line.strip() for line in (result.stderr or result.stdout).splitlines() if line.strip()]
        raise BuildError(page.name, side, lines[-1] if lines else f"{command[2]} exited {result.returncode}")


def build(page: Page, root: Path, folder: Path, side: str) -> Path:
    """``page`` built by the side whose root is ``root``, with that side's own environment and its
    machine folder in ``folder``, into ``folder``; the HTML file. Its source is in that root or, for a
    page of the core, in CORE_ROOT. A ``BuildError`` names the page and the side."""
    folder.mkdir(parents=True, exist_ok=True)
    html = (folder / f"{page.name}.html").resolve()
    try:
        machine = machine_folder(root, folder)
    except (KeyError, OSError, ValueError) as error:
        raise BuildError(page.name, side, f"{root / 'pyproject.toml'} names no project version, or "
                         f"{root / 'adapter.json'} no component name: {error}") from error
    adapter = component(root)
    uv = ["uv", "run", "--locked"]
    source = (CORE_ROOT if page.origin == CORE else root) / page.source
    if page.kind == "document":
        _run([*uv, "obs-html", str(source), str(html)], root, root, machine, page, side)
    elif page.kind == "deck":
        _run([*uv, "obs-document", "--source", str(source), "--adapter", adapter, "--destination", str(html)],
             root, root, machine, page, side)
    else:
        work = folder / f"{page.name}-work"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir()
        if page.kind == "spec":
            shutil.copytree(source.parent, work / page.source.parent, ignore=shutil.ignore_patterns("design_output"))
            command = ["obs-document", "--source", page.source.as_posix(), "--execute-commands", "--adapter", adapter,
                       "--destination", str(html)]
            _run([*uv, *command], work, root, machine, page, side)
        else:
            _run([*uv, "obs-html", "--build-own-spec", str(html)], work, root, machine, page, side)
        shutil.rmtree(work, ignore_errors=True)
    return html


Builder = Callable[[Page, Path, Path, str], Path]


def check(roots: dict[str, Path], folder: Path, builder: Builder = build) -> tuple[list[str], int]:
    """Each side's set, discovered in its root (``roots``, by side) and in CORE_ROOT, built into
    ``folder/<side>`` with ``builder`` and compared: the report's lines and the exit code, 2 where a
    build fails."""
    core = core_files(CORE_ROOT)
    sets = {side: reference_set(side_files(roots[side]), core) for side in SIDES}
    try:
        html = {side: {page.name: builder(page, roots[side], folder / side, side).read_text(encoding="utf-8")
                       for page in sets[side]} for side in SIDES}
    except BuildError as error:
        return [str(error)], 2
    return report((name, base and html["base"][name], head and html["head"][name])
                  for name, base, head in paired(sets["base"], sets["head"]))


def _git(*arguments: str, cwd: Path = ADAPTER) -> str:
    return subprocess.run(["git", *arguments], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


@contextlib.contextmanager
def worktree(ref: str, side: str) -> Iterator[Path]:
    """A detached worktree of ``ref`` in a temporary folder whose name starts with PREFIX, removed
    with its environment on leaving, also on an error or an interruption."""
    path = Path(tempfile.mkdtemp(prefix=f"{PREFIX}{side}-"))
    try:
        _git("worktree", "add", "--detach", str(path), ref)
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        _git("worktree", "prune")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", metavar="REF", help="the base (default: the merge base of HEAD and origin/main)")
    parser.add_argument("--head", metavar="REF", help="the head (default: the working tree)")
    parser.add_argument("--keep", type=Path, metavar="FOLDER", help="build into FOLDER/base and FOLDER/head and keep them")
    options = parser.parse_args(argv)
    try:
        with contextlib.ExitStack() as stack:
            base = options.base or _git("merge-base", "HEAD", "origin/main")
            roots = {"base": stack.enter_context(worktree(base, "base")),
                     "head": stack.enter_context(worktree(options.head, "head")) if options.head
                     else Path(_git("rev-parse", "--show-toplevel"))}
            folder = options.keep.resolve() if options.keep else Path(stack.enter_context(tempfile.TemporaryDirectory()))
            lines, code = check(roots, folder)
    except subprocess.CalledProcessError as error:
        print(f"unchanged_output.py: {' '.join(error.cmd)} failed: {(error.stderr or '').strip()}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("unchanged_output.py: interrupted; its worktrees are removed", file=sys.stderr)
        return 130
    print("\n".join(lines), file=sys.stderr if code == 2 else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
