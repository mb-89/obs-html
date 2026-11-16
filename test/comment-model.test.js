"use strict";

// The HTML adapter's one comment mapping (src/obs_html/comment-model.js; spec/input-model.md, Comments
// and the core model): every native thread fixture (test/fixtures/comment-threads.json) maps to the
// core's format and back unchanged, and the browser's review state holds the core's shared cases
// (test/fixtures/review-state-conformance.json at the repository root), which test/test_comments.py
// there runs against obs.comments.review_state and obs.comments.comment_state.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
vm.runInThisContext(fs.readFileSync(path.join(root, "src", "obs_html", "comment-model.js"), "utf8"));
const model = globalThis.obsCommentModel;
const read = (...parts) => JSON.parse(fs.readFileSync(path.join(...parts), "utf8"));

const {fixtures} = read(root, "test", "fixtures", "comment-threads.json");
for (const [name, native] of Object.entries(fixtures)) {
    const core = model.toCore(native);
    assert.equal(core.version, 1, name);
    assert.ok(core.comments.every((comment) => comment.replies === undefined && typeof comment.body.text === "string"),
        `${name}: the core's comments are flat, each with a body`);
    assert.deepEqual(model.fromCore(core), native, `${name}: native, then core, then native`);
    assert.deepEqual(model.toCore(model.fromCore(core)), core, `${name}: core, then native, then core`);
}

const reply = {id: "r", author: "A", created: "2026-11-09T10:00:00Z", body: {mediaType: "text/plain", text: ""},
    state: "open", inReplyTo: "missing"};
assert.throws(() => model.fromCore({version: 1, files: [], comments: [reply], decisions: []}), /answers/);
assert.throws(() => model.fromCore({version: 2, annotations: []}), /version 1/);

const conformance = read(root, "..", "..", "test", "fixtures", "review-state-conformance.json");
for (const {target, reviewer, expected} of conformance.cases) {
    assert.equal(model.reviewState(conformance.decisions, target, reviewer), expected,
        `${JSON.stringify(target)} ${reviewer ?? "aggregate"}`);
}
const comments = new Map(conformance.comments.map((comment) => [comment.id, comment]));
for (const {comment, expected} of conformance.commentCases) {
    assert.equal(model.commentState(comments.get(comment), conformance.states), expected, comment);
}

// The home page's chapter key is the core's abstract, in every target a comment or decision carries.
const home = {annotations: [{id: "h", author: "A", created: "2026-11-09T10:00:00Z", mediaType: "text/plain",
    text: "", state: "open", target: {chapter: "home", node: "paragraph-1", quote: "x"},
    batch: {scope: "document", items: [{chapter: "home"}, {chapter: "one", node: "list-1"}]}, replies: []}],
decisions: [{id: "d", reviewer: "A", created: "2026-11-09T10:00:00Z", target: {chapter: "home", node: "p"},
    state: "accepted"}], states: [], files: [], names: []};
const mapped = model.toCore(home);
assert.deepEqual(mapped.comments[0].target, {abstract: true, node: "paragraph-1", quote: "x"});
assert.deepEqual(mapped.comments[0].batch.items, [{abstract: true}, {chapter: "one", node: "list-1"}]);
assert.deepEqual(mapped.decisions[0].target, {abstract: true, node: "p"});
assert.deepEqual(model.fromCore(mapped), home);

// A text target's place (anchorSpan): its positions where its quote is there; a copy saved by release
// 3.9.0 or earlier counted the review gutter's text, and its quote is found without it.
const gutter = "✓×💬";
const own = "See the details, the site and the detour.";
const at = (text, span) => text.slice(span.start, span.end);
assert.deepEqual(model.anchorSpan(own, {start: 4, end: 10, quote: "the de"}, gutter), {start: 4, end: 10});
assert.deepEqual(model.anchorSpan(own, {start: 4 + gutter.length, end: 10 + gutter.length, quote: "the de"}, gutter),
    {start: 4, end: 10}, "an old selection: one gutter's length earlier, not the nearest other 'the de'");
assert.deepEqual(model.anchorSpan(own, {start: 30 + gutter.length, end: 36 + gutter.length, quote: "the de"}, gutter),
    {start: 30, end: 36}, "the same words twice: the occurrence nearest the corrected place");
assert.equal(at(own, model.anchorSpan(own, {start: 0, end: gutter.length + own.length, quote: gutter + own}, gutter)),
    own, "an old whole-item target quotes the gutter too");
const spanning = "First.\nSecond block.";
assert.equal(at(spanning, model.anchorSpan(spanning,
    {start: 2 + gutter.length, end: 15 + 2 * gutter.length, quote: `rst.\n${gutter}Second b`}, gutter)),
    "rst.\nSecond b", "a quote across blocks held the next block's gutter");
assert.deepEqual(model.anchorSpan(own, {start: 3, end: 5, quote: "absent"}, gutter), {start: 3, end: 5},
    "a quote found nowhere keeps its positions");
assert.deepEqual(model.anchorSpan(own, {start: 3, end: 5}, gutter), {start: 3, end: 5}, "no quote: its positions");

// A span's two ends over text pieces (rangePoints): a start on a boundary is the earlier piece's end.
assert.deepEqual(model.rangePoints([4, 6, 3], 4, 12), {start: {index: 0, offset: 4}, end: {index: 2, offset: 2}});
assert.deepEqual(model.rangePoints([4, 6], 5, 7), {start: {index: 1, offset: 1}, end: {index: 1, offset: 3}});
assert.deepEqual(model.rangePoints([4, 6], 0, 0), {start: {index: 0, offset: 0}, end: {index: 0, offset: 0}});
assert.equal(model.rangePoints([4, 6], 5, 11), null, "a span past the text");
assert.equal(model.rangePoints([], 0, 1), null);
