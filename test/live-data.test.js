"use strict";

// A Base's live source, its pure layer (src/obs_html/live-data.js; generic-tables.md, Current data):
// paths, templates, the mapping of fetched items, the merge by value, a read's since, the safe nodes
// of a new row's text and the check. A row carries no date. No page and no network: base.js and query.js, the page's one conditions evaluator,
// load with a #case-folding stand-in, as bases-filter-conformance.test.js does. The declaration is
// the capability note's example (spec/capabilities/live-data.md), read with the page's YAML library.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = name => fs.readFileSync(path.join(root, "src", "obs_html", name), "utf8");
const folding = fs.readFileSync(path.join(root, "..", "..", "src", "obs", "case-folding.json"), "utf8");
const islands = {"#base-schema": source("base.schema.json"), "#case-folding": folding};
globalThis.document = {querySelector: selector => selector in islands ? {textContent: islands[selector]} : null};
vm.runInThisContext(source("vendor/js-yaml.min.js"));
vm.runInThisContext(source("base.js"));
vm.runInThisContext(source("query.js"));
vm.runInThisContext(source("live-data.js"));
const live = globalThis.obsLiveData;

const note = fs.readFileSync(path.join(root, "spec", "capabilities", "live-data.md"), "utf8");
const declaration = globalThis.jsyaml.load(/```yaml\n([\s\S]*?)```/.exec(note)[1]).obsHtml.liveSource;
const [connector, web] = declaration.changes;
const [request] = connector.requests;
const plain = value => JSON.parse(JSON.stringify(value));

// The exported names later pieces call stay as they are.
assert.deepEqual(Object.keys(live).sort(), ["LIMITS", "READER_TEXT", "check", "fillTemplate", "lower", "mapItem",
    "merge", "notePath", "project", "readList", "readPath", "reader", "requestInput", "since", "statusLine",
    "targetNames", "validateNodes"]);
assert.deepEqual(plain(live.LIMITS), {items: 2000, fieldBytes: 65536, pathSteps: 8});

// Paths: dotted keys and [], own keys only; an object is absent; scalars keep their type; a list
// of scalars stays a list; absent and null are undefined; more than 8 steps read nothing.
const item = {a: {b: 2, c: null, d: {e: true}}, list: [{name: "x"}, {name: 3}, {other: 1}], tags: ["p", "q"]};
assert.equal(live.readPath(item, "a.b"), 2);
assert.equal(live.readPath(item, "a.d.e"), true);
assert.equal(live.readPath(item, "a.d"), undefined);
assert.equal(live.readPath(item, "a.c"), undefined);
assert.equal(live.readPath(item, "a.missing"), undefined);
assert.deepEqual(plain(live.readPath(item, "list[].name")), ["x", 3]);
assert.deepEqual(plain(live.readPath(item, "tags")), ["p", "q"]);
assert.equal(live.readPath(item, "a.toString"), undefined);
assert.equal(live.readPath({a: {a: {a: {a: {a: {a: {a: {a: {a: 1}}}}}}}}}, "a.a.a.a.a.a.a.a.a"), undefined);
assert.equal(live.readPath({a: {a: {a: {a: {a: {a: {a: {a: 1}}}}}}}}, "a.a.a.a.a.a.a.a"), 1);

// Templates: {name} only; a missing or non-scalar value fills nothing; inside a url, encoded.
assert.equal(live.fillTemplate("issues/{repo}-{number}.md", {repo: "widgets", number: 12}), "issues/widgets-12.md");
assert.equal(live.fillTemplate("issues/{repo}-{number}.md", {repo: "widgets"}), undefined);
assert.equal(live.fillTemplate("?q={q}", {q: "a b&c"}, {url: true}), "?q=a%20b%26c");
assert.equal(live.fillTemplate("?q={q}", {q: ["a"]}, {url: true}), undefined);

// Map: a connector-shaped answer and a REST-shaped one give the same fields through the declaration.
const connectorItem = {number: 12, state: "OPEN", labels: ["ready", "bug"], updated_at: "2026-11-05T09:30:00Z",
    title: "Fix the widget", body: "Steps"};
const restItem = {number: 12, state: "open", labels: [{name: "ready"}, {name: "bug"}],
    updated_at: "2026-11-05T09:30:00Z", title: "Fix the widget", body: "Steps", pull_request: null};
