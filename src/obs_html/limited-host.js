// The limited-host banner (spec/architecture.md, Limited-host banner): where the page showing this HTML
// lacks what the page declared it needs (artifact.limitedHostNeeds), one plain line says what does not
// work and where to open it instead. It ships only where a need is declared. The banner's HTML holds
// the line for missing scripts (limited-host.json, noScripts), so where no script runs it stays; this
// script runs as the page is parsed, before the first paint, and words the line from what it finds
// (the table of each declared need the page carries, limited-host-needs) or hides it.
// Adapted from ctrl's src/ui/limited.js (MIT License, Copyright (c) 2026 mb-89).
(() => {
    // Pure: the declared needs the host lacks, in declared order. A fact that is not false is met.
    const missingNeeds = (needs, facts) => needs.filter((need) => facts[need] === false);

    // Pure: the banner's line for the missing needs, from the table of what each stops and where to
    // open the page instead (limited-host.json); "" where nothing is missing.
    const bannerText = (missing, table) => {
        if (!missing.length) return "";
        const what = missing.map((need) => table[need].missing).join("; ");
        const where = [...new Set(missing.map((need) => table[need].openInstead))].join(", or ");
        return `Limited viewer: ${what}. ${where}.`;
    };

    // Probes the host. Every probe is guarded: one that throws reads as a missing feature.
    const hostFacts = (view) => {
        const storage = (() => {
            try {
                const store = view.localStorage, key = "__obs-limited-host";
                store.setItem(key, "1");
                const kept = store.getItem(key) === "1";
                store.removeItem(key);
                return kept;
            } catch {
                return false;
            }
        })();
        let runtime = false;
        try {
            runtime = typeof view.claude?.use === "function";
        } catch { /* a host that hides it lacks it */ }
        // Scripts run: this script does.
        return {scripts: true, storage, "claude-runtime": runtime};
    };

    // The wiring: read the declared needs, probe, word or hide the banner.
    const mount = (view) => {
        const banner = view.document?.getElementById("limited-host");
        const island = view.document?.getElementById("limited-host-needs");
        if (!banner || !island) return [];
        const table = JSON.parse(island.textContent);
        const missing = missingNeeds(Object.keys(table), hostFacts(view));
        banner.textContent = bannerText(missing, table);
        banner.hidden = missing.length === 0;
        banner.dataset.limitedHostMissing = missing.join(" ");
        return missing;
    };

    const missing = mount(globalThis);
    globalThis.obsLimitedHost = Object.freeze({missingNeeds, bannerText, hostFacts, missing: Object.freeze(missing)});
})();
