"use strict";

// The chosen detail fields' pure layer (src/obs_html/table.js, chosenDetailEntries, hiddenDetailFields
// and shownRowText; input-model.md,
// Compact declarative table presentation, obsHtml.detailFields): the fields an opened row shows, out
// of its note's metadata entries, as the view lists them, and the fields search leaves out of such a row. No page: the runtime's only top-level use
// of the page is the canvas it measures text with, so a document stand-in that offers one loads it.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const context = {document: {createElement: () => ({getContext: () => ({})})}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "src", "obs_html", "table.js"), "utf8"), context);
const {chosenDetailEntries, hiddenDetailFields, shownRowText} = context.obsDataTable;
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

// Search: no list hides nothing (the option omitted).
const fields = names(entries);
assert.deepEqual(plain(hiddenDetailFields(fields, undefined, [])), []);

// An empty list hides every field of the note that no shown column or group is.
assert.deepEqual(plain(hiddenDetailFields(fields, [], [])), fields);

// A listed field, with the fields nested under it, is read; the rest is hidden.
assert.deepEqual(plain(hiddenDetailFields(fields, ["owner"], [])), ["status", "date", "owners", "kind"]);

// A shown column or group keeps its field, with or without its note. prefix, and the fields nested under
// it, but not a field that only starts with the same letters; a column that is no field of the note
// (file.name) keeps nothing.
assert.deepEqual(plain(hiddenDetailFields(fields, [], ["file.name", "note.status", "owner"])), ["date", "owners", "kind"]);
assert.deepEqual(plain(hiddenDetailFields(fields, ["date"], ["kind"])),
    ["status", "owner.name", "owner.team", "owners"]);

// A row's own text joins its values as a table record does, without the hidden fields' values, a
// value named with or without its note. prefix; a value that is no field of the note stays.
const values = {"file.name": "t1", status: "Needs you", "note.date": "2026-11-16", kind: "issue"};
assert.equal(shownRowText(values, []), "t1 Needs you 2026-11-16 issue");
assert.equal(shownRowText(values, ["date", "kind"]), "t1 Needs you");