const fromConnector = live.mapItem(declaration, connector, request, connectorItem);
const fromWeb = live.mapItem(declaration, web, web.requests[0], restItem);
assert.deepEqual(plain(fromConnector), plain(fromWeb));
assert.equal(fromConnector.path, "issues/widgets-12.md");
assert.deepEqual(plain(fromConnector.fields), {repo: "widgets", number: 12, state: "open", labels: ["ready", "bug"],
    status: "Next", where: "Fix the widget"});
assert.deepEqual(plain(fromConnector.body), [{type: "paragraph", children: [{type: "text", text: "Steps"}]}]);
// exclude: a pull request is ignored; without its key an item is no row.
assert.equal(live.mapItem(declaration, connector, request, {...connectorItem, pull_request: {url: "https://x.test/1"}}), null);
assert.equal(live.mapItem(declaration, connector, request, {...connectorItem, number: null}), null);
// derive: the first case that matches wins; a closed item is Done whatever its labels.
assert.equal(live.mapItem(declaration, connector, request, {...connectorItem, state: "CLOSED"}).fields.status, "Done");
// A shown row the item belongs to keeps its text and its kept value; fillNew is for new rows only.
const shownRow = {sourcePath: "issues/widgets-12.md", frontmatter: {repo: "widgets", number: 12, status: "Waiting"}};
const planned = live.mapItem(declaration, connector, request, {...connectorItem, labels: ["planned"]}, () => shownRow);
assert.equal(planned.fields.status, "Waiting");
assert.equal(planned.body, undefined);
assert.equal(planned.fields.where, undefined);
// A new item whose derive lands on keep is no row: the page cannot know its value.
assert.equal(live.mapItem(declaration, connector, request, {...connectorItem, labels: ["planned"]}), null);
assert.equal(live.mapItem(declaration, connector, request, {...connectorItem, labels: []}), null);
// accept: a new item must meet it; a shown one need not.
const accepting = {...declaration, accept: [{field: "labels", equals: "bug"}]};
assert.notEqual(live.mapItem(accepting, connector, request, connectorItem), null);
assert.equal(live.mapItem(accepting, connector, request, {...connectorItem, labels: ["ready"]}), null);
assert.notEqual(live.mapItem(accepting, connector, request, {...connectorItem, labels: ["ready"]}, () => shownRow), null);

// Fetched text is data. Hostile values end as text or are refused; no function returns HTML.
const hostile = live.mapItem(declaration, connector, request, {...connectorItem,
    title: "<script>alert(1)</script>",
    body: "<img src=x onerror=alert(1)>\n[link](javascript:alert(1)) **bold**\n\nsee https://example.test/a.",
    labels: ["ready", "__proto__"]});
assert.equal(hostile.fields.where, "<script>alert(1)</script>");
assert.deepEqual(plain(hostile.fields.labels), ["ready", "__proto__"]);
assert.deepEqual(plain(hostile.body), [
    {type: "paragraph", children: [
        {type: "text", text: "<img src=x onerror=alert(1)>"}, {type: "lineBreak"},
        {type: "text", text: "[link](javascript:alert(1)) **bold**"}]},
    {type: "paragraph", children: [
        {type: "text", text: "see "}, {type: "link", label: "https://example.test/a", url: "https://example.test/a"},
        {type: "text", text: "."}]}]);
assert.throws(() => live.validateNodes([{type: "paragraph", children: [
    {type: "link", label: "x", url: "javascript:alert(1)"}]}]), TypeError);
assert.throws(() => live.validateNodes([{type: "paragraph", children: [{type: "html", html: "<b>x</b>"}]}]), TypeError);
assert.throws(() => live.validateNodes([{type: "paragraph", children: [{type: "text", text: "x", html: "<b>"}]}]), TypeError);
assert.throws(() => live.validateNodes([{type: "text", text: "outside a paragraph"}]), TypeError);
assert.throws(() => live.validateNodes([{type: "paragraph", children: [
    {type: "link", label: "x", url: "http://example.test"}]}]), TypeError);
