"""No link of the README or the specification leaves this repository.

Reader: whoever links a note of obs, the core, from this repository's README or specification.

This repository stands alone beside the core (README "Core"), so a relative link that climbs out of
it, such as `../../spec/design_input/input-model.md`, leads nowhere. A note of the core is named in
the text as obs's <note> (<section>), the note in the core checked out beside as `../obs` at the
pinned tag; inside the specification it goes through the reference note `obs-specification`
(test_manifest.py). An `http(s)` link and a link inside the repository stay as they are.

A link is a Markdown link or image target, a link reference definition, an HTML `href` or `src`,
or a note's frontmatter `url`; code, fenced or inline, holds no link.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[`~]*[ \t]*$", re.MULTILINE | re.DOTALL)
CODE_SPAN = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)", re.DOTALL)
FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
TARGETS = (
    re.compile(r"\]\(\s*<([^>\n]*)>"),  # [text](<target>), ![alt](<target>)
    re.compile(r"\]\(\s*([^)\s<]+)"),  # [text](target "title")
    re.compile(r"^ {0,3}\[[^\]\n]+\]:[ \t]*<?([^\s>]+)", re.MULTILINE),  # [label]: target
    re.compile(r"\b(?:href|src)\s*=\s*[\"']([^\"']+)", re.IGNORECASE),  # <a href="target">
    re.compile(r"^url:[ \t]*[\"']?([^\"'\n]+?)[\"']?[ \t]*$", re.MULTILINE),  # frontmatter url
)
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _blanked(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match[0])


def _searchable(text: str) -> str:
    """The text with code and the frontmatter's other fields blanked, so offsets keep their lines."""
    frontmatter = FRONTMATTER.match(text)
    head = "" if frontmatter is None else frontmatter[0]
    fields = re.sub(r"^(?!url:).*$", lambda line: " " * len(line[0]), head, flags=re.MULTILINE)
    body = CODE_SPAN.sub(_blanked, FENCE.sub(_blanked, text[len(head):]))
    return fields + re.sub(r"^url:", "    ", body, flags=re.MULTILINE)


def leaving(root: Path, notes: list[Path]) -> list[str]:
    """Each relative link of ``notes`` whose target resolves outside ``root``, as
    `<file>:<line>: <link>`, the file relative to ``root``."""
    found = []
    for note in notes:
        text = _searchable(note.read_text(encoding="utf-8"))
        for pattern in TARGETS:
            for match in pattern.finditer(text):
                link = match[1].strip()
                target = link.split("#", 1)[0].split("?", 1)[0]
                if not target or SCHEME.match(target):
                    continue
                resolved = (note.parent / target).resolve()
                if not resolved.is_relative_to(root.resolve()):
                    found.append((note.relative_to(root).as_posix(), text.count("\n", 0, match.start(1)) + 1, link))
    return [f"{file}:{line}: {link}" for file, line, link in sorted(found)]


def _authored(root: Path) -> list[Path]:
    return [root / "README.md", *sorted((root / "spec").rglob("*.md"))]


def test_no_link_of_the_readme_or_the_specification_leaves_the_repository() -> None:
    found = leaving(ROOT, _authored(ROOT))
    assert not found, ("these links leave the repository and lead nowhere beside the core; name the core's "
                       "note as obs's <note> (<section>), as README \"Core\" says:\n" + "\n".join(found))


def test_a_link_that_leaves_the_repository_is_named_by_file_line_and_link(tmp_path: Path) -> None:
    spec = tmp_path / "spec" / "capabilities"
    spec.mkdir(parents=True)
    (tmp_path / "README.md").write_text(
        "# Planted\n\nSee [inside](spec/capabilities/note.md), [the web](https://example.org/a)\n"
        "and the core's [input\nmodel](../../spec/design_input/input-model.md#chapter-content).\n\n"
        "```sh\ngit clone x ../obs\n```\n\n`[code](../outside.md)` is code.\n", encoding="utf-8")
    (spec / "note.md").write_text(
        "---\ntitle: Planted\nurl: ../../../../spec/manifest.md\n---\n\n"
        "[up](../../src/module.js) stays inside; ![out](../../../outside.png) leaves.\n\n"
        "[label]: ../../../elsewhere.md\n<a href=\"../../../page.html\">page</a>\n", encoding="utf-8")

    assert leaving(tmp_path, _authored(tmp_path)) == [
        "README.md:5: ../../spec/design_input/input-model.md#chapter-content",
        "spec/capabilities/note.md:3: ../../../../spec/manifest.md",
        "spec/capabilities/note.md:6: ../../../outside.png",
        "spec/capabilities/note.md:8: ../../../elsewhere.md",
        "spec/capabilities/note.md:9: ../../../page.html",
    ]
