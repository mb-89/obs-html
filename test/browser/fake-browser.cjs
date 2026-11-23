// The fake browser: happy-dom in Node behind the browser door (test/browser/browser-door.md, The
// fake browser). One process per test worker serves the pages of test/conftest.py's `fake_page`
// fixture, whose facade (test/browser/fake_page.py) sends it one JSON request per line on stdin and
// reads one JSON answer per line on stdout:
//
//   {"id": 1, "op": "open", "page": 1, "url": "file:///...", "viewport": [1280, 720], ...}
//   {"id": 1, "ok": true, "value": ..., "events": [...]}   or   {"id": 1, "ok": false, "error": {...}}
//
// What a page does between two requests runs on the page's own clock: its timers, animation frames
// and idle callbacks are tasks of a virtual clock, and a wait (`until`) advances that clock to the
// next task only once the page has nothing else to do. No request waits on wall time, and a wait
// that the page can never satisfy ends as soon as nothing is left to run, or once the clock passes
// the request's timeout.
//
// The page gets the stand-ins the design lists (Option, the Popover API, print, the compression
// streams, structuredClone, crypto and a canvas text measure). A page opened with a state's
// recording (the `replay` request, test/browser/door.py) answers every supplied call for an
// element's key (door-key.js) from the latest step the test has reached (`reach`): boxes, client
// rects, sizes, the observers' entries, text widths, decoded image sizes, `document.fonts` and, in
// the viewer frame, the refusals Chromium gave. A call without a recorded answer gets the door's
// default for layout: an element whose computed display is `none`, or that is not in the document,
// has an empty box; every other element is 384 by 24 pixels at the viewport's origin. Each default
// the page was given is listed, by call and element key, in the `defaults` request's answer, which
// the test's report shows; the `asked` request lists, by step, each key and call the page asked,
// which the recorder measures in Chromium. Network requests to anything but a loopback server are refused, as
// test/network_guard.py refuses them, and each refusal is an event the facade fails the test with.
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");
const util = require("node:util");
const {fileURLToPath} = require("node:url");
const {resolveObjectURL} = require("node:buffer");
const {doorKey} = require("./door-key.js");

const NAME = "test/browser/fake-browser.cjs";
const NOTE = "test/browser/browser-door.md";
const HAPPY_DOM = path.join(__dirname, "node_modules", "happy-dom");
// The door's default box (browser-door.md, Recording and replay), the DOM tier's constant size.
const BOX = {width: 384, height: 24};
// One frame of the page's clock, and the time that passes between two requests: one frame.
const FRAME_MS = 16;
// The canvas stand-in's text width: every character 7 pixels wide, as the DOM tier measures.
const CHARACTER_WIDTH = 7;
// How many tasks the page may run at one instant of its clock before a wait gives up on it: a
// timer loop of zero delays never lets the clock move.
const TASKS_PER_INSTANT = 10000;
// How many turns of Node's event loop a settling page may wait for work it awaits outside happy-dom
// (a stream, a digest, a local server's answer) before it counts as idle: a stream nobody ends
// would otherwise hold every wait.
const BUSY_TURNS = 100000;

class FakeError extends Error {
    constructor(kind, message) {
        super(message);
        this.kind = kind;
    }
}

let happyDom;
let PropertySymbol;
try {
    happyDom = require(HAPPY_DOM);
    PropertySymbol = require(path.join(HAPPY_DOM, "lib", "PropertySymbol.js"));
} catch (error) {
    process.stdout.write(JSON.stringify({id: 0, ok: false, error: {kind: "setup", message:
        `${NAME}: happy-dom could not be loaded from ${HAPPY_DOM}: ${error.message}. Remedy: npm --prefix test/browser ci.`,
    }}) + "\n");
    process.exit(1);
}

// The Popover API stand-in (happy-dom 21 has none): which popovers are open, and `:popover-open`
// in every selector match, the stylesheets' and the page's alike.
const openPopovers = new WeakSet();
const SelectorItem = require(path.join(HAPPY_DOM, "lib", "query-selector", "SelectorItem.js")).default;
const matchPseudoItem = SelectorItem.prototype.matchPseudoItem;
SelectorItem.prototype.matchPseudoItem = function (scope, element, parentChildren, pseudo, ignoreErrors) {
    if (pseudo.name === "popover-open") return openPopovers.has(element) ? {priorityWeight: 10} : null;
    return matchPseudoItem.call(this, scope, element, parentChildren, pseudo, ignoreErrors);
};

// A click on a link with a `download` attribute that no listener prevented downloads the file its
// blob: or data: URL holds, as Chromium does, instead of navigating; the facade's expect_download
// hands it over. happy-dom would open the link's URL instead. Its element classes are shared by
// every window, so the link is patched once, and the page is the one of the link's window. happy-dom
// calls a target's dispatchEvent once per phase; as its own link does, the download follows the
// dispatch's end (phase none) or its bubbling through the link.
const windowPages = new WeakMap();
const HTMLAnchorElement = require(path.join(HAPPY_DOM, "lib", "nodes", "html-anchor-element", "HTMLAnchorElement.js")).default;
const dispatchAnchor = HTMLAnchorElement.prototype.dispatchEvent;
const dispatchElement = Object.getPrototypeOf(HTMLAnchorElement.prototype).dispatchEvent;
HTMLAnchorElement.prototype.dispatchEvent = function (event) {
    const window = this[PropertySymbol.window];
    const page = windowPages.get(window);
    if (!page || event.type !== "click" || !this.hasAttribute("download")) return dispatchAnchor.call(this, event);
    const result = dispatchElement.call(this, event);
    const phase = event.eventPhase;
    if (!event.defaultPrevented && event instanceof window.MouseEvent && (phase === 0 || phase === 3)) {
        page.download(this.getAttribute("href") || "", this.getAttribute("download"));
    }
    return result;
};

// light-dark() in the cascade (happy-dom 21 drops a colour it cannot parse): the first colour where
// the page's used colour scheme is light, the second where it is dark. The scheme is the root
// element's computed color-scheme where it names one, else the device's preference; print is light.
const declarationUtilities = path.join(HAPPY_DOM, "lib", "css", "declaration", "property-manager", "utilities");
const CSSValueFormatter = require(path.join(declarationUtilities, "CSSValueFormatter.js")).default;
const CSSStringUtility = require(path.join(declarationUtilities, "CSSStringUtility.js")).default;
const getColor = CSSValueFormatter.getColor;
let usedScheme = () => "light";
CSSValueFormatter.getColor = function (value) {
    const match = /^light-dark\((.*)\)$/is.exec(String(value).trim());
    if (!match) return getColor.call(this, value);
    const parts = CSSStringUtility.splitByComma(match[1]);
    if (parts.length !== 2) return null;
    return CSSValueFormatter.getColor((usedScheme() === "dark" ? parts[1] : parts[0]).trim());
};

function schemeOf(page) {
    let resolving = false;
    return () => {
        const window = page.window;
        const device = page.browser?.settings.device;
        if (!window || !device) return "light";
        if (device.mediaType === "print") return "light";
        const preferred = device.prefersColorScheme === "dark" ? "dark" : "light";
        if (resolving) return preferred;
        resolving = true;
        try {
            const declared = String(ownStyle(window, window.document.documentElement).colorScheme || "").split(/\s+/);
            if (declared.includes(preferred)) return preferred;
            return declared.includes("dark") ? "dark" : declared.includes("light") ? "light" : preferred;
        } finally {
            resolving = false;
        }
    };
}

// Chromium's user-agent rules happy-dom 21 lacks: `[hidden]` and a closed `[popover]` are display
// none, at the user-agent level, so an author's display still wins. happy-dom's element defaults
// apply an entry's keys where the element's property of that name is truthy.
const CLOSED_POPOVER = "obsFakeClosedPopover";
const elementDefaults = require(path.join(HAPPY_DOM, "lib", "css", "declaration", "computed-style", "config",
    "CSSComputedStyleElementDefault.js")).default;
for (const [tag, rule] of Object.entries(elementDefaults)) {
    if (tag === "default") continue;
    elementDefaults[tag] = {...(typeof rule === "string" ? {default: rule} : rule), hidden: "display: none;",
        [CLOSED_POPOVER]: "display: none;"};
}

// The cascade's speed: happy-dom matches every style rule against every element it computes. A rule
// whose selectors each need, in their rightmost compound, an id, a class or a tag the element lacks
// cannot match it, so the full match is skipped; every other rule is matched as before. Only the
// cascade's calls are filtered (they ignore errors); a page's own matches() is not.
const QuerySelector = require(path.join(HAPPY_DOM, "lib", "query-selector", "QuerySelector.js")).default;
const fullMatch = QuerySelector.matches;
const requirements = new Map();

function topLevel(text, separators) {
    const parts = [];
    let depth = 0;
    let quote = "";
    let start = 0;
    for (let index = 0; index < text.length; index += 1) {
        const character = text[index];
        if (quote) {
            if (character === "\\") index += 1;
            else if (character === quote) quote = "";
        } else if (character === "\"" || character === "'") quote = character;
        else if (character === "(" || character === "[") depth += 1;
        else if (character === ")" || character === "]") depth -= 1;
        else if (depth === 0 && separators.includes(character)) {
            parts.push(text.slice(start, index));
            start = index + 1;
        }
    }
    parts.push(text.slice(start));
    return parts;
}

