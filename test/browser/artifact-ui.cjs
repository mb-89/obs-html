const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const harness = require("./artifact-harness.cjs");
async function run() {
const {window, document, context, parseHTML, TextRange, timers, runTimers} =
    await harness.open(process.argv[2], process.argv[3]);
const body = document.querySelector("[data-chapter-body]");
// Artifact-ui.md "Reading shell": Home and the breadcrumbs live in the one-row top band.
const band = document.querySelector("[data-top-band-path]");
assert.equal(document.documentElement.classList.contains("paged-mode"), true);
context.obsPages.setPaged(false);
const current = () => document.querySelector("[data-active-chapter]").dataset.chapter;
const click = (element) => element.dispatchEvent(new window.Event("click", {
    bubbles: true, cancelable: true,
}));
const tables = () => [...body.querySelectorAll(".data-table-shell")];
const navigate = (slug) => context.obsArtifact.activateChapter(slug);
// Artifact-ui.md "Floating window": a link to a note outside the contents shows it as context; the page stays.
const followToContext = (link, slug) => {
    const page = current();
    click(link);
    assert.equal(current(), page);
    const floating = document.querySelector("[data-guided-card]");
    assert.ok(floating, `${slug} opens in the floating window`);
    assert.equal(floating.querySelector("[data-guided-card-use]").textContent, "Context");
    assert.equal(floating.querySelector(".guided-card-title").textContent,
        context.obsArtifact.records.find((record) => record.slug === slug).title);
    click(floating.querySelector("[data-guided-card-close]"));
    assert.equal(document.querySelector("[data-guided-card]"), null);
    navigate(slug);
};
if (process.argv[7] === "--discovered-query-controls-only") {
    for (const path of process.argv.slice(4, 6)) {
        vm.runInContext(fs.readFileSync(path, "utf8"), context, {filename: path});
    }
    let changes = 0;
    document.addEventListener("obs-filter-change", () => { changes++; });
    const filter = document.querySelector("[data-filter-input]");
    const search = document.querySelector("[data-search-input]");
    const draft = document.querySelector(
        '[data-filter-fields] .filter-field[data-field="status"] [data-filter-value="draft"]');
    assert.ok(draft, "The discovered Filter exposes canonical status facets.");
    click(draft);
    const applied = context.obsArtifact.filterSummary().expression;
    assert.match(applied, /status.*draft/);
    assert.equal(context.obsArtifact.filterSummary().chapters, 3);
    const selection = document.querySelector("[data-filter-selections] button");
    assert.equal(selection.getAttribute("aria-label"), "Remove status: draft");
    assert.equal(selection.firstChild.textContent, "status: draft");
    filter.value = "(";
    filter.dispatchEvent(new window.Event("input"));
    assert.equal(filter.getAttribute("aria-invalid"), "true");
    assert.equal(context.obsArtifact.filterSummary().expression, applied);
    search.value = "status: final";
    search.dispatchEvent(new window.Event("input"));
    assert.equal(document.querySelectorAll("[data-search-results] li").length, 3);
    assert.equal(context.obsArtifact.filterSummary().expression, applied,
        "Searching does not replace the independently applied Filter.");
    document.dispatchEvent(new window.CustomEvent("obs-bar-change", {
        detail: {bar: "filter", open: false},
    }));
    assert.equal(filter.value, "");
    assert.equal(context.obsArtifact.filterSummary().empty, true);
    assert.equal(changes, 2);
    return;
}
if (process.argv[7] === "--table-controls-only") {
    const rows = Array.from({length: 5}, (_, index) => ({
        key: `row-${index + 1}`,
        values: {name: `Item ${index + 1}`, status: index < 3 ? "A" : "B"},
        fields: {name: `Item ${index + 1}`, status: index < 3 ? "A" : "B"},
    }));
    const table = context.obsDataTable.render({
        key: "controls", rows, initialPageSize: 2,
        columns: [{key: "name", label: "Name"}, {key: "status", label: "Status"}],
        initialGroup: [{property: "status", direction: "ASC"}],
    });
    body.append(table.element);
    const shell = table.element;
    const visible = () => [...shell.querySelectorAll("tbody tr[data-row-key]")]
        .map(row => row.dataset.rowKey);
    const footer = shell.querySelector(".data-table-footer");
    const button = name => footer.querySelector(`[aria-label="${name} table page"]`);
    assert.ok(shell.querySelector("th .data-table-controls"));
    assert.ok(shell.querySelector(".data-table-group-toggle"));
    assert.equal(footer.querySelector(".data-table-count").textContent, "5 of 5 items");
    assert.deepEqual([...footer.querySelectorAll("button[aria-label]")].map(node =>
        node.getAttribute("aria-label")), [
        "First table page", "Previous table page", "Next table page", "Last table page",
    ]);
    assert.equal(button("First").disabled, true);
    assert.equal(button("Previous").disabled, true);
    assert.deepEqual(visible(), ["row-1", "row-2"]);
    click(button("Next"));
    assert.deepEqual(visible(), ["row-3", "row-4"]);
    assert.equal(footer.querySelector(".data-table-page").textContent, "Page 2 of 3");
    click(button("Last"));
    assert.deepEqual(visible(), ["row-5"]);
    assert.equal(button("Next").disabled, true);
    assert.equal(button("Last").disabled, true);
    click(button("Previous"));
    assert.deepEqual(visible(), ["row-3", "row-4"]);
    click(button("First"));
    assert.deepEqual(visible(), ["row-1", "row-2"]);
    const size = footer.querySelector('[aria-label="Items per page"]');
    size.value = "3";
    size.dispatchEvent(new window.Event("change"));
    assert.deepEqual(visible(), ["row-1", "row-2", "row-3"]);
    size.value = "0";
    size.dispatchEvent(new window.Event("change"));
    assert.equal(size.getAttribute("aria-invalid"), "true");
    assert.deepEqual(visible(), ["row-1", "row-2", "row-3"]);
    table.setExpression("name: missing");
    assert.deepEqual(visible(), []);
    assert.equal(footer.querySelector(".data-table-count").textContent, "0 of 5 items");
    return;
}
if (process.argv[7] === "--table-help-only") {
    await verifyTableHelpOnly();
    return;
}
if (process.argv[7] === "--inspect-json") {
    // Prints records, rendered table row keys and duplicate DOM ids for the listed chapters.
    const chapters = {};
    for (const slug of JSON.parse(process.argv[8] || "[]")) {
        navigate(slug);
        await context.obsArtifact.whenChapterReady();
        runTimers();
        const ids = [...document.querySelectorAll("[id]")].map(element => element.id);
        const rowKeys = shell => [...shell.querySelectorAll("tbody tr[data-row-key]")].map(row => row.dataset.rowKey);
        const buttons = index => [...tables()[index].querySelectorAll("[data-table-views] button")];
        chapters[slug] = {
            tables: tables().map(rowKeys),
            duplicateIds: [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))],
            // Per table, each view's name, labels (the obsHtml.label cells) and row keys, chosen in turn.
            views: tables().map((_, index) => {
                const views = (buttons(index).length ? buttons(index) : [null]).map((_, view) => {
                    if (buttons(index).length) click(buttons(index)[view]);
                    runTimers();
                    const shell = tables()[index];
                    const label = [...shell.querySelectorAll("thead th")]
                        .findIndex(cell => cell.dataset.columnKey === "obsHtml.label");
                    return {
                        name: buttons(index)[view]?.textContent ?? "",
                        rows: rowKeys(shell),
                        labels: label < 0 ? [] : [...shell.querySelectorAll("tbody tr[data-row-key]")]
                            .map(row => row.children[label].textContent),
                    };
                });
                if (buttons(index).length) click(buttons(index)[0]);
                runTimers();
                return views;
            }),
        };
    }
    const records = context.obsArtifact.records.map(record => ({
        slug: record.slug, filterAttributes: record.filterAttributes, metadataEntries: record.metadataEntries,
    }));
    console.log(JSON.stringify({records, chapters}));
    return;
}
if (process.argv[7] === "--comments-only") {
    await verifyCommentExportOnly();
    return;
}
if (process.argv[7] === "--artifact-change-only") {
    context.structuredClone = structuredClone;
    context.Node = window.Node;
    context.CSS = {escape: value => value};
    context.getSelection = () => null;
    context.localStorage = {getItem: () => null, setItem() {}};
    vm.runInContext(fs.readFileSync(process.argv[6], "utf8"), context);
    vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), context);
    vm.runInContext(fs.readFileSync(process.argv[5], "utf8"), context);
    const changed = () => {
        const entry = document.querySelector('[data-notice-list="information"] [data-notice="changed-html"]');
        assert.equal(Boolean(entry?.querySelector("[data-artifact-download]")), Boolean(entry),
            "The changed-HTML entry carries the existing save owner's download button.");
        return Boolean(entry);
    };
    const semanticDirty = () => document.querySelector("[data-review-save-guidance]").dataset.dirty === "true";
    const artifactDirty = () => {
        const event = new window.Event("beforeunload", {cancelable: true});
        window.dispatchEvent(event);
        assert.equal(changed(), event.defaultPrevented);
        return event.defaultPrevented;
    };
    assert.equal(artifactDirty(), false);
    context.obsArtifact.commitProperty("one", "explanation", "Original");
    assert.equal(artifactDirty(), false, "No-op canonical editors do not dirty HTML.");
    context.obsFilter.setExpression("status:draft");
    assert.equal(artifactDirty(), false, "Applying a filter is not a change of the HTML.");
    assert.equal(semanticDirty(), false, "Saved reader state is not a semantic review edit.");
    context.obsFilter.setExpression("status: /[");
    assert.equal(artifactDirty(), false, "An invalid filter draft is not a change of the HTML.");
    assert.ok(document.querySelector('[data-notice-list="information"] [data-notice="applied-filter"]'),
        "The applied filter is an information entry.");
    click(document.querySelector('[data-notice="applied-filter"] [data-filter-clear]'));
    assert.equal(document.querySelector('[data-notice="applied-filter"]'), null);
    assert.equal(artifactDirty(), false, "Clearing a filter is not a change of the HTML.");
    context.obsArtifact.setViewSelection("proof", ["a"], ["a", "b"]);
    assert.equal(artifactDirty(), true);
    assert.equal(semanticDirty(), false);
    context.obsArtifact.commitProperty("one", "explanation", "Changed");
    assert.equal(semanticDirty(), true);
    assert.equal(artifactDirty(), true);
    let output, closed = false;
    context.showSaveFilePicker = async () => ({createWritable: async () => ({
        write: async contents => {output = contents;},
        close: async () => {closed = true;},
    })});
    await context.obsComments.saveReviewedCopy();
    assert.equal(closed, true);
    assert.equal(artifactDirty(), false);
    assert.equal(semanticDirty(), false);
    assert.ok(output.includes("Changed"));
    const saved = parseHTML(output).document;
    assert.equal(saved.querySelector("[data-header-notices]"), null, "Notice DOM is never saved.");
    context.obsFilter.setExpression("status:draft");
    assert.equal(artifactDirty(), false, "A filter after a save is not a change of the HTML.");
    context.obsArtifact.setViewSelection("proof", ["b"], ["a", "b"]);
    context.showSaveFilePicker = async () => {throw Object.assign(new Error("cancel"), {name: "AbortError"});};
    await context.obsComments.saveReviewedCopy();
    assert.equal(artifactDirty(), true, "Cancel is not a save.");
    context.Blob = Blob;
    let downloads = 0;
    context.URL = {createObjectURL: () => {downloads++; return "blob:proof";}, revokeObjectURL() {}};
    context.showSaveFilePicker = async () => ({createWritable: async () => ({
        write: async () => {}, close: async () => {throw new Error("close failed");},
    })});
    await context.obsComments.saveReviewedCopy();
    assert.equal(artifactDirty(), true, "Failed close cannot confirm retention.");
    assert.equal(downloads, 1);
    delete context.showSaveFilePicker;
    await context.obsComments.saveReviewedCopy();
    assert.equal(artifactDirty(), true, "Fallback download is unconfirmed.");
    assert.equal(downloads, 2);
    const writeIsland = context.obsArtifactTransport.writeIsland;
    let resume;
    context.obsArtifactTransport = {...context.obsArtifactTransport, writeIsland: async (...args) => {
        await new Promise(resolve => {resume = resolve;});
        return writeIsland(...args);
    }};
    context.showSaveFilePicker = async () => ({createWritable: async () => ({
        write: async contents => {output = contents;}, close: async () => {},
    })});
    const pending = context.obsComments.saveReviewedCopy();
    while (!resume) await new Promise(setImmediate);
    context.obsArtifact.commitProperty("one", "explanation", "Newer edit");
    context.obsArtifact.setViewSelection("proof", ["a"], ["a", "b"]);
    resume();
    await pending;
    assert.equal(artifactDirty(), true, "A confirmed capture cannot clean later canonical or reader edits.");
    assert.equal(semanticDirty(), true);
    assert.ok(!output.includes("Newer edit"));
    context.obsArtifact.commitProperty("one", "explanation", "Changed");
    assert.equal(artifactDirty(), true, "Later reader-only edits remain unsaved.");
    assert.equal(semanticDirty(), false);
    context.obsArtifact.setViewSelection("proof", ["b"], ["a", "b"]);
    assert.equal(artifactDirty(), false, "Reverting to the confirmed capture is clean.");
    console.log("PASS artifact/review dirty, revert, invalid draft, save/cancel/failure/download/newer edits.");
    return;
}
navigate("metadata-only");
assert.equal(document.querySelector("[data-frontmatter-panel]").hidden, false);
assert.equal(document.querySelector("[data-frontmatter-toggle]").getAttribute("aria-expanded"), "true");
assert.ok(document.querySelector("[data-frontmatter-body]").textContent.includes("Ada"));
assert.ok(document.querySelector("[data-frontmatter-body] strong"));
assert.ok(document.querySelector('[data-frontmatter-body] a[href="#details"]'));
navigate("home");
assert.equal(document.querySelector("[data-frontmatter-panel]").hidden, true);
const openChildren = (labels) => {
    const crumb = band.querySelector("[data-breadcrumb-current]");
    const chapter = current();
    click(crumb);
    const chooser = document.getElementById(crumb.getAttribute("aria-controls"));
    assert.equal(chooser.hasAttribute("open"), true);
    assert.equal(crumb.getAttribute("aria-expanded"), "true");
    assert.equal(current(), chapter);
    assert.deepEqual([...chooser.querySelectorAll("a")].map((link) => link.textContent), labels);
    click(crumb);
    assert.equal(chooser.hasAttribute("open"), false);
    click(crumb);
    return chooser;
};

