"""Write the vaults of the moved DOM contracts and build their Documents with the obs core.

Reader: whoever changes a vault below or regenerates ``test/fixtures/documents``.

The tests read only the committed Documents (``documents/<name>.json``), never the core. The
vaults are the interim adapter's test vaults in obs (test_browser.py, test_artifact_changes.py,
test_record_projections.py, test_table_help_browser.py), changed where a docstring says so.
Regenerate after changing a vault, with an obs checkout whose core accepts ``obsHtml`` keys in
Bases (the core this adapter was built against refused them; the Documents validate against the core's schema,
which test_moved_dom_contracts.py checks)::

    uv run python test/fixtures/build_documents.py <obs checkout>
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


HERE = Path(__file__).parent


def complete(root: Path) -> None:
    """test_complete_document_dom_interactions. Changed: the glossary links its BLUF note, which
    the core includes only when linked (the interim included every glossary note); the subtitle
    badges are vault files, so the Document carries their bytes without a network fetch."""
    notes = {
        "parent": "# Parent\n\n[[node#Extra]]\n\n[1](reference.md)\n",
        "child": "---\nbottom line: Child result.\n---\n# Child\n\nQuestion. #mark/question/child_question\n\nResolve this. #mark/open_point/child_open\n",
        "node": (
            "---\nbottom line: Node result.\nowner: {team: [Ada, Lin]}\n"
            f"description: {'Long metadata ' * 20}\nstatus: draft\nextra: omitted\n"
            "---\n# Node\n\n## Extra\n\n" + "Long prose for the preview. " * 40 +
            "\n\n```text\nCODE MUST NOT APPEAR\n```\n\n"
            "```base\nfilters: 'kind == \"quantity\"'\n"
            "properties:\n  citation:\n    displayName: Citation\n"
            "views:\n  - type: table\n    order: [citation]\n```\n"
        ),
        "flatness": (
            "---\nkind: quantity\nvalue: 20\nunit: µm\naliases: [flatness_A]\n"
            "source: '[[details]]'\n"
            "citation: 'See [[details]] **sheet 2** and $x$.'\n---\n# Flatness\n\n"
            "Canonical datum A flatness.\n"
        ),
        "glossary": (
            '# Glossary\n\nSee [[bluf]].\n\n```base\nobsHtml: {records: glossary}\n'
            "views:\n  - type: table\n    order: [term, definition]\n```\n\n"
            "```base\nfilters: 'table == \"abbreviations\"'\n"
            "properties:\n  term:\n    displayName: Term\n"
            "  citation:\n    displayName: Citation\n"
            "views:\n  - type: table\n    order: [term, citation]\nobsHtml: {records: glossary}\n```\n"
        ),
        "tags": (
            '# Tags\n\n```base\nobsHtml: {records: tag}\n'
            "views:\n  - type: table\n    order: [label, text, source]\n```\n"
        ),
        "conclusion": (
            "---\nkind: glossary\nterm: Conclusion\naliases: [bottom line]\n"
            "definition: The conclusion.\ntable: abbreviations\n"
            "citation: 'See [[details]] **source note**.'\n---\n# Conclusion\n"
        ),
        "bluf": (
            "---\nkind: glossary\nterm: BLUF\naliases: [Conclusion upfront]\n"
            "definition: The principle of presenting the [[bottom line]] first.\n---\n# BLUF\n\n[[details]]\n"
            "\n```base\nobsHtml: {records: glossary}\n"
            "views:\n  - type: table\n    order: [term, definition]\n```\n"
        ),
        "details": "# Extra details\n\n[[bottom line]] [[metadata-only]]\n\n## More\n\nNested content.\n",
        "metadata-only": "---\nowner: Ada\ncitation: '**Canonical** [[details]]'\n---\n",
        "reference": (
            "---\ndocument: '[Source document](details.md)'\n"
            "description: A source whose metadata is its complete content.\nkind: reference\n---\n"
        ),
        "quiet-reference": (
            "---\ndocument: Unlinked source\n"
            "description: Selected only by a Bases query.\nkind: reference\n---\n"
        ),
        "references": (
            "# References\n\n```base\nfilters: 'kind == \"reference\"'\n"
            "properties:\n  obsHtml.label:\n    displayName: No.\n"
            "views:\n  - type: table\n    order: [obsHtml.label, document, description]\n"
            "obsHtml:\n  members:\n    - path: reference.md\n      label: '[1]'\n"
            "    - path: quiet-reference.md\n      label: '[2]'\n```\n\n"
            "```base\nfilters: 'kind == \"reference\"'\n"
            "views:\n  - type: table\n    order: [obsHtml.label, document]\n"
            "obsHtml:\n  members:\n    - path: quiet-reference.md\n      label: B\n"
            "    - path: reference.md\n      label: A\n```\n"
        ),
        "unreferenced": "# Not included\n\n[[missing]]\n",
    }
    shared_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8xoAAAAASUVORK5CYII="
    )
    (root / "shared.png").write_bytes(shared_image)
    notes["parent"] += "\n![Shared image](shared.png)\n"
    notes["child"] += "\n![Shared image](shared.png)\n"
    for badge in ("obsidian", "html"):
        (root / f"{badge}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="20"><rect width="60" height="20"/></svg>',
            encoding="utf-8")
    for name, source in notes.items():
        (root / f"{name}.md").write_text(source, encoding="utf-8")
    manifest = root / "manifest.md"
    manifest.write_text(
        "---\ntitle: Test document\n"
        "subtitle: 'Bridge **subtitle** ![Obsidian](obsidian.svg) ![HTML](html.svg)'\n"
        "status: active\nowners: {team: [Ada, Lin]}\n"
        "---\n"
        "- [[parent|Parent]]\n  - [[child|Child]]\n    - [[node|Node]]\n"
        "- [[glossary|Glossary]]\n- [[tags|Tags]]\n- [[references|References]]\n"
        "\n> [!important]\n> Abstract prose.\n"
        "\n```base\nfilters: 'note[\"bottom line\"] != null'\n"
        "views:\n  - type: table\n    name: Conclusions\n    order: [chapter, bottom line]\n"
        "obsHtml: {records: chapter}\n```\n"
        "\n## Metadata\n"
        "\n```base\nfilters:\n  not:\n    or:\n      - 'key == \"title\"'\n      - 'key == \"subtitle\"'\n"
        "views:\n  - type: table\n    name: Metadata\n    order: [key, value]\n"
        "obsHtml: {records: documentMetadata}\n```\n",
        encoding="utf-8",
    )


def artifact_change(root: Path) -> None:
    """test_artifact_changes.py's artifact_html: two notes with a property editor and a Base."""
    (root / "manifest.md").write_text("---\ntitle: Design notes\n---\n- [[one]]\n- [[two]]\n", encoding="utf-8")
    (root / "sample.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="100" viewBox="0 0 240 100">'
        '<rect width="240" height="100" fill="#ddd"/>'
        '<path d="M20 80L80 50L140 65L220 20" fill="none" stroke="#135" stroke-width="4"/>'
        '</svg>', encoding="utf-8",
    )
    for slug in ("one", "two"):
        (root / f"{slug}.md").write_text(
            "---\nexplanation: Original\nstatus: draft\n---\n"
            f"# {slug.title()}\n\nReviewable text.\n\n![Sample](sample.svg)\n\n"
            "```property-editor\nversion: 1\nfield: explanation\nlabel: Explanation\n```\n\n"
            "```base\nobsHtml: {records: note}\nviews:\n"
            "  - type: table\n    order: [title, status, explanation]\n```\n", encoding="utf-8",
        )