// For each comma-separated selector, what its subject must have, or null where nothing is sure.
function required(selector) {
    if (requirements.has(selector)) return requirements.get(selector);
    let needs = [];
    if (/[\\|]/.test(selector)) needs = null;
    else {
        for (const part of topLevel(selector, ",")) {
            const compounds = topLevel(part.trim(), " >+~").filter(Boolean);
            const subject = (compounds[compounds.length - 1] || "").split("::")[0];
            const outside = subject.replace(/\([^()]*\)|\[[^\]]*\]/g, "");
            const id = /#([\w-]+)/.exec(outside);
            const name = /\.([\w-]+)/.exec(outside);
            const tag = /^([a-zA-Z][\w-]*)/.exec(outside);
            if (id) needs.push({id: id[1]});
            else if (name) needs.push({className: name[1]});
            else if (tag) needs.push({tag: tag[1].toLowerCase()});
            else {
                needs = null;
                break;
            }
        }
    }
    requirements.set(selector, needs);
    return needs;
}

function possible(element, needs) {
    return needs.some((need) => need.id !== undefined ? element.id === need.id
        : need.className !== undefined ? element.classList.contains(need.className)
            : element.localName.toLowerCase() === need.tag);
}

QuerySelector.matches = function (element, selector, options) {
    if (options?.ignoreErrors && typeof selector === "string") {
        const needs = required(selector);
        if (needs && !possible(element, needs)) return null;
    }
    return fullMatch.call(this, element, selector, options);
};

// A structured clone in the page's own realm, so a clone's objects are the page's objects. It is
// evaluated in the page; it closes over nothing of this file.
function structuredCloneStandIn(value) {
    const seen = new Map();
    const fail = (what) => {
        throw new DOMException(`${what} could not be cloned.`, "DataCloneError");
    };
    const clone = (current) => {
        if (current === null || typeof current !== "object") {
            if (typeof current === "function" || typeof current === "symbol") fail(String(current));
            return current;
        }
        if (seen.has(current)) return seen.get(current);
        const tag = Object.prototype.toString.call(current);
        let result;
        if (Array.isArray(current)) {
            result = [];
            seen.set(current, result);
            current.forEach((item, index) => { result[index] = clone(item); });
            return result;
        }
        if (tag === "[object Date]") result = new Date(current.getTime());
        else if (tag === "[object RegExp]") result = new RegExp(current.source, current.flags);
        else if (tag === "[object ArrayBuffer]") result = current.slice(0);
        else if (ArrayBuffer.isView(current)) result = new globalThis[current.constructor.name](current);
        else if (tag === "[object Map]") {
            result = new Map();
            seen.set(current, result);
            current.forEach((item, key) => result.set(clone(key), clone(item)));
            return result;
        } else if (tag === "[object Set]") {
            result = new Set();
            seen.set(current, result);
            current.forEach((item) => result.add(clone(item)));
            return result;
        } else if (typeof current.nodeType === "number" || typeof current.then === "function") fail(tag);
        else {
            result = {};
            seen.set(current, result);
            for (const key of Object.keys(current)) result[key] = clone(current[key]);
            return result;
        }
        seen.set(current, result);
        return result;
    };
    return clone(value);
}

function isLoopback(hostname) {
    const host = hostname.replace(/^\[|\]$/g, "");
    return host === "localhost" || host === "::1" || host === "0.0.0.0" || host === "::" ||
        /^127\.\d+\.\d+\.\d+$/.test(host);
}

// Whether a URL leaves the machine: http, https, ws and wss to a host that is not loopback.
function remote(url) {
    let parsed;
    try {
        parsed = new URL(url);
    } catch {
        return null;
    }
    if (!["http:", "https:", "ws:", "wss:"].includes(parsed.protocol)) return null;
    if (isLoopback(parsed.hostname)) return null;
    return {host: parsed.hostname, port: parsed.port || {"http:": 80, "ws:": 80}[parsed.protocol] || 443};
}

// The page's clock: timers, intervals, animation frames and idle callbacks as tasks at virtual times.
class Clock {
    constructor(page) {
        this.page = page;
        this.now = 0;
        this.tasks = [];
        this.serial = 0;
    }

    add(handler, delay, args, interval, at) {
        const id = ++this.serial;
        const wait = Math.max(0, Number(delay) || 0);
        this.tasks.push({id, at: at ?? this.now + wait, handler, args, interval: interval ? Math.max(1, wait) : 0});
        return id;
    }

    frame(callback) {
        const at = (Math.floor(this.now / FRAME_MS) + 1) * FRAME_MS;
        return this.add(callback, 0, null, false, at);
    }

    clear(id) {
        const index = this.tasks.findIndex((task) => task.id === id);
        if (index >= 0) this.tasks.splice(index, 1);
    }

    next() {
        let first = null;
        for (const task of this.tasks) {
            if (!first || task.at < first.at || task.at === first.at && task.id < first.id) first = task;
        }
        return first;
    }

    // Runs the first task; the page's error handling sees what it throws.
    run(task) {
        this.tasks.splice(this.tasks.indexOf(task), 1);
        this.now = Math.max(this.now, task.at);
        if (task.interval) this.tasks.push({...task, at: this.now + task.interval});
        const window = this.page.window;
        try {
            if (typeof task.handler === "string") window.eval(task.handler);
            else if (task.args === null) task.handler.call(window, this.now);
            else task.handler.apply(window, task.args);
        } catch (error) {
            this.page.uncaught(error);
        }
    }

    // Runs every task due by `until`, in order; the clock ends at `until`.
    async advance(until) {
        let ran = 0;
        for (let task = this.next(); task && task.at <= until; task = this.next()) {
            this.run(task);
            await turns(1);
            if (++ran > TASKS_PER_INSTANT * 10) break;
        }
        this.now = Math.max(this.now, until);
    }
}

function turns(count) {
    let chain = Promise.resolve();
    for (let index = 0; index < count; index += 1) chain = chain.then(() => new Promise((resolve) => setImmediate(resolve)));
    return chain;
}

function formatted(args) {
    return args.map((arg) => typeof arg === "string" ? arg : util.inspect(arg, {depth: 2})).join(" ");
}

const CONSOLE_TYPES = {log: "log", info: "info", warn: "warning", error: "error", debug: "debug", trace: "trace",
    dir: "dir", table: "table", assert: "assert", count: "count", group: "startGroup", groupCollapsed: "startGroup",
    groupEnd: "endGroup", time: "time", timeEnd: "timeEnd", timeLog: "log", clear: "clear", dirxml: "dirxml"};

class FakePage {
    constructor(id, options) {
        this.id = id;
        this.viewport = options.viewport || [1280, 720];
        this.media = {mediaType: "screen", prefersColorScheme: "light", prefersReducedMotion: "no-preference",
            forcedColors: "none", ...(options.media || {})};
        this.events = [];
        this.defaults = new Map();
        this.browser = null;
        this.window = null;
        this.storage = {};
        this.hovered = null;
        this.dirty = new WeakSet();
        this.pending = 0;
        // The files the page downloaded, in order: {filename, url, bytes (a Buffer) or error}.
        this.downloads = [];
        // The state's recording the page replays (null: the door's defaults), the step it has
        // reached, and what it asked at each step, by expectation and key.
        this.recording = null;
        this.reached = 0;
        this.asked = new Map();
    }

    // The page asked `kind` (an expectation's name) of `key`: listed for the recorder by step.
    ask(kind, key) {
        if (!this.asked.has(this.reached)) this.asked.set(this.reached, {});
        const step = this.asked.get(this.reached);
        (step[kind] = step[kind] || new Set()).add(key);
    }

    // The answer of the latest step reached that recorded `kind` for `key` (for the whole answer
    // where `key` is undefined), or undefined where no step did.
    recorded(kind, key) {
        const answers = this.recording?.answers || [];
        for (let index = answers.length - 1; index >= 0; index -= 1) {
            const answer = answers[index];
            if (answer.step > this.reached || !answer[kind]) continue;
            if (key === undefined) return answer[kind];
            if (Object.prototype.hasOwnProperty.call(answer[kind], key)) return answer[kind][key];
        }
        return undefined;
    }

    // Work the page awaits outside happy-dom: it is busy until the promise settles.
    track(promise) {
        this.pending += 1;
        const end = () => { this.pending -= 1; };
        promise.then(end, end);
        return promise;
    }

    event(event) {
        this.events.push(event);
    }

