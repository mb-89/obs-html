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
    state: "accepted"}], states: [], files: []};
const mapped = model.toCore(home);
assert.deepEqual(mapped.comments[0].target, {abstract: true, node: "paragraph-1", quote: "x"});
assert.deepEqual(mapped.comments[0].batch.items, [{abstract: true}, {chapter: "one", node: "list-1"}]);
assert.deepEqual(mapped.decisions[0].target, {abstract: true, node: "p"});
assert.deepEqual(model.fromCore(mapped), home);
