"""Write the vaults of the moved DOM contracts and build their Documents with the obs core.

Reader: whoever changes a vault below or regenerates ``test/fixtures/documents``.

The tests read the committed Documents (``documents/<name>.json``); test_fixture_documents.py
builds every vault with the current core each run and fails on a refused vault or a stale
Document, so a core change cannot hide behind them. The
vaults are the interim adapter's test vaults in obs (test_browser.py, test_artifact_changes.py,
test_record_projections.py, test_table_help_browser.py), changed where a docstring says so.
Regenerate after changing a vault, with an obs checkout whose core reads the ``obs`` keys of
Bases (input-model#Core and adapter namespaces; the Documents validate against the core's schema,
which test_moved_dom_contracts.py checks)::

    uv run python test/fixtures/build_documents.py <obs checkout> [vault ...]

Name vaults to rebuild only those (the keys of ``VAULTS``); without one it rebuilds all. A build
never reaches the network: a remote image fails it, and so does a Document with diagnostics, so
nothing environment-specific is committed.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml


HERE = Path(__file__).parent


def complete(root: Path) -> None:
    """test_complete_document_dom_interactions. Changed: the glossary links its BLUF note, which
    the core includes only when linked (the interim included every glossary note); the subtitle
    badges are vault files, so the Document carries their bytes without a network fetch; the
    references are two registers, whose views declare the members, since only a register carries
    the core's rows (the interim read Base-level members of fences)."""
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
            '# Glossary\n\nSee [[bluf]].\n\n```base\nobs: {records: glossary}\n'
            "views:\n  - type: table\n    order: [term, definition]\n```\n\n"
            "```base\nfilters: 'table == \"abbreviations\"'\n"
            "properties:\n  term:\n    displayName: Term\n"
            "  citation:\n    displayName: Citation\n"
            "views:\n  - type: table\n    order: [term, citation]\nobs: {records: glossary}\n```\n"
        ),
        "tags": (
            '# Tags\n\n```base\nobs: {records: tag}\n'
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
            "\n```base\nobs: {records: glossary}\n"
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
        "references": "# References\n\n![[numbered.base]]\n\n![[lettered.base]]\n",
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
    (root / "numbered.base").write_text(
        "filters: 'kind == \"reference\"'\n"
        "properties:\n  obsHtml.label:\n    displayName: No.\n"
        "views:\n  - type: table\n    order: [obsHtml.label, document, description]\n"
        "    obs:\n      members:\n        - path: reference.md\n          label: '[1]'\n"
        "        - path: quiet-reference.md\n          label: '[2]'\n", encoding="utf-8")
    (root / "lettered.base").write_text(
        "filters: 'kind == \"reference\"'\n"
        "views:\n  - type: table\n    order: [obsHtml.label, document]\n"
        "    obs:\n      members:\n        - path: quiet-reference.md\n          label: B\n"
        "        - path: reference.md\n          label: A\n", encoding="utf-8")
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
        "obs: {records: chapter}\n```\n"
        "\n## Metadata\n"
        "\n```base\nfilters:\n  not:\n    or:\n      - 'key == \"title\"'\n      - 'key == \"subtitle\"'\n"
        "views:\n  - type: table\n    name: Metadata\n    order: [key, value]\n"
        "obs: {records: documentMetadata}\n```\n",
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
            "```base\nobs: {records: note}\nviews:\n"
            "  - type: table\n    order: [title, status, explanation]\n```\n", encoding="utf-8",
        )


def _base(filters: str, order: str, records: str = "") -> str:
    profile = f"obs: {{records: {records}}}\n" if records else ""
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


