"use strict";

// Runs the core's shared Bases filter fixture (test/fixtures at the repository root) against the
// browser evaluator; test_render.py runs the same fixture against the renderer's filter check.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const schema = fs.readFileSync(path.join(root, "src", "obs_html", "base.schema.json"), "utf8");
globalThis.document = {querySelector: selector => selector === "#base-schema" ? {textContent: schema} : null};
vm.runInThisContext(fs.readFileSync(path.join(root, "src", "obs_html", "base.js"), "utf8"));

const fixture = JSON.parse(fs.readFileSync(
    path.join(root, "..", "..", "test", "fixtures", "bases-filter-conformance.json"), "utf8"));
const records = fixture.records.map(record => ({
    id: record.id, sourcePath: record.path, frontmatter: record.frontmatter,
}));
const valueFor = (record, field) => globalThis.obsBases.recordValue(record, field);

for (const {filter, expected} of fixture.cases) {
    const compiled = globalThis.obsBases.compileFilter(filter, valueFor);
    assert.deepEqual(records.filter(record => compiled.match(record)).map(record => record.id), expected,
        `filter ${JSON.stringify(filter)}`);
}
for (const filter of fixture.unsupported) {
    assert.throws(() => globalThis.obsBases.compileFilter(filter, valueFor), TypeError,
        `unsupported filter ${JSON.stringify(filter)} must be rejected`);
}
console.log(`${fixture.cases.length} cases and ${fixture.unsupported.length} unsupported filters conform.`);
