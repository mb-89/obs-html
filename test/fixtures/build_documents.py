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
nothing environment-specific is committed; the fields that hold the build machine's state are set
in one place, ``normalised`` (MACHINE_FIELDS).
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
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
        "A line  \nbroken twice\\\nand a soft\nline.\n\n"
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


POINT_FLOW = {"version": 1, "data": {"where": [{"field": "kind", "equals": "point"}]}, "nodes": [
    {"id": "points", "label": "Points", "stage": 0, "records": {"where": [{"field": "owner", "equals": "lin"}]}},
    {"id": "open", "label": "Open", "stage": 1, "records": {"where": [{"field": "status", "equals": "open"}]},
     "unique": "owner"},
    {"id": "closed", "label": "Closed", "stage": 1, "records": {"where": [{"field": "status", "equals": "closed"}]},
     "unique": "assignees"}], "links": [
    {"source": "points", "target": "open", "value": 2, "where": [{"field": "status", "equals": "open"}]},
    {"source": "points", "target": "closed", "value": 1, "where": [{"field": "status", "equals": "closed"}]}]}


def cards(root: Path) -> None:
    """test_cards_counts_quantities.py's vault: a card whose body holds a Base fence and a nested
    cards fence; a card with every metric field (two quantity notes for ``from`` and
    ``secondary``, a trusted projection); a card whose metrics are a series from a note's list;
    and a dynamic Sankey over the same points, one node of which narrows its incident links by its
    own ``records`` and one of which has more distinct ``unique`` items than rows, so every kind of
    count has a drill-down."""
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
             "link": "#overview", "obs": {"projection": "review"}}]},
        {"title": "Series", "body": "", "metricStyle": "pills", "obs": {"metricsFrom": {
            "sourceNote": "groups", "property": "groups.list", "labelProperty": "name",
            "distinctProperty": "field", "where": point, "tone": "positive",
            "toneRules": [{"value": "primary", "when": "zero", "tone": "negative"}],
            "link": {"note": "overview", "groupProperty": "status"}}}},
    ]}
    (root / "manifest.md").write_text("- [[overview]]\n- [[target]]\n", encoding="utf-8")
    (root / "overview.md").write_text(
        "# Overview\n\n```cards\n" + json.dumps(outer) + "\n```\n\n"
        "```figure\nversion: 1\nkind: sankey\ncaption: Points by status.\nsource: flow.json\n```\n^points\n",
        encoding="utf-8")
    (root / "flow.json").write_text(json.dumps(POINT_FLOW), encoding="utf-8")
    (root / "target.md").write_text(
        "# Target\n\nTarget text.\n\n```base\nfilters: 'kind == \"point\"'\nviews:\n  - type: table\n"
        "    order: [file.name, status]\n```\n", encoding="utf-8")
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
    for name, status, owner, extra in (("a", "open", "ada", ""), ("b", "closed", "lin", "assignees: [kim, max]\n"),
                                       ("c", "open", "lin", "")):
        (root / f"{name}-point.md").write_text(
            f"---\nkind: point\nstatus: {status}\nowner: {owner}\n{extra}---\n# Point {name}\n", encoding="utf-8")

