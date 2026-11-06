// Canary of Chapter addresses (features.py, history): replacing the address either works or throws.
globalThis.obsCapabilities.canary({
    key: "history", feature: "Chapter addresses",
    blocks: "address changes, so the address bar and browser Back do not follow chapters",
    remedy: "Open the HTML file directly in a browser to use chapter addresses and Back.",
    probe({view}) {
        const address = view.location.href;
        view.history.replaceState(view.history.state, "", "#obs-capability-canary");
        view.history.replaceState(view.history.state, "", address);
        return {allowed: true, observation: "history.replaceState changed the address"};
    },
});
