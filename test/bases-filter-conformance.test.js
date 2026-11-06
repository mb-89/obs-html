"use strict";

// Runs the core's shared Bases filter and query condition fixture (test/fixtures at the repository
// root) against the browser evaluators; test_render.py runs it against the renderer's filter check.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const schema = fs.readFileSync(path.join(root, "src", "obs_html", "base.schema.json"), "utf8");
// The core's case-folding table, which the page embeds as #case-folding.
const folding = fs.readFileSync(path.join(root, "..", "..", "src", "obs", "case-folding.json"), "utf8");
const islands = {"#base-schema": schema, "#case-folding": folding};
globalThis.document = {querySelector: selector => selector in islands ? {textContent: islands[selector]} : null};
vm.runInThisContext(fs.readFileSync(path.join(root, "src", "obs_html", "base.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(root, "src", "obs_html", "query.js"), "utf8"));

const fixture = JSON.parse(fs.readFileSync(
    path.join(root, "..", "..", "test", "fixtures", "bases-filter-conformance.json"), "utf8"));
// Artifact records also carry the reader's own fields; a condition must not see them.
const records = fixture.records.map(record => ({
    id: record.id, sourcePath: record.path, frontmatter: record.frontmatter,
    marks: (record.marks || []).map(mark => ({kind: mark.category, label: mark.id})),
    fields: {title: record.id, slug: record.id},
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
for (const {where, expected} of fixture.conditions) {
    const conditions = globalThis.obsQuery.compileConditions(where);
    assert.deepEqual(records.filter(record => conditions.match(record)).map(record => record.id),
        expected, `where ${JSON.stringify(where)}`);
}
// A drill-down's expression retains exactly the records its conditions select.
for (const {where, expected} of fixture.conditions) {
    const query = globalThis.obsQuery.compile(globalThis.obsQuery.conditionsExpression(where));
    assert.deepEqual(records.filter(record => query.match(record)).map(record => record.id), expected,
        `drill-down of ${JSON.stringify(where)}`);
}
// The reader's filter applies the same rule set; its /…/c flag is a condition's matchCase.
for (const [expression, expected] of [
    ["status: /^Open$/", ["a"]], ["status: /^Open$/c", []], ["status: /^open$/c", ["a"]],
    ["Owner.Name: /^EVE$/", ["e"]], ["note.slug: a", []],
    ["street: STRASSE", ["e"]], ["street: stra*e", ["e"]], ["street: /^strasse$/", ["e"]],
    ["street: /^STRASSE$/c", []], ["dotless: i", []], ["word: \u03bf\u03b4\u03bf\u03c2", ["e"]],
]) {
    const query = globalThis.obsQuery.compile(expression);
    assert.deepEqual(records.filter(record => query.match(record)).map(record => record.id), expected,
        `reader filter ${expression}`);
}
console.log(`${fixture.cases.length} cases, ${fixture.conditions.length} conditions and ${fixture.unsupported.length} unsupported filters conform.`);