RESPONSE = {"schemaVersion": 1, "id": "response", "data": {"traces": [{"label": "measured", "x": [0, 1, 2], "y": [1, 4, 9]}, {"label": "model", "x": [0, 1, 2], "y": [1, 3, 8], "mode": "lines+markers"}]}, "panels": [{"id": "main", "bounds": {"x": 0, "y": 0, "width": 720, "height": 320}, "grid": {"row": 0, "column": 0, "rowSpan": 1, "columnSpan": 1}, "axes": [{"id": "time", "scale": "linear", "limits": {"minimum": 0, "maximum": 2}, "label": "Time"}, {"id": "value", "scale": "log", "limits": {"minimum": 1, "maximum": 10}, "label": "Value"}]}], "provenance": {"command": ["generate-response"]}}
FLOW = {"schemaVersion": 1, "id": "flow", "data": {"sankey": {"version": 1, "nodes": [{"id": "in", "label": "Input", "stage": 0}, {"id": "out", "label": "Output", "stage": 1}, {"id": "loss", "label": "Loss", "stage": 1}], "links": [{"source": "in", "target": "out", "value": 8}, {"source": "in", "target": "loss", "value": 2}]}}, "panels": [{"id": "flow", "bounds": {"x": 0, "y": 0, "width": 700, "height": 680}, "grid": {"row": 0, "column": 0, "rowSpan": 1, "columnSpan": 1}, "axes": [{"id": "stage", "scale": "linear", "limits": {"minimum": 0, "maximum": 1}, "label": "Stage"}]}], "provenance": {"command": ["generate-flow"]}}
CARDS = '{"version": 1, "cards": [{"title": "Items", "body": "Ranked: [[rankedItems]].", "metrics": [{"label": "Items", "where": [{"field": "kind", "equals": "item"}]}, {"label": "Ranks", "from": "ranked", "where": [], "distinct": "rank"}]}]}'


def document(root: Path) -> None:
    """The adapter's main fixture (conftest.py's FIXTURE): a paged manifest with a cover, a chapter
    with a nested chapter, a Base and command fences, an appendix with figures (a Mermaid and a
    PlantUML diagram among them, an equation figure and a decision figure), a callout, cards and a register, a count quantity and a glossary note with a property editor. Its one
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
        f"```cards\n{CARDS}\n```\n\n![[items.base]]\n\n"
        "```mermaid\ngraph LR\n  Item --> Rank\n```\n\n```plantuml\n@startuml\nItem -> Rank\n@enduml\n```\n\n"
        f"```figure\nversion: 1\nkind: equations\ncontent:\n{_indent(PARABOLA)}```\n\n"
        "```pugh\ncriteria: [{key: cost, weight: 1, better: lower}]\n"
        "candidates: [{key: now, values: {cost: 2}}, {key: new, values: {cost: 1}}]\n```\n",
        encoding="utf-8")
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


PARABOLA = "equations: y = a*x**2\nvariables:\n  x: {default: 0, range: [-2, 2]}\n  a: {default: 1, range: [0.5, 2]}\n  y: {}\nplot: {x: x, y: y}\n"
"""The small equation figure of the gallery and the main fixture: one exact branch over one sweep."""


def _indent(text: str) -> str:
    return "".join(f"  {line}\n" for line in text.splitlines())


ENGINE_SPEED = ("---\nkind: quantity\nvalue: 3000\nunit: rpm\nrange: [800, 6000]\naliases: [engineSpeed]\n"
                "source: '[[curves]]'\n---\n# Engine speed\n")
EQUATIONS = {
    # block id: the figure's content (the core's test_equation_figures.py shapes)
    "torque": """\
equations: T = T_max*throttle*(1 - (n/n_max)**2)
variables:
  n: "[[engineSpeed]]"
  n_max: {default: 6000, unit: rpm}
  T_max: {default: 250, unit: N*m}
  throttle: {default: 1, range: [0, 1]}
  T: {unit: N*m}
plot:
  x: n
  y: [T, {expression: T*n, axis: secondary}]
  family: {variable: throttle, values: [0.25, 0.5, 1]}
""",
    "saturated": """\
equations: y'' + 2*zeta*w*y' + w**2*Min(Max(y, -1), 1) = w**2*u
variables:
  t: {default: 0, range: [0, 10], unit: s}
  y: {of: t, initial: [0, 0]}
  zeta: {default: 0.3, range: [0.05, 2]}
  w: {default: 2, range: [0.5, 5], unit: 1/s}
  u: {default: 1.5, range: [0, 2]}
plot: {x: t, y: y}
""",
    "quintic": """\
