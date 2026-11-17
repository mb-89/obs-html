(() => {
    // A Base's live source, its pure layer (generic-tables.md, Current data): paths, templates, the
    // mapping of one fetched item onto a row, the merge over the saved rows, the safe nodes of a new
    // row's text, a read's since and the check of a declaration against the build's rows. It uses no
    // page and no network, and no function returns HTML: fetched text is data. A row carries no
    // date: an item is compared with its saved row by value. Conditions are the page's one
    // evaluator's (obsQuery.compileConditions), over the mapped fields as a note's frontmatter.
    // Later pieces call these names; they stay stable.
    const LIMITS = Object.freeze({items: 2000, fieldBytes: 65536, pathSteps: 8});
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

    // One fetched item as a row: the request's set, then fields with the route's own paths and
    // lowercase, then exclude, derive and, for a new item, fillNew, its text and accept.
    const mapItem = (declaration, route, request, item, shownFor = () => undefined) => {
        if (!isObject(item)) return null;
        const fields = {};
        Object.entries(request.set || {}).forEach(([name, value]) => assign(fields, name, value));
        Object.entries(declaration.fields).forEach(([name, spec]) => {
            const path = route.fields?.[name] ?? (typeof spec === "string" ? spec : spec.path);
            let value = readPath(item, path);
            if (typeof spec === "object" && spec.lowercase) {
                value = Array.isArray(value) ? value.map(entry => typeof entry === "string" ? entry.toLowerCase() : entry)
                    : typeof value === "string" ? value.toLowerCase() : value;
            }
            assign(fields, name, value);
        });
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
                assign(fields, name, "value" in chosen ? chosen.value : readPath(item, chosen.path));
            }
        }
        let body;
        if (!shown) {
            Object.entries(declaration.fillNew || {}).forEach(([name, from]) => assign(fields, name, readPath(item, from)));
            if (declaration.bodyPath) {
                const text = readPath(item, declaration.bodyPath);
                if (typeof text === "string") body = lower(text);
            }
            if (declaration.accept && !matches(declaration.accept, fields)) return null;
        }
        return {path, fields, body};
    };

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
    const merge = (declaration, route, request, items, saved) => {
        let partial = !Array.isArray(items) || items.length > LIMITS.items;
        const latest = new Map();
        (Array.isArray(items) ? items.slice(0, LIMITS.items) : []).forEach(item => {
            const mapped = mapItem(declaration, route, request, item, path => saved.get(path));
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

    globalThis.obsLiveData = {LIMITS, readPath, fillTemplate, notePath, mapItem, lower, validateNodes, since, merge,
        check};
})();
