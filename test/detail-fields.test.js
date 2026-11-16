"use strict";

// The chosen detail fields' pure layer (src/obs_html/table.js, chosenDetailEntries; input-model.md,
// Compact declarative table presentation, obsHtml.detailFields): the fields an opened row shows, out
// of its note's metadata entries, as the view lists them. No page: the runtime's only top-level use
// of the page is the canvas it measures text with, so a document stand-in that offers one loads it.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const context = {document: {createElement: () => ({getContext: () => ({})})}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "src", "obs_html", "table.js"), "utf8"), context);
const {chosenDetailEntries} = context.obsDataTable;
const plain = value => JSON.parse(JSON.stringify(value));
const names = entries => plain(entries.map(([field]) => field));

const entries = [
    ["status", "Needs you"], ["date", "2026-11-16"], ["owner.name", "Ada"], ["owner.team", "Core"],
    ["owners", "Lin"], ["kind", "issue"],
];

// No list: every entry, as it is (the option omitted).
assert.equal(chosenDetailEntries(entries, undefined), entries);

// An empty list: no entry.
assert.deepEqual(names(chosenDetailEntries(entries, [])), []);

// One field: only that field.
assert.deepEqual(plain(chosenDetailEntries(entries, ["date"])), [["date", "2026-11-16"]]);

// The listed order, not the note's.
assert.deepEqual(names(chosenDetailEntries(entries, ["kind", "date", "status"])), ["kind", "date", "status"]);

// A name selects the fields nested under it, in the note's order, but not a field that only starts
// with the same letters.
assert.deepEqual(names(chosenDetailEntries(entries, ["owner"])), ["owner.name", "owner.team"]);

// A nested field listed after its parent is shown once, where the parent placed it.
assert.deepEqual(names(chosenDetailEntries(entries, ["owner", "owner.team", "date"])),
    ["owner.name", "owner.team", "date"]);

// A name the note has no entry for (a blank field is no entry) selects nothing.
assert.deepEqual(names(chosenDetailEntries(entries, ["missing", "date"])), ["date"]);

// The entries given are left as they are.
assert.deepEqual(names(entries), ["status", "date", "owner.name", "owner.team", "owners", "kind"]);
