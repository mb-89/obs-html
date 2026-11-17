"use strict";

// Runs the shared list of Base definitions (fixtures/base-rules.json) through base.js's own check,
// obsBases.project, as the page runs it; test_base_rules.py runs the same list through the build.
// The assets schema is served as the page serves it: without it every icon fails the schema check.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = name => fs.readFileSync(path.join(root, "src", "obs_html", name), "utf8");
const islands = {
    "#base-schema": source("base.schema.json"),
    '[data-json-schema="assets.schema.json"]': source("assets.schema.json"),
};
globalThis.document = {querySelector: selector => selector in islands ? {textContent: islands[selector]} : null};
vm.runInThisContext(source("base.js"));

const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "base-rules.json"), "utf8"));
const project = definition => globalThis.obsBases.project(structuredClone(definition), fixture.records);

for (const {name, definition} of fixture.refused) {
    assert.throws(() => project(definition), error => {
        assert.ok(error instanceof TypeError, `${name}: ${error}`);
        // A message that starts with root is the schema check's: the case must pass the schema.
        assert.ok(!error.message.startsWith("root"), `${name}: the schema refused it: ${error.message}`);
        return true;
    }, `refused case ${name} must be refused`);
}
for (const {name, definition} of fixture.accepted) {
    assert.doesNotThrow(() => project(definition), `accepted case ${name}`);
}
console.log(`${fixture.refused.length} refused and ${fixture.accepted.length} accepted Base definitions agree with base.js.`);
