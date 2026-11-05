// Canaries: probe, before any feature runs, what the host lets this HTML do.
// One registry entry per browser capability; adding a capability is one entry.
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
    const registry = [
        {
            key: "history", feature: "Chapter addresses",
            blocks: "address changes, so the address bar and browser Back do not follow chapters",
            remedy: "Open the HTML file directly in a browser to use chapter addresses and Back.",
            probe() {
                const address = view.location.href;
                view.history.replaceState(view.history.state, "", "#obs-capability-canary");
                view.history.replaceState(view.history.state, "", address);
                return {allowed: true, observation: "history.replaceState changed the address"};
            },
        },
        {
            key: "storage", feature: "Saved settings",
            blocks: "browser storage, so reader settings are not kept",
            remedy: "Open the HTML file directly in a browser to keep reader settings.",
            probe() {
                const key = "obs-capability-canary";
                view.localStorage.setItem(key, "1");
                view.localStorage.removeItem(key);
                return {allowed: true, observation: "localStorage.setItem stored a value"};
            },
        },
        {
            key: "printing", feature: "Print to PDF",
            blocks: "the print dialog",
            remedy: "Open the HTML file directly in a browser to print.",
            probe: () => sandboxAllows("allow-modals"),
        },
        {
            key: "dialogs", feature: "Dialogs",
            blocks: "browser dialogs, so messages appear in the page instead",
            remedy: "Open the HTML file directly in a browser for browser dialogs.",
            probe: () => sandboxAllows("allow-modals"),
        },
        {
            key: "downloads", feature: "Downloads",
            blocks: "downloads, so Download HTML, the source archive and attachments may not save",
            remedy: "Open the HTML file directly in a browser to download.",
            probe: () => sandboxAllows("allow-downloads"),
        },
        {
            key: "clipboard", feature: "Clipboard",
            blocks: "clipboard access, so Copy comments cannot copy",
            remedy: "Open the HTML file directly in a browser to copy comments.",
            probe() {
                if (typeof view.navigator?.clipboard?.writeText !== "function") {
                    return {allowed: false, observation: "navigator.clipboard.writeText is missing"};
                }
                const policy = view.document.permissionsPolicy || view.document.featurePolicy;
                if (policy) {
                    const allowed = policy.allowsFeature("clipboard-write");
                    return {allowed, observation: `the permissions policy ${allowed ? "allows" : "denies"} clipboard-write`};
                }
                return view === view.top
                    ? {allowed: true, observation: "a top-level page with navigator.clipboard"}
                    : {allowed: undefined, observation: "a frame without a permissions policy API to ask"};
            },
        },
        {
            key: "popups", feature: "Separate windows",
            blocks: "new windows, so guided cards open inside the page",
            remedy: "Open the HTML file directly in a browser to open cards in their own window.",
            probe: () => sandboxAllows("allow-popups"),
        },
    ];
    // Every canary's result, allowed ones included; limits holds the ones that are not allowed.
    const results = Object.freeze(registry.map(({key, feature, blocks, remedy, probe}) => {
        let result;
        try {
            result = probe();
        } catch (error) {
            const message = String(error?.message || error).replace(/\.+$/, "");
            result = {allowed: false, observation: `it threw ${error?.name || "an error"}: ${message}`};
        }
        const {allowed, observation} = result;
        const reason = allowed === true ? ""
            : allowed === false
                ? `The page showing this HTML blocks ${blocks}.`
                : `The page showing this HTML may block ${blocks}; this HTML cannot check.`;
        return Object.freeze({key, feature, reason, remedy, observation, allowed: allowed === true,
            refused: allowed === false});
    }));
    const limits = results.filter((entry) => !entry.allowed);
    const limit = (key) => limits.find((entry) => entry.key === key) || null;
    globalThis.obsCapabilities = Object.freeze({
        results,
        limits: Object.freeze(limits),
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
    const warnings = [...limits, ...(island ? JSON.parse(island.textContent) : [])];
    if (!warnings.length) return;
    const mount = () => warnings.forEach((entry) => {
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