// __proto__ in a fetched answer, or as a set target, reaches no prototype.
const polluting = JSON.parse('{"number": 13, "state": "open", "labels": ["ready"], ' +
    '"updated_at": "2026-11-05T09:30:00Z", "title": {"__proto__": {"polluted": true}}, "__proto__": {"polluted": true}}');
const unpolluted = live.mapItem(declaration, connector, {set: {repo: "widgets", ["__proto__"]: "x"}}, polluting);
assert.equal(unpolluted.fields.where, undefined);
assert.equal(Object.getPrototypeOf(unpolluted.fields), Object.prototype);
assert.equal(unpolluted.fields.polluted, undefined);
assert.equal({}.polluted, undefined);
assert.equal(Object.hasOwn(unpolluted.fields, "__proto__"), false);

// Merge, by value: an item whose compared values (set and fields targets, canonical JSON) equal its
// saved row's changes nothing; one that differs in any of them applies.
const savedRow = {sourcePath: "issues/widgets-12.md", frontmatter: {
    repo: "widgets", number: 12, state: "open", labels: ["ready", "bug"], status: "Next", kind: "issue", owner: "ada"}};
const saved = new Map([["issues/widgets-12.md", savedRow]]);
const merged = items => live.merge(declaration, connector, request, items, saved);
assert.equal(merged([connectorItem]).rows.size, 0);
// Absent, null and an empty list are all left out of the compared text, and key order does not count.
assert.equal(live.merge(declaration, connector, request, [{...connectorItem, pull_request: null}],
    new Map([["issues/widgets-12.md", {...savedRow, frontmatter: {pullRequest: null, ...savedRow.frontmatter}}]])).rows.size, 0);
for (const change of [{state: "CLOSED"}, {labels: ["ready"]}, {labels: ["bug", "ready"]}]) {
    assert.equal(merged([{...connectorItem, ...change}]).rows.size, 1, JSON.stringify(change));
}
const closed = merged([{...connectorItem, state: "CLOSED", labels: []}]);
assert.equal(closed.partial, false);
assert.deepEqual(plain(closed.rows.get("issues/widgets-12.md")), {sourcePath: "issues/widgets-12.md", added: false,
    frontmatter: {repo: "widgets", number: 12, state: "closed", labels: [], status: "Done", kind: "issue", owner: "ada"}});
// The projection is computed from the saved rows and the latest result alone: an item equal to its
// saved row shows the saved row, even after an earlier read changed it.
assert.equal(merged([{...connectorItem, state: "CLOSED"}]).rows.size, 1);
assert.equal(merged([connectorItem]).rows.size, 0);
assert.deepEqual(plain(savedRow.frontmatter.labels), ["ready", "bug"]);
// An item read twice in one read keeps its last occurrence.
assert.equal(merged([{...connectorItem, labels: ["running"]}, {...connectorItem, labels: ["ready"]}])
    .rows.get("issues/widgets-12.md").frontmatter.status, "Next");
assert.equal(merged([{...connectorItem, state: "CLOSED"}, connectorItem]).rows.size, 0);
// A path absent on the item removes the property from the row.
const unlabelled = {...connectorItem};
delete unlabelled.labels;
assert.equal(Object.hasOwn(merged([unlabelled]).rows.get("issues/widgets-12.md").frontmatter, "labels"), false);
// A new item on keep adds no row; a new one that derives a value is added with its text, and its
// text follows a later read.
assert.equal(merged([{...connectorItem, number: 40, labels: ["planned"]}]).rows.size, 0);
const added = merged([{...connectorItem, number: 41}]).rows.get("issues/widgets-41.md");
assert.equal(added.added, true);
assert.equal(added.frontmatter.status, "Next");
assert.equal(added.frontmatter.where, "Fix the widget");
assert.deepEqual(plain(added.body), [{type: "paragraph", children: [{type: "text", text: "Steps"}]}]);
const later = merged([{...connectorItem, number: 41, title: "Fixed", body: "Done now"}]).rows.get("issues/widgets-41.md");
assert.equal(later.frontmatter.where, "Fixed");
assert.deepEqual(plain(later.body), [{type: "paragraph", children: [{type: "text", text: "Done now"}]}]);
// Limits: past 2000 items, or a value over 64 KiB, the item is dropped and the read is partial.
const many = Array.from({length: 2001}, (_, index) => ({...connectorItem, number: 100 + index}));
const capped = merged(many);
assert.equal(capped.partial, true);
assert.equal(capped.rows.size, 2000);
assert.equal(capped.rows.has("issues/widgets-2100.md"), false);
const huge = merged([{...connectorItem, number: 42, title: "x".repeat(65537)}, {...connectorItem, number: 43}]);
assert.equal(huge.partial, true);
assert.deepEqual([...huge.rows.keys()], ["issues/widgets-43.md"]);
assert.equal(merged([{...connectorItem, number: 44, title: "x".repeat(65536)}]).partial, false);

