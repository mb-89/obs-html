"use strict";

// The passing fold's pure layer (src/obs_html/table.js, foldPassingRows and passingCaption;
// generic-tables.md, Query and filtering): the rows the filters keep and which of them pass in, the
// rows listed while folded, the count of passing rows and the total out, and the line that names
// them. No page: the runtime's only top-level use of the page is the canvas it measures text with,
// so a document stand-in that offers one loads it.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const context = {document: {createElement: () => ({getContext: () => ({})})}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "src", "obs_html", "table.js"), "utf8"), context);
const {foldPassingRows, passingCaption} = context.obsDataTable;
const plain = value => JSON.parse(JSON.stringify(value));
const keys = fold => plain(fold.listed.map(row => row.key));
const row = (key, status, parentKey = "") => ({key, parentKey, values: {status}});
const passes = item => item.values.status === "verified";

// 266 rows, 2 failing: the failing rows are listed, in their order; 264 of 266 pass.
const many = Array.from({length: 266}, (_, index) =>
    row(`r${index}`, index === 7 || index === 200 ? "open" : "verified"));
const folded = foldPassingRows(many, passes);
assert.deepEqual(keys(folded), ["r7", "r200"]);
assert.deepEqual([folded.passing, folded.total], [264, 266]);
assert.equal(passingCaption(folded, "verified"), "264 of 266 verified");

// One passing row fewer in (a table-local filter hid it): the counts follow the rows given.
const narrowed = foldPassingRows(many.filter(item => item.key !== "r0"), passes);
assert.equal(passingCaption(narrowed, "verified"), "263 of 265 verified");
assert.deepEqual(keys(narrowed), ["r7", "r200"]);

// Every row passes: nothing is listed, and the line is the all-pass sentence.
const green = foldPassingRows(many.filter(passes), passes);
assert.deepEqual(keys(green), []);
assert.equal(passingCaption(green, "verified"), "All 264 verified.");

// No row passes: every row is listed, and the line still counts them.
const red = foldPassingRows([row("a", "open"), row("b", "open")], passes);
assert.deepEqual(keys(red), ["a", "b"]);
assert.equal(passingCaption(red, "verified"), "0 of 2 verified");

// No row at all: nothing listed, no line (the view keeps today's empty result).
const none = foldPassingRows([], passes);
assert.deepEqual([keys(none), none.passing, none.total], [[], 0, 0]);
assert.equal(passingCaption(none, "verified"), "");

// A tree: a failing row keeps its ancestor path, as a table-local filter keeps it, and a passing
// ancestor listed for that reason still counts as passing.
const tree = [
    row("root", "verified"), row("child", "verified", "root"), row("leaf", "open", "child"),
    row("other", "verified"), row("sibling", "verified", "root"),
];
const kept = foldPassingRows(tree, passes);
assert.deepEqual(keys(kept), ["root", "child", "leaf"]);
assert.deepEqual([kept.passing, kept.total], [4, 5]);
assert.equal(passingCaption(kept, "verified"), "4 of 5 verified");

// The rows given are left as they are.
assert.equal(many.length, 266);

console.log("passing-rows: ok");
