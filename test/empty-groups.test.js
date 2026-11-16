"use strict";

// The empty groups' pure layer (src/obs_html/table.js, emptyGroupLabels; generic-tables.md, groupOrder):
// a view's groupOrder and the labels of the groups its filtered rows form in, the listed labels no
// row has out, in their listed order. No page: the runtime's only top-level use of the page is the
// canvas it measures text with, so a document stand-in that offers one loads it.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const context = {document: {createElement: () => ({getContext: () => ({})})}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "src", "obs_html", "table.js"), "utf8"), context);
const {emptyGroupLabels, compareGroupLabels} = context.obsDataTable;
const plain = labels => JSON.parse(JSON.stringify(labels));

const order = ["design", "build", "commissioning"];
// Only the listed values no row has, in listed order, whatever order the rows' groups came in.
assert.deepEqual(plain(emptyGroupLabels(order, ["build", "design"])), ["commissioning"]);
assert.deepEqual(plain(emptyGroupLabels(order, new Map([["commissioning", []], ["design", []]]).keys())), ["build"]);
// A filter that removes every row leaves every listed value empty; a full table leaves none.
assert.deepEqual(plain(emptyGroupLabels(order, [])), order);
assert.deepEqual(plain(emptyGroupLabels(order, ["design", "build", "commissioning", "unlisted"])), []);
// A value no row has is matched exactly, as the group labels are: no case folding, no trimming.
assert.deepEqual(plain(emptyGroupLabels(order, ["Design", "build ", "commissioning"])), ["design", "build"]);
// The order itself is left as it is.
assert.deepEqual(plain(order), ["design", "build", "commissioning"]);

// The labels it returns sort with the others by the one group comparison: listed first in listed
// order, unlisted after in the groupBy direction, and a reader sort on the property overrides both.
const level = {property: "phase", direction: "ASC", order};
const labels = ["zeta", "build", "alpha", ...emptyGroupLabels(order, ["zeta", "build", "alpha"])];
assert.deepEqual(plain([...labels].sort(compareGroupLabels(level))), ["design", "build", "commissioning", "alpha", "zeta"]);
assert.deepEqual(plain([...labels].sort(compareGroupLabels({...level, direction: "DESC"}))),
    ["design", "build", "commissioning", "zeta", "alpha"]);
assert.deepEqual(plain([...labels].sort(compareGroupLabels(level, {property: "phase", direction: "DESC"}))),
    ["zeta", "design", "commissioning", "build", "alpha"]);

console.log("empty-groups: ok");
