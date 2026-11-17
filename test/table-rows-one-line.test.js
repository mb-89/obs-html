"use strict";

// One line per table row's pure layers (artifact.tableRowsOneLine; generic-tables.md, Columns and cells,
// One line per row, and Pipe tables): src/obs_html/table.js's isCut and rowCutToggle for a Base table,
// src/obs_html/pipe-tables.js's isCut, rowDisclosure, wholeText and toggleLabel for a pipe table. No page:
// each runtime's top-level use of the page is a stand-in here (the canvas table.js measures text with,
// the chapter body and the listeners pipe-tables.js registers).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = name => fs.readFileSync(path.join(__dirname, "..", "src", "obs_html", name), "utf8");
const base = {document: {createElement: () => ({getContext: () => ({})})}};
vm.runInNewContext(source("table.js"), base);
const pipe = {document: {querySelector: () => null, addEventListener: () => {}}};
vm.runInNewContext(source("pipe-tables.js"), pipe);
const {isCut, rowCutToggle} = base.obsDataTable;
const {rowDisclosure, wholeText, toggleLabel} = pipe.obsPipeTables;

// A box is cut where its content overflows it by more than a pixel's rounding, down or across.
for (const cut of [isCut, pipe.obsPipeTables.isCut]) {
    assert.equal(cut({scrollHeight: 20, clientHeight: 20, scrollWidth: 100, clientWidth: 100}), false);
    assert.equal(cut({scrollHeight: 21, clientHeight: 20, scrollWidth: 101, clientWidth: 100}), false);
    assert.equal(cut({scrollHeight: 60, clientHeight: 20, scrollWidth: 100, clientWidth: 100}), true);
    assert.equal(cut({scrollHeight: 20, clientHeight: 20, scrollWidth: 140, clientWidth: 100}), true);
}

// A Base row's own disclosure (children, details) is never doubled by a cut's.
assert.equal(rowCutToggle({structural: true, open: false, cut: true, had: false}), false);
assert.equal(rowCutToggle({structural: true, open: true, cut: null, had: false}), false);
// Without one: a cut row gets it, a row that fits has none, an open row keeps it, an unmeasured
// closed row keeps what it had.
assert.equal(rowCutToggle({structural: false, open: false, cut: true, had: false}), true);
assert.equal(rowCutToggle({structural: false, open: false, cut: false, had: true}), false);
assert.equal(rowCutToggle({structural: false, open: true, cut: null, had: true}), true);
assert.equal(rowCutToggle({structural: false, open: false, cut: null, had: true}), true);
assert.equal(rowCutToggle({structural: false, open: false, cut: null, had: false}), false);

// A pipe row: the same rule, without children or details.
assert.equal(rowDisclosure({open: false, cut: true, had: false}), true);
assert.equal(rowDisclosure({open: false, cut: false, had: true}), false);
assert.equal(rowDisclosure({open: true, cut: null, had: true}), true);
assert.equal(rowDisclosure({open: false, cut: null, had: false}), false);

// A cut cell's title: its lines, white space collapsed, empty ones left out.
assert.equal(wholeText(["See  Ada", "", "and a second\n line "]), "See Ada\nand a second line");
assert.equal(wholeText(["", "  "]), "");

// The disclosure's name: what it does and the row's first cell.
assert.equal(toggleLabel(false, "long"), "Expand long");
assert.equal(toggleLabel(true, "long"), "Collapse long");
assert.equal(toggleLabel(false, ""), "Expand");
