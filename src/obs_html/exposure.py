"""The build-time check that a finished artifact exposes nothing of the build machine."""
from __future__ import annotations

import getpass
import os
import re
from pathlib import Path
from typing import Iterator

from obs_html.artifact_data import ARTIFACT_PATTERN, decode_artifact_data


REMEDY = ("Remedy: write the path relative to the vault, or with ~ for the home folder, in the "
          "source; the core replaces them in captured command output (capabilities/command-fences), "
          "so a hit there is an obs defect to report.")
_BASE64 = re.compile(r"base64,[A-Za-z0-9+/=]+")
SEGMENT = r"""[^\s/\\:*?"'<>|`,;()\[\]{}=]"""
ABSOLUTE_PATH = re.compile(
    r"(?<![\w.~/\\:<])(?:[A-Za-z]:[/\\]|\\\\|/)"  # POSIX root, drive letter or UNC prefix
    rf"(?:{SEGMENT}+[/\\])*{SEGMENT}+"
)
"""An absolute path, as the core recognises one in captured output; an adapter imports no core module."""


class ExposureError(ValueError):
    """Raised when a finished artifact contains the build machine's home folder or user name."""


def check_artifact(artifact: str) -> None:
    """Fail naming where the artifact exposes the build machine, and the remedy."""
    flags = re.IGNORECASE if os.name == "nt" else 0
    home = Path.home()
    folders = [("home folder", home)] if home.parent != home else []
    patterns = [(f"the build machine's {label} '{folder}'",
                 re.compile("|".join(re.escape(spelling) + rf"(?!{SEGMENT})"
                                     for spelling in path_spellings(folder)), flags))
                for label, folder in folders]
    user = _user_name()
    for where, text in _texts(artifact):
        text = _BASE64.sub("base64,", text)
        for what, pattern in patterns:
            if pattern.search(text):
                raise ExposureError(f"obs-html: the artifact exposes {what} in {where}. {REMEDY}")
        if user and any(user.casefold() in (part.casefold() for part in re.split(r"[/\\]", path[0]))
                        for path in ABSOLUTE_PATH.finditer(text)):
            raise ExposureError(f"obs-html: the artifact exposes the build machine's user name "
                                f"'{user}' in a path in {where}. {REMEDY}")


def path_spellings(folder: Path) -> list[str]:
    """The folder as written and resolved, with native and forward slashes, longest first."""
    paths = {folder.absolute(), folder.resolve()}
    spellings = {spelling for path in paths for spelling in (str(path), path.as_posix())}
    return sorted(spellings, key=len, reverse=True)


def _user_name() -> str | None:
    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):
        return None


def _texts(artifact: str) -> Iterator[tuple[str, str]]:
    """The artifact's HTML, line by line without the data island, then each decoded data string."""
    island = ARTIFACT_PATTERN.search(artifact)
    html = artifact[:island.start(2)] + artifact[island.end(2):] if island else artifact
    for number, line in enumerate(html.splitlines(), 1):
        yield f"HTML line {number}", line
    if island:
        yield from _strings(decode_artifact_data(artifact), "artifact-data ")


def _strings(value: object, where: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield where.rstrip(), value
    elif isinstance(value, dict):
        for key, item in value.items():
            path = f"{where}{'' if where.endswith(' ') else '.'}{key}"
            yield f"{path} (the key)", key
            yield from _strings(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{where.rstrip()}[{index}]")
