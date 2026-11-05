// The artifact verification harness: opens a generated artifact in a Node DOM (linkedom) with no
// native browser, runs its embedded runtime and drives it step by step.
//
// As a module: `open(artifactPath, linkedomPath)` returns the opened artifact; artifact-ui.cjs and
// the steps below build on it. As a command:
//
//   node artifact-harness.cjs <artifact.html> <linkedom module> <steps.json>
//
// runs the JSON list of steps (each {"step": <name>, ...arguments}) and prints one JSON result
// per step as a JSON list. A failed step exits 1 with a message naming the harness, the step and
// the remedy.
const fs = require("node:fs");
const vm = require("node:vm");

const NAME = "test/browser/artifact-harness.cjs";
const STARTUP_SCRIPTS = ["reader-startup-script", "running-header-script", "artifact-bootstrap-script"];
const RUNTIME_SCRIPTS = ["query-script", "yaml-script", "base-script", "data-table-script",
    "assets-script", "notices-script", "canonical-transaction-script", "artifact-script", "pages-script"];

class HarnessError extends Error {
    constructor(step, problem, remedy) {
        super(`${NAME}: ${step}: ${problem}${remedy ? ` Remedy: ${remedy}` : ""}`);
    }
}

// Browser stand-ins the runtime needs and linkedom lacks. Layout is constant: every element is
// 384 by 24 pixels in a 1200 by 900 window and every sheet fits, so geometry comes from the
// runtime's declared paper, never from measured pixels.
function install(window, document) {
    Object.defineProperty(Object.getPrototypeOf(document.createDocumentFragment()), "textContent", {
        configurable: true,
        get() { return [...this.childNodes].map((node) => node.textContent || "").join(""); },
    });
    if (document.createElement("a").hash === undefined) {
        Object.defineProperty(window.HTMLAnchorElement.prototype, "hash", {
            get() { return new URL(this.href, "https://artifact.invalid/").hash; },
        });
    }
    window.HTMLCanvasElement.prototype.getContext = () => ({
        font: "", measureText: (text) => ({width: text.length * 7}),
    });
    window.HTMLElement.prototype.showPopover = function () { this.dataset.open = "true"; };
    window.HTMLElement.prototype.hidePopover = function () { delete this.dataset.open; };
    window.HTMLElement.prototype.getBoundingClientRect = () => ({
        left: 100, right: 122, top: 200, bottom: 222, width: 384, height: 24,
    });
    window.HTMLElement.prototype.getClientRects = function () { return [this.getBoundingClientRect()]; };
    window.HTMLElement.prototype.scrollIntoView = function () {};
    Object.defineProperty(window.HTMLElement.prototype, "clientHeight", {
        configurable: true, get() { return 10000; },
    });
    Object.defineProperty(window.HTMLElement.prototype, "scrollHeight", {
        configurable: true, get() { return 0; },
    });
    window.location = {hash: "", pathname: "/artifacts/artifact.html"};
    window.history = {
        pushState(_state, _unused, hash) { window.location.hash = hash; },
        replaceState(_state, _unused, hash) { window.location.hash = hash; },
    };
    window.innerWidth = 1200;
    window.innerHeight = 900;
}

function textRange(document) {
    return class TextRange {
        selectNodeContents(node) {
            this.root = node;
            this.commonAncestorContainer = node;
            this.startContainer = node;
            this.startOffset = 0;
            this.endContainer = node;
            this.endOffset = node.childNodes.length;
        }
        cloneRange() { return Object.assign(new TextRange(), this); }
        cloneContents() {
            const fragment = document.createDocumentFragment();
            fragment.append(document.createTextNode(this.toString()));
            return fragment;
        }
        setStart(node, offset) { this.startContainer = node; this.startOffset = offset; }
        setEnd(node, offset) { this.endContainer = node; this.endOffset = offset; }
        toString() {
            const root = this.root || (this.startContainer.nodeType === 3
                ? this.startContainer.parentElement : this.startContainer);
            const position = (node, offset) => {
                let total = 0;
                let found = false;
                const visit = (current) => {
                    if (found) return;
                    if (current === node) {
                        total += current.nodeType === 3 ? offset
                            : [...current.childNodes].slice(0, offset).reduce(
                                (sum, child) => sum + child.textContent.length, 0,
                            );
                        found = true;
                    } else if (current.nodeType === 3) total += current.textContent.length;
                    else [...current.childNodes].forEach(visit);
                };
                visit(root);
                return total;
            };
            return root.textContent.slice(
                position(this.startContainer, this.startOffset), position(this.endContainer, this.endOffset),
            );
        }
        getClientRects() { return []; }
    };
}

