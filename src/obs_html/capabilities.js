// Canaries: probe, before any feature runs, what the host lets this HTML do.
// Each feature of the registry (features.py) that the artifact includes brings its canary,
// canaries/<key>.js, which calls canary() with its name, what a host blocks, the remedy and a probe.
// A probe returns {allowed, observation}: allowed is true, false (refused) or undefined (unknown, which
// counts as limited); observation says what the canary saw, so an artifact can show why it is limited.
// A probe that throws is refused, and its error is what it observed.
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
    // Every canary's result, allowed ones included; limits holds the ones that are not allowed.
    const results = [];
    const canary = ({key, feature, blocks, remedy, probe}) => {
        let result;
        try {
            result = probe(helpers);
        } catch (error) {
            const message = String(error?.message || error).replace(/\.+$/, "");
            result = {allowed: false, observation: `it threw ${error?.name || "an error"}: ${message}`};
        }
        const {allowed, observation} = result;
        const reason = allowed === true ? ""
            : allowed === false
                ? `The page showing this HTML blocks ${blocks}.`
                : `The page showing this HTML may block ${blocks}; this HTML cannot check.`;
        results.push(Object.freeze({key, feature, reason, remedy, observation, allowed: allowed === true,
            refused: allowed === false}));
    };
    const limits = () => results.filter((entry) => !entry.allowed);
    const limit = (key) => limits().find((entry) => entry.key === key) || null;
    globalThis.obsCapabilities = Object.freeze({
        canary,
        get results() { return Object.freeze([...results]); },
        get limits() { return Object.freeze(limits()); },
        limit,
        // The message a degraded control shows inline when used, or "" where the feature is allowed.
        explain(key) {
            const entry = limit(key);
            return entry ? `${entry.feature} is limited here: ${entry.reason} ${entry.remedy}` : "";
        },
        // Shows a message inline right after the control that was used, in place of alert().
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

    // Each limit is a warning entry of the notice center: the feature, why, what the canary observed
    // (where its result records an observation) and the remedy. So is each limited function of the
    // Document that obs-html wrote into the page (document-limits), such as a node type shown as text.
    const island = view.document.getElementById("document-limits");
    const mount = () => [...limits(), ...(island ? JSON.parse(island.textContent) : [])].forEach((entry) => {
        const details = view.document.createElement("dl");
        details.dataset.capability = entry.key;
        [["Feature", entry.feature], ["Why", entry.reason], ["Observed", entry.observation],
            ["Remedy", entry.remedy]].filter(([, text]) => text).forEach(([term, text]) => {
            const name = view.document.createElement("dt");
            name.textContent = term;
            const value = view.document.createElement("dd");
            value.textContent = text;
            details.append(name, value);
        });
        globalThis.obsNotices.post({
            id: `capability-${entry.key}`, severity: "warning",
            title: `Limited functionality: ${entry.feature}`, details,
        });
    });
    // The startup loader announces this once every artifact script, artifact.js included, has run.
    view.document.addEventListener("obs-html-interactive", mount, {once: true});
})();
