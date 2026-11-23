"""The default style component, obs-html-style-generic, for the machine folders the tests build in.

Reader: whoever changes how the tests give a build its default style (README "Default style",
spec/configuration.md, Default style).

obs-html builds no style in: a build without ``--style`` and without ``obs.style`` applies the
installed component NAME, which se.toml requires at the versions its ``[components.NAME]`` admits.
``provided(core_root)`` installs its newest admitted release once into a cache machine folder
(CACHE), through the core's own install code (obs's ``src/obs/components.py``, ``install``), under
a lock that every xdist worker and every checkout on the machine shares; only that first install
reaches the network, before any test runs, and every later run reads the cache. A newer admitted
release reaches the tests once the cache folder is removed. ``install_into(machine, core_root)``
copies it into a test machine folder from the cache and returns its components.json entry.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
NAME = "obs-html-style-generic"
ADDRESS = f"https://github.com/mb-89/{NAME}"
REQUIREMENT = tomllib.loads((ROOT / "se.toml").read_text(encoding="utf-8"))["components"][NAME]["version"]
CACHE = Path(tempfile.gettempdir()) / "obs-html-components" / f"{NAME}-{REQUIREMENT.lstrip('^')}"
_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


class ProvisionError(RuntimeError):
    """The default style component cannot be provided; the message names why and the remedy."""


def core_components(core_root: Path):
    """The core's component code, obs's ``src/obs/components.py`` in the checkout ``core_root``."""
    spec = importlib.util.spec_from_file_location("obs_core_components", core_root / "src" / "obs" / "components.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(machine: Path) -> dict[str, str] | None:
    try:
        listed = json.loads((machine / "components.json").read_text(encoding="utf-8"))["components"]
    except (OSError, ValueError, KeyError):
        return None
    entry = next((entry for entry in listed if entry.get("name") == NAME), None)
    return entry if entry and (machine / "components" / NAME / "style.css").is_file() else None


def _newest(admits) -> tuple[tuple[int, int, int], str, str]:
    """The newest release of NAME that se.toml's requirement admits, read by the core's ``admits``, as its
    version, tag and commit, from the repository's tags."""
    listed = subprocess.run(["git", "ls-remote", "--tags", ADDRESS], capture_output=True, text=True,
                            encoding="utf-8", env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, check=False)
    if listed.returncode:
        raise ProvisionError(f"test/style_component.py: {ADDRESS} cannot be read: "
                             f"{(listed.stderr.strip().splitlines() or ['git ls-remote failed'])[-1]}. Remedy: run "
                             "the tests once with the network, which installs it into the cache " + str(CACHE))
    commits: dict[str, str] = {}
    for line in listed.stdout.splitlines():
        commit, _, reference = line.partition("\t")
        tag = reference.removeprefix("refs/tags/")
        if tag.endswith("^{}"):
            commits[tag[:-3]] = commit
        else:
            commits.setdefault(tag, commit)
    releases = sorted((tuple(map(int, match.groups())), tag, commit) for tag, commit in commits.items()
                      if (match := _TAG.fullmatch(tag)) and admits(REQUIREMENT, tuple(map(int, match.groups()))))
    if not releases:
        raise ProvisionError(f"test/style_component.py: {ADDRESS} has no release that se.toml's {REQUIREMENT} "
                             "admits. Remedy: release one, or change the requirement in se.toml")
    return releases[-1]


def provided(core_root: Path) -> Path:
    """The cache machine folder that holds NAME installed, installing it there first where it does not."""
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(f"{CACHE}.lock"):
        if _entry(CACHE) is None:
            core = core_components(core_root)
            version, tag, commit = _newest(core.admits)
            release = core.Release("style", NAME, version, tag, commit, ADDRESS)
            previous = os.environ.get(core.VARIABLE)
            os.environ[core.VARIABLE] = str(CACHE)
            try:
                core.install(core_root, release)
            except core.ComponentError as error:
                raise ProvisionError(f"test/style_component.py: {error}") from error
            finally:
                if previous is None:
                    del os.environ[core.VARIABLE]
                else:
                    os.environ[core.VARIABLE] = previous
    return CACHE


def install_into(machine: Path, core_root: Path) -> dict[str, str]:
    """Install NAME in the machine folder ``machine`` as a copy of the cache's installed folder; its
    components.json entry, which the caller lists with the folder's other components."""
    cache = provided(core_root)
    shutil.copytree(cache / "components" / NAME, machine / "components" / NAME, dirs_exist_ok=True)
    return _entry(cache)
