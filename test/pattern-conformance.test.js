"use strict";

// Runs the shared pattern table (test/fixtures/pattern-conformance.json) through base.js's
// patternMatches, the page's answer; test_page_pattern.py runs it through the build's page_pattern.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const schema = fs.readFileSync(path.join(root, "src", "obs_html", "base.schema.json"), "utf8");
const islands = {"#base-schema": schema};
globalThis.document = {querySelector: selector => selector in islands ? {textContent: islands[selector]} : null};
vm.runInThisContext(fs.readFileSync(path.join(root, "src", "obs_html", "base.js"), "utf8"));

const fixture = JSON.parse(fs.readFileSync(path.join(root, "test", "fixtures", "pattern-conformance.json"), "utf8"));
for (const {pattern, text, matches} of fixture.cases) {
    assert.equal(globalThis.obsBases.patternMatches(pattern, text), matches,
        `pattern ${JSON.stringify(pattern)} on ${JSON.stringify(text)}`);
}
console.log(`pattern conformance: ${fixture.cases.length} of ${fixture.cases.length} cases conform`);