assert.equal(current(), "home");
const tocHeader = document.querySelector('[data-bar="toc"] .dock-bar-header');
assert.equal(tocHeader.querySelectorAll("[data-toc-action]").length, 2);
assert.equal(document.querySelector('[data-bar="toc"] .dock-bar-content [data-toc-action]'), null);
assert.equal(body.querySelector("h1.document-title").textContent, "Test document");
assert.equal(body.querySelectorAll("h1").length, 1);
assert.ok(body.textContent.includes("Abstract prose."));
assert.equal(body.querySelector(".content-emphasis p").textContent.trim(), "Abstract prose.");
const pageNumber = (element) => Number(element.textContent.match(/^Page (\d+) of \d+$/)[1]);
assert.equal(tables().length, 2);
assert.equal(tables()[0].querySelectorAll("tbody tr").length, 3);
assert.equal(tables()[1].querySelectorAll("tbody tr").length, 5);
assert.deepEqual(
    ["timestamp", "generator", "target"].map((key) =>
        tables()[1].querySelector(`[data-row-key="generation:${key}"]`)?.firstElementChild.textContent),
    ["timestamp", "generator", "target"],
);
assert.match(
    tables()[1].querySelector('[data-row-key="generation:target"] .data-table-preformatted').textContent,
    /^name: {4}\S.*\nversion: \S+\ncommit: {2}\S+$/,
);
const drillDown = `#tags?tableFilter=${encodeURIComponent("type:/^open_point$/")}`;
window.location.hash = drillDown;
window.dispatchEvent(new window.Event("popstate"));
assert.equal(current(), "tags");
assert.equal(body.querySelectorAll("tbody tr[data-row-key]").length, 1);
assert.ok(body.querySelector("tbody").textContent.includes("child_open"));
assert.notEqual(document.querySelector("[data-menu-button]").dataset.filterActive, "true");
navigate("home");
assert.ok(body.innerHTML.indexOf("Abstract prose.") < body.innerHTML.indexOf("data-data-table="));
assert.equal(tables()[1].querySelector("tbody").textContent.includes("team: Ada, Lin"), true);
assert.equal(tables()[1].querySelector("tbody").textContent.includes('{"team"'), false);
openChildren(["Parent", "Glossary", "Tags", "References"]);
click(band.querySelector(".chapter-breadcrumb-menu a[href='#parent']"));
assert.equal(current(), "parent");
let chooser = openChildren(["Child"]);
click(chooser.querySelector("a"));
assert.equal(current(), "child");
chooser = openChildren(["Node"]);
click(chooser.querySelector("a"));
assert.equal(current(), "node");
const quantityTable = body.querySelector(".data-table-shell");
const quantityRow = quantityTable.querySelector("tbody tr[data-row-key]");
assert.ok(quantityRow.querySelector('a[href="#details"]'));
assert.ok(quantityRow.querySelector("strong"));
assert.ok(quantityRow.querySelector(".data-table-tree-toggle"));
click(quantityRow.querySelector(".data-table-tree-toggle"));
assert.ok([...body.querySelectorAll(".data-table-detail-row .note-detail-metadata dt")]
    .some((term) => term.textContent === "citation"));
