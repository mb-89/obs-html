// Canary of Dialogs (features.py, dialogs): the frame sandbox's allow-modals, where visible.
globalThis.obsCapabilities.canary({
    key: "dialogs", feature: "Dialogs",
    blocks: "browser dialogs, so messages appear in the page instead",
    remedy: "Open the HTML file directly in a browser for browser dialogs.",
    probe: ({sandboxAllows}) => sandboxAllows("allow-modals"),
});
