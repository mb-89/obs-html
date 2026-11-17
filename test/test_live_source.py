"""A Base's live source, obsHtml.liveSource (generic-tables.md, Current data): the build's refusals,
the island the page receives and the capability note's authoring example.

Reader: whoever changes what a Base may declare about where newer values of its rows are read. The
refusals are tested at their field path and owner reference, never their wording (AGENTS.md); the
page's check is live-data.test.js's and test_live_source_browser.py's.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
import yaml

from conftest import CORE_ROOT, ROOT
from documents import chapter, document as build, node
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data, same_artifact_content
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render


CONFIG = load_config()
NOTE = ROOT / "spec" / "capabilities" / "live-data.md"
EXAMPLE = yaml.safe_load(re.search(r"```yaml\n(.*?)```", NOTE.read_text(encoding="utf-8"), re.S)[1])
DECLARATION = EXAMPLE["obsHtml"]["liveSource"]
"""The capability note's example, the declaration the issue states: one source of truth for the tests."""
OWNER = "generic-tables.md, Current data"

ISSUES = [
    {"repo": "widgets", "number": 1, "state": "open", "labels": ["ready"],
     "status": "Next", "kind": "issue"},
    {"repo": "widgets", "number": 2, "state": "closed", "labels": [],
     "status": "Done", "kind": "issue"},
    {"repo": "widgets", "number": 3, "state": "open", "labels": ["running"],
     "status": "Running", "kind": "issue"},
]
RECORDS = ({"id": "tracker", "type": "note", "path": "tracker.md", "fields": {}},
           *({"id": f"widgets-{item['number']}", "type": "note", "path": f"issues/widgets-{item['number']}.md",
              "fields": item} for item in ISSUES))
VIEW = {"type": "table", "name": "Board", "order": ["file.name", "status"], "groupBy": {"property": "status"},
        "obsHtml": {"groupOrder": ["Next", "Running", "Done"]}}


def base(declaration: dict | None = None, **changes: object) -> dict:
    """A Base over the issue notes, with ``declaration`` as its live source unless it is None."""
    spec = {"filters": 'kind == "issue"', "views": [copy.deepcopy(VIEW)], **copy.deepcopy(changes)}
    if declaration is not None:
        spec["obsHtml"] = {**spec.get("obsHtml", {}), "liveSource": copy.deepcopy(declaration)}
    return spec


def fence(spec: dict) -> dict:
    return build("Tracker", chapter("tracker", "Tracker", node("bases", source="", spec=spec)), records=RECORDS)


def register(spec: dict, view: int | None = None) -> dict:
    """A register embedding ``spec`` as issues.base, whole or by one view heading."""
    rows = [[record["id"] for record in RECORDS[1:]] for _ in spec["views"]]
    heading = "" if view is None else spec["views"][view]["name"]
    return build("Tracker", chapter("tracker", "Tracker", node(
        "registers", target="issues.base", heading=heading, base=spec, view=view, rows=rows)), records=RECORDS)


def tables(html: str) -> list[dict]:
    data = decode_artifact_data(html)
    return [table for note in data["notes"] for table in note["tables"]]


def edit(declaration: dict, change) -> dict:
    changed = copy.deepcopy(declaration)
    change(changed)
    return changed


def _set(path: list, value: object):
    def change(declaration: dict) -> None:
        parent = declaration
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
    return change


def _drop(path: list):
    def change(declaration: dict) -> None:
        parent = declaration
        for key in path[:-1]:
            parent = parent[key]
        del parent[path[-1]]
    return change


