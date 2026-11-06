// Canary of Downloads (features.py, downloads): the frame sandbox's allow-downloads, where visible.
globalThis.obsCapabilities.canary({
    key: "downloads", feature: "Downloads",
    blocks: "downloads, so Download HTML, the source archive and attachments may not save",
    remedy: "Open the HTML file directly in a browser to download.",
    probe: ({sandboxAllows}) => sandboxAllows("allow-downloads"),
});