assert.ok(body.querySelector(".data-table-detail-row .note-detail-metadata a[href='#details']"));
assert.ok(body.querySelector(".data-table-detail-row .note-detail-metadata strong"));
let crumb = band.querySelector("[data-breadcrumb-current]");
assert.equal(crumb.hasAttribute("aria-controls"), false);
click(crumb);
assert.equal(current(), "node");
click(band.querySelector(".chapter-breadcrumbs > a[href='#parent']"));
assert.equal(current(), "parent");
navigate("child");
assert.equal(body.querySelector(".chapter-bluf"), null);
navigate("home");
let shell = tables()[0];
assert.equal(shell.querySelector('tr[data-row-key="parent"] td:last-child').textContent, "");
assert.equal(shell.querySelector('tr[data-row-key="node"] .data-table-tree-toggle'), null);
assert.equal(shell.querySelector('tr[data-row-key="child"] [data-table-detail-toggle]'), null);
assert.ok(shell.querySelector('tr[data-row-key="child"] a[href="#child"]'));
const preview = document.getElementById("hover-card");
const childLink = shell.querySelector('tr[data-row-key="child"] a[href="#child"]');
const settings = JSON.parse(document.querySelector("[data-artifact-data]").textContent).hoverCard;
const trigger = (element, type, relatedTarget = null, properties = {}) => {
    const event = new window.Event(type, {bubbles: true});
    Object.assign(event, {relatedTarget, ...properties});
    element.dispatchEvent(event);
};
trigger(childLink, "pointerover");
assert.equal(preview.hidden, true);
assert.equal([...timers.values()][0].delay, settings.showDelayMilliseconds);
runTimers();
assert.equal(preview.hidden, false);
assert.equal(preview.querySelector("a").getAttribute("href"), "#child");
assert.ok(preview.querySelector("p").textContent.startsWith("Question."));
assert.ok(preview.querySelector("p").textContent.length <= settings.excerptCharacters);
assert.equal(current(), "home");
assert.equal(childLink.getAttribute("aria-describedby"), preview.id);
// Lifecycle (artifact-ui.md "Overlays"): leaving the link and the card keeps the card.
trigger(childLink, "pointerout", preview);
trigger(preview, "pointerout");
runTimers();
assert.equal(preview.hidden, false);
click(document.querySelector("[data-chapter-scroll]"));
assert.equal(preview.hidden, true, "A click outside closes the card");
assert.equal(childLink.hasAttribute("aria-describedby"), false);
trigger(childLink, "pointerover");
trigger(childLink, "pointerout");
runTimers();
assert.equal(preview.hidden, true);
trigger(childLink, "focusin");
runTimers();
assert.equal(preview.hidden, false);
trigger(childLink, "keydown", null, {key: "Escape"});
assert.equal(preview.hidden, true);
trigger(childLink, "pointerover", null, {pointerType: "touch"});
runTimers();
assert.equal(preview.hidden, true);
trigger(childLink, "focusin");
runTimers();
click(preview.querySelector("a"));
assert.equal(current(), "child");
assert.equal(preview.hidden, true);
navigate("home");
shell = tables()[0];
const nodeLink = shell.querySelector('tr[data-row-key="node"] a[href="#node"]');
trigger(nodeLink, "pointerover");
runTimers();
assert.equal(preview.hidden, false);
assert.ok(preview.querySelectorAll("dt").length <= settings.metadataEntries);
assert.ok(preview.querySelectorAll("dd").length);
assert.ok(preview.querySelector("p").textContent.startsWith("Long prose"));
assert.ok(preview.querySelector("p").textContent.endsWith("..."));
assert.ok(preview.querySelector("p").textContent.length <= settings.excerptCharacters);
assert.equal(preview.textContent.includes("CODE MUST NOT APPEAR"), false);
assert.ok(parseFloat(preview.style.left) >= 0);
assert.ok(parseFloat(preview.style.top) >= 0);
const otherLink = shell.querySelector('tr[data-row-key="child"] a[href="#child"]');
trigger(otherLink, "pointerover");
runTimers();
assert.equal(preview.hidden, false, "Hovering another link replaces the card in place");
assert.equal(preview.querySelector("a").getAttribute("href"), "#child");
assert.equal(nodeLink.hasAttribute("aria-describedby"), false);
trigger(nodeLink, "pointerover");
runTimers();
trigger(nodeLink, "focusout", preview.querySelector("a"));
trigger(preview.querySelector("a"), "focusin");
runTimers();
assert.equal(preview.hidden, false);
trigger(preview, "scroll");
assert.equal(preview.hidden, false);
trigger(document.querySelector("[data-chapter-scroll]"), "scroll");
assert.equal(preview.hidden, false, "Scrolling keeps the card while its trigger stays in view");
nodeLink.getBoundingClientRect = () => ({top: -60, bottom: -40, left: 0, right: 80, width: 80, height: 20});
trigger(document.querySelector("[data-chapter-scroll]"), "scroll");
assert.equal(preview.hidden, true, "The card closes once its trigger scrolls out of view");
const referenceRecord = context.obsArtifact.records.find((record) => record.slug === "reference");
assert.ok(referenceRecord, "The linked reference note is in the canonical store");
navigate("parent");
const referenceLink = body.querySelector('a[href="#reference"]');
assert.ok(referenceLink, "The rendered citation remains a clickable internal link");
trigger(referenceLink, "pointerover");
runTimers();
assert.equal(preview.hidden, false);
assert.deepEqual([...preview.querySelectorAll("dt")].map((term) => term.textContent),
    ["document", "description", "kind"]);
assert.equal(preview.querySelector("dd a[href='#details']").textContent, "Source document");
assert.equal(preview.querySelectorAll("dd")[1].textContent,
    "A source whose metadata is its complete content.");
assert.equal(preview.textContent.includes("position"), false);
assert.equal(preview.textContent.includes("origin"), false);
navigate("references");
const referenceTables = tables();
assert.equal(referenceTables.length, 2);
assert.deepEqual([...referenceTables[0].querySelectorAll("tr[data-row-key]")]
    .map((row) => row.dataset.rowKey), ["note:reference", "note:quiet-reference"]);
assert.ok(referenceTables[0].querySelector("tbody tr[data-row-key='note:reference']")
    .textContent.includes("[1]"));
assert.ok(referenceTables[0].querySelector("tbody tr[data-row-key='note:quiet-reference']")
    .textContent.includes("[2]"));
assert.deepEqual([...referenceTables[1].querySelectorAll("tr[data-row-key]")]
    .map((row) => row.dataset.rowKey), ["note:quiet-reference", "note:reference"]);
navigate("home");
shell = tables()[0];
const external = document.createElement("a");
external.href = "https://example.invalid/";
body.append(external);
trigger(external, "pointerover");
runTimers();
assert.equal(preview.hidden, true);
external.setAttribute("href", "#missing");
trigger(external, "focusin");
runTimers();
assert.equal(preview.hidden, true);
external.remove();
click(shell.querySelector('tr[data-row-key="node"] a[href="#node"]'));
assert.equal(current(), "node");
navigate("home");
shell = tables()[0];
click(shell.querySelector(".data-table-tree-toggle"));
assert.equal(shell.querySelectorAll("tbody tr").length, 1);
click(shell.querySelector(".data-table-tree-toggle"));
assert.equal(shell.querySelectorAll("tbody tr").length, 3);
click(shell.querySelector(".data-table-options-toggle"));
click([...shell.querySelectorAll(".filter-pill")].find((button) => button.textContent === "Query view"));
let editor = shell.querySelector("textarea");
assert.equal(editor.hidden, false);
const original = editor.value;
editor.value = "views: [";
editor.dispatchEvent(new window.Event("input"));
editor.dispatchEvent(new window.Event("blur"));
assert.equal(editor.getAttribute("aria-invalid"), "true");
assert.equal(shell.querySelector('[role="alert"]').hidden, false);
assert.equal(shell.querySelectorAll("tbody tr").length, 3);
navigate("parent");
navigate("home");
shell = tables()[0];
editor = shell.querySelector("textarea");
assert.equal(editor.value, "views: [");
assert.equal(editor.hidden, false);
const edited = context.obsBases.parse(original);
// The authored Home fence selects chapter records; the edit selects glossary records instead.
edited.obs = {records: "glossary"};
delete edited.filters;
edited.views[0].order = ["term", "definition"];
editor.value = context.obsBases.dump(edited);
editor.dispatchEvent(new window.Event("input"));
editor.dispatchEvent(new window.Event("blur"));
shell = tables()[0];
assert.equal(shell.dataset.queryView, "false");
assert.equal(shell.querySelectorAll("tbody tr").length, 2);
assert.equal(shell.querySelector("thead th").dataset.columnKey, "term");
assert.equal(tables()[1].querySelectorAll("tbody tr").length, 5);
navigate("parent");
navigate("home");
assert.equal(tables()[0].querySelectorAll("tbody tr").length, 2);
assert.equal(tables()[0].querySelector("thead th").dataset.columnKey, "term");
navigate("tags");
assert.equal(body.querySelector(".data-table-tree-toggle"), null);
assert.equal(body.querySelector("[data-table-detail-toggle]"), null);
assert.equal(body.querySelector(".data-table-detail-row"), null);
assert.equal(body.querySelectorAll("tbody tr[data-row-key]").length, 2);
click(body.querySelector('tbody a[data-source-chapter="child"]'));
assert.equal(current(), "child");
assert.ok(body.textContent.includes("Question."));
navigate("glossary");
assert.equal(body.querySelectorAll("tbody tr").length, 3);
const abbreviationTable = body.querySelectorAll(".data-table-shell")[1];
assert.equal(abbreviationTable.querySelectorAll("tbody tr[data-row-key]").length, 1);
assert.equal(
    abbreviationTable.querySelector("tbody tr[data-row-key]").dataset.rowKey,
    "glossary:conclusion",
);
const citation = abbreviationTable.querySelector("tbody tr[data-row-key] td:nth-child(2) a[href='#details']");
assert.ok(citation);
assert.equal(citation.textContent, "Extra details");
assert.ok(abbreviationTable.querySelector("tbody tr td strong"));
assert.ok(abbreviationTable.querySelector("tbody tr .data-table-tree-toggle"));
assert.equal(body.querySelector('tr[data-row-key="glossary:conclusion"] a[href="#conclusion"]'), null);
assert.equal(body.querySelector('tr[data-row-key="glossary:bluf"] a[href="#bluf"]'), null);
let conclusion = body.querySelector('tr[data-row-key="glossary:conclusion"] [data-table-detail-toggle]');
assert.ok(conclusion);
const glossaryLink = body.querySelector('a[href="#conclusion"]');
trigger(glossaryLink, "pointerover");
runTimers();
assert.equal(preview.hidden, false);
assert.equal(preview.querySelector("p").textContent, "The conclusion.");
// Glossary hover card: term and definition only (artifact-ui.md "Link hover card").
assert.equal(preview.querySelectorAll("dt").length, 0);
assert.equal(preview.querySelector(".hover-card-title").getAttribute("href"), "#conclusion");
assert.equal(preview.querySelector("h1, table, img, script"), null);
trigger(glossaryLink, "keydown", null, {key: "Escape"});
trigger(conclusion, "pointerover");
runTimers();
assert.equal(preview.hidden, true);
assert.equal(conclusion.getAttribute("aria-expanded"), "false");
const glossaryHash = window.location.hash;
click(conclusion);
assert.equal(current(), "glossary");
assert.equal(window.location.hash, glossaryHash);
assert.ok(body.querySelector('tr[data-detail-owner="glossary:conclusion"] h1'));
assert.equal(body.querySelector('tr[data-row-key="glossary:conclusion"] [data-table-detail-toggle]').getAttribute("aria-expanded"), "true");
click(body.querySelector('tr[data-row-key="glossary:conclusion"] .data-table-tree-toggle'));
assert.equal(body.querySelector('tr[data-detail-owner="glossary:conclusion"]'), null);
assert.equal(current(), "glossary");
click(body.querySelector('tr[data-row-key="glossary:conclusion"] [data-table-detail-toggle]'));
assert.ok(body.querySelector('tr[data-detail-owner="glossary:conclusion"]'));
click(body.querySelector('tr[data-row-key="glossary:conclusion"] [data-table-detail-toggle]'));
assert.equal(body.querySelector('tr[data-detail-owner="glossary:conclusion"]'), null);
assert.ok(body.querySelector("tbody").textContent.includes("presenting the Conclusion"));
assert.equal(document.querySelector('[data-toc-link="bluf"]'), null);
assert.equal(document.querySelector('[data-toc-link="conclusion"]'), null);
assert.equal(context.obsArtifact.records.filter((record) => record.slug === "bluf").length, 1);
let entry = body.querySelector('tr[data-row-key="glossary:bluf"]');
assert.equal(entry.querySelector(".disclosure-toggle").getAttribute("aria-expanded"), "false");
click(entry.querySelector(".disclosure-toggle"));
let detail = body.querySelector('tr[data-detail-owner="glossary:bluf"]');
assert.ok(detail);
assert.equal(detail.querySelector("td").colSpan, 2);
assert.ok(detail.querySelector("h1").textContent.includes("BLUF"));
assert.equal(detail.querySelectorAll(".data-table-shell").length, 1);
assert.equal(detail.querySelectorAll(".data-table-shell tbody tr[data-row-key]").length, 2);
assert.equal(body.querySelector(".data-table-count").textContent, "2 of 2 items");
followToContext(detail.querySelector('a[href="#details"]'), "details");
assert.equal(current(), "details");
assert.equal(band.querySelector(".chapter-home-link").getAttribute("href"), "#home");
assert.ok(body.textContent.includes("Nested content."));
assert.equal(document.querySelector('[data-step="1"]').disabled, true);
assert.equal(document.querySelector('[data-step="-1"]').disabled, true);
followToContext(body.querySelector('a[href="#conclusion"]'), "conclusion");
assert.equal(current(), "conclusion");
assert.equal(body.querySelector("h1").textContent, "Conclusion");
const outsideHome = band.querySelector(".chapter-home-link");
assert.equal(outsideHome.hasAttribute("data-breadcrumb-current"), false);
click(outsideHome);
assert.equal(current(), "home");
assert.equal(window.location.hash, "#home");
openChildren(["Parent", "Glossary", "Tags", "References"]);
const tocCount = document.querySelectorAll("[data-toc-link]").length;
context.obsArtifact.activateChapter("details/more");
assert.equal(current(), "details");
assert.equal(window.location.hash, "#details/more");
assert.ok(document.getElementById("details--more"));
assert.equal(document.querySelectorAll("[data-toc-link]").length, tocCount);
const noteFilter = context.obsQuery.compile("title: Parent");
assert.equal(context.obsArtifact.setFilter(noteFilter), 1);
click(band.querySelector(".chapter-home-link"));
assert.equal(current(), "home");
context.obsArtifact.setFilter(context.obsQuery.compile(""));
navigate("glossary");
entry = body.querySelector('tr[data-row-key="glossary:bluf"]');
click(entry.querySelector("[data-table-detail-toggle]"));
assert.equal(current(), "glossary");
followToContext(body.querySelector('tr[data-detail-owner="glossary:bluf"] a[href="#details"]'), "details");
assert.equal(current(), "details");
followToContext(body.querySelector('a[href="#conclusion"]'), "conclusion");
assert.equal(current(), "conclusion");
click(band.querySelector(".chapter-home-link"));
assert.equal(current(), "home");
navigate("child");
navigate("bluf");
assert.equal(current(), "bluf");
assert.equal(body.querySelector("h1").textContent, "BLUF");
click(band.querySelector(".chapter-home-link"));
assert.equal(current(), "home");

