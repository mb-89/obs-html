// The artifact verification harness: opens a generated artifact in the fake browser (happy-dom in
// Node, test/browser/fake-browser.cjs, browser-door.md) with no native browser, lets its runtime start
// as a reader's browser starts it and drives it step by step.
//
// As a module: `open(artifactPath, options)` returns the opened artifact; artifact-ui.cjs and the
// steps below build on it. Its options: `recording`, a browser door state's recording (door.py), so
// the page answers its layout calls from it (else from the door's default answers); `hold`, the ids
// of runtime scripts the page does not run, which a caller runs itself with its own stand-ins
// (`run`); and `viewport`. As a command:
//
//   node ./artifact-harness.cjs <artifact.html> <steps.json> [<recording.json>]
//
// runs the JSON list of steps (each {"step": <name>, ...arguments}) and prints one JSON result
// per step as a JSON list. A failed step exits 1 with a message naming the harness, the step and
// the remedy.
const fs = require("node:fs");
const path = require("node:path");
const {pathToFileURL} = require("node:url");
const {FakePage, use, runScript} = require("./fake-browser.cjs");
const {doorElement} = require("./door-key.js");

const NAME = "test/browser/artifact-harness.cjs";

class HarnessError extends Error {
    constructor(step, problem, remedy) {
        super(`${NAME}: ${step}: ${problem}${remedy ? ` Remedy: ${remedy}` : ""}`);
    }
}

// Each animation frame the runtime asks for while the harness runs the page's timers, at most.
const FRAMES = 100;
// How long the page may take, on its own clock, to open and to reach its ready mark.
const TIMEOUT = 30000;

// The page's own global: what a script of the page reads as globalThis, and where a caller's
// stand-in (`artifact.context.localStorage = ...`) is defined, as the fake defines its refusals.
function globalOf(window) {
    const global = window.eval("globalThis");
    const define = window.eval("(name, value) => Object.defineProperty(globalThis, name, " +
        "{value, writable: true, configurable: true, enumerable: true})");
    return new Proxy(global, {
        get: (target, name) => target[name],
        set: (_target, name, value) => {
            define(name, value);
            return true;
        },
        deleteProperty: (target, name) => Reflect.deleteProperty(target, name),
        has: (target, name) => name in target,
    });
}

// The page's scripts without the held ones: the HTML parser ends a script at its first `</script`,
// so this match is exactly the element the parser would build.
function without(html, held) {
    let shown = html;
    for (const id of held) {
        const pattern = new RegExp(`<script id="${id}"[^>]*>[\\s\\S]*?</script>`, "g");
        if (!pattern.test(shown)) {
            throw new HarnessError("open", `the artifact has no <script id="${id}"> to hold back.`,
                "render the artifact with this repository's obs-html, not another adapter or an older build.");
        }
        shown = shown.replace(pattern, "");
    }
    return shown;
}