equations: y**5 + y = a
variables:
  a: {default: 2, range: [0, 10]}
  y: {default: 1}
plot: {x: a, y: y}
""",
}


SWEEPS = {
    # block id: a figure with a parallel-coordinates plot, in its own chapter so that it computes
    # only where a test opens that chapter.
    "step": """\
equations: y'' + 2*zeta*w*y' + w**2*y = w**2*u
variables:
  t: {default: 0, range: [0, 10], unit: s}
  y: {of: t, initial: [0, 0]}
  zeta: {default: 0.5, range: [0.1, 1.5]}
  w: {default: 2, range: [1, 3], unit: 1/s}
  u: {default: 1}
plot:
  x: t
  y: y
  parallelCoordinates: true
  grid: {zeta: {values: [0.2, 0.5, 0.8, 1.3]}}
  computed:
    - {name: settling, summary: settlingTime, of: y, tolerance: 0.02}
    - {name: error area, summary: absoluteArea, of: u - y}
""",
    "cap": """\
equations: y = a + b*x + c*x**2
variables:
  x: {default: 0, range: [0, 1]}
  a: {default: 0, range: [0, 1]}
  b: {default: 0, range: [0, 1]}
  c: {default: 0, range: [0, 1]}
  y: {}
plot:
  x: x
  y: y
  grid: {a: {steps: 20}, b: {steps: 20}, c: {steps: 20}}
""",
}


def _equation_chapter(title: str, figures: dict[str, str]) -> str:
    return f"# {title}\n\n" + "".join(
        f"```figure\nversion: 1\nkind: equations\ncaption: The {name} figure.\ncontent:\n{_indent(content)}```\n"
        f"^{name}\n\n" for name, content in figures.items())


def equations(root: Path) -> None:
    """The live equation figures (test_equation_figures_browser.py): the torque family over a
    quantity note's range with a second axis, the saturated oscillator the core leaves as a
    differential system, and an algebraic equation it leaves for Newton's method; in a second
    chapter, a step response swept over a grid with computed axes and a grid of 8000
    combinations above the cap. Not a moved interim vault."""
    (root / "manifest.md").write_text("---\ntitle: Equations\n---\n- [[curves]]\n- [[sweeps]]\n", encoding="utf-8")
    (root / "speed.md").write_text(ENGINE_SPEED, encoding="utf-8")
    (root / "curves.md").write_text(_equation_chapter("Curves", EQUATIONS), encoding="utf-8")
    (root / "sweeps.md").write_text(_equation_chapter("Sweeps", SWEEPS), encoding="utf-8")


DECISION = {
    "title": "Which option", "chosen": "A",
    "criteria": [
        {"key": "err", "label": "Error", "weight": 3, "better": "lower", "tolerance": 0.1, "floor": 0},
        {"key": "speed", "label": "Speed", "weight": 2, "better": "higher", "tolerance": 0.1, "floor": 0},
        {"key": "cost", "label": "Cost of ownership", "weight": 1, "better": "lower", "tolerance": 0.25, "floor": 1},
    ],
    "candidates": [
        {"key": "D", "label": "What runs today", "what": "The datum: nothing changes.",
         "values": {"err": 1, "speed": 10, "cost": 9}, "wins": "Nothing to migrate."},
        {"key": "A", "label": "Precise", "what": "Precise but dear.",
         "values": {"err": 0.4, "speed": 10.5, "cost": 19}, "tieBreak": 2, "losses": ["A new licence", "Training"]},
        {"key": "B", "label": "Quick", "what": "Quick and cheap.",
         "values": {"err": 0.85, "speed": 30, "cost": 4}, "tieBreak": 1, "wins": "Runs on a phone."},
        {"key": "C", "label": "Middling", "values": {"err": 0.95, "speed": 22, "cost": 9}, "tieBreak": 0},
    ],
    "datum": {"prefer": ["D"]},
    "sensitivity": {"seed": 3, "draws": 2000},
    "checklist": [
        {"item": "Does it keep the data in the EU?", "answer": "All of them do.", "pass": True},
        {"item": "Is there a second supplier?", "answer": "Not for this kind of system.", "pass": False},
    ],
}
"""ctrl's test matrix with a fourth option (test/fixtures/pugh-vectors.json, small with C), lettered A
(the datum D), B (ctrl's A), C (ctrl's B) and D (ctrl's C), with names, sentences, wins and losses, a
chosen option that is a runner-up, and a checklist whose failed item names no option, so the totals
stay ctrl's."""
WIDE = {**DECISION, "title": "Many options", "chosen": "O9", "checklist": [
    {"item": "Can we leave it within a month?", "answer": "Not the last two.", "pass": False, "options": ["I", "J"]}],
    "checklistWeight": 2, "candidates": [
    {"key": f"O{index}", "label": f"A long option name number {index}",
     "values": {"err": 1 - index / 20, "speed": 10 + 2 * index, "cost": 9 + 3 * index}} for index in range(10)],
    "datum": {"prefer": ["O0"]}}
"""Ten options, wider than a phone: the matrix scrolls in its own box; a failed checklist item marks the
last two on a Checklist row of weight 2 (test_pugh_figures_browser.py)."""


def pugh(root: Path) -> None:
    """The decision figures (test_pugh_figures_browser.py): ctrl's test matrix with a chosen runner-up,
    and one of ten options. Not a moved interim vault."""
    (root / "manifest.md").write_text("---\ntitle: Decisions\n---\n- [[decisions]]\n", encoding="utf-8")
    (root / "decisions.md").write_text("# Decisions\n\n" + "".join(
        f"```figure\nversion: 1\nkind: pugh\ncaption: The {name} decision.\ncontent: {json.dumps(matrix)}\n```\n"
        f"^{name}\n\n" for name, matrix in (("option", DECISION), ("wide", WIDE))), encoding="utf-8")


GALLERY_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
               '<rect width="20" height="20" fill="#587894"/><circle cx="30" cy="10" r="8" fill="#73869a"/></svg>')


