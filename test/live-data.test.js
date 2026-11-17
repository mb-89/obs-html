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
assert.deepEqual(Object.keys(live).sort(), ["LIMITS", "check", "fillTemplate", "lower", "mapItem", "merge",
    "notePath", "readPath", "since", "validateNodes"]);
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