// since: the page's generation timestamp minus lookbackHours (1 by default, 24 when declared), in
// whole seconds ending in Z, the same for every request.
assert.equal(live.since(declaration, "2026-11-17T10:30:45.123456+00:00"), "2026-11-17T09:30:45Z");
assert.equal(live.since(declaration, "2026-11-17T11:30:45+01:00"), "2026-11-17T09:30:45Z");
assert.equal(live.since({...declaration, lookbackHours: 24}, "2026-11-17T10:30:45+00:00"), "2026-11-16T10:30:45Z");
assert.equal(live.since(declaration, "not a time"), undefined);
assert.equal(live.since.length, 2);

// The check: a population the declaration reproduces passes.
const row = (number, status, extra = {}) => ({sourcePath: `issues/widgets-${number}.md`, frontmatter: {
    repo: "widgets", number, state: "open", labels: ["ready"], status, ...extra}});
const good = [row(1, "Next"), row(2, "Done", {state: "closed"}), row(3, "Anything", {labels: ["planned"]}),
    row(4, "Kept", {labels: []})];
assert.deepEqual(live.check(declaration, good), []);
// Each failure names the note, the check and the field.
assert.deepEqual(plain(live.check(declaration, [...good, row(5, "Running")])),
    [{notePath: "issues/widgets-5.md", check: "derive", field: "status"}]);
assert.deepEqual(plain(live.check(declaration, [...good, {...row(6, "Next"), sourcePath: "elsewhere/six.md"}])),
    [{notePath: "elsewhere/six.md", check: "notePath", field: "issues/{repo}-{number}.md"}]);
assert.deepEqual(plain(live.check(declaration, [...good, row(7, "Next", {number: " "})])),
    [{notePath: "issues/widgets-7.md", check: "key", field: "number"}]);
assert.deepEqual(plain(live.check(declaration, [...good, {...row(1, "Next"), sourcePath: "issues/widgets-1.md"}])),
    [{notePath: "issues/widgets-1.md", check: "key", field: "repo, number"}]);
// Each request's set values occur in at least one row.
const elsewhere = good.map(entry => ({...entry, frontmatter: {...entry.frontmatter, repo: "gadgets"},
    sourcePath: entry.sourcePath.replace("widgets", "gadgets")}));
assert.deepEqual(plain(live.check(declaration, elsewhere)),
    [{notePath: "", check: "set", field: "repo"}, {notePath: "", check: "set", field: "repo"}]);


// The reader's texts (generic-tables.md, Status line): one frozen table, no date or time in any of
// them, composed from the reader's state. Nothing before a read; a part with nothing before it
// starts the line, its first letter capitalised; every further part follows " · ".
assert.equal(Object.isFrozen(live.READER_TEXT), true);
const TIME = /\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}|\b(?:am|pm|today|yesterday|ago|minutes?|hours?|seconds?)\b/i;
Object.values(live.READER_TEXT).forEach(text => assert.doesNotMatch(text, TIME));
const line = (view) => plain(live.statusLine({shown: "saved", parts: [], button: false, refresh: "hidden", ...view},
    "Example Tracker"));
assert.deepEqual(line({}), {text: "", warning: false, button: "", refresh: {label: "Check for updates", shown: false,
    disabled: false}});
assert.equal(line({shown: "current"}).text, "Showing current data");
assert.equal(line({shown: "earlier"}).text, "Could not check for updates; showing the data read earlier");
assert.equal(line({shown: "earlier"}).warning, true);
assert.equal(line({shown: "comments"}).text, "Showing the saved version while comments are open");
assert.equal(line({parts: [{key: "unavailable"}]}).text, "Newer updates cannot be shown here");
assert.equal(line({parts: [{key: "unavailable"}]}).warning, false);
assert.equal(line({shown: "current", parts: [{key: "first", n: 300}]}).text,
    "Showing current data · showing the first 300 changes");
