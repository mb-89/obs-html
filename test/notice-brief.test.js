"use strict";

// The notice center's passing line, its pure core (src/obs_html/notices.js, obsNoticeBrief; artifact-ui.md,
// Dock menu), and the sink's name it says (src/obs_html/answers.js, readerName; answers.md, Contract):
// values in, values out, no page.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = path.resolve(__dirname, "..", "src", "obs_html");
const context = {};  // No document: notices.js gives its core and wires nothing.
vm.runInNewContext(fs.readFileSync(path.join(source, "notices.js"), "utf8"), context);
const {timing, sent, sentRecord} = context.obsNoticeBrief;
assert.equal(context.obsNotices, undefined);
const plain = value => JSON.parse(JSON.stringify(value));

// The setting's default, 0, keeps the line off, as does anything but a positive whole time.
for (const off of [0, undefined, null, -1, 1.5, "4000", Number.NaN]) assert.equal(timing(off, false), null, String(off));
// A positive time is how long it holds; then it fades, or with reduced motion it goes at once.
const fade = timing(4000, false).fade;
assert.ok(fade > 0);
assert.deepEqual(plain(timing(4000, false)), {hold: 4000, fade});
assert.deepEqual(plain(timing(1, true)), {hold: 1, fade: 0});

// Send's words: where the sink names itself, the line says where; else it says only that it went.
assert.equal(sent("Claude"), "Sent to Claude.");
assert.equal(sent(undefined), "Sent.");
assert.equal(sent(""), "Sent.");
assert.equal(sentRecord("1 verdict and 2 comments", "Claude"), "1 verdict and 2 comments sent to Claude.");
assert.equal(sentRecord("1 verdict and 0 comments", undefined), "1 verdict and 0 comments sent.");

// The sink's name: plain text of 1 to 40 characters for the reader.
const answers = require(path.join(source, "answers.js"));
for (const name of ["Claude", "x", "x".repeat(40), "Claude · review"]) assert.equal(answers.readerName(name), true, name);
for (const name of ["", " Claude", "Claude ", "x".repeat(41), "Two\nlines", "tab\there", "\u0085", 7, null, {}]) {
    assert.equal(answers.readerName(name), false, JSON.stringify(name));
}