def _base(filters: str, order: str, records: str = "") -> str:
    profile = f"obsHtml: {{records: {records}}}\n" if records else ""
    return (f"```base\nfilters:\n  and: [{filters}]\nviews:\n  - type: table\n    order: [{order}]\n"
            f"{profile}```\n\n")


def projections(root: Path) -> None:
    """test_record_projections.py's projected vault. Changed: the manifest lists the marked note,
    whose marks reach the tag rows only when the core includes it (the interim read every note)."""
    (root / "extra").mkdir()
    (root / "manifest.md").write_text("- [[registers]]\n- [[marked]]\n", encoding="utf-8")
    (root / "registers.md").write_text(
        "# Registers\n\nCheck the register. #mark/risk/register_check\n\n"
        + _base("'status == \"approved\"'", "term", "glossary")
        + _base("'sourcePath == \"extra/located.md\"'", "title", "note")
        + _base("'slug == \"custom\"'", "title", "note")
        + _base("'slug == \"slugged\"'", "title", "note")
        + _base("'type == \"open_point\"'", "label", "tag")
        + _base("'kind == \"evidence\"'", "file.name")
        + _base("'type == \"risk\"'", "label", "tag"),
        encoding="utf-8",
    )
    (root / "glossary.md").write_text(
        "---\nkind: glossary\nterm: Datum\ndefinition: A reference.\nstatus: approved\n---\n# Datum\n",
        encoding="utf-8",
    )
    (root / "draft-term.md").write_text(
        "---\nkind: glossary\nterm: Draft\ndefinition: Not yet.\nstatus: draft\n---\n# Draft\n",
        encoding="utf-8",
    )
    (root / "extra" / "located.md").write_text("---\nkind: other\n---\n# Located\n", encoding="utf-8")
    (root / "extra" / "elsewhere.md").write_text("---\nkind: other\n---\n# Elsewhere\n", encoding="utf-8")
    (root / "slugged.md").write_text(
        "---\nkind: evidence\nslug: custom\ntags: [a, b]\nnested: {owner: Ann}\nempty: []\n"
        "blank: {}\nitems: [{name: x}, {name: y}]\n---\n# Slugged\n",
        encoding="utf-8",
    )
    (root / "marked.md").write_text(
        "---\ntype: risk\n---\n# Marked\n\nWatch the datum. #mark/open_point/datum_watch\n",
        encoding="utf-8",
    )


