"use strict";

// Runs the shared action icons (fixtures/action-icons.json) through base.js's own schema check,
// obsBases.validate, as the page and its query view run it; test_registers.py runs the same icons
// through the build. The assets schema is served as the page serves it: icon names refer to it.
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

const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "action-icons.json"), "utf8"));
const definitions = icon => [
    {properties: {run: {obsHtml: {icon}}}, views: [{type: "table", order: ["file.name"]}]},
    {properties: {run: {obsHtml: {icons: [{name: "upload", label: "Run", action: "app.run"}, icon]}}},
        views: [{type: "table", order: ["file.name"]}]},
];
for (const {name, icon} of fixture.refused) {
    for (const definition of definitions(icon)) {
        assert.throws(() => globalThis.obsBases.validate(structuredClone(definition)), TypeError,
            `refused icon ${name} must be refused`);
    }
}
for (const {name, icon} of fixture.accepted) {
    for (const definition of definitions(icon)) {
        assert.doesNotThrow(() => globalThis.obsBases.validate(structuredClone(definition)), `accepted icon ${name}`);
    }
}
console.log(`${fixture.refused.length} refused and ${fixture.accepted.length} accepted action icons agree with base.js.`);
