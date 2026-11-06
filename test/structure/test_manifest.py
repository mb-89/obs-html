"""The adapter's specification is its own vault: spec/manifest.md and the notes it reaches.

Reader: whoever changes this adapter's specification. obs's spec builds it with this adapter and
references it (obs spec/appendix/references/obs-html-specification.md); a link from here to obs's
spec goes through the reference note `obs-specification`, never a wikilink into obs's vault.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
SPEC = ROOT / "spec"
LINE = re.compile(r"^( *)- \[\[([^\]|#]+)(?:\|[^\]]*)?\]\]$")
WIKILINK = re.compile(r"\[\[([^\]|]*)(?:\|[^\]]*)?\]\]")
HEADING = re.compile(r"^#+ (.+)$", re.MULTILINE)


def _notes() -> dict[str, Path]:
    return {path.relative_to(SPEC).with_suffix("").as_posix(): path for path in SPEC.rglob("*.md")}


def _toc() -> list[tuple[int, str]]:
    body = (SPEC / "manifest.md").read_text(encoding="utf-8").split("\n---\n", 1)[1]
    return [(len(match[1]) // 2, match[2]) for match in map(LINE.match, body.splitlines()) if match]


def test_manifest_is_a_nested_list_of_existing_notes() -> None:
    notes, previous = _notes(), -1
    toc = _toc()
    assert toc
    for depth, target in toc:
        assert depth <= previous + 1, f"spec/manifest.md: {target} nests deeper than its parent"
        assert target in notes, f"spec/manifest.md: [[{target}]] names no note; add spec/{target}.md"
        previous = depth


def test_manifest_reaches_every_note_outside_its_registers() -> None:
    listed = {target for _, target in _toc()}
    registered = {"manifest", *(name for name in _notes() if name.startswith(("capabilities/", "references/")))}
    assert sorted(set(_notes()) - listed - registered) == []


def _without_code(text: str) -> str:
    return re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", text, flags=re.DOTALL))


def test_every_wikilink_resolves_inside_this_vault() -> None:
    notes = _notes()
    by_name: dict[str, list[str]] = {}
    for name in notes:
        by_name.setdefault(name.rsplit("/", 1)[-1], []).append(name)
    headings = {name: {heading.strip().lower() for heading in HEADING.findall(path.read_text(encoding="utf-8"))}
                for name, path in notes.items()}
    broken = []
    for name, path in notes.items():
        for target in WIKILINK.findall(_without_code(path.read_text(encoding="utf-8"))):
            note, _, heading = target.partition("#")
            resolved = name if not note else note if note in notes else (
                by_name[note][0] if len(by_name.get(note, [])) == 1 else None)
            if resolved is None:
                broken.append(f"spec/{name}.md: [[{target}]] names no note of this vault; link obs's spec "
                              "through [[obs-specification]]")
            elif heading and not heading.startswith("^") and heading.lower() not in headings[resolved]:
                broken.append(f"spec/{name}.md: [[{target}]] names no heading of spec/{resolved}.md")
    assert broken == []
