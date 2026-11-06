"""The adapter spec's naming for what goes out: an adapter's output is the artifact.

Reader: a structure test of this adapter's specification.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]

_OLD_NAME = re.compile(r"document[- ]presentation", re.IGNORECASE)
_HEADING = re.compile(r"^#{1,6} ")
_LINK = re.compile(r"\[\[[^\]]*\]\]|\]\([^)]*\)")
_CAPABILITY_ID = re.compile(r"^\s*id:\s")


def says_document_presentation(relative: str) -> list[str]:
    """The capability ids, headings and links in a spec file that still say "document presentation"."""
    found = []
    for number, line in enumerate((ROOT / relative).read_text(encoding="utf-8").splitlines(), 1):
        named = [line] if _HEADING.match(line) or _CAPABILITY_ID.match(line) else _LINK.findall(line)
        if any(_OLD_NAME.search(part) for part in named):
            found.append(f"{relative}:{number}: say 'artifact presentation' instead: {line.strip()}")
    return found
