"use strict";

// The limited-host banner's pure layer (src/obs_html/limited-host.js; architecture.md, Limited-host
// banner): environment facts in, the missing needs and the banner's line out, no page.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const context = {};  // No document: the wiring finds no banner and leaves nothing missing.
vm.runInNewContext(fs.readFileSync(path.join(root, "src", "obs_html", "limited-host.js"), "utf8"), context);
const {missingNeeds, bannerText, hostFacts, missing} = context.obsLimitedHost;
const table = JSON.parse(fs.readFileSync(path.join(root, "src", "obs_html", "limited-host.json"), "utf8")).needs;
const plain = value => JSON.parse(JSON.stringify(value));

assert.deepEqual(plain(missing), []);
// Only a declared need that the host lacks is missing; a fact that is not false is met.
const facts = {scripts: true, storage: false, "claude-runtime": false};
assert.deepEqual(plain(missingNeeds(["storage", "claude-runtime"], facts)), ["storage", "claude-runtime"]);
assert.deepEqual(plain(missingNeeds(["scripts"], facts)), []);
assert.deepEqual(plain(missingNeeds(["storage"], {storage: true})), []);
assert.deepEqual(plain(missingNeeds(["storage"], {})), []);
// One line: what does not work, then where to open the page instead, each place once.
assert.equal(bannerText([], table), "");
assert.equal(bannerText(["storage"], table), `Limited viewer: ${table.storage.missing}. ${table.storage.openInstead}.`);
assert.equal(bannerText(["storage", "claude-runtime"], table),
    `Limited viewer: ${table.storage.missing}; ${table["claude-runtime"].missing}. ` +
    `${table.storage.openInstead}, or ${table["claude-runtime"].openInstead}.`);
// The probes: a store that throws or loses the value is missing storage; claude.use is the runtime.
const store = () => {
    const values = new Map();
    return {setItem: (k, v) => values.set(k, v), getItem: k => values.get(k) ?? null, removeItem: k => values.delete(k)};
};
assert.deepEqual(plain(hostFacts({localStorage: store()})), {scripts: true, storage: true, "claude-runtime": false});
assert.deepEqual(plain(hostFacts({get localStorage() { throw new Error("SecurityError"); }})).storage, false);
assert.deepEqual(plain(hostFacts({localStorage: {...store(), getItem: () => null}})).storage, false);
assert.equal(hostFacts({localStorage: store(), claude: {use: () => {}}})["claude-runtime"], true);
assert.equal(hostFacts({localStorage: store(), get claude() { throw new Error("hidden"); }})["claude-runtime"], false);
console.log("limited-host: ok");