def registers(root: Path) -> None:
    """test_registers.py's vault: register embeds whose rows the core selects. ``points.base`` has
    two views with different view-level members, embedded whole and by one view heading;
    ``types.base`` has one view per record type."""
    (root / "manifest.md").write_text(
        "---\ntitle: Registers\nstatus: draft\nhistory:\n  - {version: '1', date: '2026-01-01', author: Ann, change: First}\n"
        "  - {version: '2', author: Ann, change: Second}\n---\n- [[points]]\n- [[second]]\n- [[types]]\n",
        encoding="utf-8",
    )
    (root / "points.base").write_text(
        "filters: 'kind == \"point\"'\n"
        "views:\n"
        "  - type: table\n    name: Labelled\n    order: [file.name, obsHtml.label]\n"
        "    obs:\n      members:\n        - path: c-point.md\n          label: C\n"
        "        - path: a-point.md\n          label: A\n"
        "  - type: table\n    name: Second\n    order: [file.name]\n"
        "    obs:\n      members:\n        - path: b-point.md\n",
        encoding="utf-8",
    )
    (root / "types.base").write_text(
        "views:\n"
        "  - {type: table, name: Notes, filters: 'kind == \"point\"', order: [file.name], obs: {records: note}}\n"
        "  - {type: table, name: Chapters, order: [chapter], obs: {records: chapter}}\n"
        "  - {type: table, name: Tags, filters: 'type == \"risk\"', order: [label, text], obs: {records: tag}}\n"
        "  - {type: table, name: Glossary, order: [term, definition], obs: {records: glossary}}\n"
        "  - {type: table, name: Metadata, filters: 'key != \"title\"', order: [key, value],"
        " obs: {records: documentMetadata}}\n"
        "  - {type: table, name: History, order: [version, date, change], obs: {records: documentHistory}}\n",
        encoding="utf-8",
    )
    (root / "points.md").write_text("# Points\n\nAll views.\n\n![[points.base]]\n", encoding="utf-8")
    (root / "second.md").write_text(
        "# Second\n\nOne view. #mark/risk/second_risk\n\n![[points.base#Second]]\n", encoding="utf-8")
    (root / "types.md").write_text(
        "# Types\n\nSee [[datum]]. #mark/open_point/types_open\n\n![[types.base]]\n", encoding="utf-8")
    for name in ("a", "b", "c", "d"):
        (root / f"{name}-point.md").write_text(f"---\nkind: point\n---\n# Point {name.upper()}\n", encoding="utf-8")
    (root / "datum.md").write_text(
        "---\nkind: glossary\nterm: Datum\ndefinition: A reference.\n---\n# Datum\n", encoding="utf-8")


def callouts(root: Path) -> None:
    """test_callouts_embeds_attachments.py's vault: a titled callout whose body holds a list with a
    wikilink and a nested callout with a link."""
    (root / "manifest.md").write_text("- [[guide]]\n- [[target]]\n", encoding="utf-8")
    (root / "guide.md").write_text(
        "# Guide\n\n"
        "> [!warning] Check the limits\n"
        "> - first item\n"
        "> - see [[target]]\n"
        ">\n"
        "> > [!tip]\n"
        "> > Nested **tip** with [a link](https://example.org).\n",
        encoding="utf-8",
    )
    (root / "target.md").write_text("# Target\n\nTarget text.\n", encoding="utf-8")


def cards(root: Path) -> None:
    """test_cards_counts_quantities.py's vault: a card whose body holds a Base fence and a nested
    cards fence; a card with every metric field (two quantity notes for ``from`` and
    ``secondary``, a trusted projection); and a card whose metrics are a series from a note's list."""
    point = [{"field": "kind", "equals": "point"}]
    inner = {"version": 1, "cards": [{"title": "Inner", "body": "Nested **body** with [[target]]."}]}
    outer = {"version": 1, "cards": [
        {"title": "Outer", "body": (
            "Points as a table:\n\n```base\nfilters: 'kind == \"point\"'\n"
            "views:\n  - type: table\n    order: [file.name, status]\n```\n\n"
            "```cards\n" + json.dumps(inner) + "\n```\n")},
        {"title": "Metrics", "body": "", "metricStyle": "lines", "metrics": [
            {"key": "open-share", "label": "Open share", "where": [{"field": "status", "equals": "open"}],
             "denominator": point, "link": "#target", "tone": "neutral",
             "toneRules": [{"value": "remaining", "when": "positive", "tone": "warning"}]},
            {"label": "Points (open)", "from": "counts/points", "where": [], "secondary": "counts/open",
             "link": "#overview", "secondaryLink": "#target", "tone": "negative",
             "toneRules": [{"value": "secondary", "when": "zero", "tone": "positive"}]},
            {"label": "Reviewed open", "where": [{"field": "status", "equals": "open"}], "tone": "positive",
             "obs": {"projection": "review"}}]},
        {"title": "Series", "body": "", "metricStyle": "pills", "obs": {"metricsFrom": {
            "sourceNote": "groups", "property": "groups.list", "labelProperty": "name",
            "distinctProperty": "field", "where": point, "tone": "positive",
            "toneRules": [{"value": "primary", "when": "zero", "tone": "negative"}],
            "link": {"note": "overview", "groupProperty": "status"}}}},
    ]}
    (root / "manifest.md").write_text("- [[overview]]\n- [[target]]\n", encoding="utf-8")
    (root / "overview.md").write_text("# Overview\n\n```cards\n" + json.dumps(outer) + "\n```\n",
                                      encoding="utf-8")
    (root / "target.md").write_text("# Target\n\nTarget text.\n", encoding="utf-8")
    (root / "groups.md").write_text(
        "---\ngroups:\n  list:\n    - {name: open, field: owner}\n    - {name: closed, field: reviewer}\n---\n",
        encoding="utf-8")
    (root / "counts").mkdir()
    (root / "counts" / "points.md").write_text(
        "---\nkind: quantity\naliases: [pointCount]\nsource: '[[target]]'\n"
        "query: {where: [{field: kind, equals: point}]}\n---\n", encoding="utf-8")
    (root / "counts" / "open.md").write_text(
        "---\nkind: quantity\naliases: [openCount]\nsource: '[[target]]'\n"
        "query: {from: counts/points, where: [{field: status, equals: open}]}\n---\n", encoding="utf-8")
    for name, status, owner in (("a", "open", "ada"), ("b", "closed", "lin"), ("c", "open", "lin")):
        (root / f"{name}-point.md").write_text(
            f"---\nkind: point\nstatus: {status}\nowner: {owner}\n---\n# Point {name}\n", encoding="utf-8")

