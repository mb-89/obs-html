(() => {
    // A Base's live source, its pure layer (generic-tables.md, Current data): paths, templates, the
    // mapping of one fetched item onto a row, the merge over the saved rows, the safe nodes of a new
    // row's text, a read's since and the check of a declaration against the build's rows. It uses no
    // page and no network, and no function returns HTML: fetched text is data. A row carries no
    // date: an item is compared with its saved row by value. Conditions are the page's one
    // evaluator's (obsQuery.compileConditions), over the mapped fields as a note's frontmatter.
    // Later pieces call these names; they stay stable.
    const LIMITS = Object.freeze({items: 2000, fieldBytes: 65536, pathSteps: 8, answerBytes: 8 * 1024 * 1024});
    const TEMPLATE = /\{([^{}]*)\}/g;
    const UNSAFE_NAMES = new Set(["__proto__", "constructor", "prototype"]);

    const isScalar = value => typeof value === "string" || typeof value === "number" || typeof value === "boolean";
    const isObject = value => value !== null && typeof value === "object" && !Array.isArray(value);

    // A path's steps: each key and each [] is one (generic-tables.md, Paths).
    const steps = path => path.split(".").map(part => part.endsWith("[]")
        ? {key: part.slice(0, -2), each: true} : {key: part, each: false});

    // The value at a path: own keys only; an object is absent, never a value; a list of scalars
    // stays a list; absent and null are undefined.
    const readPath = (value, path) => {
        const parts = steps(path);
        if (parts.reduce((count, part) => count + 1 + part.each, 0) > LIMITS.pathSteps) return undefined;
        const walk = (current, index) => {
            if (index === parts.length) return current;
            const {key, each} = parts[index];
            if (!isObject(current) || !Object.hasOwn(current, key)) return undefined;
            const next = current[key];
            if (!each) return walk(next, index + 1);
            if (!Array.isArray(next)) return undefined;
            return next.flatMap(item => {
                const found = walk(item, index + 1);
                return found === undefined ? [] : Array.isArray(found) ? found : [found];
            });
        };
        const found = walk(value, 0);
        if (Array.isArray(found)) {
            const scalars = found.filter(isScalar);
            return scalars;
        }
        return isScalar(found) ? found : undefined;
    };

    // A template filled from scalar values: {name} only; with url, each value URL-encoded.
    const fillTemplate = (template, values, {url = false} = {}) => {
        let missing = false;
        const filled = template.replace(TEMPLATE, (_, name) => {
            const value = Object.hasOwn(values, name) ? values[name] : undefined;
            if (!isScalar(value)) {
                missing = true;
                return "";
            }
            return url ? encodeURIComponent(String(value)) : String(value);
        });
        return missing ? undefined : filled;
    };

    // A row's field as conditions resolve it (obsBases.recordValue over its frontmatter).
    const rowValue = (row, field) => globalThis.obsBases.recordValue({frontmatter: row.frontmatter || {}}, field);
    const keyValues = (declaration, read) => Object.fromEntries(declaration.key.map(name => [name, read(name)]));
    const notePath = (declaration, fields) => fillTemplate(declaration.notePath, fields);
    const matches = (conditions, fields) => globalThis.obsQuery.compileConditions(conditions)
        .match({frontmatter: fields});
    // A target the build allows (live_source.py); the page refuses the rest too, so a fetched
    // name never reaches an object's prototype.
    const assign = (fields, name, value) => {
        if (UNSAFE_NAMES.has(name)) return;
        if (value === undefined) delete fields[name];
        else fields[name] = value;
    };

    // The values one fetched item gives the declaration, and nothing else of it: its note path and
    // its set, fields (with the route's own paths and lowercase), derive path, fillNew and bodyPath
    // values. It is what a web route keeps (generic-tables.md, The web route), so it holds no value
    // the declaration does not map.
    const extract = (declaration, route, request, item) => {
        if (!isObject(item)) return null;
        const set = {};
        Object.entries(request.set || {}).forEach(([name, value]) => assign(set, name, value));
        const fields = {};
        Object.entries(declaration.fields).forEach(([name, spec]) => {
            const path = route.fields?.[name] ?? (typeof spec === "string" ? spec : spec.path);
            let value = readPath(item, path);
            if (typeof spec === "object" && spec.lowercase) {
                value = Array.isArray(value) ? value.map(entry => typeof entry === "string" ? entry.toLowerCase() : entry)
                    : typeof value === "string" ? value.toLowerCase() : value;
            }
            assign(fields, name, value);
        });
        const derive = {};
        Object.values(declaration.derive || {}).flat().filter(entry => "path" in entry)
            .forEach(entry => assign(derive, entry.path, readPath(item, entry.path)));
        const fillNew = {};
        Object.entries(declaration.fillNew || {}).forEach(([name, from]) => assign(fillNew, name, readPath(item, from)));
        const text = declaration.bodyPath ? readPath(item, declaration.bodyPath) : undefined;
        const path = notePath(declaration, withoutUnset(declaration, set, fields));
        return {...(path === undefined ? {} : {path}), set, fields, derive, fillNew,
            ...(typeof text === "string" ? {body: text} : {})};
    };
    // The row's fields an item gives: the set values, then each mapped field, which an absent value
    // removes.
    const withoutUnset = (declaration, set, fields) => {
        const merged = {...set};
        Object.keys(declaration.fields).forEach(name => assign(merged, name, Object.hasOwn(fields, name) ? fields[name] : undefined));
        return merged;
    };
    const own = (values, name) => isObject(values) && Object.hasOwn(values, name) ? values[name] : undefined;

    // One extracted item as a row: then exclude, derive and, for a new item, fillNew, its text and accept.
    const mapExtracted = (declaration, extracted, shownFor = () => undefined) => {
        if (!isObject(extracted) || !isObject(extracted.set) || !isObject(extracted.fields)) return null;
        const fields = {};
        Object.entries(extracted.set).forEach(([name, value]) => assign(fields, name, value));
        Object.keys(declaration.fields).forEach(name => assign(fields, name, own(extracted.fields, name)));
        const path = notePath(declaration, fields);
        if (path === undefined) return null;
        if (declaration.exclude && matches(declaration.exclude, fields)) return null;
        const shown = shownFor(path);
        for (const [name, cases] of Object.entries(declaration.derive || {})) {
            const chosen = cases.find(entry => !entry.where || matches(entry.where, fields));
            if (!chosen || chosen.keep) {
                // No case matched: the value is unknown, so a shown row keeps its own.
                if (!chosen) {
                    if (shown) assign(fields, name, rowValue(shown, name));
                    continue;
                }
                if (!shown) return null;
                assign(fields, name, rowValue(shown, name));
            } else {
                assign(fields, name, "value" in chosen ? chosen.value : own(extracted.derive, chosen.path));
            }
        }
        let body;
        if (!shown) {
            Object.keys(declaration.fillNew || {}).forEach(name => assign(fields, name, own(extracted.fillNew, name)));
            if (declaration.bodyPath && typeof extracted.body === "string") body = lower(extracted.body);
            if (declaration.accept && !matches(declaration.accept, fields)) return null;
        }
        return {path, fields, body};
    };

    // One fetched item as a row: the request's set, then fields with the route's own paths and
    // lowercase, then exclude, derive and, for a new item, fillNew, its text and accept.
    const mapItem = (declaration, route, request, item, shownFor = () => undefined) =>
        mapExtracted(declaration, extract(declaration, route, request, item), shownFor);

    // Raw text as safe content nodes: a blank line starts a paragraph, a newline is a line break
    // and a bare https URL a link; every other character stays text, Markdown markers included.
    const URL = /https:\/\/[^\s<>"'`]+/g;
    const TRAILING = /[.,;:!?)\]]+$/;
    const inline = line => {
        const nodes = [];
        let last = 0;
        for (const match of line.matchAll(URL)) {
            const url = match[0].replace(TRAILING, "");
            if (match.index > last) nodes.push({type: "text", text: line.slice(last, match.index)});
            nodes.push({type: "link", label: url, url});
            last = match.index + url.length;
        }
        if (last < line.length) nodes.push({type: "text", text: line.slice(last)});
        return nodes;
    };
    const lower = text => validateNodes(String(text).replace(/\r\n?/g, "\n").split(/\n[ \t]*\n+/)
        .map(block => block.replace(/^\n+|\n+$/g, "")).filter(block => block.trim() !== "")
        .map(block => ({type: "paragraph", children: block.split("\n").flatMap((line, index) =>
            [...(index ? [{type: "lineBreak"}] : []), ...inline(line)])})));

    // The nodes when every one is of the safe subset renderSafeCanonicalContent (artifact.js)
    // accepts and a live row may carry: paragraph, text, lineBreak and an https link.
    const validateNodes = nodes => {
        const inlineNode = node => {
            if (!isObject(node)) return false;
            const keys = Object.keys(node).sort().join(",");
            if (node.type === "text") return keys === "text,type" && typeof node.text === "string";
            if (node.type === "lineBreak") return keys === "type";
            if (node.type === "link") {
                return keys === "label,type,url" && typeof node.label === "string" && typeof node.url === "string"
                    && /^https:\/\/[^\s<>"'`]+$/.test(node.url);
            }
            return false;
        };
        const valid = Array.isArray(nodes) && nodes.every(node => isObject(node) && node.type === "paragraph"
            && Object.keys(node).sort().join(",") === "children,type"
            && Array.isArray(node.children) && node.children.every(inlineNode));
        if (!valid) throw new TypeError("A live row's text holds a node outside paragraph, text, lineBreak and https link.");
        return nodes;
    };

    // The rows of a population that carry a request's set values.
    const carries = (request, row) => Object.entries(request.set || {}).every(([name, value]) => {
        const actual = rowValue(row, name);
        return actual !== undefined && actual !== null && String(actual) === String(value);
    });
    // A read's since, one for every request of the page: the page's generation timestamp minus
    // lookbackHours (default 1), in whole seconds, as YYYY-MM-DDTHH:MM:SSZ in UTC.
    const since = (declaration, generationTimestamp) => {
        const built = Date.parse(generationTimestamp);
        if (Number.isNaN(built)) return undefined;
        const start = Math.floor(built / 1000) * 1000 - (declaration.lookbackHours ?? 1) * 3600 * 1000;
        return new Date(start).toISOString().replace(/\.\d{3}Z$/, "Z");
    };

    const bytes = text => new TextEncoder().encode(text).length;
    const oversized = mapped => [...Object.values(mapped.fields).flat(), ...(mapped.body || []).flatMap(node =>
        node.children.map(child => child.text ?? child.url ?? ""))]
        .some(value => typeof value === "string" && bytes(value) > LIMITS.fieldBytes);
    // The targets an item is compared by: its request's set and the declaration's fields.
    const comparedTargets = (declaration, request) => [...new Set([...Object.keys(request.set || {}),
        ...Object.keys(declaration.fields)])].sort();
    // The targets an item sets on a row the build had: every one it maps, derives or sets.
    const liveTargets = (declaration, request) => new Set([...comparedTargets(declaration, request),
        ...Object.keys(declaration.derive || {})]);
    // Values as canonical JSON: keys sorted, a list in its order, a target that is absent, null or an
    // empty list left out, so the same values give the same text.
    const canonical = (targets, read) => JSON.stringify(Object.fromEntries(targets.flatMap(name => {
        const value = read(name);
        return value === undefined || value === null || (Array.isArray(value) && !value.length) ? [] : [[name, value]];
    })));

    // The rows one request's latest result changes, by note path, computed from the saved rows (a
    // Map of note path to {sourcePath, frontmatter}) and that result alone; nothing is stored. An
    // item whose compared values equal its saved row's changes nothing, so the saved row is shown as
    // built; one that differs is laid over it; one with no saved row is a new row. An item read more
    // than once keeps its last occurrence.
    const merge = (declaration, route, request, items, saved, {extracted = false} = {}) => {
        let partial = !Array.isArray(items) || items.length > LIMITS.items;
        const latest = new Map();
        (Array.isArray(items) ? items.slice(0, LIMITS.items) : []).forEach(item => {
            const mapped = extracted ? mapExtracted(declaration, item, path => saved.get(path))
                : mapItem(declaration, route, request, item, path => saved.get(path));
            if (!mapped) return;
            if (oversized(mapped)) {
                partial = true;
                return;
            }
            latest.delete(mapped.path);
            latest.set(mapped.path, mapped);
        });
        const targets = comparedTargets(declaration, request);
        const rows = new Map();
        latest.forEach(mapped => {
            const row = saved.get(mapped.path);
            if (row) {
                if (canonical(targets, name => mapped.fields[name]) === canonical(targets, name => rowValue(row, name))) return;
                const frontmatter = {...row.frontmatter};
                liveTargets(declaration, request).forEach(name => assign(frontmatter, name, mapped.fields[name]));
                rows.set(mapped.path, {sourcePath: mapped.path, frontmatter, added: false});
            } else {
                rows.set(mapped.path, {sourcePath: mapped.path, frontmatter: mapped.fields, added: true,
                    ...(mapped.body ? {body: mapped.body} : {})});
            }
        });
        return {rows, partial};
    };

    const nonblank = value => isScalar(value) && String(value).trim() !== "";
    // Whether a derive target's cases reproduce a row's own value: the first case that matches
    // gives it; a keep case, and a path case, which reads an item the row does not have, count.
    const reproduces = (cases, row, name) => {
        const chosen = cases.find(entry => !entry.where || matches(entry.where, row.frontmatter || {}));
        if (!chosen || chosen.keep || "path" in chosen) return true;
        const own = rowValue(row, name);
        return own !== undefined && own !== null && String(own) === String(chosen.value);
    };

    // The check of a declaration against the build's rows (generic-tables.md, The check): each
    // failure as {notePath, check, field}.
    const check = (declaration, population) => {
        const failures = [];
        const keys = new Map();
        population.forEach(row => {
            const fail = (checkName, field) => failures.push({notePath: row.sourcePath, check: checkName, field});
            const values = keyValues(declaration, name => rowValue(row, name));
            const blank = declaration.key.find(name => !nonblank(values[name]));
            if (blank !== undefined) {
                fail("key", blank);
            } else {
                const identity = JSON.stringify(declaration.key.map(name => String(values[name])));
                if (keys.has(identity)) fail("key", declaration.key.join(", "));
                keys.set(identity, row.sourcePath);
                if (notePath(declaration, values) !== row.sourcePath) fail("notePath", declaration.notePath);
            }
            Object.entries(declaration.derive || {}).forEach(([name, cases]) => {
                if (!reproduces(cases, row, name)) fail("derive", name);
            });
        });
        declaration.changes.forEach(route => route.requests.forEach(request => {
            if (!population.some(row => carries(request, row))) {
                Object.keys(request.set || {}).forEach(name => failures.push({notePath: "", check: "set", field: name}));
            }
        }));
        return failures;
    };

    // The texts a reader sees of a live table (generic-tables.md, Status line), in one frozen table:
    // no date or time in any of them, and no word for how the page is made. {name} is the source's
    // name as the declaration says it, {n} a count.
    const READER_TEXT = Object.freeze({
        current: "Showing current data",
        earlier: "Could not check for updates; showing the data read earlier",
        comments: "Showing the saved version while comments are open",
        unavailable: "newer updates cannot be shown here",
        notNow: "could not check for updates now",
        first: "showing the first {n} changes",
        off: "current data is turned off for this page",
        connect: "connect {name} in Claude to see current data",
        reauth: "sign in to {name} again in Claude",
        wait: "{name} asks to wait before the next check",
        show: "Show current data",
        refresh: "Check for updates",
        notice: "Newer updates from {name} cannot be shown on this page.",
    });
    const WARNINGS = new Set(["notNow", "connect", "reauth", "wait"]);
    // The line under a live table from the reader's view (reader().view()): its text, whether it
    // tells of a failure, the button's label (empty without one) and the refresh key.
    const statusLine = (view, name) => {
        const word = (key, n) => fillTemplate(READER_TEXT[key], {name, n: n ?? 0});
        const head = {current: READER_TEXT.current, earlier: READER_TEXT.earlier,
            comments: READER_TEXT.comments}[view.shown] || "";
        const parts = view.shown === "comments" ? [] : view.parts.map(part => word(part.key, part.n));
        const text = head ? [head, ...parts].join(" · ")
            : parts.length ? (line => line.charAt(0).toUpperCase() + line.slice(1))(parts.join(" · ")) : "";
        return {
            text,
            warning: view.shown === "earlier" || (view.shown !== "comments" && view.parts.some(part => WARNINGS.has(part.key))),
            button: view.button && view.shown !== "comments" ? READER_TEXT.show : "",
            refresh: {label: READER_TEXT.refresh, shown: view.refresh !== "hidden", disabled: view.refresh === "busy"},
        };
    };

    // Every target the declaration writes, whose columns its table always knows (generic-tables.md,
    // Projection, Known columns): each request's set, fields, derive and fillNew.
    const targetNames = declaration => [...new Set([
        ...declaration.changes.flatMap(route => route.requests.flatMap(request => Object.keys(request.set || {}))),
        ...Object.keys(declaration.fields), ...Object.keys(declaration.derive || {}),
        ...Object.keys(declaration.fillNew || {})])].sort();
    const ONE_TEMPLATE = /^\{([^{}]*)\}$/;
    // A connector request's input: each value that is one template alone takes the value as it is,
    // any other string is text with its templates filled, from the request's set and since.
    const requestInput = (request, sinceValue) => {
        const values = {...(request.set || {}), since: sinceValue};
        return Object.fromEntries(Object.entries(request.input || {}).flatMap(([name, value]) => {
            if (typeof value !== "string") return [[name, value]];
            const whole = ONE_TEMPLATE.exec(value);
            const filled = whole ? (Object.hasOwn(values, whole[1]) ? values[whole[1]] : undefined) : fillTemplate(value, values);
            return filled === undefined ? [] : [[name, filled]];
        }));
    };
    // The list at a result's dotted path, own keys only, or undefined.
    const readList = (value, path) => {
        const found = path.split(".").reduce((current, key) => isObject(current) && Object.hasOwn(current, key)
            ? current[key] : undefined, value);
        return Array.isArray(found) ? found : undefined;
    };

    // The pseudo-notes of one table key (generic-tables.md, Projection) from every request's latest
    // items, the saved rows by note path ({slug, sourcePath, frontmatter}) and the slugs new rows
    // were given before (a Map of note path to slug). A changed saved row keeps its slug, takes the
    // merged values and drops the built HTML of every target it maps, sets or derives; a new row
    // gets a slug no chapter can take, its path's file name as title and its lowered text.
    const project = (declaration, route, results, saved, tableKey, assigned) => {
        const slugs = new Map(assigned);
        const merged = new Map();
        let partial = false;
        results.forEach(({request, items, extracted}) => {
            const result = merge(declaration, route, request, items, saved, {extracted: extracted === true});
            partial ||= result.partial;
            result.rows.forEach((row, path) => merged.set(path, row));
        });
        const drop = [...new Set(results.flatMap(({request}) => [...liveTargets(declaration, request)]))].sort();
        const matched = [];
        const added = [];
        merged.forEach((row, path) => {
            if (!row.added) {
                matched.push({slug: saved.get(path).slug, frontmatter: row.frontmatter, drop});
                return;
            }
            if (!slugs.has(path)) slugs.set(path, `live~${tableKey}~${slugs.size + 1}`);
            added.push({slug: slugs.get(path), sourcePath: path, title: path.split("/").at(-1).replace(/\.md$/i, ""),
                frontmatter: row.frontmatter, body: row.body || []});
        });
        return {matched, added, partial, assigned: slugs};
    };

    // A live table's route in Claude's artifact viewer (generic-tables.md, Reading): mcp and
    // permissions are the viewer's namespaces (mcp null where this view cannot reach the source),
    // now and wait its clock and timer, notice posts the one notice, onChange tells of each change.
    // view() is the reader's state: what is shown, the line's parts, the button, the refresh key
    // and each request's latest items.
    const RESET = {needs_reauth: "reauth", server_not_connected: "connect", selection_required: "connect",
        server_not_found: "connect", blocked_by_policy: "unavailable"};
    const ABSENT = new Set(["not_granted", "capability_disabled", "capability_removed"]);
    const reader = ({declaration, route, since: sinceValue, mcp, permissions, now = Date.now,
        wait = ms => new Promise(resolve => setTimeout(resolve, ms)), notice = () => {}, onChange = () => {}}) => {
        const {server, tool} = route;
        const age = (declaration.refreshMinutes ?? 10) * 60 * 1000;
        const cache = {staleTime: age, gcTime: age};
        const requests = route.requests.map(request => ({request, input: requestInput(request, sinceValue),
            freshness: -Infinity, items: null, partial: false, token: 0, unsubscribe: null}));
        // consent: unknown, prompt, granted or closed (no key); issue: the line's own part.
        let consent = "unknown";
        let issue = null;
        let busy = false;
        let noticed = false;
        let waitUntil = -Infinity;
        const changed = () => onChange();
        const view = () => {
            const results = requests.filter(entry => entry.items).map(({request, items}) => ({request, items}));
            const read = results.length > 0;
            const parts = [];
            if (["unavailable", "off", "reauth", "connect", "wait"].includes(issue)) parts.push({key: issue});
            if (issue === "transient" && !read) parts.push({key: "notNow"});
            if (read && requests.some(entry => entry.items && entry.partial)) {
                parts.push({key: "first", n: results.reduce((count, result) => count + result.items.length, 0)});
            }
            return {shown: read ? (issue === "transient" ? "earlier" : "current") : "saved", parts,
                button: consent === "prompt", refresh: consent === "closed" || consent === "unknown" ? "hidden"
                    : busy ? "busy" : "enabled", results};
        };
        const unwatch = () => requests.forEach(entry => {
            entry.unsubscribe?.();
            entry.unsubscribe = null;
        });
        const drop = () => requests.forEach(entry => {
            entry.items = null;
            entry.partial = false;
            entry.freshness = -Infinity;
            entry.token += 1;
        });
        const close = part => {
            consent = "closed";
            issue = part;
            unwatch();
            drop();
            changed();
        };
        const consentState = async () => {
            try {
                return permissions ? await permissions.state(`mcp:${server}`) : "unavailable";
            } catch {
                return "unavailable";
            }
        };
        const fail = async error => {
            const code = error?.code;
            if (ABSENT.has(code)) return close("unavailable");
            if (code in RESET) {
                drop();
                issue = RESET[code];
                if (code === "blocked_by_policy" && !noticed) {
                    noticed = true;
                    notice(fillTemplate(READER_TEXT.notice, {name: declaration.name}));
                }
            } else if (code === "approval_required") {
                drop();
                issue = null;
                consent = "prompt";
            } else if (code === "not_in_manifest") {
                drop();
                if (await consentState() === "denied") return close("off");
                issue = "unavailable";
            } else if (code === "rate_limited" && Number.isFinite(error.retryAfterMs)) {
                issue = "wait";
                waitUntil = now() + error.retryAfterMs;
            } else issue = "transient";
            changed();
        };
        // One call, and for a retryable error one more after retryAfterMs.
        const call = async (input, options) => {
            try {
                return await mcp.callTool(server, tool, input, options);
            } catch (error) {
                if (error?.retryable !== true) throw error;
                await wait(Number.isFinite(error.retryAfterMs) ? error.retryAfterMs : 0);
                return mcp.callTool(server, tool, input, options);
            }
        };
        // A request's first page and the pages after it, one after another, up to maxPages.
        const accept = async (entry, result) => {
            const freshness = result?.cache?.storedAt ?? now();
            if (freshness < entry.freshness) return;
            const token = ++entry.token;
            const pages = [];
            let current = result;
            let more = false;
            try {
                for (;;) {
                    const items = readList(current?.payload, route.rows);
                    if (!items) throw {code: "upstream_error"};
                    pages.push(items);
                    more = Boolean(route.next) && readPath(current.payload, route.next.more) === true;
                    const cursor = more ? readPath(current.payload, route.next.cursor) : undefined;
                    if (!more || pages.length >= route.maxPages || !isScalar(cursor)) break;
                    current = await call({...entry.input, [route.next.input]: cursor}, {cache});
                    if (token !== entry.token) return;
                }
            } catch (error) {
                if (token === entry.token) await fail(error);
                return;
            }
            if (token !== entry.token || consent === "closed") return;
            entry.freshness = freshness;
            entry.items = pages.flat();
            entry.partial = more;
            if (issue !== "wait" || now() >= waitUntil) issue = null;
            changed();
        };
        const watch = () => requests.forEach(entry => {
            entry.unsubscribe?.();
            entry.unsubscribe = mcp.watchTool(server, tool, entry.input, event => {
                if (event?.type === "data") accept(entry, event.result);
                else if (event?.type === "error") fail(event.error);
            }, {cache});
        });
        // Whether the viewer reports the route's tool as a read; a tool that is not is never called again.
        const reads = async () => {
            try {
                const listed = await mcp.listTools(server);
                const info = listed?.servers?.find(entry => entry.server === server)?.tools?.find(entry => entry.name === tool);
                if (info?.annotations?.readOnlyHint === true) return true;
                close("unavailable");
            } catch (error) {
                await fail(error);
            }
            return false;
        };
        const start = async () => {
            if (!mcp) return close("unavailable");
            const state = await consentState();
            if (state === "granted") {
                if (!await reads()) return;
                consent = "granted";
                watch();
                changed();
            } else if (state === "prompt") {
                consent = "prompt";
                changed();
            } else close(state === "denied" ? "off" : "unavailable");
        };
        // The button's click: the first call with callTool, the one call that asks the viewer.
        const allow = async () => {
            if (consent !== "prompt" || busy) return;
            busy = true;
            changed();
            try {
                const [first, ...rest] = requests;
                const result = await mcp.callTool(server, tool, first.input, {cache});
                if (!await reads()) return;
                consent = "granted";
                await accept(first, result);
                await Promise.all(rest.map(entry => call(entry.input, {cache}).then(answer => accept(entry, answer))));
                watch();
            } catch (error) {
                await fail(error);
            } finally {
                busy = false;
                changed();
            }
        };
        // The refresh key: every request again at once, past refreshMinutes.
        const refresh = async () => {
            if (consent === "prompt") return allow();
            if (consent !== "granted" || busy || now() < waitUntil) return;
            busy = true;
            changed();
            try {
                await Promise.all(requests.map(entry => mcp.callTool(server, tool, entry.input,
                    {cache: {...cache, refresh: true}}).then(result => accept(entry, result), fail)));
            } finally {
                busy = false;
                changed();
            }
        };
        // The page shown again: past refreshMinutes, its watches are registered again.
        const resume = () => {
            if (consent !== "granted" || now() < waitUntil) return;
            const oldest = Math.min(...requests.map(entry => entry.freshness));
            if (now() - oldest > age) watch();
        };
        return {start, allow, refresh, resume, stop: unwatch, view};
    };

    // The web route (generic-tables.md, The web route). A request's URL: its url with since and the
    // request's set values filled in, each URL-encoded.
    const webUrl = (route, request, sinceValue) => fillTemplate(request.url, {...(request.set || {}), since: sinceValue},
        {url: true});
    // A Link header's rel="next" URL, resolved against the answer's URL: {url} on the declared URL's
    // origin, {foreign: true} on another, undefined where there is none.
    const LINK = /<([^>]*)>\s*((?:;\s*[^;,]*)*)/g;
    const nextLink = (header, current, declared) => {
        if (typeof header !== "string") return undefined;
        for (const [, target, params] of header.matchAll(LINK)) {
            const rel = /;\s*rel\s*=\s*(?:"([^"]*)"|([^;,\s]*))/i.exec(params);
            if (!rel || !(rel[1] ?? rel[2]).toLowerCase().split(/\s+/).includes("next")) continue;
            let url;
            try {
                url = new globalThis.URL(target, current);
            } catch {
                return {foreign: true};
            }
            return url.origin === new globalThis.URL(declared).origin ? {url: url.href} : {foreign: true};
        }
        return undefined;
    };
    // A refusal by its status and the headers the page can read (header(name) is null for one it
    // cannot): {key: "wait", until} for a rate limit with a time, {key: "unavailable"} for 401 and
    // 404, else {key: "notNow"}.
    const refusal = (status, header, now) => {
        if (status === 401 || status === 404) return {key: "unavailable"};
        if (status !== 403 && status !== 429) return {key: "notNow"};
        const reset = header("x-ratelimit-reset");
        if (header("x-ratelimit-remaining") === "0" && reset !== null && /^\d+$/.test(reset.trim())) {
            return {key: "wait", until: Number(reset.trim()) * 1000};
        }
        const after = header("retry-after");
        if (after !== null) {
            const text = after.trim();
            const until = /^\d+$/.test(text) ? now + Number(text) * 1000
                : /[A-Za-z]/.test(text) ? Date.parse(text) : NaN;
            if (Number.isFinite(until)) return {key: "wait", until};
        }
        return {key: "notNow"};
    };
    // An answer's list: with a JSON content type, the body parsed as data, its top-level array or the
    // array at the route's rows path; else undefined.
    const JSON_TYPE = /^\s*application\/(?:[A-Za-z0-9.!#$&^_-]+\+)?json\s*(?:;|$)/i;
    const answerList = (contentType, text, route) => {
        if (typeof contentType !== "string" || !JSON_TYPE.test(contentType) || typeof text !== "string") return undefined;
        let value;
        try {
            value = JSON.parse(text);
        } catch {
            return undefined;
        }
        if (route.rows) return readList(value, route.rows);
        return Array.isArray(value) ? value : undefined;
    };
    // A body's text, counted while it streams: past answerBytes the stream is cancelled and the
    // answer gives undefined.
    const readBody = async body => {
        if (!body || typeof body.getReader !== "function") return undefined;
        const reader = body.getReader();
        const decoder = new TextDecoder();
        let size = 0;
        let text = "";
        for (;;) {
            const {done, value} = await reader.read();
            if (done) return text + decoder.decode();
            size += value.byteLength;
            if (size > LIMITS.answerBytes) {
                await reader.cancel().catch(() => {});
                return undefined;
            }
            text += decoder.decode(value, {stream: true});
        }
    };
    // Canonical JSON: object keys sorted at every level, lists in their order.
    const canonicalJson = value => JSON.stringify(value, (_, entry) => isObject(entry)
        ? Object.fromEntries(Object.keys(entry).sort().map(name => [name, entry[name]])) : entry);
    // The kept result's storage key: the page's title and the declaration's canonical JSON. file:
    // pages can share one storage origin, so it does not rely on the origin, and no digest is
    // computed: crypto.subtle is missing on a plain http: page.
    const keptKey = (title, declaration) => `obs-live:${title}${canonicalJson(declaration)}`;

    // A live table's web route (generic-tables.md, The web route): fetch, storage ({get, set}, either
    // of which may throw), blocked (whether the page's policy refused an origin), now and notice
    // handed in; generated is the page's generation timestamp in milliseconds and key the kept
    // result's key. start() reads once; view() is the reader's state, as reader's view() is.
    const webReader = ({declaration, route, since: sinceValue, generated, key, fetch, storage = null,
        blocked = async () => false, now = Date.now, notice = () => {}, onChange = () => {}}) => {
        const age = (declaration.refreshMinutes ?? 10) * 60 * 1000;
        const urls = route.requests.map(request => webUrl(route, request, sinceValue));
        let results = null;
        let issue = null;
        let noticed = false;
        const load = () => {
            try {
                const entry = JSON.parse(storage?.get(key) ?? "null");
                if (!isObject(entry)) return null;
                const read = Number.isFinite(entry.read) ? entry.read : undefined;
                const kept = Array.isArray(entry.results) && entry.results.length === route.requests.length
                    && entry.results.every(result => isObject(result) && typeof result.partial === "boolean"
                        && Array.isArray(result.items)) ? entry.results : undefined;
                return {read: kept ? read : undefined, results: read === undefined ? undefined : kept,
                    wait: Number.isFinite(entry.wait) ? entry.wait : undefined};
            } catch {
                return null;
            }
        };
        const keep = entry => {
            try {
                storage?.set(key, JSON.stringify(entry));
            } catch {
                // Storage is optional: the page shows what it read and keeps nothing.
            }
        };
        const view = () => {
            const shown = (results || []).map((result, index) => ({request: route.requests[index], items: result.items,
                extracted: true}));
            const read = results !== null;
            const parts = [];
            if (issue === "unavailable" || issue === "wait") parts.push({key: issue});
            if (issue === "transient" && !read) parts.push({key: "notNow"});
            if (read && results.some(result => result.partial)) {
                parts.push({key: "first", n: results.reduce((count, result) => count + result.items.length, 0)});
            }
            return {shown: read ? (issue === "transient" ? "earlier" : "current") : "saved", parts, button: false,
                refresh: "hidden", results: shown};
        };
        // One request's pages, one after another; {items, partial} or {failure}.
        const readRequest = async (request, first) => {
            const items = [];
            let url = first;
            for (let pageCount = 1; ; pageCount += 1) {
                let response;
                try {
                    response = await fetch(url, {method: "GET", credentials: "omit", referrerPolicy: "no-referrer",
                        redirect: "error", mode: "cors", headers: {Accept: "application/json"}});
                } catch {
                    return {failure: await blocked(new globalThis.URL(url).origin) ? {key: "policy"} : {key: "notNow"}};
                }
                const header = name => {
                    try {
                        return response.headers.get(name);
                    } catch {
                        return null;
                    }
                };
                if (!response.ok) return {failure: refusal(response.status, header, now())};
                let list;
                try {
                    list = answerList(header("content-type"), await readBody(response.body), route);
                } catch {
                    list = undefined;
                }
                if (!list) return {failure: {key: "notNow"}};
                list.forEach(item => {
                    const extracted = extract(declaration, route, request, item);
                    if (extracted) items.push(extracted);
                });
                if (route.next !== "link") return {items, partial: false};
                const link = nextLink(header("link"), response.url || url, first);
                if (!link) return {items, partial: false};
                if (link.foreign || pageCount >= route.maxPages) return {items, partial: true};
                url = link.url;
            }
        };
        const start = async () => {
            const kept = load();
            if (kept?.results && kept.read > generated) results = kept.results;
            if (kept?.wait !== undefined && now() < kept.wait) {
                issue = "wait";
                onChange();
                return;
            }
            if (results && now() - kept.read < age) {
                onChange();
                return;
            }
            const read = [];
            for (const [index, request] of route.requests.entries()) {
                const url = urls[index];
                const outcome = url === undefined ? {failure: {key: "notNow"}} : await readRequest(request, url);
                if (outcome.failure) {
                    const {key: failure, until} = outcome.failure;
                    if (failure === "wait") {
                        issue = "wait";
                        keep({...(results ? {read: kept.read, results} : {}), wait: until});
                    } else if (failure === "notNow") {
                        issue = "transient";
                    } else {
                        results = null;
                        issue = "unavailable";
                        if (failure === "policy" && !noticed) {
                            noticed = true;
                            notice(fillTemplate(READER_TEXT.notice, {name: declaration.name}));
                        }
                    }
                    onChange();
                    return;
                }
                read.push({partial: outcome.partial, items: outcome.items});
            }
            results = read;
            issue = null;
            keep({read: now(), results});
            onChange();
        };
        return {start, view};
    };

    globalThis.obsLiveData = {LIMITS, readPath, fillTemplate, notePath, mapItem, lower, validateNodes, since, merge,
        check, READER_TEXT, statusLine, targetNames, requestInput, readList, project, reader, extract, webUrl, nextLink,
        refusal, answerList, readBody, keptKey, webReader};
})();
