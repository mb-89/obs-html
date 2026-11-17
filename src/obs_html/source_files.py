"""Source file links: the rules of the `Source file` row, pure (data in, data out).

Each page's frontmatter table ends with the vault path of the note it shows, a link where the
core passed ``--vault-link`` (spec/cli.md, Source file links). This module checks that link,
drops it where a private term names the vault folder, joins it with a note's vault path, and
names the notes that get a row; ``cli.py`` and ``render.py`` only wire it, ``source-file.js``
writes the row.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

from .errors import InputError

PROG = "obs-html"
FIELD = "--vault-link"
PARENT = ".."
REFUSED_CHARACTERS = frozenset("/\\:")


def checked(link: str) -> str:
    """``link`` where it is zero or more ``..`` parts, then one part that is not ``.`` or ``..``,
    does not start with ``-`` and holds no ``/``, ``\\``, ``:`` or control character; any other
    value is an input error of field ``--vault-link``."""
    *climb, name = link.split("/")
    if any(part != PARENT for part in climb) or not _usable_name(name):
        raise InputError(PROG, FIELD, f"is {link!r}, not the way from DESTINATION's folder to the vault folder",
                         "Pass zero or more ../ and then the vault folder's name, as obs-document does, "
                         "or drop --vault-link")
    return link


def usable(link: str, terms: tuple[tuple[str, re.Pattern[str]], ...]) -> str | None:
    """``link``, or None where one of the local list's ``terms`` (provenance.local_terms) matches its
    last part, the vault folder's name, so no page names it."""
    name = link.rsplit("/", 1)[-1]
    return None if any(pattern.search(name) for _label, pattern in terms) else link


def href(link: str, path: str) -> str:
    """The link to the note at vault path ``path``: the parts of ``link`` and ``path`` joined with
    ``/``, each part but ``..`` percent-encoded as UTF-8, so the result is 7-bit ASCII."""
    return "/".join(part if part == PARENT else quote(part, safe="")
                    for part in (*link.split("/"), *path.split("/")))


def note_fields(document: dict[str, object], link: str | None, home: str) -> dict[str, dict[str, str]]:
    """Per note slug, the fields its page data gains: ``sourceFilePath``, the note's vault path as the
    Document names it (a note record's ``path``; for ``home``, the manifest's), and with ``link``
    also ``sourceFileHref``. A note the Document names no path for is not in it."""
    paths = {home: document["manifest"]["path"]}
    paths.update({record["id"]: record["path"] for record in document["records"]
                  if record.get("type") == "note" and record.get("path") and record["id"] != home})
    return {slug: {"sourceFilePath": path, **({"sourceFileHref": href(link, path)} if link is not None else {})}
            for slug, path in paths.items()}


def _usable_name(name: str) -> bool:
    return name not in {"", ".", PARENT} and not name.startswith("-") and not any(
        character in REFUSED_CHARACTERS or unicodedata.category(character) == "Cc" for character in name)
