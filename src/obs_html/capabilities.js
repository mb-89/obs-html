// Canaries: probe, before any feature runs, what the host lets this HTML do.
// Each feature of the registry (features.py) that the artifact includes brings its canary,
// canaries/<key>.js, which calls canary() with its name, what a host blocks, the remedy and a probe.
// A probe returns {allowed, observation}: allowed is true (works), false (refused) or undefined (the
// canary cannot decide); observation says what the canary saw. A probe that throws is refused, and its
// error is what it observed. A refusal is one warning; a canary that cannot decide raises nothing, and
// its feature is tried on use: a failure the feature observes then (fail()) is the refusal.
(() => {
    const view = globalThis.window || globalThis;
    // The sandbox tokens of every frame up to the top, intersected: null outside any sandbox,
    // undefined where a frame hides its permissions (a cross-origin or sandboxed host).
    const sandbox = (() => {
        let tokens = null;
        let current = view;
        while (current.top && current !== current.top) {
            const frame = current.frameElement;
            if (!frame) return undefined;
            if (frame.hasAttribute("sandbox")) {
                const own = frame.getAttribute("sandbox").toLowerCase().split(/\s+/).filter(Boolean);
                tokens = tokens ? new Set(own.filter((token) => tokens.has(token))) : new Set(own);
            }
            current = current.parent;
        }
        return tokens;
    })();
    const sandboxAllows = (token) => {
        if (sandbox === null) return {allowed: true, observation: "no sandboxed frame up to the top window"};
        if (sandbox === undefined) {
            return {allowed: undefined, observation: "an enclosing frame hides its sandbox flags (cross-origin host)"};
        }
        const flags = sandbox.size ? [...sandbox].join(" ") : "no flags";
        return sandbox.has(token)
            ? {allowed: true, observation: `the frame sandbox (${flags}) grants ${token}`}
            : {allowed: false, observation: `the frame sandbox (${flags}) lacks ${token}`};
    };
    const helpers = Object.freeze({view, sandboxAllows});
    // Every canary's result in registry order: allowed, refused, or neither where it could not decide.
    const results = [];
    const declared = new Map();
    const entry = (key, allowed, observation) => {
        const {feature, blocks, remedy} = declared.get(key);
        return Object.freeze({
            key, feature, remedy, observation, allowed: allowed === true, refused: allowed === false,
            decided: allowed !== undefined,
            reason: allowed === false ? `The page showing this HTML blocks ${blocks}.` : "",
        });
    };
    const canary = ({key, feature, blocks, remedy, probe}) => {
        let result;
        try {
            result = probe(helpers);
        } catch (error) {
            const message = String(error?.message || error).replace(/\.+$/, "");
            result = {allowed: false, observation: `it threw ${error?.name || "an error"}: ${message}`};
        }
        declared.set(key, {feature, blocks, remedy});
        results.push(entry(key, result.allowed, result.observation));
    };
    const find = (key) => results.find((item) => item.key === key) || null;
    const limits = () => results.filter((item) => item.refused);
    const limit = (key) => (find(key)?.refused ? find(key) : null);
    const explain = (key) => {
        const item = limit(key);
        return item ? `${item.feature} is limited here: ${item.reason} ${item.remedy}` : "";
    };

    // Each refusal is a warning entry of the notice center: the feature, why, what was observed and the
    // remedy. So is each limited function of the Document that obs-html wrote into the page
    // (document-limits), such as a node type shown as text.
    const island = view.document.getElementById("document-limits");
    let mounted = false;
    const warn = (item) => {
        const details = view.document.createElement("dl");
        details.dataset.capability = item.key;
        [["Feature", item.feature], ["Why", item.reason], ["Observed", item.observation],
            ["Remedy", item.remedy]].filter(([, text]) => text).forEach(([term, text]) => {
            const name = view.document.createElement("dt");
            name.textContent = term;
            const value = view.document.createElement("dd");
            value.textContent = text;
            details.append(name, value);
        });
        globalThis.obsNotices.post({
            id: `capability-${item.key}`, severity: "warning",
            title: `Limited functionality: ${item.feature}`, details,
        });
    };
    globalThis.obsCapabilities = Object.freeze({
        canary,
        get results() { return Object.freeze([...results]); },
        get limits() { return Object.freeze(limits()); },
        limit,
        // Whether the feature's canary could not decide, so the feature is tried on use.
        undecided: (key) => find(key)?.decided === false,
        // The message a refused feature's control shows inline when used, or "" where it is not refused.
        explain,
        // Help text for a control whose failure cannot be observed where the canary could not decide.
        hint(key) {
            const item = find(key);
            return item?.decided === false ? `If this does not work here: ${item.remedy}` : "";
        },
        // A failure a feature observed on use where its canary could not decide: from now on the feature is
        // refused, with what was observed, and raises its one warning. Returns the inline explanation, or ""
        // where the canary found the feature allowed (the failure has another cause, which the caller says).
        fail(key, observation) {
            const index = results.findIndex((item) => item.key === key);
            if (index < 0) throw new Error(`obsCapabilities.fail(${key}): no canary of that feature is in this HTML.`);
            if (results[index].decided) return explain(key);
            results[index] = entry(key, false, observation);
            if (mounted) warn(results[index]);
            return explain(key);
        },
        // Shows a message inline right after the control that was used; no feature uses a browser dialog.
        note(control, message) {
            let note = control.nextElementSibling;
            if (!note?.hasAttribute("data-capability-message")) {
                note = view.document.createElement("span");
                note.className = "capability-message";
                note.dataset.capabilityMessage = "";
                note.dataset.transientView = "";
                note.setAttribute("role", "status");
                control.after(note);
            }
            note.textContent = message;
        },
    });

    // The startup loader announces this once every artifact script, artifact.js included, has run.
    view.document.addEventListener("obs-html-interactive", () => {
        mounted = true;
        [...limits(), ...(island ? JSON.parse(island.textContent) : [])].forEach(warn);
    }, {once: true});
})();