// Opens the artifact in the fake browser and runs it until its ready mark.
async function open(artifactPath, {recording = null, hold = [], viewport} = {}) {
    let html;
    try {
        html = fs.readFileSync(artifactPath, "utf8");
    } catch (error) {
        throw new HarnessError("open", `the artifact ${artifactPath} could not be read: ${error.message}`,
            "pass the path of an artifact rendered with obs-html.");
    }
    const page = new FakePage(1, {viewport: viewport || recording?.context?.viewport || [1280, 720]});
    page.recording = recording;
    use(page);
    await page.open(pathToFileURL(path.resolve(artifactPath)).href, TIMEOUT, without(html, hold));
    const {window} = page;
    const {document} = window;
    const status = () => document.documentElement.dataset.artifactStatus;
    await page.until(() => ["ready", "error"].includes(status()), TIMEOUT);
    const artifact = {page, window, document, context: globalOf(window)};
    // The errors the page raised since the last look, thrown as the step's own.
    artifact.raise = () => {
        const errors = page.events.filter((event) => event.type === "pageerror");
        page.events = page.events.filter((event) => event.type !== "pageerror");
        if (errors.length) {
            const [first] = errors;
            const error = new Error(`the page raised ${first.name}: ${first.message}\n${first.stack}`);
            error.name = first.name;
            throw error;
        }
    };
    if (status() !== "ready") {
        const errors = page.events.filter((event) => event.type === "pageerror").map((event) => event.message);
        throw new HarnessError("open", `the artifact did not reach its ready mark (status ${status() || "none"})` +
            `${errors.length ? `: ${errors.join("; ")}` : ""}.`, "open it in a browser and read the page's error notice.");
    }
    artifact.raise();
    // Runs a runtime's source in the page as one of its scripts, named `filename` in stacks, and
    // throws what it threw.
    artifact.run = (source, filename = "script") => {
        runScript(window, source, filename);
        artifact.raise();
    };
    // The page's pending timers (not its animation frames), each with its delay and callback.
    artifact.timers = {
        values: () => page.clock.tasks.filter((task) => !task.frame)
            .map((task) => ({delay: task.delay, callback: () => {
                if (!page.clock.tasks.includes(task)) return;
                page.clock.run(task);
                artifact.raise();
            }}))[Symbol.iterator](),
    };
    // Runs every timer and frame the page has asked for, and each frame those ask for in turn, on
    // the page's clock; a timer a timer sets waits for the next call.
    artifact.runTimers = () => {
        const due = [...page.clock.tasks].sort((one, other) => one.at - other.at || one.id - other.id);
        for (const task of due) if (page.clock.tasks.includes(task)) page.clock.run(task);
        for (let round = 0; round < FRAMES; round += 1) {
            const frames = page.clock.tasks.filter((task) => task.frame);
            if (!frames.length) break;
            for (const task of frames) if (page.clock.tasks.includes(task)) page.clock.run(task);
        }
        artifact.raise();
    };
    // Lets the page run what is due now and one frame of its clock, as passes between two inputs.
    artifact.settle = async () => {
        await page.between();
        artifact.raise();
    };
    // Awaits a promise of the page while its clock runs, as time passes in a browser, and throws
    // what the page raised meanwhile; a promise that never settles fails the step.
    artifact.wait = async (value, what = "a promise of the page") => {
        if (!value || typeof value.then !== "function") return value;
        const outcome = {done: false};
        value.then((result) => Object.assign(outcome, {done: true, result}),
            (error) => Object.assign(outcome, {done: true, error, failed: true}));
        if (!await page.until(() => outcome.done, TIMEOUT)) {
            throw new HarnessError("wait", `${what} did not settle within ${TIMEOUT} ms of the page's clock, ` +
                "and the page had nothing left to run.", "await only what the page resolves on its own.");
        }
        artifact.raise();
        if (outcome.failed) throw outcome.error;
        return outcome.result;
    };
    // Runs the page on its clock until `check` holds, and returns what it answered; fails the step
    // where the page has nothing left to run first.
    artifact.until = async (check, what = "the page's condition") => {
        const met = await page.until(check, TIMEOUT);
        artifact.raise();
        if (!met) {
            throw new HarnessError("until", `${what} did not hold within ${TIMEOUT} ms of the page's clock, ` +
                "and the page had nothing left to run.", "wait only for what the page reaches on its own.");
        }
        return met;
    };
    // From now on the page answers its layout calls from the recording's step `step` (door.py).
    artifact.reach = (step) => { page.reached = step; };
    // A saved copy's HTML as a document of the page's own realm.
    artifact.parse = (source) => new window.DOMParser().parseFromString(source, "text/html");
    return artifact;
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
        await artifact.wait(artifact.context.obsArtifact.whenChapterReady(), "the chapter's ready promise");
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
        await artifact.settle();
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
        await artifact.settle();
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
    // From now on the page answers from the recording's step (browser-door.md, Recording and replay).
    async reach(artifact, {index}) {
        artifact.reach(index);
        return {reached: index};
    },
    // The border box the page gets for the element of a door key (door-key.js): the recording's
    // answer at the step reached, else the door's default.
    async box(artifact, {key}) {
        const element = doorElement(key, artifact.document);
        if (!element) {
            throw new HarnessError("box", `no element of the page has the key "${key}".`,
                "name a key a recording of this artifact lists under box.");
        }
        const {x, y, width, height} = element.getBoundingClientRect();
        return {key, border: [x, y, width, height]};
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
        const [artifactPath, stepsPath, recordingPath] = process.argv.slice(2);
        if (!stepsPath) {
            throw new HarnessError("usage", "expected <artifact.html> <steps.json> [<recording.json>].",
                "pass the artifact and its steps, and a state's recording where the page answers from one.");
        }
        const recording = recordingPath ? JSON.parse(fs.readFileSync(recordingPath, "utf8")) : null;
        const artifact = await open(artifactPath, {recording});
        const steps = JSON.parse(fs.readFileSync(stepsPath, "utf8"));
        process.stdout.write(JSON.stringify(await runSteps(artifact, steps)));
        artifact.page.close();
    })().catch((error) => {
        console.error(error instanceof HarnessError ? error.message : error);
        process.exitCode = 1;
    });
}
