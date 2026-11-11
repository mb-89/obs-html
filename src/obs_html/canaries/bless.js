// Canary of Bless verdicts (features.py, bless): which verdicts were sent is kept in local storage and the
// unsent drafts in session storage, per chapter version (bless.js), so both outlast a reload; storing either
// works or throws.
globalThis.obsCapabilities.canary({
    key: "bless", feature: "Bless verdicts",
    blocks: "browser storage, so a sent verdict shows as unsent and an unsent comment is gone after a reload",
    remedy: "Open the HTML file directly in a browser to keep which verdicts were sent.",
    probe({view}) {
        const key = "obs-capability-canary-bless";
        view.localStorage.setItem(key, "1");
        view.localStorage.removeItem(key);
        view.sessionStorage.setItem(key, "1");
        view.sessionStorage.removeItem(key);
        return {allowed: true, observation: "localStorage.setItem and sessionStorage.setItem stored a value"};
    },
});