def figures(root: Path) -> None:
    """One figure of each kind (test_figure_frame.py), captioned and numbered by chapter, each with
    a block id; the image, the Sankey and the Mermaid diagram read their content from files, the
    others inline. Not a
    moved interim vault: it is the adapter's own fixture of the one figure frame."""
    (root / "manifest.md").write_text(
        "---\ntitle: Figures\nobsHtml: {figures: {numbering: chapter}}\n---\n- [[gallery]]\n", encoding="utf-8")
    (root / "drawing.svg").write_text(GALLERY_SVG, encoding="utf-8")
    (root / "flow.json").write_text(json.dumps(FLOW["data"]["sankey"]), encoding="utf-8")
    (root / "flow.mmd").write_text("graph LR\n  Draft --> Review\n", encoding="utf-8")
    fences = {
        "image": "source: drawing.svg",
        "svg": f"content: {json.dumps(GALLERY_SVG)}\npanels: [{{id: left, title: Square, box: [0, 0, 20, 20]}}]",
        "sankey": "source: flow.json\ncountLabels: {unit: items}",
        "plot": f"content: {json.dumps(RESPONSE)}",
        "mermaid": "source: flow.mmd",
        "plantuml": "content: |\n  @startuml\n  Draft -> Review : submit\n  @enduml",
        "equations": f"content:\n{_indent(PARABOLA)}",
        "pugh": f"content: {json.dumps(DECISION)}",
    }
    (root / "gallery.md").write_text("# Gallery\n\n" + "".join(
        f"```figure\nversion: 1\nkind: {kind}\ncaption: The {kind} figure, see [[gallery]].\n{fence}\n```\n"
        f"^{kind}-figure\n\n" for kind, fence in fences.items()), encoding="utf-8")