HELP = (
    "Keep the **original evidence**.\n\n"
    "- Read [[target|the canonical instructions]].\n"
    "- Open [the official export](https://example.org/export).\n"
    "- Download [the source archive](obs-source:archive).\n\n"
    '<script>window.helpInjected = true</script>'
)


def table_help(root: Path) -> None:
    """test_table_help_browser.py's help fixture."""
    spec = {
        "filters": 'kind == "evidence"',
        "properties": {
            "replace": {"obsHtml": {"icon": {
                "name": "replace", "label": "Replace evidence", "action": "replaceEvidence",
                "helpProperty": "instructions", "help": "Select the exported file, not a screenshot.",
            }}},
            "help": {"obsHtml": {"icon": {
                "name": "help", "label": "Evidence help", "helpProperty": "instructions",
            }}},
            "plain": {"obsHtml": {"icon": {
                "name": "help", "label": "Plain help", "help": "Plain text <em>is not HTML</em>.",
            }}},
            "missing": {"obsHtml": {"icon": {
                "name": "upload", "label": "Unavailable import", "unavailable": "No importer",
            }}},
        },
        "views": [{"type": "table", "order": ["title", "replace", "help", "plain", "missing"]}],
    }
    (root / "manifest.md").write_text("- [[chapter]]\n- [[target]]\n", encoding="utf-8")
    (root / "chapter.md").write_text(
        "# Evidence\n\n```base\n" + yaml.safe_dump(spec, sort_keys=False) + "```\n", encoding="utf-8")
    (root / "target.md").write_text("# Instructions\n\nCanonical instructions are kept here.\n", encoding="utf-8")
    (root / "evidence.md").write_text(
        "---\n" + yaml.safe_dump({"kind": "evidence", "instructions": HELP}, sort_keys=False) + "---\n",
        encoding="utf-8")


def structural(root: Path) -> None:
    """test_structural_nodes.py's vault: every Markdown construct the core emits as a structural node."""
    (root / "manifest.md").write_text("- [[formatting]]\n", encoding="utf-8")
    (root / "formatting.md").write_text(
        "---\nowner: {name: '*Ada* **Lovelace**'}\ntags: ['~~old~~', plain]\ncount: 3\n---\n"
        "# Formatting\n\n"
        "Plain, **strong *emphasis inside* and ~~struck~~**, *emphasis **strong inside***, "
        "~~struck **strong *all three***~~ and inline $x^2$ math.\n\n"
        "$$\nE = mc^2\n$$\n\n"
        "> A quoted **line**.\n\n"
        "| Left | Center | Right |\n|:---|:---:|---:|\n| a | *b* | 3 |\n\n"
        "---\n\n"
        "> [!note]\n> Untitled note body.\n",
        encoding="utf-8",
    )


VAULTS = {"complete": complete, "artifact-change": artifact_change, "projections": projections,
          "table-help": table_help, "structural": structural}


def main(core: Path) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        capabilities = work / "capabilities.json"
        subprocess.run(["uv", "run", "python", "-m", "obs.capabilities", "--notes", "spec/capabilities",
                        "--output", str(capabilities)], cwd=core, check=True)
        for name, write in VAULTS.items():
            root = work / name
            root.mkdir()
            write(root)
            subprocess.run(["uv", "run", "obs-document", "--document", str(HERE / "documents" / f"{name}.json"),
                            "--source", str(root / "manifest.md"), "--capability-reference", str(capabilities)],
                           cwd=core, check=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("test/fixtures/build_documents.py: usage: build_documents.py <obs checkout>. Remedy: "
                         "name an obs checkout whose core accepts obsHtml keys in Bases.")
    main(Path(sys.argv[1]).resolve())