shell = tables()[0];
click(shell.querySelector(".data-table-options-toggle"));
click([...shell.querySelectorAll(".filter-pill")].find((button) => button.textContent === "Query view"));
editor = shell.querySelector("textarea");
const notesDefinition = context.obsBases.parse(editor.value);
notesDefinition.obs = {records: "note"};
delete notesDefinition.filters;
notesDefinition.views[0].order = ["title"];
editor.value = context.obsBases.dump(notesDefinition);
editor.dispatchEvent(new window.Event("input"));
editor.dispatchEvent(new window.Event("blur"));
shell = tables()[0];
const chapterNote = shell.querySelector('tr[data-row-key="note:child"]');
assert.equal(chapterNote.querySelector(".data-table-tree-toggle"), null);
assert.equal(chapterNote.querySelector("[data-table-detail-toggle]"), null);
assert.ok(chapterNote.querySelector('a[href="#child"]'));
const nonChapterNote = shell.querySelector('tr[data-row-key="note:conclusion"]');
assert.ok(nonChapterNote.querySelector(".data-table-tree-toggle"));
assert.ok(nonChapterNote.querySelector("[data-table-detail-toggle]"));
click(nonChapterNote.querySelector("[data-table-detail-toggle]"));
assert.equal(current(), "home");
assert.equal(shell.querySelector('tr[data-detail-owner="note:conclusion"] h1').textContent, "Conclusion");

const nodeRows = ["A", "B"].map((name) => ({
    key: name, values: {name, type: "Group"}, fields: {name, type: "Group"}, noteId: name,
}));
let detailCalls = 0;
const nodeTable = context.obsDataTable.render({
    key: "node-test", rows: nodeRows, initialPageSize: 1,
    columns: [{key: "name", label: "Name"}, {key: "type", label: "Type"}],
    initialGroup: [{property: "type", direction: "ASC"}],
    hasDetails: (row) => Boolean(row.noteId),
    renderDetails: (row, element) => {
        detailCalls += 1;
        element.textContent = `Details of ${row.noteId}`;
    },
});
body.append(nodeTable.element);
const nodeShell = nodeTable.element;
assert.equal(detailCalls, 0);
click(nodeShell.querySelector(".data-table-tree-toggle"));
assert.equal(nodeShell.querySelector('[data-detail-owner="A"]').textContent, "Details of A");
assert.equal(nodeShell.querySelector(".data-table-count").textContent, "2 of 2 items");
click(nodeShell.querySelector('[aria-label="Next table page"]'));
assert.equal(nodeShell.querySelector("[data-detail-owner]"), null);
assert.ok(nodeShell.querySelector('[data-row-key="B"]'));
click(nodeShell.querySelector('[aria-label="Previous table page"]'));
assert.equal(nodeShell.querySelector('[data-detail-owner="A"]').textContent, "Details of A");
click(nodeShell.querySelector("th[data-column-key='name']"));
click(nodeShell.querySelector("th[data-column-key='name']"));
assert.equal(nodeShell.querySelector("[data-detail-owner]"), null);
click(nodeShell.querySelector('[aria-label="Next table page"]'));
assert.ok(nodeShell.querySelector('[data-detail-owner="A"]'));
nodeTable.setExpression("name: B");
assert.equal(nodeShell.querySelector("[data-detail-owner]"), null);
nodeTable.setExpression("");
click(nodeShell.querySelector('[aria-label="Next table page"]'));
assert.ok(nodeShell.querySelector('[data-detail-owner="A"]'));
click(nodeShell.querySelector(".data-table-options-toggle"));
click([...nodeShell.querySelectorAll(".filter-pill")].find((button) => button.textContent === "Properties"));
click([...nodeShell.querySelector('[aria-label="Properties"]').querySelectorAll("button")].find(
    (button) => button.textContent === "Type",
));
const firstToggle = nodeShell.querySelector(".data-table-tree-toggle");
if (!nodeShell.querySelector("[data-detail-owner]")) click(firstToggle);
assert.equal(nodeShell.querySelector("[data-detail-owner] td").colSpan, 1);