CONNECTOR, WEB = ["changes", 0], ["changes", 1]
REFUSED_DECLARATIONS = [
    # A schema violation: an unknown key (no key for headers, tokens or credentials exists), a
    # missing one, a refresh below 5 minutes, a tool outside the reviewed enum, more than 5 pages.
    pytest.param(_set(["headers"], {"Authorization": "x"}), "headers", id="schema-unknown-key"),
    pytest.param(_drop(["name"]), "name", id="schema-missing-name"),
    pytest.param(_set(["refreshMinutes"], 4), "refreshMinutes", id="schema-refresh"),
    pytest.param(_set([*CONNECTOR, "tool"], "create_issue"), "changes[0].tool", id="schema-tool"),
    pytest.param(_set([*WEB, "maxPages"], 6), "changes[1].maxPages", id="schema-pages"),
    pytest.param(_set(["changes"], []), "changes", id="schema-no-route"),
    pytest.param(_set(["derive", "status"], [{"keep": True}, {"value": "Done"}]), "derive.status[0]",
                 id="default-case-not-last"),
    # Targets that are no plain name, or names the page or the core reserves.
    pytest.param(_set(["fields", "__proto__"], "x"), "fields.__proto__", id="target-proto"),
    pytest.param(_set(["fields", "constructor"], "x"), "fields.constructor", id="target-constructor"),
    pytest.param(_set(["fields", "1st"], "x"), "fields.1st", id="target-not-plain"),
    pytest.param(_set(["fields", "title"], "title"), "fields.title", id="target-title"),
    pytest.param(_set(["fields", "file.name"], "x"), "fields.file.name", id="target-file"),
    pytest.param(_set(["fields", "obsHtml"], "x"), "fields.obsHtml", id="target-adapter-namespace"),
    pytest.param(_set(["derive", "mark.risk"], [{"value": "x"}]), "derive.mark.risk", id="derive-target-mark"),
    pytest.param(_set(["fillNew"], {"slug": "title"}), "fillNew.slug", id="fill-new-target"),
    pytest.param(_set([*CONNECTOR, "requests", 0, "set", "obs.records"], "x"),
                 "changes[0].requests[0].set.obs.records", id="set-target"),
    # A key or condition field nothing maps.
    pytest.param(_set(["key"], ["repo", "id"]), "key[1]", id="key-unmapped"),
    # An instant per row has no key: a row carries no date.
    pytest.param(_set(["changed"], "updated"), "changed", id="schema-no-instant-key"),
    pytest.param(_set(["lookbackHours"], 0), "lookbackHours", id="schema-lookback-low"),
    pytest.param(_set(["lookbackHours"], 721), "lookbackHours", id="schema-lookback-high"),
    pytest.param(_set(["exclude"], [{"field": "draft", "exists": True}]), "exclude[0].field",
                 id="condition-unmapped"),
    # Templates.
    pytest.param(_set(["notePath"], "issues/{state}.md"), "notePath", id="note-path-outside-key"),
    pytest.param(_set(["notePath"], "issues/{repo}-{number.md"), "notePath", id="note-path-braces"),
    pytest.param(_set([*WEB, "requests", 0, "url"], "https://api.example.test/{owner}/issues"),
                 "changes[1].requests[0].url", id="url-template-unknown"),
    pytest.param(_set([*CONNECTOR, "requests", 0, "input", "since"], "{when}"),
                 "changes[0].requests[0].input.since", id="input-template-unknown"),
    # Paths of more than 8 steps.
    pytest.param(_set(["fields", "labels"], "a.b.c.d.e.f.g.h.i"), "fields.labels", id="path-steps"),
    pytest.param(_set(["fields", "state"], {"path": "a[].b[].c[].d[].e", "lowercase": True}), "fields.state.path",
                 id="path-steps-list"),
    # URLs and inputs that read as credentials.
    pytest.param(_set([*WEB, "requests", 0, "url"], "http://api.example.test/issues?since={since}"),
                 "changes[1].requests[0].url", id="url-not-https"),
    pytest.param(_set([*WEB, "requests", 0, "url"], "https://ada:secret@api.example.test/issues"),
                 "changes[1].requests[0].url", id="url-credentials"),
    pytest.param(_set([*WEB, "requests", 0, "url"], "https://api.example.test/issues?Access_Token=x"),
                 "changes[1].requests[0].url", id="url-token-query"),
    pytest.param(_set([*WEB, "requests", 0, "url"], "https://api.example.test/issues?sig=x&state=all"),
                 "changes[1].requests[0].url", id="url-sig-query"),
    pytest.param(_set([*CONNECTOR, "requests", 0, "input", "apiKey"], "x"),
                 "changes[0].requests[0].input.apiKey", id="input-key"),
    pytest.param(_set([*CONNECTOR, "next", "input"], "authCode"), "changes[0].next.input", id="next-input-auth"),
]


