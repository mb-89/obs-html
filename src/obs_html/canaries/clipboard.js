// Canary of Clipboard (features.py, clipboard): the permissions policy for clipboard-write.
globalThis.obsCapabilities.canary({
    key: "clipboard", feature: "Clipboard",
    blocks: "clipboard access, so Copy comments cannot copy",
    remedy: "Open the HTML file directly in a browser to copy comments.",
    probe({view}) {
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
});
