"use strict";

// The timeline figure's pure model (src/obs_html/timeline-figure.js, obsTimeline.model; obs
// input-model, Timeline figures): the content and the records in, the lanes and the rows out, no
// page and no clock. Every row order and cell rule is checked here, without a browser.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const context = {};  // No document: the model needs no page.
vm.runInNewContext(fs.readFileSync(path.join(root, "src", "obs_html", "timeline-figure.js"), "utf8"), context);
const {model} = context.obsTimeline;
const plain = value => JSON.parse(JSON.stringify(value));

const CONTENT = {
  records: {where: [{field: "kind", equals: "work-item"}]},
  date: "when", lane: "team", today: "2026-01-02", lanes: ["Build", "Review"],
  band: "state", bands: [
    {value: "doing", label: "Today", at: "today"}, {value: "next", label: "Next", at: "end"},
    {value: "later", label: "Later", at: "end"}],
  anchor: "today", label: "short", text: "summary", flags: "flags", marker: "release",
};
let serial = 0;
const record = fields => ({path: `work/${++serial}.md`, slug: `work-${serial}`, title: `Note ${serial}`, fields});
const RECORDS = [
  record({when: "2026-01-04", team: "Build", short: "Planned"}),
  record({when: "2025-12-30", team: "Build", short: "Old", summary: "The old one.",
          flags: [{label: "late", tone: "warning"}, {label: "odd", tone: "loud"}, {tone: "positive"}]}),
  record({when: "2026-01-02", team: "Review", short: "Now"}),
  record({when: "2025-12-30", team: "Review"}),
  record({state: "doing", team: "Review", short: "Doing"}),
  record({state: "later", team: "Build", short: "Later", when: "2026-03-01"}),
  record({when: "2026-01-02", team: "Build", short: "v1", release: true}),
  record({when: "2026-01-02", team: "Build", short: "Second", release: "true"}),
];

// The rows, top to bottom: the past days oldest first with a divider where the year changes, the
// at-today bands, the planned days, then the at-end bands in listed order.
const shown = model(CONTENT, RECORDS);
assert.deepEqual(plain(shown.lanes), ["Build", "Review"]);
assert.deepEqual(plain(shown.rows.map(row => row.kind === "year" ? `year ${row.year}` : `${row.kind} ${row.key}`)), [
  "past 2025-12-30", "year 2026", "past 2026-01-02", "band band:doing", "planned 2026-01-04",
  "band band:next", "band band:later"]);
assert.deepEqual(plain(shown.rows.filter(row => row.kind !== "year").map(row => row.label)),
  ["30 Dec", "2 Jan", "Today", "4 Jan", "Next", "Later"]);
assert.equal(shown.empty, false);

// anchor: today names the first row after the past rows; a band value names that band.
assert.deepEqual(plain(shown.rows.filter(row => row.anchor).map(row => row.key)), ["band:doing"]);
assert.equal(model({...CONTENT, anchor: "later"}, RECORDS).rows.find(row => row.anchor).key, "band:later");
assert.equal(model({...CONTENT, bands: [], band: undefined}, RECORDS).rows.find(row => row.anchor).key, "2026-01-04",
  "without bands at today, the anchor is the first planned day");
assert.equal(model({...CONTENT, anchor: undefined}, RECORDS).rows.some(row => row.anchor), false);

// A cell: its stop, its items (not markers), their count, the last one's label, its markers.
const cells = key => shown.rows.find(row => row.key === key).cells;
const [build, review] = cells("2026-01-02");
assert.deepEqual(plain({stop: build.stop, count: build.count, last: build.last, markers: build.markers}),
  {stop: "past", count: 1, last: "Second", markers: ["v1"]}, "only a marker field of true makes a marker");
assert.deepEqual(plain({stop: review.stop, count: review.count, last: review.last}), {stop: "past", count: 1, last: "Now"});
assert.equal(cells("2026-01-04")[0].stop, "planned");
assert.equal(cells("2026-01-04")[1].stop, "none", "a lane without records here has no stop");
assert.equal(cells("band:doing")[1].stop, "band");
assert.equal(cells("band:next")[0].stop, "none", "an empty band still has its row");
assert.equal(cells("band:later")[0].last, "Later", "a record in a listed band sits there, whatever its day");

// An item: its label (the label field, else the note's title), its text and its flags, a tone
// outside the four drawn as neutral and a flag without a label left out.
const [old] = cells("2025-12-30")[0].items;
assert.deepEqual(plain(old), {key: "2025-12-30", lane: "Build", day: "2025-12-30", path: old.path, slug: old.slug,
  label: "Old", text: "The old one.", flags: [{label: "late", tone: "warning"}, {label: "odd", tone: "neutral"}],
  marker: false});
assert.equal(cells("2025-12-30")[1].items[0].label, "Note 4");

// A filter's records: rows with no record left go, the lanes stay as the population fixes them.
const filtered = model(CONTENT, RECORDS.filter(item => item.fields.team === "Build"), RECORDS);
assert.deepEqual(plain(filtered.lanes), ["Build", "Review"]);
assert.ok(filtered.rows.filter(row => row.kind !== "year").every(row => row.cells[1].count === 0 && row.cells[1].stop !== "past"));
assert.deepEqual(plain(filtered.rows.map(row => row.key || row.year)),
  ["2025-12-30", "2026", "2026-01-02", "band:doing", "2026-01-04", "band:next", "band:later"]);

// Without lanes, the population's lane names in case-insensitive order.
assert.deepEqual(plain(model({...CONTENT, lanes: undefined}, [...RECORDS, record({when: "2025-12-30", team: "audit"})]).lanes),
  ["audit", "Build", "Review"]);

// No record to draw: the model says so, and the page draws one sentence instead of a grid.
assert.equal(model(CONTENT, []).empty, true);
assert.equal(context.obsTimeline.EMPTY, "No records to show.");

// The same records in another order give the same rows.
assert.deepEqual(plain(model(CONTENT, [...RECORDS].reverse())), plain(shown));
