// Canary of Separate windows (features.py, popups): the frame sandbox's allow-popups, where visible.
globalThis.obsCapabilities.canary({
    key: "popups", feature: "Separate windows",
    blocks: "new windows, so guided cards open inside the page",
    remedy: "Open the HTML file directly in a browser to open cards in their own window.",
    probe: ({sandboxAllows}) => sandboxAllows("allow-popups"),
});
