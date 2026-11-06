// Canary of Bless verdicts (features.py, bless): which verdicts were sent is kept in browser storage per
// chapter version (bless.js), so a sent verdict shows as sent after a reload; storing either works or throws.
globalThis.obsCapabilities.canary({
    key: "bless", feature: "Bless verdicts",
    blocks: "browser storage, so a sent verdict shows as unsent after a reload",
    remedy: "Open the HTML file directly in a browser to keep which verdicts were sent.",
    probe({view}) {
        const key = "obs-capability-canary-bless";
        view.localStorage.setItem(key, "1");
        view.localStorage.removeItem(key);
        return {allowed: true, observation: "localStorage.setItem stored a value"};
    },
});
