"""A live table in Claude's artifact viewer, for the live-source browser tests (generic-tables.md,
Current data: Reading, Projection, Never saved, Status line).

Reader: whoever changes test_live_rows_browser.py or test_live_connector_browser.py.

The tracker holds four issue notes and three tables of one live Base: a fence whose filter takes
every widget (``repo == "widgets"``), so a new item can become its row; a register whose filter
takes only notes of kind issue, which no read item carries, so a new item never becomes its row;
and a plain fence without the option. The declaration is the capability note's example.

``stand_in(config)`` is a fake of the viewer's runtime, ``claude.use`` resolving the ``mcp`` and
``permissions`` namespaces as runtime contract 0.2.96 describes them, put into the artifact's head
by test/browser/viewer.py (``with_stand_in``). It records every call in ``fakeClaude.calls``:

- ``consent``: what ``permissions.state("mcp:<server>")`` answers; ``mcp: false``: ``use("mcp")``
  resolves ``null``;
- ``watch``: per watch registration, in order, the events its handler gets, each ``{items}`` or
  ``{error}``; a registration past the list gets ``items``;
- ``call``: per ``callTool``, in order, ``{items}`` or ``{error}``, optionally with ``consentAfter``,
  the state the permissions read gives from then on; a call past the list gets ``items``.
"""
import copy
import json
import re

from conftest import ROOT
from documents import chapter, document as build, heading, node, paragraph

DECLARATION = __import__("yaml").safe_load(re.search(r"```yaml\n(.*?)```", (
    ROOT / "spec" / "capabilities" / "live-data.md").read_text(encoding="utf-8"), re.S)[1])["obsHtml"]["liveSource"]
ISSUES = {
    1: {"state": "open", "labels": ["ready"], "status": "Next"},
    2: {"state": "closed", "labels": ["running"], "status": "Done"},
    3: {"state": "open", "labels": ["running"], "status": "Running"},
    4: {"state": "open", "labels": ["planned"], "status": "Someday"},
}
SHELL = "[data-active-chapter] .data-table-shell"
LINE = f"{SHELL} [data-table-live-status]"
HOSTILE = '<script>globalThis.hostile = 1</script><img src=x onerror="globalThis.hostile = 2"> javascript:alert(1)'
# What the stand-in's list_issues answers by default: issue 3 closed since the build, a new issue 5,
# and a new issue 6 whose text is hostile.
CHANGES = [
    {"number": 3, "state": "CLOSED", "labels": ["running"], "title": "Widget 3", "body": "Closed now"},
    {"number": 5, "state": "OPEN", "labels": ["ready"], "title": "Widget 5", "body": "Issue 5's text.\n\nSecond paragraph."},
    {"number": 6, "state": "OPEN", "labels": ["ready"], "title": HOSTILE, "body": HOSTILE},
]


def _base(live: bool, filters: str) -> dict:
    view = {"type": "table", "name": "Board", "order": ["file.name", "status", "where"],
            "groupBy": {"property": "status"}, "obsHtml": {"groupOrder": ["Next", "Running", "Done", "Someday"]}}
    spec = {"filters": filters, "views": [view]}
    return {**spec, "obsHtml": {"liveSource": copy.deepcopy(DECLARATION)}} if live else spec


def tracker() -> dict:
    """The tracker Document; the issue notes sit outside the contents, so an opened row shows its text."""
    notes = [{**chapter(f"widgets-{number}", f"Widget {number}", paragraph(f"Issue {number}'s text."),
                        metadata={"kind": "issue", "repo": "widgets", "number": number, **item}), "toc": False}
             for number, item in ISSUES.items()]
    register = _base(True, 'kind == "issue"')
    register["views"][0]["order"] = ["file.name", "status"]
    return build(
        "Tracker",
        chapter("live", "Live", heading(1, "Live"), node("bases", source="", spec=_base(True, 'repo == "widgets"'))),
        chapter("register", "Register", heading(1, "Register"), {**node(
            "registers", target="issues.base", heading="", base=register, view=None,
            rows=[[f"widgets-{number}" for number in ISSUES]]), "id": "issues-register"}),
        chapter("plain", "Plain", heading(1, "Plain"), node("bases", source="", spec=_base(False, 'repo == "widgets"'))),
        *notes,
        records=tuple({"id": f"widgets-{number}", "type": "note", "path": f"issues/widgets-{number}.md",
                       "fields": {"kind": "issue", "repo": "widgets", "number": number, **item}}
                      for number, item in ISSUES.items()))


STAND_IN = """
(() => {
    const config = %s;
    const calls = [];
    globalThis.fakeClaude = {calls};
    let consent = config.consent ?? "granted";
    const result = items => ({content: [], payload: {issues: items, pageInfo: {hasNextPage: false, endCursor: null}}});
    const callAnswers = [...(config.call || [])];
    const watchEvents = [...(config.watch || [])];
    const items = config.items || [];
    const mcp = Object.freeze({
        callTool(server, tool, input, options) {
            calls.push({kind: "call", server, tool, input, options});
            const entry = callAnswers.length ? callAnswers.shift() : {items};
            if (entry.consentAfter) consent = entry.consentAfter;
            return entry.error ? Promise.reject(entry.error) : Promise.resolve(result(entry.items));
        },
        watchTool(server, tool, input, handler, options) {
            calls.push({kind: "watch", server, tool, input, options});
            let active = true;
            const events = watchEvents.length ? watchEvents.shift() : [{items}];
            setTimeout(() => events.forEach(event => active && handler(event.error
                ? {type: "error", error: event.error} : {type: "data", result: result(event.items)})), 0);
            return () => { active = false; };
        },
        async listTools(server) {
            calls.push({kind: "list", server});
            return {servers: [{server, authStatus: "connected", tools: [{name: "list_issues", description: "",
                annotations: {readOnlyHint: true}}]}]};
        },
    });
    const permissions = Object.freeze({
        async state(name) {
            calls.push({kind: "state", name});
            return consent;
        },
    });
    globalThis.claude = Object.freeze({use: name => new Promise(resolve => setTimeout(() => resolve(
        name === "mcp" ? (config.mcp === false ? null : mcp) : name === "permissions" ? permissions : null), 0))});
})();"""


def stand_in(**config) -> str:
    """The fake viewer runtime for ``config`` (the module docstring); every ``<`` of its data escaped,
    so hostile text stays data in the artifact's head."""
    return STAND_IN % json.dumps({"items": CHANGES, **config}).replace("<", "\\u003c")


SHOW = """async slug => {
    obsPages.setPaged(false);
    await obsArtifact.activateChapter(slug);
    await obsArtifact.whenChapterReady();
}"""
