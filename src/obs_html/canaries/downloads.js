// Canary of Downloads (features.py, downloads): the frame sandbox's allow-downloads, where visible. In
// Claude's artifact viewer (claude.use exists) the file offers save through the viewer's downloads
// capability, which only its answer decides, so the canary stays undecided and file-offers.js reports
// a page that has none (spec/capabilities/file-offers.md).
globalThis.obsCapabilities.canary({
    key: "downloads", feature: "Downloads",
    blocks: "downloads, so Download HTML, the source archive and attachments may not save",
    remedy: typeof globalThis.claude?.use === "function"
        ? "Publish the artifact declaring the downloads capability (capabilities: {downloads: true}), " +
            "or open the HTML file directly in a browser to download."
        : "Open the HTML file directly in a browser to download.",
    probe: ({sandboxAllows}) => (typeof globalThis.claude?.use === "function"
        ? {allowed: undefined, observation: "Claude's artifact viewer, whose downloads capability decides"}
        : sandboxAllows("allow-downloads")),
});
