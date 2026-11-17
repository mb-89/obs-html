"use strict";

// The Theme select's pure core (src/obs_html/style-choice.js, obsStyleChoice.choice; artifact-ui.md,
// Styling): the page's themes and the reader's choice in, the root's attributes and the select's
// options out; no page.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = path.resolve(__dirname, "..", "src", "obs_html");
const context = {};  // No document: style-choice.js gives its core and wires nothing.
vm.runInNewContext(fs.readFileSync(path.join(source, "style-choice.js"), "utf8"), context);
const {choice} = context.obsStyleChoice;
const plain = value => JSON.parse(JSON.stringify(value));

// Default first, labelled Default; every other theme by its name, in the page's order.
assert.deepEqual(plain(choice(["default", "contrast", "work"], "contrast")), {
    root: {"data-style": "contrast"},
    options: [{value: "default", label: "Default"}, {value: "contrast", label: "contrast"},
              {value: "work", label: "work"}],
});
assert.deepEqual(plain(choice(["default", "work"], "default")).root, {"data-style": "default"});
// A choice the page does not carry is refused, naming the themes it carries.
assert.throws(() => choice(["default", "work"], "other"), /"other".*default, work/);