function runScript(document, context, id) {
    const script = document.getElementById(id);
    if (!script) {
        throw new HarnessError("open", `the artifact has no <script id="${id}">.`,
            "render the artifact with this repository's obs-html, not another adapter or an older build.");
    }
    vm.runInContext(script.textContent, context, {filename: id});
}

// Opens the artifact and runs its startup and runtime scripts in the order the browser does.
async function open(artifactPath, linkedomPath) {
    let parseHTML;
    try {
        ({parseHTML} = require(linkedomPath));
    } catch (error) {
        throw new HarnessError("open", `linkedom could not be loaded from ${linkedomPath}: ${error.message}`,
            "npm --prefix test/browser ci");
    }
    let html;
    try {
        html = fs.readFileSync(artifactPath, "utf8");
    } catch (error) {
        throw new HarnessError("open", `the artifact ${artifactPath} could not be read: ${error.message}`,
            "pass the path of an artifact rendered with obs-html.");
    }
    const {window, document} = parseHTML(html);
    install(window, document);
    const TextRange = textRange(document);
    document.createRange = () => new TextRange();
    let timerId = 0;
    const timers = new Map();
    const runTimers = () => {
        const pending = [...timers.values()];
        timers.clear();
        pending.forEach(({callback}) => callback());
    };
    const context = vm.createContext({
        window, document, console, CustomEvent: window.CustomEvent, AbortController, URLSearchParams, URL,
        MutationObserver: window.MutationObserver,
        TextEncoder, TextDecoder, ReadableStream, Response, CompressionStream, DecompressionStream,
        atob, btoa, structuredClone, performance,
        addEventListener: window.addEventListener.bind(window),
        removeEventListener: window.removeEventListener.bind(window),
        NodeFilter: {SHOW_TEXT: 4},
        getComputedStyle: () => ({
            font: "14px sans-serif", fontSize: "16px", paddingLeft: "24px", getPropertyValue: () => "0",
        }),
        ResizeObserver: class { observe() {} disconnect() {} },
        setTimeout: (callback, delay) => {
            timers.set(++timerId, {callback, delay});
            return timerId;
        },
        clearTimeout: (id) => timers.delete(id),
        requestAnimationFrame: (callback) => callback(),
    });
    STARTUP_SCRIPTS.forEach((id) => runScript(document, context, id));
    await context.obsHtmlDataReady;
    await context.obsHtmlReady;
    vm.runInContext("globalThis.obsStartup = undefined;", context);
    RUNTIME_SCRIPTS.forEach((id) => runScript(document, context, id));
    return {window, document, context, parseHTML, TextRange, timers, runTimers};
}

const activeChapter = (artifact) => artifact.document.querySelector("[data-active-chapter]");
// The paged screen reader; the runtime detaches it while page mode is off.
const pagedReader = (artifact) => {
    const screen = artifact.document.querySelector(".paged-reader");
    return screen && !screen.hidden ? screen : null;
};

// Every sheet of a paged container, with the paper the runtime declares for it.
function sheets(artifact, container) {
    const paper = artifact.data.paper;
    return [...container.querySelectorAll(":scope > .paper-sheet")].map((sheet) => {
        const landscape = sheet.dataset.pageOrientation === "landscape";
        const number = sheet.querySelector(".paper-page-number")?.textContent.match(/\d+/);
        return {
            chapter: sheet.dataset.pageChapter,
            orientation: sheet.dataset.pageOrientation,
            side: sheet.dataset.pageSide || null,
            page: number ? Number(number[0]) : null,
            widthMillimeters: landscape ? paper.heightMillimeters : paper.widthMillimeters,
            heightMillimeters: landscape ? paper.widthMillimeters : paper.heightMillimeters,
            marginMillimeters: paper.marginMillimeters,
        };
    });
}