    // The page downloads the file `url` names, a blob: URL the page made or a data: URL, under the
    // link's `download` name, else the URL's last segment.
    download(url, name) {
        const entry = {url, filename: name || decodeURIComponent(url.split(/[?#]/)[0].split("/").pop() || "") || "download"};
        this.downloads.push(entry);
        if (url.startsWith("blob:")) {
            const blob = resolveObjectURL(url);
            if (!blob) {
                entry.error = `the blob: URL ${url} names no blob; the page revoked it before the download`;
                return;
            }
            entry.pending = true;
            this.track(blob.arrayBuffer().then((buffer) => { entry.bytes = Buffer.from(buffer); },
                (error) => { entry.error = String(error?.message || error); })
                .finally(() => { entry.pending = false; }));
        } else if (url.startsWith("data:")) {
            const inline = /^data:[^,]*?(;base64)?,(.*)$/s.exec(url);
            entry.bytes = inline[1] ? Buffer.from(decodeURIComponent(inline[2]), "base64")
                : Buffer.from(decodeURIComponent(inline[2]), "utf8");
        } else {
            entry.error = `the fake browser downloads only a blob: or data: URL, not ${url} (${NOTE}, The fake browser)`;
        }
    }

    uncaught(error) {
        const window = this.window;
        if (!window) return;
        window[PropertySymbol.dispatchError](error);
    }

    // A default answer the page was given, by the call and the element's key.
    gave(call, element, answer) {
        const key = `${call} ${element ? doorKey(element) : "window"} -> ${answer}`;
        this.defaults.set(key, (this.defaults.get(key) || 0) + 1);
    }

    console() {
        const page = this;
        const console = {};
        for (const [method, type] of Object.entries(CONSOLE_TYPES)) {
            console[method] = (...args) => {
                if (method === "assert") {
                    if (args[0]) return;
                    args = ["Assertion failed:", ...args.slice(1)];
                }
                page.event({type: "console", level: type, text: formatted(args)});
            };
        }
        return console;
    }

    settings() {
        const page = this;
        return {
            enableJavaScriptEvaluation: true,
            suppressInsecureJavaScriptEnvironmentWarning: true,
            suppressCodeGenerationFromStringsWarning: true,
            device: {...this.media},
            viewport: {width: this.viewport[0], height: this.viewport[1], devicePixelRatio: 1},
            navigation: {disableMainFrameNavigation: true, disableChildPageNavigation: true},
            fetch: {interceptor: {
                beforeAsyncRequest: ({request, window}) => {
                    page.request(request, window);
                    return undefined;
                },
                beforeSyncRequest: ({request, window}) => {
                    page.request(request, window);
                    return undefined;
                },
            }},
        };
    }

    // Each request the page makes through happy-dom's fetch (fetch, XMLHttpRequest and the resources
    // happy-dom loads) is a `request` event, as Playwright's page reports it, but for happy-dom's
    // CORS preflight, which Playwright does not report. The interceptor cannot tell the preflight
    // from a page's own OPTIONS request, which the runtime never makes, so no OPTIONS request is
    // reported. One that leaves the machine is refused.
    request(request, window) {
        if (request.method !== "OPTIONS") this.event({type: "request", url: String(request.url)});
        this.refuse(request.url, window);
    }

    // Refuses a request that leaves the machine, as test/network_guard.py refuses a socket.
    refuse(url, window) {
        const target = remote(url);
        if (!target) return;
        this.event({type: "network", host: target.host, port: target.port, url});
        throw new (window || this.window).TypeError(
            `${NAME}: the fake page requested ${url}, which leaves the machine; only a local server a test starts ` +
            `answers a fake page (${NOTE}, The fake browser).`);
    }

    close() {
        if (this.browser) {
            const browser = this.browser;
            this.saveStorage();
            this.browser = null;
            this.window = null;
            browser.close().catch(() => {});
        }
    }

    saveStorage() {
        const window = this.window;
        if (!window) return;
        const origin = storageOrigin(window.location.href);
        if (!origin) return;
        const read = (storage) => {
            const entries = {};
            for (let index = 0; index < storage.length; index += 1) entries[storage.key(index)] = storage.getItem(storage.key(index));
            return entries;
        };
        try {
            this.storage[origin] = {local: read(window.localStorage), session: read(window.sessionStorage)};
        } catch {
            // The viewer frame's replayed refusal: its storage keeps nothing.
        }
    }

    restoreStorage(window, url) {
        const saved = this.storage[storageOrigin(url)];
        if (!saved) return;
        for (const [key, value] of Object.entries(saved.local)) window.localStorage.setItem(key, value);
        for (const [key, value] of Object.entries(saved.session)) window.sessionStorage.setItem(key, value);
    }

    async open(url, timeout) {
        this.close();
        const target = remote(url);
        if (target) {
            this.event({type: "network", host: target.host, port: target.port, url});
            throw new FakeError("network", `${NAME}: goto ${url} leaves the machine; only a local server a test starts ` +
                `answers a fake page (${NOTE}, The fake browser).`);
        }
        this.clock = new Clock(this);
        this.hovered = null;
        this.browser = new happyDom.Browser({settings: this.settings(), console: this.console()});
        const page = this.browser.newPage();
        this.happyPage = page;
        this.window = page.mainFrame.window;
        install(this.window, this);
        if (url.startsWith("file:")) {
            let html;
            try {
                html = fs.readFileSync(fileURLToPath(url), "utf8");
            } catch (error) {
                throw new FakeError("error", `${NAME}: goto ${url}: the file could not be read: ${error.message}.`);
            }
            page.url = url;
            this.restoreStorage(this.window, url);
            page.content = html;
        } else if (url !== "about:blank") {
            page.url = url;
            this.restoreStorage(this.window, url);
            const response = await this.window.fetch(url);
            page.content = await response.text();
        }
        const loaded = await this.until(() => this.window.document.readyState === "complete", timeout);
        if (!loaded) throw new FakeError("timeout", `${NAME}: goto ${url}: the page did not load within ${timeout} ms of its clock.`);
    }

    // Lets the page run what is due now: its microtasks, its zero-delay tasks and the I/O it awaits.
    async settle() {
        for (let round = 0; round < TASKS_PER_INSTANT; round += 1) {
            await turns(2);
            for (let waited = 0; this.busy() && waited < BUSY_TURNS; waited += 1) await turns(1);
            const task = this.clock.next();
            if (!task || task.at > this.clock.now) return;
            this.clock.run(task);
        }
    }

    busy() {
        if (this.pending > 0) return true;
        const manager = this.happyPage?.mainFrame?.[PropertySymbol.asyncTaskManager];
        return manager ? manager.getTaskCount() > 0 : false;
    }

    // Runs the page until `check` answers something truthy, which it returns, or until nothing is left
    // to run before `timeout` milliseconds of its clock have passed, when it returns null.
    async until(check, timeout) {
        const deadline = this.clock.now + timeout;
        for (;;) {
            await this.settle();
            const result = await check();
            if (result) return result;
            const task = this.clock.next();
            if (!task || task.at > deadline) return null;
            this.clock.run(task);
        }
    }

    // What passes between two requests: the page settles and one frame of its clock passes.
    async between() {
        await this.settle();
        await this.clock.advance(this.clock.now + FRAME_MS);
        await this.settle();
    }
}

function storageOrigin(url) {
    try {
        const parsed = new URL(url);
        if (parsed.protocol === "file:") return "file://";
        return ["http:", "https:"].includes(parsed.protocol) ? parsed.origin : "";
    } catch {
        return "";
    }
}

// The initial values of the computed properties the runtime reads, which happy-dom leaves empty
// where no rule sets them (the expectation cascade).
const INITIAL_VALUES = Object.fromEntries([
    ...["padding", "margin"].flatMap((box) => ["Top", "Right", "Bottom", "Left"].map((side) => [`${box}${side}`, "0px"])),
    ...["Top", "Right", "Bottom", "Left"].map((side) => [`border${side}Width`, "0px"]),
    ["visibility", "visible"], ["overflowX", "visible"], ["overflowY", "visible"], ["backgroundColor", "rgba(0, 0, 0, 0)"],
]);

// The fake's own reading of a computed style, which the page's `asked` does not list.
const OWN_STYLE = Symbol("ownStyle");
function ownStyle(window, element) {
    return (window[OWN_STYLE] || window.getComputedStyle).call(window, element);
}

// Whether the element takes part in layout: in the document, and neither it nor an ancestor has a
// computed display of `none` (as `[hidden]` and a closed popover have by the user-agent rules above).
function rendered(window, element) {
    if (!element || !element.isConnected) return false;
    for (let current = element; current && current.nodeType === 1; current = current.parentElement) {
        if (ownStyle(window, current).display === "none") return false;
    }
    return true;
}

// A compression stream class whose streams keep the page busy (FakePage.busy) until they end.
function tracked(Stream, page) {
    return class {
        constructor(format) {
            const inner = new Stream(format);
            let open = true;
            page.pending += 1;
            const end = () => {
                if (open) {
                    open = false;
                    page.pending -= 1;
                }
            };
            const tap = new TransformStream({
                transform(chunk, controller) { controller.enqueue(chunk); },
                flush() { end(); },
                cancel() { end(); },
            });
            inner.readable.pipeTo(tap.writable).catch(end);
            this.readable = tap.readable;
            this.writable = inner.writable;
        }
    };
}

function closedPopover(element) {
    return element && element.nodeType === 1 && element.hasAttribute("popover") && !openPopovers.has(element);
}

// The stand-ins and the door's default answers, installed in a page before its first script.
function install(window, page) {
    const clock = page.clock;
    const timers = {
        setTimeout: (handler, delay, ...args) => clock.add(handler, delay, args, false),
        clearTimeout: (id) => clock.clear(id),
        setInterval: (handler, delay, ...args) => clock.add(handler, delay, args, true),
        clearInterval: (id) => clock.clear(id),
        requestAnimationFrame: (callback) => clock.frame(callback),
        cancelAnimationFrame: (id) => clock.clear(id),
        requestIdleCallback: (callback) => clock.add(callback, 0, [{didTimeout: false, timeRemaining: () => 50}], false),
        cancelIdleCallback: (id) => clock.clear(id),
    };
    for (const [name, value] of Object.entries(timers)) {
        Object.defineProperty(window, name, {value, writable: true, configurable: true});
    }
    // An uncaught error is the page error Playwright reports, not a console message as well.
    window[PropertySymbol.dispatchError] = (error) => {
        const message = error && error.message !== undefined ? String(error.message) : String(error);
        window.dispatchEvent(new window.ErrorEvent("error", {message, error, cancelable: true}));
    };
    // A fragment navigation fires popstate and then hashchange, as Chromium fires them; happy-dom
    // fires only hashchange. The runtime opens a chapter on popstate.
    window.addEventListener("hashchange", () => {
        window.dispatchEvent(new window.PopStateEvent("popstate", {state: window.history.state}));
    }, true);
    window.addEventListener("error", (event) => {
        if (event.target !== window) return;
        const error = event.error;
        page.event({type: "pageerror", name: error?.name || "Error",
            message: error?.message !== undefined ? String(error.message) : String(event.message),
            stack: error?.stack ? String(error.stack) : ""});
    });

    // Node's compression streams and Node's crypto, whose work runs on Node's thread pool: the page
    // counts as busy until each stream ends and each digest resolves. And a structured clone and
    // Option in the page's own realm.
    window.CompressionStream = tracked(globalThis.CompressionStream, page);
    window.DecompressionStream = tracked(globalThis.DecompressionStream, page);
    const subtle = globalThis.crypto.subtle;
    Object.defineProperty(window, "crypto", {configurable: true, value: {
        getRandomValues: (array) => globalThis.crypto.getRandomValues(array),
        randomUUID: () => globalThis.crypto.randomUUID(),
        subtle: new Proxy(subtle, {get: (target, name) => typeof target[name] === "function"
            ? (...args) => page.track(target[name](...args)) : target[name]}),
    }});
    window.structuredClone = window.eval(`(${structuredCloneStandIn.toString()})`);
    // happy-dom's TextEncoder is Node's, whose bytes are Node's Uint8Array: the runtime's
    // `bytes instanceof Uint8Array` refused them. The stand-in encodes with Node's and hands the
    // bytes over as the page's own Uint8Array, as Chromium does.
    const encoder = new globalThis.TextEncoder();
    window.TextEncoder = window.eval(`(encode, encodeInto) => class TextEncoder {
        get encoding() { return "utf-8"; }
        encode(text = "") { return new Uint8Array(encode(String(text))); }
        encodeInto(text, target) { return encodeInto(String(text), target); }
    }`)((text) => encoder.encode(text), (text, target) => encoder.encodeInto(text, target));
    window.Option = window.eval(`(function Option(text, value, defaultSelected, selected) {
        const option = document.createElement("option");
        if (text !== undefined) option.textContent = String(text);
        if (value !== undefined) option.value = String(value);
        if (defaultSelected) option.setAttribute("selected", "");
        if (selected || defaultSelected) option.selected = true;
        return option;
    })`);

    windowPages.set(window, page);

    // print fires beforeprint and afterprint, as Chromium's returns at once in a test run. Nothing is
    // laid out for print, so no print media is applied in between: print layout and the printed PDF
    // are recorded answers (browser-door.md); emulate_media("print") gives print media.
    window.print = () => {
        window.dispatchEvent(new window.Event("beforeprint"));
        window.dispatchEvent(new window.Event("afterprint"));
    };

    // The canvas text measure: a 2D context whose measureText is the DOM tier's constant width.
    window.HTMLCanvasElement.prototype.getContext = function (type) {
        if (type !== "2d") return null;
        const canvas = this;
        const context = {
            canvas, font: "10px sans-serif",
            measureText(text) {
                const key = `${context.font}|${text}`;
                page.ask("text-width", key);
                const recorded = page.recorded("text-width", key);
                const width = recorded ?? String(text).length * CHARACTER_WIDTH;
                if (recorded === undefined) page.gave("measureText", null, `${width}`);
                return {width, actualBoundingBoxLeft: 0, actualBoundingBoxRight: width,
                    actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2, fontBoundingBoxAscent: 8,
                    fontBoundingBoxDescent: 2};
            },
        };
        return new Proxy(context, {get: (target, name) => name in target ? target[name] : () => undefined});
    };

    installPopovers(window, page);
    installFocus(window);
    installLayout(window, page);
    installRecorded(window, page);
    installNetwork(window, page);
}

// What the page asks that the recorder measures, and the supplied answers that are not layout: the
// computed styles and media queries the page reads (listed, never replayed: happy-dom computes
// them), decoded image sizes, `document.fonts`, where `scrollIntoView` scrolls to, and the viewer
// frame's refusals (browser-door.md, Recording and replay).
function installRecorded(window, page) {
    const getComputedStyle = window.getComputedStyle;
    window[OWN_STYLE] = getComputedStyle;
    // Each property the page reads of an element's computed style is listed as `<key>|<property>`;
    // one no rule sets has its initial value, where happy-dom leaves it empty.
    window.getComputedStyle = function (element, pseudo) {
        const style = getComputedStyle.call(window, element, pseudo);
        if (!element || element.nodeType !== 1 || pseudo) return style;
        const key = doorKey(element);
        const initial = (property, value) => value === "" && INITIAL_VALUES[property] !== undefined ? INITIAL_VALUES[property] : value;
        return new Proxy(style, {get(target, name) {
            if (name === "getPropertyValue") {
                return (property) => {
                    page.ask("cascade", `${key}|${property}`);
                    const camel = String(property).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
                    return initial(camel, target.getPropertyValue(property));
                };
            }
            const value = target[name];
            if (typeof value === "function") return value.bind(target);
            if (typeof name === "string" && /^[a-z]/i.test(name) && name !== "length") {
                page.ask("cascade", `${key}|${name}`);
                return initial(name, value);
            }
            return value;
        }});
    };
    const matchMedia = window.matchMedia;
    window.matchMedia = function (query) {
        page.ask("media", String(query));
        return matchMedia.call(window, query);
    };
    for (const [name, side] of [["naturalWidth", 0], ["naturalHeight", 1]]) {
        Object.defineProperty(window.HTMLImageElement.prototype, name, {configurable: true, get() {
            const key = doorKey(this);
            page.ask("image-size", key);
            const recorded = page.recorded("image-size", key);
            if (recorded) return recorded[side];
            page.gave(name, this, "0");
            return 0;
        }});
    }
    const scrollIntoView = window.Element.prototype.scrollIntoView;
    window.Element.prototype.scrollIntoView = function (...args) {
        const key = doorKey(this);
        page.ask("scroll-into-view", key);
        if (scrollIntoView) scrollIntoView.apply(this, args);
        const recorded = page.recorded("scroll-into-view", key);
        const scroller = window.document.scrollingElement || window.document.documentElement;
        if (recorded && scroller) scroller.scrollTop = recorded.scrollTop;
    };
    const fonts = page.recorded("fonts");
    if (fonts) {
        const set = {
            status: fonts.status, size: 0,
            check: () => true, load: () => Promise.resolve([]), forEach() {}, addEventListener() {},
            removeEventListener() {}, [Symbol.iterator]: function* () {},
        };
        set.ready = Promise.resolve(set);
        Object.defineProperty(window.document, "fonts", {configurable: true, get: () => set});
    }
    if (page.recording?.context?.frame === "viewer") refuse(window, page.recorded("viewer-frame") || {});
}

// The viewer frame's refusals as Chromium gave them (the expectation viewer-frame): each call path,
// `window.open()` for a method and `window.localStorage` for a property, throws, returns or rejects
// as recorded, and fires the events recorded with it.
function refuse(window, refusals) {
    for (const [path, outcome] of Object.entries(refusals)) {
        const method = path.endsWith("()");
        const names = path.replace(/\(\)$/, "").split(".");
        const parts = names[0] === "window" ? names.slice(1) : names;
        let owner = window;
        for (const name of parts.slice(0, -1)) owner = owner?.[name];
        if (!owner) continue;
        const refusal = (name) => new window.DOMException(
            `${path} is refused in the viewer frame, as the recorded Chromium refused it (${NOTE}).`, name);
        const act = () => {
            for (const type of outcome.fires || []) window.dispatchEvent(new window.Event(type));
            if (outcome.throws) throw refusal(outcome.throws);
            if (outcome.rejects) return Promise.reject(refusal(outcome.rejects));
            if (Object.prototype.hasOwnProperty.call(outcome, "resolves")) return Promise.resolve(outcome.resolves);
            return outcome.returns ?? (method ? undefined : null);
        };
        const last = parts[parts.length - 1];
        const descriptor = method ? {configurable: true, writable: true, value: () => act()}
            : {configurable: true, get: act, set() { if (outcome.throws) throw refusal(outcome.throws); }};
        // A property of the window is defined on the page's own global: a getter that throws on the
        // window object outside it reads as undefined inside the page.
        if (owner === window) window.eval("(name, descriptor) => Object.defineProperty(globalThis, name, descriptor)")(last, descriptor);
        else Object.defineProperty(owner, last, descriptor);
    }
}

// Focus as Chromium moves it (the expectation focus): focus() on an element that cannot take focus
// does nothing, and a dialog that opens focuses its first focusable descendant and, as it closes,
// gives focus back to the element that had it.
function installFocus(window) {
    const prototype = window.HTMLElement.prototype;
    const focus = prototype.focus;
    const focusable = (element) => element.isConnected && element.matches(FOCUSABLE) && !element.disabled &&
        !(element.localName === "input" && element.type === "hidden") && rendered(window, element);
    prototype.focus = function (...args) {
        if (focusable(this)) focus.apply(this, args);
    };
    const dialog = window.HTMLDialogElement?.prototype;
    if (!dialog) return;
    const before = new WeakMap();
    for (const name of ["show", "showModal"]) {
        const open = dialog[name];
        dialog[name] = function (...args) {
            const wasOpen = this.open;
            before.set(this, window.document.activeElement);
            const result = open.apply(this, args);
            if (!wasOpen) {
                const first = [...this.querySelectorAll("*")].find(focusable);
                if (first) first.focus();
            }
            return result;
        };
    }
    const close = dialog.close;
    dialog.close = function (...args) {
        const wasOpen = this.open;
        const result = close.apply(this, args);
        const previous = before.get(this);
        if (wasOpen && previous && previous.isConnected && previous !== window.document.body) previous.focus();
        return result;
    };
}

function installPopovers(window, page) {
    const prototype = window.HTMLElement.prototype;
    Object.defineProperty(prototype, CLOSED_POPOVER, {configurable: true, enumerable: false,
        get() { return closedPopover(this); }});
    // A popover's state is no attribute, so happy-dom's caches of its styles and matches are cleared by hand.
    const restyle = (element) => {
        for (const each of [element, ...element.querySelectorAll("*")]) each[PropertySymbol.clearCache]();
    };
    const toggle = (element, from, to) => {
        restyle(element);
        const event = new window.Event("toggle");
        Object.assign(event, {oldState: from, newState: to});
        page.clock.add(() => element.dispatchEvent(event), 0, [], false);
    };
    const hide = (element) => {
        if (!openPopovers.has(element)) return;
        openPopovers.delete(element);
        toggle(element, "open", "closed");
    };
    Object.defineProperty(prototype, "popover", {
        configurable: true,
        get() { return this.hasAttribute("popover") ? (this.getAttribute("popover") || "auto") : null; },
        set(value) { if (value === null) this.removeAttribute("popover"); else this.setAttribute("popover", value); },
    });
    prototype.showPopover = function () {
        if (!this.hasAttribute("popover")) {
            throw new window.DOMException("Not supported on elements that do not have a valid value for the 'popover' attribute.", "NotSupportedError");
        }
        if (openPopovers.has(this)) return;
        if (this.popover === "auto") {
            for (const other of window.document.querySelectorAll("[popover]")) {
                if (other !== this && other.popover === "auto" && !other.contains(this)) hide(other);
            }
        }
        openPopovers.add(this);
        toggle(this, "closed", "open");
    };
    prototype.hidePopover = function () { hide(this); };
    prototype.togglePopover = function (force) {
        const open = force === undefined ? !openPopovers.has(this) : Boolean(force);
        if (open) this.showPopover(); else this.hidePopover();
        return open;
    };
    // Light dismiss of `auto` popovers: Escape, and a pointerdown outside them. The listeners are the
    // window's: writing the page's content removes the document's own.
    window.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        const open = [...window.document.querySelectorAll("[popover]")].filter((each) => each.popover === "auto" && openPopovers.has(each));
        if (open.length) hide(open[open.length - 1]);
    }, true);
    window.addEventListener("pointerdown", (event) => {
        for (const each of window.document.querySelectorAll("[popover]")) {
            if (each.popover === "auto" && openPopovers.has(each) && !each.contains(event.target)) hide(each);
        }
    }, true);
}

// Layout: the recorded answers of the latest step reached, else the door's defaults
// (browser-door.md, Recording and replay).
function installLayout(window, page) {
    // The root element's box is the viewport, the window's inner size, which happy-dom knows.
    const measure = (element) => element === window.document.documentElement
        ? {x: 0, y: 0, width: page.viewport[0], height: page.viewport[1]}
        : rendered(window, element) ? {x: 0, y: 0, ...BOX} : {x: 0, y: 0, width: 0, height: 0};
    const fromRecording = (element) => {
        const recorded = page.recorded("box", doorKey(element));
        if (!recorded) return null;
        const [x, y, width, height] = recorded.border;
        return {x, y, width, height};
    };
    // `call` is the runtime's call, listed for the recorder; the fake's own hit test lists nothing.
    const box = (element, call) => {
        const key = doorKey(element);
        if (call !== "elementFromPoint") page.ask("box", key);
        const recorded = fromRecording(element);
        if (recorded) return recorded;
        const answer = measure(element);
        if (element !== window.document.documentElement) {
            page.gave(call, element, answer.width ? `${answer.width}x${answer.height}` : "empty");
        }
        return answer;
    };
    const rect = ({x, y, width, height}) => new window.DOMRect(x, y, width, height);
    const prototypes = [window.Element.prototype, window.HTMLElement.prototype];
    window.Element.prototype.getBoundingClientRect = function () { return rect(box(this, "getBoundingClientRect")); };
    window.Element.prototype.getClientRects = function () {
        const answer = box(this, "getClientRects");
        const recorded = page.recorded("box", doorKey(this));
        if (recorded) return recorded.rects.map(([x, y, width, height]) => rect({x, y, width, height}));
        return answer.width || answer.height ? [rect(answer)] : [];
    };
    if (window.HTMLElement.prototype.hasOwnProperty("getBoundingClientRect")) {
        window.HTMLElement.prototype.getBoundingClientRect = window.Element.prototype.getBoundingClientRect;
        window.HTMLElement.prototype.getClientRects = window.Element.prototype.getClientRects;
    }
    const sizes = {
        clientWidth: "width", clientHeight: "height", offsetWidth: "width", offsetHeight: "height",
        scrollWidth: "width", scrollHeight: "height",
    };
    const recordedSize = (element, name) => {
        const key = doorKey(element);
        page.ask("sizes", key);
        const recorded = page.recorded("sizes", key);
        return recorded && Object.prototype.hasOwnProperty.call(recorded, name) ? recorded[name] : undefined;
    };
    for (const [name, side] of Object.entries(sizes)) {
        for (const prototype of prototypes) {
            Object.defineProperty(prototype, name, {configurable: true, get() {
                const recorded = recordedSize(this, name);
                if (recorded !== undefined) return recorded;
                const value = measure(this)[side];
                if (this !== window.document.documentElement) page.gave(name, this, String(value));
                return value;
            }});
        }
    }
    for (const name of ["offsetLeft", "offsetTop", "clientLeft", "clientTop"]) {
        for (const prototype of prototypes) {
            Object.defineProperty(prototype, name, {configurable: true, get() { return recordedSize(this, name) ?? 0; }});
        }
    }
    // The window's inner size, where the state's recording holds it.
    for (const name of ["innerWidth", "innerHeight"]) {
        const recorded = page.recorded("sizes", "window")?.[name];
        if (recorded !== undefined) Object.defineProperty(window, name, {configurable: true, get: () => recorded});
    }
    // The point under the pointer: the last shown element whose box holds it.
    window.document.elementFromPoint = (x, y) => window.document.elementsFromPoint(x, y)[0] || null;
    window.document.elementsFromPoint = (x, y) => {
        const found = [];
        for (const element of [...window.document.querySelectorAll("body *")].reverse()) {
            const answer = box(element, "elementFromPoint");
            if (answer.width && x >= answer.x && x < answer.x + answer.width && y >= answer.y && y < answer.y + answer.height) {
                found.push(element);
            }
        }
        return found.length ? [...found, window.document.body, window.document.documentElement] : [];
    };
    // A ResizeObserver reports each observed element once, a frame after observe, with its box.
    window.ResizeObserver = class ResizeObserver {
        constructor(callback) {
            this.callback = callback;
            this.observed = new Set();
        }

        observe(element) {
            this.observed.add(element);
            page.ask("resize", doorKey(element));
            page.clock.frame(() => {
                if (!this.observed.has(element)) return;
                const answer = box(element, "ResizeObserver");
                const recorded = page.recorded("resize", doorKey(element));
                const [contentWidth, contentHeight] = recorded?.content || [answer.width, answer.height];
                const [borderWidth, borderHeight] = recorded?.border || [answer.width, answer.height];
                const content = [{inlineSize: contentWidth, blockSize: contentHeight}];
                const border = [{inlineSize: borderWidth, blockSize: borderHeight}];
                this.callback([{target: element, contentRect: rect({x: 0, y: 0, width: contentWidth, height: contentHeight}),
                    borderBoxSize: border, contentBoxSize: content, devicePixelContentBoxSize: content}], this);
            });
        }

        unobserve(element) { this.observed.delete(element); }

        disconnect() { this.observed.clear(); }
    };
}

function installNetwork(window, page) {
    const WebSocket = window.WebSocket;
    if (WebSocket) {
        window.WebSocket = class extends WebSocket {
            constructor(url, protocols) {
                page.refuse(String(url), window);
                super(url, protocols);
            }
        };
    }
}

// ---- Locators: a chain of steps the facade builds, resolved to elements in document order.

function regex(pattern) {
    return new RegExp(pattern.regex, pattern.flags || "");
}

function normalize(text) {
    return String(text ?? "").replace(/[​\s]+/g, " ").trim();
}

function textMatches(element, text) {
    const content = normalize(element.textContent);
    if (text && typeof text === "object") return regex(text).test(content);
    return content.toLowerCase().includes(normalize(text).toLowerCase());
}

function documentOrder(window, elements) {
    const unique = [...new Set(elements)];
    return unique.sort((a, b) => {
        if (a === b) return 0;
        return a.compareDocumentPosition(b) & window.Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });
}

// A selector inside an element matches within that element's subtree only, as Playwright's do: each
// of its comma-separated selectors starts at :scope unless it names :scope itself.
function scoped(selector) {
    const parts = [];
    let depth = 0;
    let quote = "";
    let start = 0;
    for (let index = 0; index < selector.length; index += 1) {
        const character = selector[index];
        if (quote) {
            if (character === "\\") index += 1;
            else if (character === quote) quote = "";
        } else if (character === "\"" || character === "'") quote = character;
        else if (character === "(" || character === "[") depth += 1;
        else if (character === ")" || character === "]") depth -= 1;
        else if (character === "," && depth === 0) {
            parts.push(selector.slice(start, index));
            start = index + 1;
        }
    }
    parts.push(selector.slice(start));
    return parts.map((part) => part.includes(":scope") ? part.trim() : `:scope ${part.trim()}`).join(", ");
}

function resolve(page, chain, roots) {
    const window = page.window;
    let current = roots || [window.document];
    for (const step of chain) {
        if (step.css !== undefined) {
            const found = [];
            for (const root of current) {
                let matched;
                try {
                    matched = root.querySelectorAll(root.nodeType === 1 ? scoped(step.css) : step.css);
                } catch (error) {
                    throw new FakeError("unsupported", `${NAME}: the selector ${JSON.stringify(step.css)} is no CSS ` +
                        `selector the fake browser knows (${error.message}). Playwright's text and role selectors do not ` +
                        `exist there: write it as CSS and a text filter (has_text) (${NOTE}, The fake browser).`);
                }
                found.push(...matched);
            }
            current = documentOrder(window, found);
        } else if (step.nth !== undefined) {
            const index = step.nth < 0 ? current.length + step.nth : step.nth;
            current = current[index] ? [current[index]] : [];
        } else if (step.filter) {
            const filter = step.filter;
            current = current.filter((element) =>
                (filter.hasText === undefined || textMatches(element, filter.hasText)) &&
                (filter.hasNotText === undefined || !textMatches(element, filter.hasNotText)) &&
                (filter.has === undefined || resolve(page, filter.has, [element]).length > 0) &&
                (filter.hasNot === undefined || resolve(page, filter.hasNot, [element]).length === 0) &&
                (filter.visible === undefined || visible(window, element) === filter.visible));
        }
    }
    return current.filter((each) => each && each.nodeType === 1);
}

function describe(chain) {
    return chain.map((step) => step.css !== undefined ? `locator(${JSON.stringify(step.css)})`
        : step.nth !== undefined ? `nth(${step.nth})` : `filter(${JSON.stringify(step.filter)})`).join(".");
}

function visible(window, element) {
    if (!rendered(window, element)) return false;
    const visibility = ownStyle(window, element).visibility;
    return visibility !== "hidden" && visibility !== "collapse";
}

function enabled(element) {
    return !(element.disabled || element.closest?.("fieldset[disabled]") || element.getAttribute("aria-disabled") === "true");
}

const FOCUSABLE = "a[href], area[href], button, input, select, textarea, summary, iframe, [tabindex], [contenteditable]:not([contenteditable='false'])";

function pageValue(window, value) {
    return value === undefined ? undefined : window.JSON.parse(JSON.stringify(value));
}

function serialized(value) {
    const seen = new WeakSet();
    return JSON.parse(JSON.stringify(value === undefined ? null : value, (key, item) => {
        if (item && typeof item === "object") {
            if (typeof item.nodeType === "number" && typeof item.nodeName === "string") return {};
            if (seen.has(item)) throw new FakeError("error", `${NAME}: evaluate returned a value that refers to itself.`);
            seen.add(item);
            if (item instanceof Map || Object.prototype.toString.call(item) === "[object Map]") return Object.fromEntries(item);
            if (Object.prototype.toString.call(item) === "[object Set]") return [...item];
        }
        return item === undefined ? null : item;
    }) ?? "null");
}

// Evaluates a Playwright page function: an expression, or a function called with its arguments. A
// promise it returns is awaited while the page's clock runs, as time passes in a browser.
async function evaluate(page, expression, args, timeout) {
    const window = page.window;
    let source = String(expression).trim();
    if (/^(async)?\s*function(\s|\()/.test(source)) source = `(${source})`;
    let value = window.eval(source);
    if (typeof value === "function") value = value(...args);
    if (!value || typeof value.then !== "function") return value;
    const outcome = {done: false};
    value.then((result) => Object.assign(outcome, {done: true, result}),
        (error) => Object.assign(outcome, {done: true, error, failed: true}));
    if (!await page.until(() => outcome.done, timeout)) {
        throw new FakeError("timeout", `${NAME}: evaluate ${JSON.stringify(String(expression).slice(0, 200))}: its promise did ` +
            `not settle within ${timeout} ms of the page's clock, and the page had nothing left to run.`);
    }
    if (outcome.failed) throw outcome.error;
    return outcome.result;
}

// ---- Input: what a reader's click, key or pointer does, as Chromium dispatches it.

const KEYS = {
    Enter: {key: "Enter", code: "Enter", keyCode: 13}, Space: {key: " ", code: "Space", keyCode: 32},
    " ": {key: " ", code: "Space", keyCode: 32}, Escape: {key: "Escape", code: "Escape", keyCode: 27},
    Tab: {key: "Tab", code: "Tab", keyCode: 9}, Backspace: {key: "Backspace", code: "Backspace", keyCode: 8},
    Delete: {key: "Delete", code: "Delete", keyCode: 46}, ArrowUp: {key: "ArrowUp", code: "ArrowUp", keyCode: 38},
    ArrowDown: {key: "ArrowDown", code: "ArrowDown", keyCode: 40}, ArrowLeft: {key: "ArrowLeft", code: "ArrowLeft", keyCode: 37},
    ArrowRight: {key: "ArrowRight", code: "ArrowRight", keyCode: 39}, Home: {key: "Home", code: "Home", keyCode: 36},
    End: {key: "End", code: "End", keyCode: 35}, PageUp: {key: "PageUp", code: "PageUp", keyCode: 33},
    PageDown: {key: "PageDown", code: "PageDown", keyCode: 34}, Shift: {key: "Shift", code: "ShiftLeft", keyCode: 16},
    Control: {key: "Control", code: "ControlLeft", keyCode: 17}, Alt: {key: "Alt", code: "AltLeft", keyCode: 18},
    Meta: {key: "Meta", code: "MetaLeft", keyCode: 91},
};
for (let number = 1; number <= 12; number += 1) KEYS[`F${number}`] = {key: `F${number}`, code: `F${number}`, keyCode: 111 + number};

function keyOf(name) {
    if (KEYS[name]) return KEYS[name];
    if ([...name].length === 1) {
        const upper = name.toUpperCase();
        return {key: name, code: /[a-z]/i.test(name) ? `Key${upper}` : /\d/.test(name) ? `Digit${name}` : "",
            keyCode: upper.charCodeAt(0), text: name};
    }
    throw new FakeError("unsupported", `${NAME}: the key ${JSON.stringify(name)} is not one the fake keyboard knows (${NOTE}, The fake browser).`);
}

class Input {
    constructor(page) {
        this.page = page;
        this.modifiers = new Set();
    }

    get window() { return this.page.window; }

    active() {
        const document = this.window.document;
        return document.activeElement && document.activeElement !== document.body ? document.activeElement : document.body;
    }

    // A text field the reader typed into fires change as it loses focus (before blur).
    leave(element) {
        if (element && this.page.dirty.has(element)) {
            this.page.dirty.delete(element);
            element.dispatchEvent(new this.window.Event("change", {bubbles: true}));
        }
    }

    focus(element) {
        const current = this.window.document.activeElement;
        if (current && current !== element) this.leave(current);
        element.focus();
    }

    blur(element) {
        this.leave(element);
        element.blur();
    }

    flags() {
        return {shiftKey: this.modifiers.has("Shift"), ctrlKey: this.modifiers.has("Control"),
            altKey: this.modifiers.has("Alt"), metaKey: this.modifiers.has("Meta")};
    }

    pointer(type, target, init = {}) {
        const window = this.window;
        const Event = type.startsWith("pointer") ? window.PointerEvent || window.MouseEvent : window.MouseEvent;
        const options = {bubbles: !type.endsWith("enter") && !type.endsWith("leave"), cancelable: true, composed: true,
            view: window, button: 0, buttons: type.endsWith("down") ? 1 : 0, clientX: 0, clientY: 0, detail: 1,
            pointerId: 1, pointerType: "mouse", isPrimary: true, ...this.flags(), ...init};
        return target.dispatchEvent(new Event(type, options));
    }

    hover(target, init) {
        if (this.page.hovered === target) {
            this.pointer("pointermove", target, init);
            this.pointer("mousemove", target, init);
            return;
        }
        const previous = this.page.hovered;
        if (previous && previous.isConnected) {
            this.pointer("pointerout", previous, init);
            this.pointer("pointerleave", previous, init);
            this.pointer("mouseout", previous, init);
            this.pointer("mouseleave", previous, init);
        }
        this.page.hovered = target;
        this.pointer("pointerover", target, init);
        this.pointer("pointerenter", target, init);
        this.pointer("mouseover", target, init);
        this.pointer("mouseenter", target, init);
        this.pointer("pointermove", target, init);
        this.pointer("mousemove", target, init);
    }

    down(target, init) {
        const pointer = this.pointer("pointerdown", target, init);
        const mouse = pointer && this.pointer("mousedown", target, init);
        if (mouse) {
            const focusable = target.closest?.(FOCUSABLE);
            if (focusable) this.focus(focusable);
            else {
                const active = this.window.document.activeElement;
                if (active && active !== this.window.document.body) this.blur(active);
            }
        }
    }

    up(target, init) {
        this.pointer("pointerup", target, init);
        this.pointer("mouseup", target, init);
    }

    activate(target, init) {
        if (typeof target.click === "function" && target instanceof this.window.HTMLElement && !this.modifiers.size && !init?.button) {
            target.click();
        } else {
            this.pointer("click", target, init);
        }
    }

    click(target, init = {}, count = 1) {
        this.hover(target, init);
        for (let index = 1; index <= count; index += 1) {
            this.down(target, {...init, detail: index});
            this.up(target, {...init, detail: index});
            this.activate(target, {...init, detail: index});
        }
        if (count === 2) this.pointer("dblclick", target, {...init, detail: 2});
    }

    // A key's events on the focused element, and what Chromium does by default for them.
    press(name) {
        const parts = name.split("+");
        const keys = parts.map(keyOf);
        const modifiers = keys.slice(0, -1);
        modifiers.forEach((key) => this.modifiers.add(key.key));
        try {
            const key = keys[keys.length - 1];
            this.down_key(key);
            this.up_key(key);
        } finally {
            modifiers.forEach((key) => this.modifiers.delete(key.key));
        }
    }

    keyboardEvent(type, key, target) {
        const window = this.window;
        return target.dispatchEvent(new window.KeyboardEvent(type, {key: key.key, code: key.code, keyCode: key.keyCode,
            which: key.keyCode, bubbles: true, cancelable: true, composed: true, view: window, ...this.flags()}));
    }

    down_key(key) {
        if (["Shift", "Control", "Alt", "Meta"].includes(key.key)) this.modifiers.add(key.key);
        const target = this.active();
        const allowed = this.keyboardEvent("keydown", key, target);
        if (!allowed) return;
        const tag = target.localName;
        const text = key.text ?? (key.key === " " ? " " : undefined);
        if (key.key === "Enter") {
            if (tag === "button" || tag === "summary" || tag === "a" && target.hasAttribute("href") ||
                    tag === "input" && ["button", "submit", "reset", "image"].includes(target.type)) {
                if (this.keyboardEvent("keypress", key, target)) this.activate(target);
            }
            return;
        }
        if (key.key === "Tab") {
            this.tab(this.modifiers.has("Shift") ? -1 : 1);
            return;
        }
        if (this.editable(target)) {
            if (text !== undefined && !this.modifiers.has("Control") && !this.modifiers.has("Meta")) {
                if (this.keyboardEvent("keypress", key, target)) this.insert(target, text);
            } else if (key.key === "Backspace") {
                this.replace(target, target.value.slice(0, -1), "deleteContentBackward");
            }
            return;
        }
        if (text !== undefined) this.keyboardEvent("keypress", key, target);
    }

    up_key(key) {
        if (["Shift", "Control", "Alt", "Meta"].includes(key.key)) this.modifiers.delete(key.key);
        const target = this.active();
        const allowed = this.keyboardEvent("keyup", key, target);
        if (allowed && key.key === " ") {
            const tag = target.localName;
            if (tag === "button" || tag === "summary" ||
                    tag === "input" && ["button", "submit", "reset", "checkbox", "radio", "image"].includes(target.type)) {
                this.activate(target);
            }
        }
    }

    editable(target) {
        return target.localName === "textarea" || target.localName === "input" &&
            !["button", "submit", "reset", "checkbox", "radio", "image", "file", "range", "color"].includes(target.type);
    }

    insert(target, text) {
        this.replace(target, `${target.value ?? ""}${text}`, "insertText", text);
    }

    replace(target, value, inputType, data = null) {
        const window = this.window;
        if (!target.dispatchEvent(new window.InputEvent("beforeinput", {bubbles: true, cancelable: true, inputType, data}))) return;
        target.value = value;
        this.page.dirty.add(target);
        target.dispatchEvent(new window.InputEvent("input", {bubbles: true, inputType, data}));
    }

    fill(target, value) {
        if (target.isContentEditable || target.getAttribute?.("contenteditable") === "true") {
            this.focus(target);
            target.textContent = value;
            target.dispatchEvent(new this.window.InputEvent("input", {bubbles: true, inputType: "insertText", data: value}));
            return;
        }
        if (!this.editable(target) && target.localName !== "input") {
            throw new FakeError("error", `${NAME}: fill: the element is no <input>, <textarea> or [contenteditable] element.`);
        }
        this.focus(target);
        if (target.localName === "input" && ["checkbox", "radio", "file"].includes(target.type)) {
            throw new FakeError("error", `${NAME}: fill: an input of type ${target.type} cannot be filled.`);
        }
        this.replace(target, value, value ? "insertText" : "deleteContentBackward", value || null);
    }

    tab(direction) {
        const document = this.window.document;
        const candidates = [...document.querySelectorAll(FOCUSABLE)].filter((element) =>
            !element.disabled && element.getAttribute("tabindex") !== "-1" && visible(this.window, element));
        if (!candidates.length) return;
        const index = candidates.indexOf(document.activeElement);
        const next = candidates[(index + direction + candidates.length + (index < 0 && direction < 0 ? 1 : 0)) % candidates.length];
        this.focus(next);
    }
}

// ---- Assertions: the retried checks of the facade's expect().

function assertion(page, request) {
    const window = page.window;
    const {name, expected} = request;
    const single = () => {
        const found = resolve(page, request.chain, undefined);
        if (found.length > 1) return {error: strict(request.chain, found.length)};
        return {element: found[0], count: found.length};
    };
    const textOf = (element) => request.useInnerText ? element.innerText : element.textContent;
    const same = (actual, wanted, partial) => {
        if (wanted && typeof wanted === "object") return regex(wanted).test(partial ? actual : actual);
        const want = normalize(wanted);
        const have = normalize(actual);
        if (request.ignoreCase) return partial ? have.toLowerCase().includes(want.toLowerCase()) : have.toLowerCase() === want.toLowerCase();
        return partial ? have.includes(want) : have === want;
    };
    const many = (values, partial) => {
        const found = resolve(page, request.chain, undefined);
        const actual = found.map(values);
        const pass = Array.isArray(expected) && actual.length === expected.length &&
            actual.every((value, index) => same(value, expected[index], partial));
        return {pass, actual};
    };
    switch (name) {
        case "to_have_text":
        case "to_contain_text":
            if (Array.isArray(expected)) return many((element) => textOf(element), name === "to_contain_text");
            {
                const {element, error} = single();
                if (error) return {error};
                if (!element) return {pass: false, actual: null};
                const actual = textOf(element);
                return {pass: same(actual, expected, name === "to_contain_text"), actual};
            }
        case "to_have_count": {
            const actual = resolve(page, request.chain, undefined).length;
            return {pass: actual === expected, actual};
        }
        case "to_have_class":
            if (Array.isArray(expected)) return many((element) => element.getAttribute("class") || "", false);
            {
                const {element, error} = single();
                if (error) return {error};
                if (!element) return {pass: false, actual: null};
                const actual = element.getAttribute("class") || "";
                return {pass: expected && typeof expected === "object" ? regex(expected).test(actual) : actual === expected, actual};
            }
        case "to_have_attribute": {
            const {element, error} = single();
            if (error) return {error};
            if (!element) return {pass: false, actual: null};
            const actual = element.getAttribute(request.attribute);
            if (expected === undefined) return {pass: actual !== null, actual};
            return {pass: actual !== null && (expected && typeof expected === "object" ? regex(expected).test(actual) : actual === expected), actual};
        }
        case "to_have_value": {
            const {element, error} = single();
            if (error) return {error};
            if (!element) return {pass: false, actual: null};
            const actual = element.value;
            return {pass: expected && typeof expected === "object" ? regex(expected).test(actual) : actual === expected, actual};
        }
        case "to_have_id": {
            const {element, error} = single();
            if (error) return {error};
            return element ? {pass: element.id === expected, actual: element.id} : {pass: false, actual: null};
        }
        case "to_be_visible":
        case "to_be_hidden": {
            const {element, error} = single();
            if (error) return {error};
            const shown = Boolean(element) && visible(window, element);
            return {pass: name === "to_be_visible" ? shown : !shown, actual: shown ? "visible" : "hidden"};
        }
        case "to_be_attached": {
            const {element, error} = single();
            if (error) return {error};
            return {pass: Boolean(element), actual: element ? "attached" : "detached"};
        }
        case "to_be_checked": {
            const {element, error} = single();
            if (error) return {error};
            if (!element) return {pass: false, actual: null};
            const checked = element.checked ?? element.getAttribute("aria-checked") === "true";
            return {pass: checked === (expected ?? true), actual: checked};
        }
        case "to_be_enabled":
        case "to_be_disabled": {
            const {element, error} = single();
            if (error) return {error};
            if (!element) return {pass: false, actual: null};
            const on = enabled(element);
            return {pass: name === "to_be_enabled" ? on : !on, actual: on ? "enabled" : "disabled"};
        }
        case "to_be_focused": {
            const {element, error} = single();
            if (error) return {error};
            return {pass: Boolean(element) && window.document.activeElement === element, actual: window.document.activeElement?.localName};
        }
        case "to_have_url":
            return {pass: expected && typeof expected === "object" ? regex(expected).test(window.location.href) : window.location.href === expected,
                actual: window.location.href};
        case "to_have_title":
            return {pass: same(window.document.title, expected, false), actual: window.document.title};
        default:
            throw new FakeError("unsupported", `${NAME}: expect(...).${name} is not an assertion the fake browser has ` +
                `(${NOTE}, The fake browser).`);
    }
}

function strict(chain, count) {
    return `${NAME}: strict mode violation: ${describe(chain)} resolved to ${count} elements; an action and a single ` +
        "read need one element (narrow the locator, or take .first or .nth()).";
}

// ---- Requests.

const pages = new Map();
let current = null;

process.on("unhandledRejection", (reason) => {
    if (!current || !current.window) return;
    current.event({type: "pageerror", name: reason?.name || "Error",
        message: reason?.message !== undefined ? String(reason.message) : String(reason), stack: reason?.stack ? String(reason.stack) : ""});
});

function pageOf(request) {
    const page = pages.get(request.page);
    if (!page) throw new FakeError("error", `${NAME}: no page ${request.page}; it was closed or never opened.`);
    return page;
}

function opened(page) {
    if (!page.window) {
        throw new FakeError("error", `${NAME}: the page shows nothing yet; call goto first (${NOTE}, The fake browser).`);
    }
    return page.window;
}

// One element for an action or a single read: it waits, on the page's clock, for exactly one match
// that meets `condition`, as Playwright's actionability checks wait.
async function one(page, request, condition, what) {
    const window = opened(page);
    let problem = "matched no element";
    const found = await page.until(() => {
        const elements = resolve(page, request.chain, undefined);
        if (elements.length > 1) throw new FakeError("error", strict(request.chain, elements.length));
        if (!elements.length) {
            problem = "matched no element";
            return null;
        }
        const element = elements[0];
        const failed = condition ? condition(window, element) : "";
        if (failed) {
            problem = failed;
            return null;
        }
        return element;
    }, request.timeout);
    if (!found) {
        throw new FakeError("timeout", `${NAME}: ${what}: ${describe(request.chain)} ${problem} within ${request.timeout} ms ` +
            "of the page's clock, and the page had nothing left to run.");
    }
    return found;
}

const actionable = (window, element) => !visible(window, element) ? "is not visible" : !enabled(element) ? "is not enabled" : "";
const shown = (window, element) => !visible(window, element) ? "is not visible" : "";

const OPERATIONS = {
    // The page's download after the first `after` it made: its name, URL and bytes, base64.
    async wait_for_download(page, request) {
        const done = await page.until(() => {
            const entry = page.downloads[request.after];
            return entry && !entry.pending ? entry : null;
        }, request.timeout);
        if (!done) {
            throw new FakeError("timeout", `${NAME}: expect_download: the page downloaded nothing within ${request.timeout} ` +
                "ms of its clock, and had nothing left to run.");
        }
        if (done.error) throw new FakeError("error", `${NAME}: expect_download: ${done.error}.`);
        await page.between();
        return {filename: done.filename, url: done.url, data: done.bytes.toString("base64")};
    },
    async downloads(page) {
        return page.downloads.length;
    },
    async new_page(request) {
        const id = pages.size ? Math.max(...pages.keys()) + 1 : 1;
        pages.set(id, new FakePage(id, request));
        return id;
    },
    async goto(page, request) {
        await page.open(request.url, request.timeout);
        await page.between();
    },
    async close(page) {
        page.close();
        pages.delete(page.id);
    },
    async set_viewport_size(page, request) {
        page.viewport = request.viewport;
        if (page.window) {
            const url = page.window.location.href;
            await page.open(url, request.timeout);
            await page.between();
        }
    },
    async emulate_media(page, request) {
        Object.assign(page.media, request.media);
        if (page.browser) Object.assign(page.browser.settings.device, request.media);
        if (page.window) await page.between();
    },
    async evaluate(page, request) {
        const window = opened(page);
        let args = [pageValue(window, request.arg)];
        if (request.chain) {
            if (request.all) args = [resolve(page, request.chain, undefined), ...args];
            else args = [await one(page, request, null, "evaluate"), ...args];
        }
        const value = await evaluate(page, request.expression, args, request.timeout ?? 30000);
        await page.between();
        return serialized(value);
    },
    async wait_for_function(page, request) {
        const window = opened(page);
        const arg = pageValue(window, request.arg);
        let failure = null;
        const value = await page.until(async () => {
            try {
                return await evaluate(page, request.expression, [arg], request.timeout);
            } catch (error) {
                failure = error;
                return true;
            }
        }, request.timeout);
        if (failure) throw failure;
        if (!value) {
            throw new FakeError("timeout", `${NAME}: wait_for_function ${JSON.stringify(request.expression)} stayed false ` +
                `within ${request.timeout} ms of the page's clock, and the page had nothing left to run.`);
        }
        await page.between();
        return serialized(value);
    },
    async wait_for(page, request) {
        const window = opened(page);
        const state = request.state || "visible";
        const met = await page.until(() => {
            const elements = resolve(page, request.chain, undefined);
            if (request.strict !== false && elements.length > 1) throw new FakeError("error", strict(request.chain, elements.length));
            const element = elements[0];
            if (state === "attached") return Boolean(element);
            if (state === "detached") return !element;
            if (state === "visible") return Boolean(element) && visible(window, element);
            return !element || !visible(window, element);
        }, request.timeout);
        if (!met) {
            throw new FakeError("timeout", `${NAME}: wait_for: ${describe(request.chain)} was not ${state} within ` +
                `${request.timeout} ms of the page's clock, and the page had nothing left to run.`);
        }
        await page.between();
    },
    async count(page, request) {
        opened(page);
        return resolve(page, request.chain, undefined).length;
    },
    async read(page, request) {
        const window = opened(page);
        if (["is_visible", "is_hidden"].includes(request.what)) {
            const elements = resolve(page, request.chain, undefined);
            if (elements.length > 1) throw new FakeError("error", strict(request.chain, elements.length));
            const shownNow = Boolean(elements[0]) && visible(window, elements[0]);
            return request.what === "is_visible" ? shownNow : !shownNow;
        }
        const element = await one(page, request, null, request.what);
        switch (request.what) {
            case "text_content": return element.textContent;
            case "inner_text": return element.innerText;
            case "inner_html": return element.innerHTML;
            case "get_attribute": return element.getAttribute(request.name);
            case "input_value": return element.value ?? "";
            case "is_enabled": return enabled(element);
            case "is_disabled": return !enabled(element);
            case "is_checked": return Boolean(element.checked);
            case "bounding_box": {
                const rect = element.getBoundingClientRect();
                return rect.width || rect.height ? {x: rect.x, y: rect.y, width: rect.width, height: rect.height} : null;
            }
            default: throw new FakeError("unsupported", `${NAME}: ${request.what} is not a read the fake browser has (${NOTE}).`);
        }
    },
    async act(page, request) {
        opened(page);
        const input = new Input(page);
        const action = request.action;
        // Playwright's actionability checks: a pointer action and fill wait for a visible, enabled
        // element, hover for a visible one, the rest for an attached one.
        const condition = action === "hover" ? shown
            : ["press", "focus", "blur", "dispatch_event", "scroll_into_view_if_needed"].includes(action) ? null : actionable;
        const element = await one(page, request, condition, action);
        switch (action) {
            case "click":
            case "tap":
                for (const modifier of request.modifiers || []) input.modifiers.add(modifier);
                input.click(element, {button: {left: 0, middle: 1, right: 2}[request.button || "left"]}, request.clickCount || 1);
                break;
            case "dblclick": input.click(element, {}, 2); break;
            case "check":
            case "uncheck":
                if (Boolean(element.checked) !== (action === "check")) input.click(element);
                break;
            case "hover": input.hover(element); break;
            case "fill": input.fill(element, request.value); break;
            case "press":
                input.focus(element);
                input.press(request.key);
                break;
            case "focus": input.focus(element); break;
            case "blur": input.blur(element); break;
            case "dispatch_event": {
                const window = page.window;
                element.dispatchEvent(new window.Event(request.type, {bubbles: true, cancelable: true, composed: true}));
                break;
            }
            case "scroll_into_view_if_needed": element.scrollIntoView(); break;
            default: throw new FakeError("unsupported", `${NAME}: ${action} is not an action the fake browser has (${NOTE}).`);
        }
        await page.between();
    },
    async keyboard(page, request) {
        opened(page);
        const input = new Input(page);
        input.modifiers = page.modifiers || new Set();
        page.modifiers = input.modifiers;
        if (request.action === "press") input.press(request.key);
        else if (request.action === "down") input.down_key(keyOf(request.key));
        else if (request.action === "up") input.up_key(keyOf(request.key));
        else if (request.action === "type") for (const character of request.text) input.press(character === " " ? "Space" : character);
        else if (request.action === "insert_text") {
            const target = input.active();
            if (input.editable(target)) input.insert(target, request.text);
        }
        await page.between();
    },
    async mouse(page, request) {
        const window = opened(page);
        const input = new Input(page);
        const [x, y] = [request.x ?? page.mouseAt?.[0] ?? 0, request.y ?? page.mouseAt?.[1] ?? 0];
        page.mouseAt = [x, y];
        const target = window.document.elementFromPoint(x, y) || window.document.documentElement;
        const init = {clientX: x, clientY: y, button: {left: 0, middle: 1, right: 2}[request.button || "left"]};
        if (request.action === "move") input.hover(target, init);
        else if (request.action === "down") input.down(target, init);
        else if (request.action === "up") input.up(target, init);
        else if (request.action === "click") input.click(target, init, request.clickCount || 1);
        else if (request.action === "dblclick") input.click(target, init, 2);
        else if (request.action === "wheel") target.dispatchEvent(new window.WheelEvent("wheel", {bubbles: true, deltaX: request.deltaX, deltaY: request.deltaY}));
        await page.between();
    },
    async expect(page, request) {
        opened(page);
        let last = null;
        const met = await page.until(() => {
            last = assertion(page, request);
            if (last.error) throw new FakeError("error", last.error);
            return last.pass !== Boolean(request.negated);
        }, request.timeout);
        await page.between();
        return {pass: Boolean(met), actual: last ? serialized(last.actual) : null};
    },
    async state(page) {
        const window = page.window;
        return window ? {url: window.location.href, title: window.document.title,
            content: `<!DOCTYPE html>${window.document.documentElement.outerHTML}`} : {url: "about:blank", title: "", content: ""};
    },
    async defaults(page) {
        const listed = [...page.defaults.entries()].map(([answer, times]) => ({answer, times}));
        page.defaults.clear();
        return listed;
    },
    // The state's recording the page replays from its next open on, or null for the door's defaults.
    async replay(page, request) {
        page.recording = request.recording;
        page.reached = 0;
    },
    // The test begins a state's step: from now on the page answers from that step's recording.
    async reach(page, request) {
        page.reached = request.step;
    },
    // What the page asked since the last call, by step, expectation and key, each list sorted.
    async asked(page) {
        const listed = {};
        for (const [step, kinds] of page.asked) {
            listed[step] = Object.fromEntries(Object.entries(kinds).map(([kind, keys]) => [kind, [...keys].sort()]));
        }
        page.asked.clear();
        return listed;
    },
};

async function answer(request) {
    const operation = OPERATIONS[request.op];
    if (!operation) {
        throw new FakeError("unsupported", `${NAME}: ${request.op} is no request the fake browser serves (${NOTE}).`);
    }
    if (request.op === "new_page") return operation(request);
    const page = pageOf(request);
    current = page;
    usedScheme = schemeOf(page);
    return operation(page, request);
}

const lines = readline.createInterface({input: process.stdin});
let queue = Promise.resolve();
lines.on("line", (line) => {
    queue = queue.then(async () => {
        let request;
        try {
            request = JSON.parse(line);
        } catch (error) {
            process.stdout.write(JSON.stringify({id: 0, ok: false, error: {kind: "error", message: `${NAME}: a request was no JSON: ${error.message}`}}) + "\n");
            return;
        }
        let reply;
        try {
            reply = {id: request.id, ok: true, value: await answer(request)};
        } catch (error) {
            reply = {id: request.id, ok: false, error: {kind: error instanceof FakeError ? error.kind : "pageerror",
                name: error?.name || "Error", message: error?.message !== undefined ? String(error.message) : String(error),
                stack: error?.stack ? String(error.stack) : ""}};
        }
        const page = pages.get(request.page);
        reply.events = page ? page.events.splice(0) : [];
        process.stdout.write(JSON.stringify(reply) + "\n");
    });
});
lines.on("close", () => {
    for (const page of pages.values()) page.close();
    process.exit(0);
});