RESPONSE = {"schemaVersion": 1, "id": "response", "data": {"traces": [{"label": "measured", "x": [0, 1, 2], "y": [1, 4, 9]}, {"label": "model", "x": [0, 1, 2], "y": [1, 3, 8], "mode": "lines+markers"}]}, "panels": [{"id": "main", "bounds": {"x": 0, "y": 0, "width": 720, "height": 320}, "grid": {"row": 0, "column": 0, "rowSpan": 1, "columnSpan": 1}, "axes": [{"id": "time", "scale": "linear", "limits": {"minimum": 0, "maximum": 2}, "label": "Time"}, {"id": "value", "scale": "log", "limits": {"minimum": 1, "maximum": 10}, "label": "Value"}]}], "provenance": {"command": ["generate-response"]}}
FLOW = {"schemaVersion": 1, "id": "flow", "data": {"sankey": {"version": 1, "nodes": [{"id": "in", "label": "Input", "stage": 0}, {"id": "out", "label": "Output", "stage": 1}, {"id": "loss", "label": "Loss", "stage": 1}], "links": [{"source": "in", "target": "out", "value": 8}, {"source": "in", "target": "loss", "value": 2}]}}, "panels": [{"id": "flow", "bounds": {"x": 0, "y": 0, "width": 700, "height": 680}, "grid": {"row": 0, "column": 0, "rowSpan": 1, "columnSpan": 1}, "axes": [{"id": "stage", "scale": "linear", "limits": {"minimum": 0, "maximum": 1}, "label": "Stage"}]}], "provenance": {"command": ["generate-flow"]}}
CARDS = '{"version": 1, "cards": [{"title": "Items", "body": "Ranked: [[rankedItems]].", "metrics": [{"label": "Items", "where": [{"field": "kind", "equals": "item"}]}, {"label": "Ranks", "from": "ranked", "where": [], "distinct": "rank"}]}]}'