assert.equal(line({parts: [{key: "notNow"}]}).text, "Could not check for updates now");
assert.equal(line({parts: [{key: "notNow"}]}).warning, true);
assert.equal(line({parts: [{key: "off"}]}).text, "Current data is turned off for this page");
assert.equal(line({parts: [{key: "connect"}]}).text, "Connect Example Tracker in Claude to see current data");
assert.equal(line({parts: [{key: "reauth"}]}).text, "Sign in to Example Tracker again in Claude");
assert.equal(line({shown: "current", parts: [{key: "wait"}]}).text,
    "Showing current data · Example Tracker asks to wait before the next check");
assert.deepEqual(line({button: true, refresh: "enabled"}), {text: "", warning: false, button: "Show current data",
    refresh: {label: "Check for updates", shown: true, disabled: false}});
assert.deepEqual(line({refresh: "busy"}).refresh, {label: "Check for updates", shown: true, disabled: true});

// The declared targets, whose columns a table always knows: set, fields, derive and fillNew.
assert.deepEqual(plain(live.targetNames(declaration)), ["labels", "number", "pullRequest", "repo", "state", "status",
    "where"]);
// A request's input: a value that is one template alone takes the value as it is, others are text.
assert.deepEqual(plain(live.requestInput({set: {repo: "widgets"}, input: {owner: "example-org", repo: "{repo}",
    since: "{since}", label: "x-{repo}", perPage: 100}}, "2026-11-17T09:30:45Z")),
    {owner: "example-org", repo: "widgets", since: "2026-11-17T09:30:45Z", label: "x-widgets", perPage: 100});
// A result's list: own keys only, a list or nothing.
assert.deepEqual(plain(live.readList({issues: [{number: 1}]}, "issues")), [{number: 1}]);
assert.deepEqual(plain(live.readList({data: {issues: []}}, "data.issues")), []);
assert.equal(live.readList({issues: {}}, "issues"), undefined);
assert.equal(live.readList(Object.create({issues: []}), "issues"), undefined);

// The projection for one table key: a changed saved row keeps its slug and drops the built HTML of
// every target it maps, sets or derives, with their flattened children; a new row gets a slug no
// chapter can take, kept for its path, its path's file name as title and its lowered text.
const savedRows = new Map([["issues/widgets-12.md", {slug: "widgets-12", sourcePath: "issues/widgets-12.md",
    frontmatter: {repo: "widgets", number: 12, state: "open", labels: ["running"], status: "Running", owner: "Ann"}}]]);
const results = [{request, items: [
    {number: 12, state: "CLOSED", labels: ["running"], title: "Twelve", body: "Old"},
    {number: 13, state: "OPEN", labels: ["ready"], title: "Thirteen", body: "First line\n\n<script>x()</script>"}]}];
const projected = live.project(declaration, connector, results, savedRows, "board", new Map());
assert.deepEqual(plain(projected.matched), [{slug: "widgets-12", frontmatter: {repo: "widgets", number: 12,
    state: "closed", labels: ["running"], status: "Done", owner: "Ann"},
    drop: ["labels", "number", "pullRequest", "repo", "state", "status"]}]);
assert.deepEqual(plain(projected.added), [{slug: "live~board~1", sourcePath: "issues/widgets-13.md", title: "widgets-13",
    frontmatter: {repo: "widgets", number: 13, state: "open", labels: ["ready"], status: "Next", where: "Thirteen"},
    body: [{type: "paragraph", children: [{type: "text", text: "First line"}]},
        {type: "paragraph", children: [{type: "text", text: "<script>x()</script>"}]}]}]);
assert.equal(projected.partial, false);
const again = live.project(declaration, connector, [{request, items: [
    {number: 14, state: "OPEN", labels: ["ready"], title: "Fourteen"}, ...results[0].items]}], savedRows, "board",
    projected.assigned);
assert.deepEqual(again.added.map(entry => entry.slug).sort(), ["live~board~1", "live~board~2"]);
assert.equal(again.added.find(entry => entry.sourcePath === "issues/widgets-13.md").slug, "live~board~1");
// An item equal to its saved row changes nothing.
assert.deepEqual(plain(live.project(declaration, connector, [{request, items: [{number: 12, state: "open",
    labels: ["running"]}]}], savedRows, "board", new Map()).matched), []);

