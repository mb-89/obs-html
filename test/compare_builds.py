"""Compare two builds of an artifact: whether they are identical and, where not, what changed.

Reader: a maintainer who builds the same source on two commits with one ``SOURCE_DATE_EPOCH``,
finds the two pages different with ``cmp``, and names in a field report what changed.

``compare`` is the whole comparison, two HTML texts in and the report's lines out. Where the texts
are equal it is ``identical``. Otherwise it is the page outside its data island (``page:``, a
unified diff with two lines of context, or ``page: same``), then the data, decoded with
``decode_artifact_data``: each top-level key, in sorted order, that is ``added``, ``removed`` or
``changed`` (``data: same`` where none is), and under a changed ``notes`` each note by its
``slug``, in AFTER's order, then the notes only BEFORE has, a changed one with its own fields that
changed. The island's opening tag stays in the page, so a change in how the data is stored
(``dataCompression``) shows there. From the adapter's folder:

    uv run python test/compare_builds.py BEFORE.html AFTER.html

It exits 0 where the files are identical, 1 where they differ and 2, with one line on standard
error naming the file, where one cannot be read or its data cannot be decoded.
"""
from __future__ import annotations

import difflib
import sys
from pathlib import Path

from obs_html.artifact_data import ARTIFACT_PATTERN, decode_artifact_data
from obs_html.errors import InputError

IDENTICAL = "identical"
_ISLAND = "\N{HORIZONTAL ELLIPSIS}"
"""What stands in the page for the island's content, which the data part of the report compares."""


def _page(artifact: str) -> list[str]:
    return ARTIFACT_PATTERN.sub(lambda match: f"{match[1]}{_ISLAND}{match[3]}", artifact, count=1).splitlines()


def _data(artifact: str, name: str) -> dict:
    try:
        return decode_artifact_data(artifact)
    except InputError as error:
        raise InputError(name, error.field, error.problem, error.remedy) from error


def _change(before: dict, after: dict, key: str) -> str | None:
    if key not in before:
        return "added"
    if key not in after:
        return "removed"
    return "changed" if before[key] != after[key] else None


def _by_slug(notes: list) -> dict[str, object]:
    keyed: dict[str, object] = {}
    for index, note in enumerate(notes):
        slug = note.get("slug") if isinstance(note, dict) else None
        keyed.setdefault(slug if isinstance(slug, str) else f"#{index}", note)
    return keyed


def _notes(before: list, after: list) -> list[str]:
    old, new = _by_slug(before), _by_slug(after)
    lines = []
    for slug in [*new, *(slug for slug in old if slug not in new)]:
        change = _change(old, new, slug)
        if change == "changed" and isinstance(old[slug], dict) and isinstance(new[slug], dict):
            fields = (field for field in sorted(old[slug].keys() | new[slug].keys())
                      if _change(old[slug], new[slug], field))
            change = f"changed: {', '.join(fields)}"
        if change:
            lines.append(f"    {slug}: {change}")
    return lines


def compare(before: str, after: str, names: tuple[str, str] = ("BEFORE", "AFTER")) -> list[str]:
    """The report on two artifacts' HTML, ``names`` naming them; an ``InputError`` names the one
    whose data ``decode_artifact_data`` cannot read."""
    if before == after:
        return [IDENTICAL]
    old, new = _data(before, names[0]), _data(after, names[1])
    diff = list(difflib.unified_diff(_page(before), _page(after), *names, n=2, lineterm=""))
    lines = ["page:", *diff] if diff else ["page: same"]
    changes = [(key, change) for key in sorted(old.keys() | new.keys()) if (change := _change(old, new, key))]
    lines.append("data:" if changes else "data: same")
    for key, change in changes:
        lines.append(f"  {key}: {change}")
        if key == "notes" and change == "changed" and isinstance(old[key], list) and isinstance(new[key], list):
            lines.extend(_notes(old[key], new[key]))
    return lines


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print("compare_builds.py: give two artifacts, BEFORE.html AFTER.html", file=sys.stderr)
        return 2
    texts = []
    for name in arguments:
        try:
            texts.append(Path(name).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            print(f"{name}: cannot be read ({getattr(error, 'strerror', None) or error})", file=sys.stderr)
            return 2
    try:
        lines = compare(*texts, names=(arguments[0], arguments[1]))
    except InputError as error:
        print(error, file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0 if lines == [IDENTICAL] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