def document(root: Path) -> None:
    """The adapter's main fixture (conftest.py's FIXTURE): a paged manifest with a cover, a chapter
    with a nested chapter, a Base and command fences, an appendix with figures, a callout, cards
    and a register, a count quantity and a glossary note with a property editor. Its one
    diagnostic, the link to the missing note, is the one the CLI test reads on stderr."""
    (root / "images").mkdir()
    (root / "images" / "logo.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="))
    (root / "guide").mkdir()
    (root / "manifest.md").write_text(
        "---\ntitle: Fixture document\ndocument type: Specification\norganization: Example org\n"
        "product: {name: Widget, version: '2'}\nauthors: [Ada, Lin]\n"
        "obsHtml:\n  layout: paged\n  print: {paper: Letter, margin: 15mm}\n"
        "  pages: [{page: cover}, {page: contents, title: Contents}, {page: abstract, title: Abstract}]\n"
        "obs: {document: true}\n---\n"
        "- [[intro]]\n  - [[guide/usage]]\n- [[appendix]]\n\nA short <abstract>.\n", encoding="utf-8")
    (root / "intro.md").write_text(
        "---\nowner: Ada\ntags: [a, b]\n---\n# Intro\n\n"
        "See [[guide/usage#Details|the details]], [the site](https://example.org/?a=1&b=2) and "
        "![a logo](images/logo.png). [[missing|gone]] `x < y` #mark/risk/limit\n\n"
        "![[guide/usage]]\n\n1. one\n2. two\n\n"
        "```base\nfilters:\n  and: ['kind == \"item\"', 'rank != null']\n"
        "properties:\n  item.name: {displayName: Name}\n"
        "views:\n  - type: table\n    name: Items\n    order: [file.name, item.name, rank]\n"
        "    sort: [{property: rank, direction: DESC}]\n```\n\n"
        "```cmd\necho derived\n```\n\n```cmd silent\necho produced > produced.txt\n```\n", encoding="utf-8")
    (root / "guide" / "usage.md").write_text("## Usage\n\n### Details\n\nBody.\n", encoding="utf-8")
    (root / "appendix.md").write_text(
        "No heading here. See [[datum]] and [[other]].\n\n"
        f"```figure\nversion: 1\nkind: plot\ncontent: {json.dumps(RESPONSE)}\n```\n\n"
        f"```figure\nversion: 1\nkind: plot\ncontent: {json.dumps(FLOW)}\n```\n\n"
        "> [!warning] Check the limits\n> The badge ![Logo](images/logo.png) marks it.\n\n"
        f"```cards\n{CARDS}\n```\n\n![[items.base]]\n", encoding="utf-8")
    (root / "items.base").write_text(
        "filters: 'kind == \"item\"'\nviews:\n"
        "  - {type: table, name: Items, order: [file.name, rank]}\n"
        "  - {type: table, name: Ranked, filters: 'rank != null', order: [file.name, rank]}\n", encoding="utf-8")
    (root / "ranked.md").write_text(
        "---\nkind: quantity\naliases: [rankedItems]\nsource: '[[intro]]'\n"
        "query: {where: [{field: kind, equals: item}], distinct: rank}\n---\n# Ranked items\n", encoding="utf-8")
    (root / "datum.md").write_text(
        "---\nkind: glossary\nterm: Datum\ndefinition: A **reference** point, see [[intro]].\n"
        "status: approved\n---\n```property-editor\nversion: 1\nfield: status\nlabel: Status\n```\n\n"
        "# Datum\n", encoding="utf-8")
    for name, fields in (("alpha", "rank: 1\nitem: {name: Alpha}"), ("beta", "rank: 2\nitem: {name: Beta}"),
                         ("gamma", "item: {name: Unranked}")):
        (root / f"{name}.md").write_text(f"---\nkind: item\n{fields}\n---\n", encoding="utf-8")
    (root / "other.md").write_text("---\nkind: other\nrank: 3\n---\n", encoding="utf-8")


def property_editor_projection(root: Path) -> None:
    """A property editor with a static projection (obs capabilities/property-editors), which the
    core carries in the node's attrs.spec."""
    (root / "manifest.md").write_text("- [[finding]]\n", encoding="utf-8")
    (root / "finding.md").write_text(
        '---\nexplanation: Original\nstatus: explained\naccepted: "yes"\noutputs: [System]\n---\n'
        "# Finding\n\n```property-editor\nversion: 1\nfield: explanation\nlabel: Review\nprojection:\n"
        '  blank: {status: finding, accepted: "no", outputs: []}\n'
        '  nonblank: {status: explained, accepted: "yes", outputs: [System, Labels]}\n```\n',
        encoding="utf-8",
    )


GALLERY_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
               '<rect width="20" height="20" fill="#587894"/><circle cx="30" cy="10" r="8" fill="#73869a"/></svg>')


def figures(root: Path) -> None:
    """One figure of each kind (test_figure_frame.py), captioned and numbered by chapter, each with
    a block id; the image and the Sankey read their content from files, the others inline. Not a
    moved interim vault: it is the adapter's own fixture of the one figure frame."""
    (root / "manifest.md").write_text(
        "---\ntitle: Figures\nobsHtml: {figures: {numbering: chapter}}\n---\n- [[gallery]]\n", encoding="utf-8")
    (root / "drawing.svg").write_text(GALLERY_SVG, encoding="utf-8")
    (root / "flow.json").write_text(json.dumps(FLOW["data"]["sankey"]), encoding="utf-8")
    fences = {
        "image": "source: drawing.svg",
        "svg": f"content: {json.dumps(GALLERY_SVG)}\npanels: [{{id: left, title: Square, box: [0, 0, 20, 20]}}]",
        "sankey": "source: flow.json\ncountLabels: {unit: items}",
        "plot": f"content: {json.dumps(RESPONSE)}",
    }
    (root / "gallery.md").write_text("# Gallery\n\n" + "".join(
        f"```figure\nversion: 1\nkind: {kind}\ncaption: The {kind} figure, see [[gallery]].\n{fence}\n```\n"
        f"^{kind}-figure\n\n" for kind, fence in fences.items()), encoding="utf-8")