// The route (generic-tables.md, Reading), with the viewer's namespaces handed in: a fake held to the
// viewer's mcp and permissions contract (runtime 0.2.96). A watch replays and refreshes through its
// handler as {type: "data", result} or {type: "error", error} and returns a synchronous unsubscribe;
// callTool resolves a result or rejects with {code, retryable?, retryAfterMs?}; listTools names the
// tool's annotations; permissions.state never asks. Time is the fake's clock, waiting its own.
const viewer = ({consent = "granted", readOnly = true, answers = [], watchEvents} = {}) => {
    const calls = [];
    const watches = [];
    let clock = 1_000_000;
    let state = consent;
    const answer = (input) => {
        const next = answers.length ? answers.shift() : {payload: {issues: [], pageInfo: {hasNextPage: false}}};
        return typeof next === "function" ? next(input) : next;
    };
    const mcp = {
        async callTool(server, tool, input, options) {
            calls.push({kind: "call", server, tool, input: plain(input), options: plain(options)});
            const result = answer(input);
            if (result.code) throw result;
            return result;
        },
        watchTool(server, tool, input, handler, options) {
            const watch = {server, tool, input: plain(input), options: plain(options), handler, active: true};
            calls.push({kind: "watch", server, tool, input: plain(input), options: plain(options)});
            watches.push(watch);
            const events = watchEvents ? watchEvents.shift() || [] : [answer(input)];
            Promise.resolve().then(() => events.forEach(event => watch.active && handler(event.code
                ? {type: "error", error: event} : {type: "data", result: event})));
            return () => {watch.active = false;};
        },
        async listTools(server) {
            calls.push({kind: "list", server});
            return {servers: [{server, authStatus: "connected", tools: [{name: "list_issues", description: "",
                ...(readOnly === undefined ? {} : {annotations: {readOnlyHint: readOnly}})}]}]};
        },
    };
    const permissions = {
        async state(name) {
            calls.push({kind: "state", name});
            if (state === "rejects") throw {code: "unavailable"};
            return state;
        },
    };
    return {mcp, permissions, calls, watches, setConsent: value => {state = value;},
        now: () => clock, advance: ms => {clock += ms;}, waits: []};
};
const page = (items, more = false, cursor = "c1", storedAt) => ({payload: {issues: items, pageInfo: {hasNextPage: more,
    endCursor: cursor}}, ...(storedAt === undefined ? {} : {cache: {storedAt, revalidating: false}})});
const settle = () => new Promise(resolve => setImmediate(resolve));
const open = (fake, options = {}) => {
    const notices = [];
    const changes = [];
    const reader = live.reader({declaration: {...declaration, ...options.declaration}, route: {...connector,
        ...options.route}, since: "2026-11-17T09:30:45Z", mcp: options.absent ? null : fake.mcp,
        permissions: fake.permissions, now: fake.now, wait: ms => {fake.waits.push(ms); return Promise.resolve();},
        notice: text => notices.push(text), onChange: () => changes.push(reader.view())});
    return {reader, notices, changes, text: () => live.statusLine(reader.view(), declaration.name).text};
};
const MINUTES = 10 * 60 * 1000;
const issue = (number, extra = {}) => ({number, state: "OPEN", labels: ["ready"], title: `Issue ${number}`, ...extra});