async function verifyPages() {
    let imageComplete = true;
    let imageWidth = 100;
    let decodeImage = () => Promise.resolve();
    Object.defineProperty(window.HTMLImageElement.prototype, "complete", {
        configurable: true, get: () => imageComplete,
    });
    Object.defineProperty(window.HTMLImageElement.prototype, "naturalWidth", {
        configurable: true, get: () => imageWidth,
    });
    window.HTMLImageElement.prototype.decode = function () { return decodeImage(this); };
    Object.defineProperty(window.HTMLElement.prototype, "clientHeight", {
        configurable: true,
        get() { return this.classList.contains("paper-content") ? 300 : 0; },
    });
    Object.defineProperty(window.HTMLElement.prototype, "scrollHeight", {
        configurable: true,
        get() {
            if (!this.classList.contains("paper-content")) return 0;
            return Math.ceil(this.textContent.length / 80) * 20 +
                this.querySelectorAll("p, h1, h2, tr").length * 10;
        },
    });
    navigate("home");
    // Restore the edited summary query, then replace the authored metadata filter.
    shell = tables()[0];
    click(shell.querySelector(".data-table-options-toggle"));
    click([...shell.querySelectorAll(".filter-pill")].find((button) => button.textContent === "Query view"));
    editor = shell.querySelector("textarea");
    editor.value = original;
    editor.dispatchEvent(new window.Event("input"));
    editor.dispatchEvent(new window.Event("blur"));
    const metadataShell = tables()[1];
    click(metadataShell.querySelector(".data-table-options-toggle"));
    click([...metadataShell.querySelectorAll(".filter-pill")].find((button) => button.textContent === "Query view"));
    const metadataEditor = metadataShell.querySelector("textarea");
    const metadataDefinition = context.obsBases.parse(metadataEditor.value);
    delete metadataDefinition.filters;
    metadataEditor.value = context.obsBases.dump(metadataDefinition);
    metadataEditor.dispatchEvent(new window.Event("input"));
    metadataEditor.dispatchEvent(new window.Event("blur"));
    // Metadata exclusions are authored filters; replacing them reveals every metadata row.
    assert.ok(tables()[1].querySelector('[data-row-key="metadata:title"]'));
    assert.ok(tables()[1].querySelector('[data-row-key="metadata:subtitle"]'));

    context.obsPages.setPaged(true);
    assert.equal(document.querySelector("[data-active-chapter]").hidden, false);
    const pagedReader = document.querySelector(".paged-reader");
    assert.equal(pagedReader.hidden, false);
    assert.ok(band.querySelector(":scope > .chapter-breadcrumbs"));
    assert.equal(pagedReader.querySelector(".chapter-breadcrumbs"), null);
    let pagedCrumb = band.querySelector("[data-breadcrumb-current]");
    click(pagedCrumb);
    let pagedChooser = document.getElementById(pagedCrumb.getAttribute("aria-controls"));
    assert.equal(pagedChooser.hasAttribute("open"), true);
    click(pagedChooser.querySelector('a[href="#parent"]'));
    assert.equal(current(), "parent");
    pagedCrumb = band.querySelector("[data-breadcrumb-current]");
    click(pagedCrumb);
    pagedChooser = document.getElementById(pagedCrumb.getAttribute("aria-controls"));
    assert.equal(pagedChooser.hasAttribute("open"), true);
    click(pagedChooser.querySelector('a[href="#child"]'));
    assert.equal(current(), "child");
    click(band.querySelector('.chapter-breadcrumbs > a[href="#parent"]'));
    assert.equal(current(), "parent");
    navigate("conclusion");
    assert.ok(band.querySelector(".chapter-breadcrumbs"));
    click(band.querySelector(".chapter-home-link"));
    assert.equal(current(), "home");
    assert.equal(band.querySelectorAll(".chapter-breadcrumbs").length, 1);
    context.obsPages.setPaged(false);
    assert.equal(band.querySelectorAll(".chapter-breadcrumbs").length, 1);
    assert.equal(body.querySelector(".chapter-breadcrumbs"), null);
    context.obsPages.setPaged(true);
    assert.equal(band.querySelectorAll(".chapter-breadcrumbs").length, 1);
    const sheets = [...pagedReader.querySelectorAll(".paper-sheet")];
    const homeLastPage = pageNumber(sheets.at(-1).querySelector(".paper-page-number"));
    assert.equal(sheets[0].dataset.pageChapter, "home");
    assert.equal(sheets[0].querySelector(".document-title").textContent, "Test document");
    assert.ok(sheets[0].querySelector(".document-subtitle"));
    assert.equal(sheets[0].textContent.includes("Abstract prose."), false);
    assert.equal(sheets[0].querySelector("table"), null);
    assert.ok(pagedReader.querySelector('[data-page-chapter="@metadata"] table'));
    assert.ok(pagedReader.querySelector('[data-page-chapter="@abstract"]').textContent.includes("Abstract prose."));
    assert.equal(pagedReader.querySelectorAll('[data-page-chapter="@abstract"] .content-emphasis').length, 1);
    assert.equal(pagedReader.querySelector('[data-page-chapter="@abstract"] .document-subtitle'), null);
    assert.equal(pagedReader.querySelectorAll(".page-contents a").length, 6);
    assert.ok(pagedReader.querySelector(".data-table-footer"));
    assert.ok(pagedReader.querySelector(".data-table-controls"));
    click(document.querySelector('[data-step="1"]'));
    assert.equal(current(), "parent");
    assert.equal(pagedReader.querySelector(".paper-sheet").dataset.pageChapter, "parent");
    assert.equal(pageNumber(pagedReader.querySelector(".paper-page-number")), homeLastPage + 1);
    const parentLastPage = pageNumber([...pagedReader.querySelectorAll(".paper-page-number")].at(-1));
    navigate("child");
    assert.equal(pageNumber(pagedReader.querySelector(".paper-page-number")), parentLastPage + 1);
    const childLastPage = pageNumber([...pagedReader.querySelectorAll(".paper-page-number")].at(-1));
    navigate("node");
    assert.equal(pageNumber(pagedReader.querySelector(".paper-page-number")), childLastPage + 1);
    assert.ok(pagedReader.querySelectorAll(".paper-sheet").length >= 1);
    navigate(drillDown.slice(1));
    assert.equal(pagedReader.querySelectorAll("tbody tr[data-row-key]").length, 1);
    assert.ok(pagedReader.textContent.includes("child_open"));
    assert.equal(pagedReader.textContent.includes("child_question"), false);
    navigate("node");
    const nodeSource = document.createElement("div");
    context.obsArtifact.renderStatic("node", nodeSource);
    const normalize = (text) => text.replace(/\s/g, "");
    assert.ok(normalize(pagedReader.textContent).includes(normalize("Long prose for the preview.")));
    const nodeRecord = context.obsArtifact.records.find((record) => record.slug === "node");
    const originalNodeHtml = nodeRecord.html;
    nodeRecord.html += '<table><thead><tr><th>Repeated header</th></tr></thead><tbody>' +
        Array.from({length: 40}, (_, index) => `<tr><td>Row ${index}</td></tr>`).join("") +
        "</tbody></table>";
    navigate("node");
    assert.equal(pagedReader.querySelectorAll("tbody tr").length, 41);
    assert.equal(pagedReader.querySelectorAll("thead").length, 2);
    assert.ok([...pagedReader.querySelectorAll(".paper-content")].every(
        (element) => !element.querySelector("table") || element.querySelector("tbody tr"),
    ));
    nodeRecord.html = originalNodeHtml;

    context.obsArtifact.setFilter(context.obsQuery.compile("title: Child"));
    assert.equal(band.querySelectorAll(".chapter-breadcrumbs").length, 1);
    navigate("home");
    assert.equal(pagedReader.querySelectorAll(".page-contents a").length, 2);
    const printBook = document.querySelector(".print-book");
    const immediateFrame = context.requestAnimationFrame;
    const frames = [];
    context.requestAnimationFrame = (callback) => frames.push(callback);
    document.fonts = {ready: Promise.resolve()};
    const pendingDecodes = [];
    decodeImage = (image) => new Promise((resolve) => pendingDecodes.push({image, resolve}));
    const flushPromises = async () => {
        for (let index = 0; index < 20; index += 1) await Promise.resolve();
    };
    let printCalls = 0;
    window.print = () => {
        printCalls += 1;
        window.dispatchEvent(new window.Event("beforeprint"));
    };
    document.documentElement.dataset.theme = "dark";
    const firstExport = context.obsPages.exportPDF();
    await flushPromises();
    assert.equal(printBook.querySelectorAll("img").length, 4);
    assert.equal(printCalls, 0);
    assert.equal(frames.length, 0);
    assert.equal(pendingDecodes.length, 4);
    await context.obsPages.exportPDF();
    assert.equal(pendingDecodes.length, 4);
    pendingDecodes.splice(0).forEach(({image, resolve}) => {
        assert.equal(image.isConnected, true);
        resolve();
    });
    await flushPromises();
    assert.ok(printBook.querySelector("#pdf-child"));
    assert.equal(pendingDecodes.length, 4);
    assert.equal(frames.length, 0);
    pendingDecodes.splice(0).forEach(({image, resolve}) => {
        assert.ok(image.closest(".paper-sheet"));
        resolve();
    });
    await flushPromises();
    assert.equal(frames.length, 1);
    frames.shift()();
    await firstExport;
    decodeImage = () => Promise.resolve();
    context.requestAnimationFrame = immediateFrame;
    assert.equal(printCalls, 1);
    assert.equal(printBook.querySelectorAll("#pdf-home img").length, 2);
    assert.equal(printBook.querySelectorAll(".content-emphasis").length, 1);
    assert.equal(document.documentElement.dataset.theme, "dark");
    assert.ok(printBook.querySelector("#pdf-child"));
    assert.ok(printBook.querySelector("#pdf-parent"));
    assert.equal(printBook.querySelector("#pdf-node, #pdf-conclusion"), null);
    assert.deepEqual([...printBook.querySelectorAll(".page-contents a")].map(link =>
        link.getAttribute("href")), ["#pdf-parent", "#pdf-child"]);
    assert.equal(printBook.querySelector(".chapter-bluf .content-card-title a").getAttribute("href"), "artifact.html#bluf");
    assert.equal(printBook.querySelector(".chapter-breadcrumbs, button, input, .data-table-detail-row"), null);
    assert.equal(new Set([...printBook.querySelectorAll("[id]")].map((element) => element.id)).size,
        printBook.querySelectorAll("[id]").length);
    window.dispatchEvent(new window.Event("afterprint"));
    assert.equal(printBook.children.length, 0);
    assert.equal(document.documentElement.classList.contains("preparing-print"), false);
    assert.equal(pagedReader.hidden, false);
    context.obsArtifact.setFilter(context.obsQuery.compile(""));
    await context.obsPages.exportPDF();
    assert.equal(printBook.querySelectorAll(".page-contents a").length, 6);
    assert.ok(printBook.querySelector("#pdf-node"));
    const artifactPageNumbers = [...printBook.querySelectorAll(".paper-page-number")].map(
        pageNumber,
    );
    assert.deepEqual(artifactPageNumbers, artifactPageNumbers.map((_number, index) => index + 1));
    const pdfNodeFirstPage = printBook.querySelector("#pdf-node .paper-page-number").textContent;
    assert.ok(printBook.querySelector('a[href="#pdf-conclusion"]') === null);
    assert.ok(printBook.querySelector('a[href="artifact.html#conclusion"]'));
    assert.ok(printBook.querySelector('a[href="#pdf-child"]'));
    assert.ok([...printBook.querySelectorAll('a[href="#pdf-tags"]')].some(
        (link) => link.textContent === "Number of open points",
    ));
    assert.ok(printBook.querySelector('a[href="#pdf-node--extra"]'));
    assert.ok([...printBook.querySelectorAll(".paper-content")].every(
        (element) => element.scrollHeight <= element.clientHeight,
    ));
    window.dispatchEvent(new window.Event("afterprint"));
    navigate("node");
    assert.equal(pagedReader.querySelector(".paper-page-number").textContent, pdfNodeFirstPage);
    context.obsPages.setPaged(false);
    assert.equal(document.querySelector("[data-active-chapter]").hidden, false);
    assert.equal(band.querySelectorAll(".chapter-breadcrumbs").length, 1);
    window.dispatchEvent(new window.Event("beforeprint"));
    assert.ok(printBook.querySelector("#pdf-child"));
    window.dispatchEvent(new window.Event("afterprint"));
    assert.equal(printBook.children.length, 0);
    const workingPrint = window.print;
    window.print = () => { throw new Error("The document is already open."); };
    await assert.rejects(context.obsPages.exportPDF(), /document is already open/);
    assert.equal(printBook.children.length, 0);
    assert.equal(document.documentElement.classList.contains("preparing-print"), false);
    window.print = workingPrint;
    await context.obsPages.exportPDF();
    assert.ok(printBook.querySelector("#pdf-child"));
    // A host that omits afterprint must not leave the export command locked.
    await context.obsPages.exportPDF();
    assert.ok(printBook.querySelector("#pdf-child"));
    window.dispatchEvent(new window.Event("afterprint"));
    const callsBeforeAssetFailure = printCalls;
    imageWidth = 0;
    await assert.rejects(context.obsPages.exportPDF(), /Image could not load: Obsidian/);
    assert.equal(printCalls, callsBeforeAssetFailure);
    assert.equal(printBook.children.length, 0);
    imageWidth = 100;
    decodeImage = () => Promise.reject(new Error("invalid image"));
    await assert.rejects(context.obsPages.exportPDF(), /could not decode/);
    assert.equal(printCalls, callsBeforeAssetFailure);
    decodeImage = () => new Promise(() => {});
    const timedOutExport = context.obsPages.exportPDF();
    await flushPromises();
    const deadline = [...timers.values()].find(
        ({delay}) => delay === JSON.parse(document.querySelector("[data-artifact-data]").textContent)
            .printReadyTimeoutMilliseconds,
    );
    assert.ok(deadline);
    deadline.callback();
    await assert.rejects(timedOutExport, /Timed out waiting for print images or fonts/);
    assert.equal(printBook.children.length, 0);
    assert.equal(printCalls, callsBeforeAssetFailure);
    decodeImage = () => Promise.resolve();
    document.fonts = {ready: new Promise(() => {})};
    const fontTimeoutExport = context.obsPages.exportPDF();
    await flushPromises();
    [...timers.values()].find(({delay}) =>
        delay === JSON.parse(document.querySelector("[data-artifact-data]").textContent)
            .printReadyTimeoutMilliseconds,
    ).callback();
    await assert.rejects(fontTimeoutExport, /Timed out waiting/);
    assert.equal(printCalls, callsBeforeAssetFailure);
    document.fonts = {ready: Promise.resolve()};
    imageComplete = false;
    const loadingExport = context.obsPages.exportPDF();
    await flushPromises();
    assert.equal(printCalls, callsBeforeAssetFailure);
    const loadingImages = [...printBook.querySelectorAll("img")];
    imageComplete = true;
    loadingImages.forEach((image) => image.dispatchEvent(new window.Event("load")));
    await loadingExport;
    assert.equal(printCalls, callsBeforeAssetFailure + 1);
    window.dispatchEvent(new window.Event("afterprint"));
    imageComplete = false;
    const failedLoad = context.obsPages.exportPDF();
    await flushPromises();
    printBook.querySelector("img").dispatchEvent(new window.Event("error"));
    await assert.rejects(failedLoad, /Image could not load/);
    assert.equal(printBook.children.length, 0);
    imageComplete = true;
    await context.obsPages.exportPDF();
    assert.equal(printCalls, callsBeforeAssetFailure + 2);
    window.dispatchEvent(new window.Event("afterprint"));
    await verifyComments();
    console.log("PASS: internal previews, canonical note details, query editing, inherited metadata filters, paged front matter, measured overflow, filtered PDF projection, anchor/companion links, and print cleanup.");
}

