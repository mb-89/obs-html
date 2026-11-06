// Canary of Saved settings (features.py, storage): storing a value either works or throws.
globalThis.obsCapabilities.canary({
    key: "storage", feature: "Saved settings",
    blocks: "browser storage, so reader settings are not kept",
    remedy: "Open the HTML file directly in a browser to keep reader settings.",
    probe({view}) {
        const key = "obs-capability-canary";
        view.localStorage.setItem(key, "1");
        view.localStorage.removeItem(key);
        return {allowed: true, observation: "localStorage.setItem stored a value"};
    },
});