VAULTS = {"figures": figures, "document": document, "complete": complete, "artifact-change": artifact_change, "projections": projections,
          "table-help": table_help, "structural": structural, "callouts": callouts,
          "registers": registers, "cards": cards,
          "property-editor-projection": property_editor_projection}
RUNS_COMMANDS = {"document"}
"""The vaults whose cmd fences the build runs (obs-document --execute-commands): ``echo`` only."""
DIAGNOSED = {"document"}
"""The vaults whose Document keeps its diagnostics: those name vault notes only, never the build
machine's folders, which the build checks."""


# Runs obs-document in the core's environment with the core's one network read refused.
DRIVER = """
import sys
from obs import document, vault
def fetch(url):
    raise SystemExit(f"test/fixtures/build_documents.py: a vault embeds the remote image {url}, which a "
                     "fixture build never fetches. Remedy: save the image into the vault and embed it locally.")
vault.fetch_remote = fetch
sys.exit(document.main(sys.argv[1:]))
"""


def build(core: Path, names: list[str], output: Path, offline: bool = False) -> dict[str, str]:
    """Build the named vaults' Documents (all without names) into ``output`` with the core, side by
    side; the core's message for each vault it refuses. ``offline`` keeps uv off the network."""
    uv = ["uv", "run", *(["--offline"] if offline else []), "--project", str(core)]
    refused: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        capabilities = work / "capabilities.json"
        result = subprocess.run([*uv, "python", "-m", "obs.capabilities", "--notes", "spec/capabilities",
                                 "--output", str(capabilities)], cwd=core, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"test/fixtures/build_documents.py: the core could not build its capability "
                               f"reference in {core}: {(result.stderr or result.stdout).strip()}")

        def one(name: str) -> None:
            root = work / name
            root.mkdir()
            VAULTS[name](root)
            document = output / f"{name}.json"
            result = subprocess.run([*uv, "python", "-c", DRIVER, "--document", str(document),
                                     "--source", str(root / "manifest.md"),
                                     "--capability-reference", str(capabilities),
                                     *(["--execute-commands"] if name in RUNS_COMMANDS else [])],
                                    cwd=core, capture_output=True, text=True)
            if result.returncode:
                # uv's own notices start with "warning:"; the core's lines name the core.
                refused[name] = "\n".join(line for line in (result.stderr or result.stdout).splitlines()
                                          if line.strip() and not line.startswith("warning:"))
                return
            diagnostics = json.loads(document.read_text(encoding="utf-8"))["diagnostics"]
            if diagnostics and (name not in DIAGNOSED or any(str(work) in item["message"] for item in diagnostics)):
                refused[name] = (f"the {name} Document has diagnostics {diagnostics}, which a committed "
                                 f"fixture must not carry. Remedy: change the {name} vault so the core "
                                 "builds it without them.")

        with ThreadPoolExecutor() as pool:
            list(pool.map(one, names or VAULTS))
    return refused


def main(core: Path, names: list[str]) -> None:
    refused = build(core, names, HERE / "documents")
    if refused:
        raise SystemExit("\n".join(f"test/fixtures/build_documents.py: the core refuses the {name} vault: "
                                   f"{message}" for name, message in refused.items()))


if __name__ == "__main__":
    unknown = sorted(set(sys.argv[2:]) - set(VAULTS))
    if len(sys.argv) < 2 or unknown:
        raise SystemExit("test/fixtures/build_documents.py: usage: build_documents.py <obs checkout> [vault ...]"
                         f"{'; unknown vault ' + ', '.join(unknown) if unknown else ''}. Remedy: name an obs "
                         "checkout whose core reads obs keys in Bases, and vaults among "
                         f"{', '.join(VAULTS)} (none builds all).")
    main(Path(sys.argv[1]).resolve(), sys.argv[2:])