async function verifyTableHelpOnly() {
    const fire = (element, type, relatedTarget = null) => {
        const event = new window.Event(type, {bubbles: true, cancelable: true});
        event.relatedTarget = relatedTarget;
        element.dispatchEvent(event);
    };
    navigate("chapter");
    const card = document.getElementById("hover-card");
    const action = body.querySelector('[data-artifact-action="replaceEvidence"]');
    assert.equal(action.title, "Replace evidence");
    assert.equal(body.querySelector(".data-table-icon-help"), null);
    fire(action, "pointerover");
    assert.equal(card.hidden, true);
    runTimers();
    assert.equal(card.hidden, false);
    assert.equal(action.getAttribute("aria-describedby"), card.id);
    assert.equal(card.querySelector("strong").textContent, "original evidence");
    assert.ok(card.textContent.includes("Read the canonical instructions"));
    assert.equal(card.querySelector('a[href="#target"]').textContent, "the canonical instructions");
    assert.equal(card.querySelector('a[href="https://example.org/export"]').textContent, "the official export");
    assert.equal(card.querySelector('a[href="obs-source:archive"]').textContent, "the source archive");
    assert.equal(card.querySelector("script, [onclick], a[href^='javascript:']"), null);
    assert.ok(card.textContent.includes("Select the exported file, not a screenshot."));
    fire(action, "pointerout", card);
    fire(card.querySelector("a"), "pointerover", action);
    runTimers();
    assert.equal(card.hidden, false);
    fire(card, "pointerout");
    runTimers();
    assert.equal(card.hidden, false, "Leaving the card keeps it (artifact-ui.md Overlays)");
    const escape = new window.Event("keydown", {bubbles: true, cancelable: true});
    escape.key = "Escape";
    action.dispatchEvent(escape);
    assert.equal(card.hidden, true);
    assert.equal(action.hasAttribute("aria-describedby"), false);
    const help = body.querySelector('[aria-label="Evidence help"]');
    fire(help, "focusin");
    runTimers();
    assert.equal(card.hidden, false);
    assert.equal(card.getAttribute("aria-label"), "Evidence help");
    const helpBox = help.getBoundingClientRect;
    help.getBoundingClientRect = () => ({top: 950, bottom: 970, left: 0, right: 20, width: 20, height: 20});
    fire(document, "scroll");
    assert.equal(card.hidden, true);
    help.getBoundingClientRect = helpBox;
    click(help);
    assert.equal(card.hidden, false);
    const plain = body.querySelector('[aria-label="Plain help"]');
    fire(plain, "focusin");
    runTimers();
    assert.ok(card.textContent.includes("Plain text <em>is not HTML</em>."));
    assert.equal(card.querySelector("em"), null);
    navigate("target");
    assert.equal(card.hidden, true);
    navigate("chapter");
    const renderedHelp = body.querySelector('[aria-label="Evidence help"]');
    assert.notEqual(renderedHelp, help);
    fire(renderedHelp, "pointerover");
    runTimers();
    assert.equal(card.hidden, false);
    assert.equal(document.querySelectorAll(".hover-card").length, 1);
    const unavailable = body.querySelector('[aria-label="Unavailable import: No importer"]');
    assert.equal(unavailable.disabled, true);
    assert.equal(unavailable.getAttribute("title"), "Unavailable import: No importer");
    renderedHelp.remove();
    await Promise.resolve();
    assert.equal(card.hidden, true);
    console.log("PASS: shared table help keeps canonical rich links, containment lifecycle and dynamic rows.");
}