def _refused(document: dict) -> InputError:
    with pytest.raises(InputError) as failure:
        render(document, CONFIG)
    return failure.value


@pytest.mark.parametrize(("change", "field"), REFUSED_DECLARATIONS)
def test_a_refused_declaration_fails_the_build_at_its_field_in_a_fence_and_in_a_base_file(change, field: str) -> None:
    """generic-tables.md, Current data, Build refusals: one input error, naming the note or the
    .base file and the field under base.obsHtml.liveSource (obsHtml.liveSource in a .base file)."""
    declaration = edit(DECLARATION, change)
    in_fence = _refused(fence(base(declaration)))
    assert (in_fence.source, in_fence.field) == ("tracker.md", f"base.obsHtml.liveSource.{field}")
    assert OWNER in in_fence.remedy
    in_file = _refused(register(base(declaration)))
    assert (in_file.source, in_file.field) == ("issues.base", f"obsHtml.liveSource.{field}")
    assert OWNER in in_file.remedy


def _protected(prop: dict, name: str = "state") -> dict:
    return base(DECLARATION, properties={f"note.{name}": {"obsHtml": prop}})


REFUSED_BASES = [
    pytest.param(lambda: _protected({"editable": True}), "fields.state", id="editable"),
    pytest.param(lambda: _protected({"reference": {"label": ["title"]}}), "fields.state", id="reference"),
    pytest.param(lambda: _protected({"reference": {"label": ["title"], "metadataFormats": {
        "summary": {"format": "html", "source": "labels"}}}}, "summary"), "fields.labels", id="metadata-source"),
    pytest.param(lambda: _protected({"linkProperty": "pullRequest"}, "title"), "fields.pullRequest",
                 id="link-property"),
    pytest.param(lambda: base(DECLARATION, obs={"records": "tag"}), "", id="base-records"),
    pytest.param(lambda: {**base(DECLARATION), "views": [{**VIEW, "obs": {"records": "chapter"}}]}, "",
                 id="view-records"),
    pytest.param(lambda: base(edit(DECLARATION, _set(["derive", "status"], [
        {"where": [{"field": "state", "equals": "closed"}], "value": "Done"}, {"value": "Next"}]))), "derive.status",
        id="group-order-unproduced"),
]


@pytest.mark.parametrize(("spec", "field"), REFUSED_BASES)
def test_a_declaration_the_rest_of_its_base_contradicts_fails_at_its_field(spec, field: str) -> None:
    """A target the Base presents or edits as its own, a Base or view that selects records other
    than notes, and a grouped view whose groupOrder lists a value no case of the derived target
    produces (the view groups by status and lists Running)."""
    suffix = f".{field}" if field else ""
    in_fence = _refused(fence(spec()))
    assert (in_fence.source, in_fence.field) == ("tracker.md", f"base.obsHtml.liveSource{suffix}")
    assert OWNER in in_fence.remedy
    in_file = _refused(register(spec()))
    assert (in_file.source, in_file.field) == ("issues.base", f"obsHtml.liveSource{suffix}")
    assert OWNER in in_file.remedy


def test_members_fail_a_fence_as_before_and_a_live_base_file_at_its_declaration() -> None:
    """A view's obs.members: a fence refuses it already, at the view (render.py, _base), with or
    without a live source; in a .base file the live source refuses it, as its rows follow no note
    path."""
    spec = {**base(DECLARATION), "views": [{**VIEW, "obs": {"members": [{"path": "issues/widgets-1.md"}]}}]}
    in_fence = _refused(fence(spec))
    assert (in_fence.source, in_fence.field) == ("tracker.md", "base.views[0].obs.members")
    in_file = _refused(register(spec))
    assert (in_file.source, in_file.field) == ("issues.base", "obsHtml.liveSource")
    assert OWNER in in_file.remedy