const STEPS = {
    // The artifact's embedded data as the runtime parsed it.
    async data(artifact) {
        const island = artifact.document.querySelector("[data-artifact-data]");
        artifact.data = JSON.parse(island.textContent);
        return {
            status: artifact.document.documentElement.dataset.artifactStatus,
            notes: artifact.data.notes.map(({slug, title}) => ({slug, title})),
            toc: artifact.data.toc.length,
            tables: artifact.data.notes.flatMap((note) => (note.tables || []).map(({key}) => ({note: note.slug, key}))),
            paper: artifact.data.paper,
        };
    },
    // The filter bar's summary of the active filter: the runtime query's counts.
    async summary(artifact) {
        const {records, totalRecords} = artifact.context.obsArtifact.filterSummary();
        return {records, totalRecords};
    },
    async activate(artifact, {chapter}) {
        if (!artifact.context.obsArtifact.records.some((record) => record.slug === chapter)) {
            throw new HarnessError("activate", `the artifact has no chapter "${chapter}".`,
                "name a slug the data step lists under notes.");
        }
        artifact.context.obsArtifact.activateChapter(chapter);
        await artifact.context.obsArtifact.whenChapterReady();
        const active = activeChapter(artifact);
        return {
            chapter: active.dataset.chapter,
            hash: artifact.window.location.hash,
            title: active.querySelector("h1")?.textContent.trim() || null,
        };
    },
    // The table the active chapter mounted for a key, as the reader sees it.
    async table(artifact, {key}) {
        const body = activeChapter(artifact).querySelector("[data-chapter-body]");
        const shell = [...body.querySelectorAll("[data-data-table]:not([data-page-continuation])")]
            .find((element) => element.dataset.dataTable === key);
        if (!shell) {
            throw new HarnessError("table", `the active chapter "${activeChapter(artifact).dataset.chapter}" `
                + `mounted no table "${key}".`, "activate the chapter the data step lists for that table first.");
        }
        return {
            key,
            columns: [...shell.querySelectorAll("thead th[data-column-key]")].map((cell) => ({
                key: cell.dataset.columnKey, label: cell.querySelector("span")?.textContent.trim() || "",
            })),
            rows: [...shell.querySelectorAll("tbody tr[data-row-key]")].map((row) => row.dataset.rowKey),
            cells: [...shell.querySelectorAll("tbody tr[data-row-key]")].map((row) =>
                [...row.querySelectorAll("td")].map((cell) => cell.textContent.trim())),
            count: shell.querySelector(".data-table-count")?.textContent.trim() || null,
        };
    },
    async paged(artifact, {enabled}) {
        artifact.context.obsPages.setPaged(enabled);
        const screen = pagedReader(artifact);
        return {
            paged: artifact.document.documentElement.classList.contains("paged-mode"),
            reader: Boolean(screen),
            chapter: activeChapter(artifact).dataset.chapter,
            sheets: screen ? screen.querySelectorAll(":scope > .paper-sheet").length : 0,
        };
    },
    // Presentation (the paged screen reader) and print (the print book and its media boxes).
    async geometry(artifact) {
        const {document, window, context} = artifact;
        const screen = pagedReader(artifact);
        const presentation = screen ? sheets(artifact, screen) : null;
        window.dispatchEvent(new window.Event("beforeprint"));
        try {
            const book = document.querySelector(".print-book");
            return {
                presentation,
                print: {
                    sheets: sheets(artifact, book),
                    mediaBoxes: context.obsPages.printMediaBoxes,
                },
            };
        } finally {
            window.dispatchEvent(new window.Event("afterprint"));
        }
    },
};

async function runSteps(artifact, steps) {
    const results = [];
    if (!artifact.data) await STEPS.data(artifact);
    for (const {step, ...argumentsOfStep} of steps) {
        if (!Object.hasOwn(STEPS, step)) {
            throw new HarnessError(step, "unknown step.", `use one of ${Object.keys(STEPS).join(", ")}.`);
        }
        results.push(await STEPS[step](artifact, argumentsOfStep));
    }
    return results;
}

module.exports = {open, runSteps, HarnessError};

if (require.main === module) {
    (async () => {
        const [artifactPath, linkedomPath, stepsPath] = process.argv.slice(2);
        if (!stepsPath) {
            throw new HarnessError("usage", "expected <artifact.html> <linkedom module> <steps.json>.",
                "pass all three arguments.");
        }
        const artifact = await open(artifactPath, linkedomPath);
        const steps = JSON.parse(fs.readFileSync(stepsPath, "utf8"));
        process.stdout.write(JSON.stringify(await runSteps(artifact, steps)));
    })().catch((error) => {
        console.error(error instanceof HarnessError ? error.message : error);
        process.exitCode = 1;
    });
}