async function verifyComments() {
    const sharedImage = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8xoAAAAASUVORK5CYII=";
    navigate("parent");
    assert.equal(body.querySelector('img[alt="Shared image"]').getAttribute("src"), sharedImage);
    const staticParent = document.createElement("div");
    context.obsArtifact.renderStatic("parent", staticParent);
    assert.equal(staticParent.querySelector('img[alt="Shared image"]').getAttribute("src"), sharedImage);

    const storage = new Map([["obs-html.appearance", "dark"]]);
    context.localStorage = {
        getItem: (key) => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value),
    };
    vm.runInContext(fs.readFileSync(process.argv[6], "utf8"), context, {filename: "storage.js"});
    context.Node = window.Node;
    context.NodeFilter = {SHOW_TEXT: 4};
    context.CSS = {escape: (value) => value};
    let selection = null;
    context.getSelection = () => selection;
    const appearance = document.querySelector("[data-theme-select]");
    Object.defineProperty(appearance, "value", {configurable: true, writable: true, value: "system"});
    vm.runInContext(fs.readFileSync(process.argv[5], "utf8"), context, {filename: "settings.js"});
    assert.equal(document.documentElement.dataset.theme, "light");
    appearance.value = "system";
    trigger(appearance, "change");
    assert.equal(document.documentElement.dataset.theme, "system");
    assert.equal(storage.get("obs-html.appearance"), "dark");
    appearance.value = "dark";
    trigger(appearance, "change");
    assert.equal(document.documentElement.dataset.theme, "dark");
    assert.equal(storage.get("obs-html.appearance"), "dark");
    appearance.value = "light";
    trigger(appearance, "change");
    assert.equal(document.documentElement.dataset.theme, "light");
    assert.equal(storage.get("obs-html.appearance"), "dark");
    const pagesToggle = document.querySelector("[data-pages-toggle]");
    const exportRow = document.querySelector(".settings-page-export");
    assert.ok(exportRow.contains(pagesToggle));
    const exportButton = document.querySelector("[data-export-pdf]");
    assert.ok(exportRow.contains(exportButton));
    assert.equal(exportButton.textContent, "Export to PDF");
    assert.ok(exportButton.title.includes("light colors"));
    assert.equal(document.querySelector('[data-bar="settings"] .dock-bar-content>p:not([role="status"])'), null);
    pagesToggle.checked = true;
    trigger(pagesToggle, "change");
    assert.equal(document.querySelector(".paged-reader").hidden, false);
    pagesToggle.checked = false;
    trigger(pagesToggle, "change");
    assert.equal(document.documentElement.classList.contains("paged-mode"), false);

    let staticRenderCalls = 0;
    const originalRenderStatic = context.obsArtifact.renderStatic;
    context.obsArtifact.renderStatic = function (...args) {
        staticRenderCalls += 1;
        return originalRenderStatic.apply(this, args);
    };
    let targetCloneCalls = 0;
    const originalCloneNode = window.Node.prototype.cloneNode;
    window.Node.prototype.cloneNode = function (...args) {
        targetCloneCalls += 1;
        return originalCloneNode.apply(this, args);
    };
    let railMeasureCalls = 0;
    const originalGetClientRects = window.HTMLElement.prototype.getClientRects;
    window.HTMLElement.prototype.getClientRects = function (...args) {
        railMeasureCalls += 1;
        return originalGetClientRects.apply(this, args);
    };
    vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), context, {filename: "comments.js"});
    context.obsPages.setPaged(true);
    navigate("glossary");
    context.obsArtifact.openBar("comments", "right");
    let row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    assert.ok(row.dataset.reviewItem.startsWith("row-"));
    const reviewId = row.dataset.reviewItem;
    assert.equal(row.querySelectorAll("[data-review-gutter]").length, 1);
    assert.equal(row.firstElementChild.querySelectorAll("[data-review-gutter]").length, 1);
    assert.equal(row.querySelectorAll("td[data-review-item], th[data-review-item]").length, 0);
    const originalTop = row.querySelector("[data-review-gutter]").getBoundingClientRect().top;
    click(row.querySelector(".review-action--accept"));
    row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    assert.equal(row.dataset.reviewState, "accepted");
    staticRenderCalls = 0;
    targetCloneCalls = 0;
    railMeasureCalls = 0;
    click(row.querySelector("[data-table-detail-toggle]"));
    assert.equal(staticRenderCalls, 0, "expanding a table detail must not statically render artifact records");
    assert.equal(targetCloneCalls, 0, "a table refresh must not clone full review-target text");
    assert.equal(
        railMeasureCalls,
        body.querySelectorAll("[data-review-item]").length,
        "paged and table-change notifications must not refresh review rails twice",
    );
    row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    const detail = body.querySelector('tr[data-detail-owner="glossary:bluf"]');
    assert.equal(row.dataset.reviewItem, reviewId);
    assert.equal(row.dataset.reviewState, "accepted");
    assert.equal(row.querySelectorAll("[data-review-gutter]").length, 1);
    assert.equal(row.querySelector("[data-review-gutter]").getBoundingClientRect().top, originalTop);
    assert.equal(detail.querySelectorAll("[data-review-item], [data-review-gutter]").length, 0);

    const paragraph = detail.querySelector("p");
    const range = new TextRange();
    range.selectNodeContents(paragraph);
    selection = {rangeCount: 1, isCollapsed: false, getRangeAt: () => range, removeAllRanges() {}};
    document.dispatchEvent(new window.Event("selectionchange"));
    const add = document.querySelector("[data-comment-add]");
    assert.equal(add.disabled, false);
    click(add);
    const annotation = context.obsComments.data.annotations.at(-1);
    assert.equal(annotation.target.table, row.closest("[data-data-table]").dataset.dataTable);
    assert.equal(annotation.target.row, "glossary:bluf");
    assert.equal(annotation.target.detail, true);
    assert.ok(annotation.target.end > annotation.target.start);
    assert.equal(row.dataset.reviewState, "accepted");
    assert.equal(row.querySelector(".review-action--comment").dataset.count, "1");
    click(row.querySelector("[data-table-detail-toggle]"));
    assert.equal(body.querySelector('tr[data-detail-owner="glossary:bluf"]'), null);
    row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    assert.equal(row.dataset.reviewState, "accepted");
    assert.equal(row.querySelector(".review-action--comment").dataset.count, "1");
    click(document.querySelector(".comment-target"));
    await context.obsArtifact.whenChapterReady();
    assert.ok(body.querySelector('tr[data-detail-owner="glossary:bluf"]'));
    row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    assert.equal(row.dataset.reviewItem, reviewId);
    assert.equal(row.querySelectorAll("[data-review-gutter]").length, 1);
    const glossaryShell = row.closest("[data-data-table]");
    click(glossaryShell.querySelector("th[data-column-key='term']"));
    row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    assert.equal(row.dataset.reviewItem, reviewId);
    assert.equal(row.dataset.reviewState, "accepted");
    assert.equal(body.querySelectorAll("tbody tr[data-row-key] [data-review-gutter]").length, 3);
    const queryShell = row.closest("[data-data-table]");
    click(queryShell.querySelector(".data-table-options-toggle"));
    click([...queryShell.querySelectorAll(".filter-pill")].find((button) => button.textContent === "Query view"));
    const queryEditor = queryShell.querySelector("textarea");
    queryEditor.value = context.obsBases.dump(context.obsBases.parse(queryEditor.value));
    queryEditor.dispatchEvent(new window.Event("input"));
    staticRenderCalls = 0;
    queryEditor.dispatchEvent(new window.Event("blur"));
    assert.ok(staticRenderCalls > 0, "editing a table definition must refresh cached review identities");
    row = body.querySelector('tr[data-row-key="glossary:bluf"]');
    assert.equal(row.dataset.reviewState, "accepted");
    staticRenderCalls = 0;
    click(row.querySelector("[data-table-detail-toggle]"));
    assert.equal(staticRenderCalls, 0, "cached review identities remain reusable after a definition edit");
    const reviewed = await context.obsComments.reviewedHtml();
    assert.ok(reviewed.includes('"detail":true'));
    assert.equal(reviewed.includes('class="paged-reader chapter-body"'), false);
    assert.equal(reviewed.includes('class="print-book chapter-body"'), false);
    const copyButton = document.querySelector("[data-comment-copy]");
    assert.ok(copyButton);
    assert.equal(copyButton.textContent.trim(), "Copy comments to clipboard");
    const originalDirty = document.querySelector("[data-review-save-guidance]").dataset.dirty;
    const originalIsland = document.querySelector("[data-comment-island]").textContent;
    context.obsComments.data.annotations.push({
        id: "selected-unicode",
        author: "Reviewer Ω",
        text: "First line.\n<Second line> & safe.",
        status: "open",
        target: {
            chapter: "beta", quote: "Quoted “text”\nacross lines.", prefix: "Before ",
            suffix: " after", start: 17, end: 42, item: "item-3", section: "Background",
        },
        batch: {
            scope: "section",
            items: [
                {chapter: "alpha", item: "item-2"},
                {chapter: "beta", item: "item-4"},
            ],
        },
        replies: [{
            id: "nested-reply",
            author: "Reply author",
            text: "Nested reply.",
            status: "resolved",
            replies: [{
                id: "deep-reply",
                author: "Third author",
                text: "Deep reply.",
                status: "open",
                replies: [],
            }],
        }],
    });
    document.querySelector("[data-comment-filter-input]").value = "no matching comment";
    document.querySelector("[data-comment-filter-input]").dispatchEvent(new window.Event("input"));
    assert.equal(document.querySelectorAll("[data-comment-list] .comment-node").length, 0);
    let clipboardText = "";
    context.navigator = {
        clipboard: {
            writeText: async (value) => { clipboardText = value; },
        },
    };
    click(copyButton);
    await new Promise((resolve) => setImmediate(resolve));
    assert.ok(clipboardText.includes("Test document"));
    assert.ok(clipboardText.includes("beta"));
    assert.ok(clipboardText.includes("Page: unavailable"));
    assert.doesNotMatch(clipboardText, /Page: \d+/);
    assert.ok(clipboardText.includes("item-3"));
    assert.ok(clipboardText.includes("17-42"));
    assert.ok(clipboardText.includes("Quoted “text”\nacross lines."));
    assert.ok(clipboardText.includes("Reviewer Ω"));
    assert.ok(clipboardText.includes("<Second line> & safe."));
    assert.ok(clipboardText.includes("Nested reply."));
    assert.ok(clipboardText.includes("Deep reply."));
    assert.ok(clipboardText.includes("Batch scope: full section"));
    assert.ok(clipboardText.includes("alpha item-2"));
    assert.ok(clipboardText.includes("beta item-4"));
    assert.equal(document.querySelector("[data-comment-announcer]").textContent,
        "Comments copied to clipboard.");
    assert.equal(document.querySelector("[data-review-save-guidance]").dataset.dirty, originalDirty);
    assert.equal(document.querySelector("[data-comment-island]").textContent, originalIsland);

    context.navigator.clipboard.writeText = async () => { throw new Error("Permission denied"); };
    click(copyButton);
    await new Promise((resolve) => setImmediate(resolve));
    assert.match(document.querySelector("[data-comment-announcer]").textContent, /clipboard.*Permission denied/i);
    assert.doesNotMatch(document.querySelector("[data-comment-announcer]").textContent, /^Comments copied/i);
    context.navigator = {};
    click(copyButton);
    await new Promise((resolve) => setImmediate(resolve));
    assert.match(document.querySelector("[data-comment-announcer]").textContent, /clipboard.*unavailable/i);
    const originalAnnotations = context.obsComments.data.annotations;
    context.obsComments.data.annotations = [];
    click(copyButton);
    assert.match(document.querySelector("[data-comment-announcer]").textContent, /no comments/i);
    context.obsComments.data.annotations = originalAnnotations;

    const runtimeErrors = [];
    context.console = {...console, error: (message) => runtimeErrors.push(message)};
    context.localStorage = {
        getItem() { throw new Error("Storage denied"); },
        setItem() { throw new Error("Storage denied"); },
    };
    vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), context, {filename: "comments-storage.js"});
    assert.equal(document.querySelector('[data-storage-warning="reviewer"]').hidden, false);
    assert.equal(document.querySelector("[data-comment-announcer]").classList.contains("visually-hidden"), false);
    const island = document.querySelector("[data-comment-island]");
    island.textContent = '{"invalid":true}';
    vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), context, {filename: "comments-invalid.js"});
    assert.equal(island.textContent, '{"invalid":true}');
    assert.equal(document.querySelector("[data-comment-save]").disabled, true);
    assert.ok(runtimeErrors.some((message) => message.includes("original review data was preserved")));
}
async function verifyCommentExportOnly() {
    navigate("parent");
    const storage = new Map();
    context.localStorage = {
        getItem: (key) => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value),
    };
    vm.runInContext(fs.readFileSync(process.argv[6], "utf8"), context, {filename: "storage.js"});
    context.Node = window.Node;
    context.NodeFilter = {SHOW_TEXT: 4};
    context.CSS = {escape: (value) => value};
    let selection = null;
    context.getSelection = () => selection;
    vm.runInContext(fs.readFileSync(process.argv[5], "utf8"), context, {filename: "settings.js"});
    vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), context, {filename: "comments.js"});
    context.obsArtifact.openBar("comments", "right");

    const paragraph = body.querySelector("p");
    assert.ok(paragraph);
    const range = new TextRange();
    range.selectNodeContents(paragraph);
    selection = {
        rangeCount: 1, isCollapsed: false, getRangeAt: () => range, removeAllRanges() {},
    };
    document.dispatchEvent(new window.Event("selectionchange"));
    click(document.querySelector("[data-comment-add]"));
    const annotation = context.obsComments.data.annotations[0];
    annotation.author = "Reviewer Ω";
    annotation.text = "First line.\n<Second line> & safe.";
    annotation.replies.push({
        id: "reply-1", author: "Reply author", text: "Nested reply.",
        status: "resolved", replies: [{
            id: "reply-2", author: "Third author", text: "Deep reply.",
            status: "open", replies: [],
        }],
    });
    const batch = {
        scope: "section",
        items: [
            {chapter: "parent", item: "item-2"},
            {chapter: "child", item: "item-4"},
        ],
    };
    const inactiveTarget = {
        chapter: "child", quote: "Inactive Unicode “quote”.", prefix: "", suffix: "",
        start: 5, end: 29, item: "item-3", section: "Background",
    };
    context.obsComments.data.annotations.push({
        id: "inactive-batch", target: inactiveTarget, batch,
        author: "Batch author", text: "Batch feedback.", status: "open",
        replies: [],
    });
    click(paragraph.querySelector(".review-action--comment"));
    const whole = context.obsComments.data.annotations.at(-1);
    assert.equal(whole.target.wholeItem, true);
    assert.equal(whole.target.item, paragraph.dataset.reviewItem);
    assert.equal(whole.target.section, "Context");
    whole.text = "Whole item feedback with ``` and ```` fences.";
    const table = document.createElement("div");
    table.innerHTML = '<div data-data-table="shared-table"><table><thead><tr>' +
        '<th data-column-key="explanation">Current column label</th></tr></thead>' +
        '<tbody><tr data-row-key="record-1"><td>Row</td></tr>' +
        '<tr data-detail-owner="record-1"><td><div data-detail-column="explanation">' +
        '<p>Expanded detail quote Ω.</p></div></td></tr></tbody></table></div>';
    body.append(table);
    const sheet = document.createElement("section");
    sheet.className = "paper-sheet";
    sheet.dataset.pageChapter = "parent";
    table.before(sheet);
    sheet.append(table);
    const footer = document.createElement("footer");
    footer.className = "paper-footer";
    footer.innerHTML = '<span class="paper-page-number">Page 8 of 9</span>';
    sheet.append(footer);
    document.documentElement.classList.add("paged-mode");
    const detailParagraph = table.querySelector("p");
    const detailRange = new TextRange();
    detailRange.selectNodeContents(detailParagraph);
    selection = {
        rangeCount: 1, isCollapsed: false, getRangeAt: () => detailRange,
        removeAllRanges() {},
    };
    document.dispatchEvent(new window.Event("selectionchange"));
    click(document.querySelector("[data-comment-add]"));
    const detail = context.obsComments.data.annotations.at(-1);
    assert.equal(detail.target.table, "shared-table");
    assert.equal(detail.target.row, "record-1");
    assert.equal(detail.target.column, "explanation");
    assert.equal(detail.target.detail, true);
    const inactiveTable = JSON.parse(JSON.stringify(detail));
    inactiveTable.id = "inactive-table";
    inactiveTable.target.chapter = "child";
    const staleDetail = JSON.parse(JSON.stringify(detail));
    staleDetail.id = "stale-detail";
    staleDetail.target.quote = "A stored quote no longer matching this detail.";
    context.obsComments.data.annotations.push(inactiveTable, staleDetail, {
        id: "unresolved", target: {
            chapter: "parent", quote: "Missing quote.", prefix: "", suffix: "",
            start: 999999, end: 1000013,
        }, author: "Legacy reviewer", text: "Unresolved feedback.", status: "open", replies: [],
    });
    const originalDirty = document.querySelector("[data-review-save-guidance]").dataset.dirty;
    const originalIsland = document.querySelector("[data-comment-island]").textContent;
    const originalData = JSON.stringify(context.obsComments.data);
    const originalFilter = document.querySelector("[data-comment-filter-input]").value;
    document.querySelector("[data-comment-filter-input]").value = "no matching comment";
    document.querySelector("[data-comment-filter-input]").dispatchEvent(new window.Event("input"));

    let clipboardText = "";
    context.navigator = {
        clipboard: {writeText: async (value) => { clipboardText = value; }},
    };
    const copyButton = document.querySelector("[data-comment-copy]");
    assert.equal(document.querySelector("[data-comment-save]").textContent, "Save");
    assert.equal(document.querySelector("[data-comment-load]").textContent, "Load");
    assert.equal(document.querySelector("[data-comment-save]").getAttribute("aria-label"), "Download HTML");
    assert.equal(document.querySelector("[data-comment-load]").getAttribute("aria-label"), "Load reviewed HTML");
    click(copyButton);
    await new Promise((resolve) => setImmediate(resolve));
    assert.ok(clipboardText.includes(document.title));
    assert.ok(clipboardText.includes("Parent"));
    assert.ok(clipboardText.includes("Page: "));
    assert.ok(clipboardText.includes("text positions"));
    assert.ok(clipboardText.includes(paragraph.textContent));
    assert.ok(clipboardText.includes("Reviewer Ω"));
    assert.ok(clipboardText.includes("<Second line> & safe."));
    assert.ok(clipboardText.includes("Nested reply."));
    assert.ok(clipboardText.includes("Deep reply."));
    assert.ok(clipboardText.includes("Inactive Unicode “quote”."));
    assert.ok(clipboardText.includes("Page: unavailable"));
    assert.ok(clipboardText.includes("Batch scope: full section"));
    assert.ok(clipboardText.includes("parent item-2"));
    assert.ok(clipboardText.includes("child item-4"));
    assert.ok(clipboardText.includes("whole-item context"));
    assert.ok(clipboardText.includes("Expanded detail quote Ω."));
    assert.ok(clipboardText.includes('table key "shared-table", row identity "record-1"'));
    assert.ok(clipboardText.includes('subject column "explanation" (Current column label)'));
    assert.ok(clipboardText.includes("- Page: 8\n"));
    assert.ok(clipboardText.includes("Unresolved feedback."));
    const inactiveThread = clipboardText.split("- Root comment: inactive-table")[1].split("## Thread")[0];
    assert.ok(inactiveThread.includes('subject column "explanation"'));
    assert.equal(inactiveThread.includes("Current column label"), false);
    assert.equal(inactiveThread.includes("Page: unavailable"), true);
    const staleThread = clipboardText.split("- Root comment: stale-detail")[1].split("## Thread")[0];
    assert.ok(staleThread.includes("Page: unavailable"));
    assert.ok(clipboardText.includes("`````text\nWhole item feedback"));
    assert.equal(document.querySelector("[data-comment-announcer]").textContent,
        "Comments copied to clipboard.");
    assert.equal(document.querySelector("[data-comment-announcer]").classList.contains("visually-hidden"), false);
    assert.equal(document.querySelector("[data-review-save-guidance]").dataset.dirty, originalDirty);
    assert.equal(document.querySelector("[data-comment-island]").textContent, originalIsland);
    assert.equal(document.querySelector("[data-comment-filter-input]").value, "no matching comment");
    assert.equal(JSON.stringify(context.obsComments.data), originalData);

    let finishWrite;
    context.navigator.clipboard.writeText = () => new Promise((resolve) => { finishWrite = resolve; });
    click(copyButton);
    assert.equal(document.querySelector("[data-comment-announcer]").textContent, "Copying comments…");
    finishWrite();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(document.querySelector("[data-comment-announcer]").textContent,
        "Comments copied to clipboard.");

    context.navigator.clipboard.writeText = async () => { throw new Error("Permission denied"); };
    click(copyButton);
    await new Promise((resolve) => setImmediate(resolve));
    assert.match(document.querySelector("[data-comment-announcer]").textContent,
        /clipboard.*Permission denied/i);
    assert.doesNotMatch(document.querySelector("[data-comment-announcer]").textContent, /^Comments copied/i);
    context.navigator = {};
    click(copyButton);
    await new Promise((resolve) => setImmediate(resolve));
    assert.match(document.querySelector("[data-comment-announcer]").textContent,
        /clipboard.*unavailable/i);
    const annotations = context.obsComments.data.annotations;
    const annotationCount = annotations.length;
    context.obsComments.data.annotations = [];
    click(copyButton);
    assert.match(document.querySelector("[data-comment-announcer]").textContent, /no comments/i);
    context.obsComments.data.annotations = annotations;
    assert.equal(originalFilter, "");
    const saved = await context.obsComments.reviewedHtml();
    const reopened = parseHTML(saved).document;
    const savedData = JSON.parse(reopened.querySelector("[data-comment-island]").textContent);
    assert.deepEqual(savedData.annotations, JSON.parse(originalData).annotations);
    assert.equal(reopened.querySelector("[data-comment-copy]").textContent, "Copy comments to clipboard");
    context.DOMParser = window.DOMParser;
    await context.obsComments.importFiles([{text: async () => saved}]);
    assert.equal(context.obsComments.data.annotations.length, annotationCount);
    const legacy = JSON.parse(JSON.stringify(savedData));
    legacy.annotations.forEach(({target}) => {
        delete target.item;
        delete target.section;
        delete target.wholeItem;
    });
    const legacyReturned = parseHTML(saved).document;
    legacyReturned.querySelector("[data-comment-island]").textContent = JSON.stringify(legacy);
    await context.obsComments.importFiles([{text: async () => legacyReturned.documentElement.outerHTML}]);
    assert.equal(context.obsComments.data.annotations.length, annotationCount);
    const imported = JSON.parse(JSON.stringify(savedData));
    imported.annotations = [imported.annotations.find((entry) => entry.target.wholeItem)];
    imported.annotations[0].text = "Imported whole item feedback.";
    const returned = parseHTML(saved).document;
    returned.querySelector("[data-comment-island]").textContent = JSON.stringify(imported);
    await context.obsComments.importFiles([{text: async () => returned.documentElement.outerHTML}]);
    const merged = context.obsComments.data.annotations.at(-1);
    assert.equal(merged.text, "Imported whole item feedback.");
    assert.equal(merged.target.wholeItem, true);
    assert.equal(merged.target.section, "Context");
    assert.equal(merged.target.item, whole.target.item);
    console.log("PASS: all comments/context, nested replies, batch/table identities, clipboard states, unchanged review state, and save/import compatibility.");
}
await verifyPages();
}
run().catch((error) => { console.error(error); process.exitCode = 1; });
