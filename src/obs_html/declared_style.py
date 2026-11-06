"""The declared style: the style module a Document's ``style`` names, fetched once per commit.

Reader: whoever changes how obs-html resolves a Document's declared style; spec/configuration.md,
"Declared style", owns the behaviour.

Fetching is this adapter's one door to a style repository: a ``Fetcher`` fetches ``url`` at
``ref`` into an empty folder and returns why it could not, or None. ``GitFetcher`` does it with git; tests use the fake in
test/style_fetchers.py, held to the same contract in test/test_styles.py. ``DeclaredStyles`` keeps
each commit's tree in a cache folder named by the commit, by default under the user's cache folder
(``user_cache``), so a second build of the same commit fetches nothing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol

from obs_html.errors import InputError

OWNER = "obs-html spec/configuration.md (Declared style)"


class Fetcher(Protocol):
    def fetch(self, url: str, ref: str, destination: Path) -> str | None:
        """Write the tree of commit ``ref`` of the repository ``url`` into the empty folder
        ``destination``; return None, or the reason it could not."""


class GitFetcher:
    """Fetches the one commit with git: a shallow fetch of ``ref`` into a fresh repository, checked out."""

    def fetch(self, url: str, ref: str, destination: Path) -> str | None:
        for command in (["init", "--quiet"], ["fetch", "--quiet", "--depth", "1", url, ref],
                        ["checkout", "--quiet", "FETCH_HEAD"]):
            try:
                result = subprocess.run(["git", "-C", str(destination), *command], capture_output=True, text=True)
            except FileNotFoundError:
                return "git is not installed"
            if result.returncode:
                return f"git {command[0]} failed: {result.stderr.strip() or f'exit status {result.returncode}'}"
        return None


def user_cache() -> Path:
    """The default cache: obs-html/styles in the user's cache folder, never inside a checkout."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "obs-html" / "styles"


class DeclaredStyles:
    """Resolves a declared style to its module folder, fetching each commit into ``cache`` once."""

    def __init__(self, fetcher: Fetcher, cache: Path) -> None:
        self.fetcher, self.cache = fetcher, Path(cache)

    def folder(self, style: dict[str, str], source: str) -> Path:
        """The module folder of ``style`` (the Document's ``style``); ``source`` names the Document."""
        url, ref = style["url"], style["ref"]
        inside = _inside(style.get("path", ""), source)
        tree = self.cache / ref
        if not tree.is_dir():
            self._fetch(url, ref, tree, source)
        folder = tree.joinpath(*inside.parts)
        if not (folder / "style.css").is_file():
            raise InputError(source, "style.path", f"is {style.get('path', '')!r}, which holds no style.css in "
                             f"{url} at commit {ref} (cached in {tree})", "Point obs.style.path in the manifest at "
                             f"the module's folder that holds style.css; see {OWNER}")
        return folder

    def _fetch(self, url: str, ref: str, tree: Path, source: str) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{ref}-", dir=self.cache))
        try:
            failure = self.fetcher.fetch(url, ref, staging)
            if failure is not None:
                raise InputError(source, "style", f"could not be fetched: style.url {url} at style.ref {ref}: "
                                 f"{failure}", "Check that obs.style.url in the manifest is the module's public "
                                 "clone URL and obs.style.ref a commit in it, or pass --style FOLDER for this "
                                 f"build; see {OWNER}")
            try:
                staging.rename(tree)
            except OSError:
                if not tree.is_dir():  # Else another build that finished first left the same commit's tree.
                    raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def _inside(path: str, source: str) -> PurePosixPath:
    """``path`` as a relative path that stays inside the fetched tree, else an input error."""
    relative = PurePosixPath(path)
    if relative.is_absolute() or PureWindowsPath(path).anchor or ".." in relative.parts:
        raise InputError(source, "style.path", f"is {path!r}, which leaves the style module's repository",
                         "Give obs.style.path in the manifest as a folder relative to the repository root, "
                         f"without '..'; see {OWNER}")
    return relative