FIGURE_REFERENCES = {
    # paragraph: its Markdown in the second chapter of the figure-references vault
    "single": "Single [[#^d]].",
    "pair": "Pair [[#^d]] and [[#^e]].",
    "run": "Run [[#^d]], [[#^e]] and [[#^f]].",
    "mixed": "Mixed [[#^a]], [[#^b]], [[#^c]], and [[#^e]] or [[#^b|the second]] [[#^c]].",
    "german": "Siehe [[#^a]] und [[#^b]].",
    "plus": "See [[#^a]] plus [[#^b]] and [[#^c]].",
    "labelled": "Labelled [[#^a|the first]].",
    "broken": "Broken [[#^d]]  \n[[#^e]].",
}


def figure_references(root: Path) -> None:
    """Two contents chapters, figures numbered by chapter: the second has six captioned figures
    with block ids and every kind of reference to them (FIGURE_REFERENCES), the first one
    reference across notes (test_figure_references.py). The interim reference reads the same
    fence syntax, so its parity test renders this vault with both. Not a moved interim vault."""
    (root / "manifest.md").write_text(
        "---\ntitle: Figure references\nobsHtml: {figures: {numbering: chapter}}\n---\n- [[one]]\n- [[two]]\n",
        encoding="utf-8")
    (root / "img.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>', encoding="utf-8")
    (root / "one.md").write_text("# One\n\nAcross [[two#^b]].\n", encoding="utf-8")
    (root / "two.md").write_text("# Two\n\n" + "".join(
        f"```figure\nversion: 1\nkind: image\nsource: img.svg\ncaption: Figure {name}.\n```\n^{name}\n\n"
        for name in "abcdef") + "\n\n".join(FIGURE_REFERENCES.values()) + "\n", encoding="utf-8")


def self_link(root: Path) -> None:
    """A whole-note self-link: a note long enough to scroll, whose last paragraph links the note
    itself, and a second chapter. Its code fence has a line too long to wrap, so in review mode
    (the Comments bar open), whose body grows to hold what overflows, the body is wider than a
    narrow reader."""
    (root / "manifest.md").write_text("- [[long]]\n- [[short]]\n", encoding="utf-8")
    prose = "\n\n".join(f"Paragraph {index} of a note long enough to scroll. " * 6 for index in range(30))
    fence = f"```text\n{'a line too long to wrap ' * 6}\n```\n"
    (root / "long.md").write_text(f"# Long\n\n{fence}\n{prose}\n\nAfter all these paragraphs and the wide fence above them, back to the top: [[long]].\n",
                                  encoding="utf-8")
    (root / "short.md").write_text("# Short\n\nBody.\n", encoding="utf-8")


def source_archive(root: Path) -> None:
    """A vault built with obs-document --embed-source that lists one of its two CSS snippets: a
    note with an image, a data file outside the chapters and the snippets in Obsidian's snippet
    folder. test_source_archive.py also builds it with the interim adapter and compares."""
    snippets = root / ".obsidian" / "snippets"
    snippets.mkdir(parents=True)
    (snippets / "house.css").write_text("p { color: rgb(1, 2, 3); }\n", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "values.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "pixel.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="))
    (root / "manifest.md").write_text("---\ntitle: Archive\nobsHtml:\n  cssSnippets: [house]\n---\n- [[intro]]\n",
                                      encoding="utf-8")
    (root / "intro.md").write_text("# Intro\n\nText.\n\n![[pixel.png]]\n", encoding="utf-8")


FEATURE_ITEMS = 24
"""The feature fixture's item notes: more than one table page (cfg.json, tablePageSize)."""
FEATURE_PROSE = "\n\n".join(f"Paragraph {index} of the closing text, which reads on after the content above it. " * 3
                              for index in range(1, 3))
"""Text after a chapter's interactive content, as a real document's chapters have."""


FEATURE_CARDS = {"version": 1, "cards": [
    {"title": "Items", "body": "The table holds [[itemCount]] items.", "metrics": [
        {"label": "Items", "where": [{"field": "kind", "equals": "item"}], "link": "#tables"}]},
    {"title": "Ranks", "body": "Each item has its own rank.", "metrics": [
        {"label": "Ranks", "from": "counts/items", "where": [], "distinct": "rank", "link": "#tables"}]}]}
"""The card group that ends the feature fixture: two cards side by side, each a metric with a link,
the first a quantity link in its body."""


def features(root: Path) -> None:
    """The browser tier's feature fixture (obs quality.md, Testing boundaries): a few chapters in
    which every feature of the registry (features.py, FEATURES, with every part) appears, read in
    both views by the reading script and the covered-control sweep (test_parity_browser.py). It is
    archived (--embed-source) for the source-archive part; a note outside the reading order,
    opened as context, needs popups; the plot figure needs plotting, the equation figure
    equations and the decision figure pugh; the prose chapter, with the decision figure, asks for a
    bless, which needs answers and bless. Its chapters also hold what those checks read in obs's spec: prose with
    links, marks, an image, a callout and nested headings; a paged table of notes outside the contents;
    a figure reference across chapters; a register and a property editor; a card group with metrics
    and a quantity link (FEATURE_CARDS). As in obs's spec, the
    chapters the reading script walks are nested three deep, with headings. Each chapter's
    interactive content is followed by text, as in a real document, but the card group, which ends
    the document, as a summary may. test_features.py fails where
    a registered feature is missing. Not a moved interim vault."""
    (root / "manifest.md").write_text(
        "---\ntitle: Feature fixture\nobsHtml: {figures: {numbering: chapter}}\n---\n"
        "- [[overview]]\n- [[figures]]\n  - [[equations]]\n    - [[tables]]\n"
        "- [[prose]]\n- [[references]]\n", encoding="utf-8")
    (root / "overview.md").write_text(
        "# Overview\n\nEvery reader feature once: [[figures]], [[tables]], [[prose]] and an "
        "[[aside]] outside the reading order.\n", encoding="utf-8")
    (root / "aside.md").write_text("# Aside\n\nA note a link opens as context.\n", encoding="utf-8")
    (root / "drawing.svg").write_text(GALLERY_SVG, encoding="utf-8")
    (root / "figures.md").write_text(
        "# Figures\n\n## Image\n\n```figure\nversion: 1\nkind: image\ncaption: The image figure.\nsource: drawing.svg\n```\n"
        f"^image-figure\n\n## Plot\n\n```figure\nversion: 1\nkind: plot\ncaption: The plot figure.\ncontent: {json.dumps(RESPONSE)}\n```\n"
        f"^plot-figure\n\n{FEATURE_PROSE}\n", encoding="utf-8")
    (root / "equations.md").write_text(
        "# Equations\n\nThe plot figure is [[figures#^plot-figure]].\n\n## Parabola\n\n"
        f"```figure\nversion: 1\nkind: equations\ncaption: The equations figure.\ncontent:\n{_indent(PARABOLA)}```\n"
        f"^equations-figure\n\n{FEATURE_PROSE}\n", encoding="utf-8")
    (root / "tables.md").write_text(
        "# Tables\n\n```base\nfilters: 'kind == \"item\"'\n"
        "properties:\n  description: {displayName: Description}\n"
        "views:\n  - type: table\n    name: Items\n    order: [file.name, rank, description]\n"
        f"    sort: [{{property: rank, direction: ASC}}]\n```\n\n{FEATURE_PROSE}\n", encoding="utf-8")
    for index in range(1, FEATURE_ITEMS + 1):
        (root / f"item-{index:02}.md").write_text(
            f"---\nkind: item\nrank: {index}\ndescription: Item {index} of the paged table, "
            "with a description long enough to wrap in a narrow column.\n---\n", encoding="utf-8")
    (root / "logo.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="))
    (root / "prose.md").write_text(
        "---\nobs: {bless: pending}\n---\n# Prose\n\nSee [[figures#Plot|the plot]], [the site](https://example.org/) and "
        "![a logo](logo.png). `x < y` #mark/risk/limit\n\n"
        "Open question. #mark/question/scope_question\n\n"
        "> [!warning] Check the limits\n> The callout's body links [[tables]].\n\n"
        "## Lists\n\n1. one\n2. two\n\n- a\n- b\n\n## Code\n\n```text\nplain code\n```\n\n"
        "## Decision\n\n```figure\nversion: 1\nkind: pugh\ncaption: The decision figure.\n"
        f"content: {json.dumps(DECISION)}\n```\n^decision-figure\n\n{FEATURE_PROSE}\n", encoding="utf-8")
    (root / "references.md").write_text(
        "---\nstatus: draft\n---\n# References\n\n![[sources.base]]\n\n"
        f"```property-editor\nversion: 1\nfield: status\nlabel: Status\n```\n\n{FEATURE_PROSE}\n\n"
        f"## Summary\n\n```cards\n{json.dumps(FEATURE_CARDS)}\n```\n", encoding="utf-8")
    (root / "counts").mkdir()
    (root / "counts" / "items.md").write_text(
        "---\nkind: quantity\naliases: [itemCount]\nsource: '[[tables]]'\n"
        "query: {where: [{field: kind, equals: item}]}\n---\n", encoding="utf-8")
    (root / "sources.base").write_text(
        "filters: 'kind == \"reference\"'\n"
        "properties:\n  obsHtml.label:\n    displayName: No.\n"
        "views:\n  - type: table\n    order: [obsHtml.label, document, description]\n"
        "    obs:\n      members:\n        - path: source-a.md\n          label: '[1]'\n"
        "        - path: source-b.md\n          label: '[2]'\n", encoding="utf-8")
    for name, text in (("source-a", "[Source A](overview.md)"), ("source-b", "Unlinked source")):
        (root / f"{name}.md").write_text(
            f"---\ndocument: '{text}'\ndescription: A source of the fixture.\nkind: reference\n---\n",
            encoding="utf-8")


VAULTS = {"figures": figures, "equations": equations, "pugh": pugh, "document": document, "complete": complete, "artifact-change": artifact_change, "projections": projections,
          "table-help": table_help, "structural": structural, "callouts": callouts,
          "registers": registers, "cards": cards,
          "property-editor-projection": property_editor_projection, "self-link": self_link,
          "figure-references": figure_references, "source-archive": source_archive,
          "features": features}
RUNS_COMMANDS = {"document"}
"""The vaults whose cmd fences the build runs (obs-document --execute-commands): ``echo`` only."""
EMBEDS_SOURCE = {"source-archive", "features"}
"""The vaults the build archives (obs-document --embed-source)."""
FIXTURE_BUILD = {"repository": "https://github.com/mb-89/obs", "commit": "0" * 40,
                 "lockfiles": {"uv.lock": {"obs": "0.0.0"}},
                 "arguments": ["--adapter", "html", "--destination", "document.html", "--embed-source"]}
"""The build record an archived fixture Document carries in place of the core's: the core records
the commit it runs from, which no committed file can hold, and this build runs without --adapter."""
MACHINE_FIELDS = {("sourceArchive", "build"): FIXTURE_BUILD}
"""Each Document field that holds the build machine's state (its paths, times or commits), by its
JSON path, with the value a committed fixture carries instead; ``normalised`` sets them."""
DIAGNOSED = {"document", "complete", "artifact-change"}
"""The vaults whose Document keeps its diagnostics: those name vault notes only, never the build
machine's folders, which the build checks. complete and artifact-change keep the interim vaults'
images alone in their paragraphs, which the core's figure lint warns about."""


# Runs in the core's environment, with the core's one network read refused: builds the capability
# reference, then each vault's Document with obs-document, one after the other in this one process,
# and writes each one's exit code and output. A job's own error is its output; the others still run.
DRIVER = """
import contextlib, io, json, sys, traceback
from obs import capabilities, document, vault

def fetch(url):
    raise SystemExit(f"test/fixtures/build_documents.py: a vault embeds the remote image {url}, which a "
                     "fixture build never fetches. Remedy: save the image into the vault and embed it locally.")
vault.fetch_remote = fetch

def run(main, arguments):
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            code = main(arguments)
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else 1
            if not isinstance(stop.code, int) and stop.code is not None:
                print(stop.code, file=sys.stderr)
        except Exception:
            code = 1
            traceback.print_exc()
    return {"code": code or 0, "output": output.getvalue()}

jobs = json.loads(open(sys.argv[1], encoding="utf-8").read())
results = {"capabilities": run(capabilities.main, jobs["capabilities"])}
if not results["capabilities"]["code"]:
    results |= {name: run(document.main, arguments) for name, arguments in jobs["documents"].items()}
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(results))
"""


def normalised(document: dict) -> dict:
    """The built Document with every field of MACHINE_FIELDS it has set to the fixture's value: the
    one place that keeps the build machine out of a committed Document."""
    for path, value in MACHINE_FIELDS.items():
        parent = document
        for key in path[:-1]:
            parent = parent.get(key) if isinstance(parent, dict) else None
        if isinstance(parent, dict) and path[-1] in parent:
            parent[path[-1]] = value
    return document


def build(core: Path, names: list[str], output: Path, offline: bool = False,
          run=subprocess.run) -> dict[str, str]:
    """Build the named vaults' Documents (all without names) into ``output`` with the core, in one
    core process (DRIVER); the core's message for each vault it refuses. ``offline`` keeps uv off
    the network."""
    refused: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        capabilities = work / "capabilities.json"
        jobs = {"capabilities": ["--notes", "spec/capabilities", "--output", str(capabilities)], "documents": {}}
        for name in names or VAULTS:
            root = work / name
            root.mkdir()
            VAULTS[name](root)
            jobs["documents"][name] = [
                "--document", str(output / f"{name}.json"), "--source", str(root / "manifest.md"),
                "--capability-reference", str(capabilities),
                *(["--execute-commands"] if name in RUNS_COMMANDS else []),
                *(["--embed-source"] if name in EMBEDS_SOURCE else [])]
        (work / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        result = run(["uv", "run", *(["--offline"] if offline else []), "--project", str(core), "python",
                      "-c", DRIVER, str(work / "jobs.json"), str(work / "results.json")],
                     cwd=core, capture_output=True, text=True)
        if result.returncode or not (work / "results.json").is_file():
            raise RuntimeError(f"test/fixtures/build_documents.py: the core in {core} could not run the fixture "
                               f"build: {(result.stderr or result.stdout).strip()}")
        results = json.loads((work / "results.json").read_text(encoding="utf-8"))
        if results["capabilities"]["code"]:
            raise RuntimeError(f"test/fixtures/build_documents.py: the core could not build its capability "
                               f"reference in {core}: {results['capabilities']['output'].strip()}")
        for name in jobs["documents"]:
            if results[name]["code"]:
                refused[name] = "\n".join(line for line in results[name]["output"].splitlines() if line.strip())
                continue
            document = output / f"{name}.json"
            built = normalised(json.loads(document.read_text(encoding="utf-8")))
            document.write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")
            diagnostics = built["diagnostics"]
            if diagnostics and (name not in DIAGNOSED or any(str(work) in item["message"] for item in diagnostics)):
                refused[name] = (f"the {name} Document has diagnostics {diagnostics}, which a committed "
                                 f"fixture must not carry. Remedy: change the {name} vault so the core "
                                 "builds it without them.")
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