(async () => {
    // granted: one watch per request, cache both refreshMinutes, no refetchInterval, since filled.
    {
        const fake = viewer({answers: [page([issue(12)])]});
        const {reader, text} = open(fake);
        await reader.start();
        await settle();
        const watch = fake.calls.find(call => call.kind === "watch");
        assert.deepEqual(watch, {kind: "watch", server: "Example Tracker", tool: "list_issues", input: {
            owner: "example-org", repo: "widgets", since: "2026-11-17T09:30:45Z", orderBy: "UPDATED_AT",
            direction: "ASC", perPage: 100}, options: {cache: {staleTime: MINUTES, gcTime: MINUTES}}});
        assert.deepEqual(fake.calls.map(call => call.kind), ["state", "list", "watch"]);
        assert.deepEqual(fake.calls[0], {kind: "state", name: "mcp:Example Tracker"});
        assert.equal(text(), "Showing current data");
        assert.deepEqual(plain(reader.view().results), [{request, items: [issue(12)]}]);
        assert.equal(reader.view().refresh, "enabled");
    }
    // Later pages follow next with callTool and the same cache, up to maxPages; more left over says
    // how many changes are shown.
    {
        const fake = viewer({answers: [page([issue(1)], true, "c1"), page([issue(2)], true, "c2"),
            page([issue(3)], true, "c3")]});
        const {reader, text} = open(fake);
        await reader.start();
        await settle();
        const follow = fake.calls.filter(call => call.kind === "call");
        assert.deepEqual(follow.map(call => call.input.after), ["c1", "c2"]);
        assert.deepEqual(follow[0].options, {cache: {staleTime: MINUTES, gcTime: MINUTES}});
        assert.equal(text(), "Showing current data · showing the first 3 changes");
    }
    // prompt: the button, and nothing called; its click makes the first call with callTool, then
    // checks the tool is a read and watches.
    {
        const fake = viewer({consent: "prompt", answers: [page([issue(12)]), page([issue(12)])]});
        const {reader, text} = open(fake);
        await reader.start();
        assert.equal(reader.view().button, true);
        assert.equal(text(), "");
        assert.deepEqual(fake.calls.map(call => call.kind), ["state"]);
        await reader.allow();
        await settle();
        assert.deepEqual(fake.calls.map(call => call.kind), ["state", "call", "list", "watch"]);
        assert.equal(reader.view().button, false);
        assert.equal(text(), "Showing current data");
    }
    // prompt, then declined: not_in_manifest, then the state reads denied.
    {
        const fake = viewer({consent: "prompt", answers: [() => {
            fake.setConsent("denied");
            return {code: "not_in_manifest"};
        }]});
        const {reader, text} = open(fake);
        await reader.start();
        await reader.allow();
        assert.equal(text(), "Current data is turned off for this page");
        assert.equal(reader.view().refresh, "hidden");
        assert.equal(reader.view().button, false);
    }
    // denied, unavailable, a rejected read and a null mcp: nothing called, no key.
    for (const [consent, expected] of [["denied", "Current data is turned off for this page"],
        ["unavailable", "Newer updates cannot be shown here"], ["rejects", "Newer updates cannot be shown here"]]) {
        const fake = viewer({consent});
        const {reader, text} = open(fake);
        await reader.start();
        assert.equal(text(), expected);
        assert.equal(reader.view().refresh, "hidden");
        assert.deepEqual(fake.calls.map(call => call.kind), ["state"]);
    }
    {
        const fake = viewer();
        const {reader, text} = open(fake, {absent: true});
        await reader.start();
        assert.equal(text(), "Newer updates cannot be shown here");
        assert.equal(reader.view().refresh, "hidden");
        assert.deepEqual(fake.calls, []);
    }
    // A tool not reported read-only is not called.
    for (const readOnly of [false, "unannotated"]) {
        const fake = viewer({readOnly});
        const {reader, text} = open(fake);
        await reader.start();
        assert.equal(text(), "Newer updates cannot be shown here");
        assert.deepEqual(fake.calls.map(call => call.kind), ["state", "list"]);
    }
    // Each failure by its code: an authorization one drops the read rows, a transient one keeps them.
    const after = async (error, {before = [page([issue(12)])]} = {}) => {
        const fake = viewer({watchEvents: [[...before, error]]});
        const opened = open(fake);
        await opened.reader.start();
        await settle();
        await settle();
        return {...opened, fake};
    };
    for (const [code, expected] of [["needs_reauth", "Sign in to Example Tracker again in Claude"],
        ["server_not_connected", "Connect Example Tracker in Claude to see current data"],
        ["selection_required", "Connect Example Tracker in Claude to see current data"],
        ["server_not_found", "Connect Example Tracker in Claude to see current data"],
        ["blocked_by_policy", "Newer updates cannot be shown here"],
        ["not_granted", "Newer updates cannot be shown here"],
        ["capability_disabled", "Newer updates cannot be shown here"],
        ["capability_removed", "Newer updates cannot be shown here"]]) {
        const {reader, text, notices} = await after({code});
        assert.equal(text(), expected, code);
        assert.deepEqual(plain(reader.view().results), [], code);
        assert.deepEqual(notices, code === "blocked_by_policy"
            ? ["Newer updates from Example Tracker cannot be shown on this page."] : [], code);
    }
    {
        const {reader, text} = await after({code: "approval_required"});
        assert.equal(reader.view().button, true);
        assert.equal(text(), "");
        assert.deepEqual(plain(reader.view().results), []);
    }
    {
        const {text, fake} = await after({code: "not_in_manifest"});
        assert.equal(text(), "Newer updates cannot be shown here");
        assert.deepEqual(fake.calls.filter(call => call.kind === "state").length, 2);
    }
    for (const code of ["server_unavailable", "upstream_error", "tool_error", "something_new"]) {
        const {reader, text} = await after({code, retryable: true});
        assert.equal(text(), "Could not check for updates; showing the data read earlier", code);
        assert.equal(reader.view().results.length, 1, code);
        assert.equal((await after({code}, {before: []})).text(), "Could not check for updates now", code);
    }
    // A retryable error followed by success shows the current data.
    {
        const fake = viewer({watchEvents: [[{code: "server_unavailable", retryable: true}, page([issue(12)])]]});
        const {reader, text, changes} = open(fake);
        await reader.start();
        await settle();
        await settle();
        assert.equal(text(), "Showing current data");
        assert.ok(changes.some(view => live.statusLine(view, "Example Tracker").text === "Could not check for updates now"));
    }
    // rate_limited with retryAfterMs: the rows stay, the line says to wait and no call is made before then.
    {
        const {reader, text, fake} = await after({code: "rate_limited", retryable: true, retryAfterMs: 30000});
        assert.equal(text(), "Showing current data · Example Tracker asks to wait before the next check");
        const before = fake.calls.length;
        await reader.refresh();
        assert.equal(fake.calls.length, before);
        fake.advance(30001);
        await reader.refresh();
        assert.equal(fake.calls.length, before + 1);
    }
    // A retryable error on a later page gets one retry, after retryAfterMs.
    {
        const fake = viewer({answers: [page([issue(1)], true), {code: "server_unavailable", retryable: true,
            retryAfterMs: 1500}, page([issue(2)])]});
        const {reader, text} = open(fake);
        await reader.start();
        await settle();
        await settle();
        assert.deepEqual(fake.waits, [1500]);
        assert.equal(text(), "Showing current data");
        assert.deepEqual(plain(reader.view().results[0].items), [issue(1), issue(2)]);
    }
    // Freshness: a result older than the one shown for the same request is dropped.
    {
        const fake = viewer({watchEvents: [[page([issue(12, {state: "CLOSED"})], false, "", 2000),
            page([issue(12)], false, "", 1000)]]});
        const {reader} = open(fake);
        await reader.start();
        await settle();
        await settle();
        assert.equal(reader.view().results[0].items[0].state, "CLOSED");
    }
    // Refresh: one callTool past the cache, then the line; in prompt it allows.
    {
        const fake = viewer({answers: [page([issue(12)]), page([issue(13)])]});
        const {reader, text} = open(fake);
        await reader.start();
        await settle();
        const count = fake.calls.length;
        const refreshing = reader.refresh();
        assert.equal(reader.view().refresh, "busy");
        await refreshing;
        const made = fake.calls.slice(count);
        assert.deepEqual(made.map(call => call.kind), ["call"]);
        assert.deepEqual(made[0].options, {cache: {staleTime: MINUTES, gcTime: MINUTES, refresh: true}});
        assert.equal(reader.view().refresh, "enabled");
        assert.equal(text(), "Showing current data");
        assert.equal(reader.view().results[0].items[0].number, 13);
    }
    // Shown again: past refreshMinutes it unsubscribes and registers its watches again; within, nothing.
    {
        const fake = viewer({answers: [page([issue(12)]), page([issue(12)])]});
        const {reader} = open(fake);
        await reader.start();
        await settle();
        reader.resume();
        assert.equal(fake.watches.length, 1);
        fake.advance(MINUTES + 1);
        reader.resume();
        assert.equal(fake.watches.length, 2);
        assert.equal(fake.watches[0].active, false);
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