def test_the_rest_of_the_definition_is_checked_first() -> None:
    """The order the build checks in: base.schema.json over the definition without the option,
    then the declaration, so a refused view option is named even beside a refused declaration."""
    spec = base(edit(DECLARATION, _drop(["name"])))
    spec["views"][0]["obsHtml"]["pageSize"] = 0
    failure = _refused(fence(spec))
    assert (failure.source, failure.field) == ("tracker.md", "base.views[0].obsHtml.pageSize")
    assert "base.schema.json" in failure.remedy


@pytest.mark.parametrize("other", [{}, {"maxRows": 5}], ids=["alone", "beside-another-option"])
def test_the_declaration_leaves_the_embedded_definition_and_rides_on_the_table_entry(other: dict) -> None:
    """generic-tables.md, Current data: the page's definition holds no liveSource (and no obsHtml
    where nothing else is left in it), and the table entry carries the declaration as live, with no
    time beside it, so the same input renders the same bytes."""
    for document in (fence(base(DECLARATION, obsHtml=other)), register(base(DECLARATION, obsHtml=other)),
                     register(base(DECLARATION, obsHtml=other), view=0)):
        html = render(document, CONFIG)
        [table] = tables(html)
        assert "liveSource" not in json.dumps(table["definition"])
        assert table["definition"].get("obsHtml") == (other or None)
        assert table["live"] == DECLARATION
        assert same_artifact_content(render(document, CONFIG), html)
    plain = tables(render(fence(base(None, **({"obsHtml": other} if other else {}))), CONFIG))
    assert "live" not in plain[0]
    assert plain[0]["definition"] == tables(render(fence(base(DECLARATION, obsHtml=other)), CONFIG))[0]["definition"]


def test_rendering_leaves_the_documents_base_as_the_core_gave_it() -> None:
    """The option leaves only the copy the page embeds: a register embedded twice keeps it in both."""
    document = register(base(DECLARATION))
    before = copy.deepcopy(document)
    render(document, CONFIG)
    assert document == before


def test_the_capability_notes_authoring_example_builds_without_warnings_even_refusing_provenance(
        tmp_path, capfd, monkeypatch) -> None:
    """spec/capabilities/live-data.md: its example, as the obsHtml of a Base fence over notes whose
    path follows from their key, builds with the core without a diagnostic and with obs-html,
    refusing provenance findings (artifact.refuseProvenance), without a warning: a row carries no
    date (generic-tables.md, Current data), so a live table adds no provenance finding."""
    import sys
    sys.path.insert(0, str(ROOT / "test" / "fixtures"))
    import build_documents

    def vault(root: Path) -> None:
        options = yaml.safe_dump(EXAMPLE, sort_keys=False, allow_unicode=True)
        (root / "manifest.md").write_text("---\ntitle: Live data\n---\n- [[tracker]]\n", encoding="utf-8")
        (root / "tracker.md").write_text(
            "# Tracker\n\n```base\nfilters: 'kind == \"issue\"'\nviews:\n  - type: table\n    name: Board\n"
            "    order: [file.name, status]\n    groupBy: {property: status}\n"
            f"    obsHtml: {{groupOrder: [Next, Running, Done]}}\n{options}```\n", encoding="utf-8")
        (root / "issues").mkdir()
        for item in ISSUES:
            (root / "issues" / f"widgets-{item['number']}.md").write_text(
                f"---\n{yaml.safe_dump(item, sort_keys=False)}---\n", encoding="utf-8")

    monkeypatch.setitem(build_documents.VAULTS, "live-data", vault)
    refused = build_documents.build(CORE_ROOT, ["live-data"], tmp_path)
    assert refused == {}
    document = json.loads((tmp_path / "live-data.json").read_text(encoding="utf-8"))
    assert document["diagnostics"] == []
    [table] = tables(render(document, CONFIG))
    assert table["live"] == DECLARATION
    config = tmp_path / "refuse.json"
    config.write_text(json.dumps({"artifact": {"refuseProvenance": True}}), encoding="utf-8")
    capfd.readouterr()
    assert cli.main(["--config", str(config), str(tmp_path / "live-data.json"), str(tmp_path / "live-data.html")]) == 0
    assert "Warning" not in capfd.readouterr().err
