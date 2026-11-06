// Canary of Print to PDF (features.py, printing): the frame sandbox's allow-modals, where visible.
globalThis.obsCapabilities.canary({
    key: "printing", feature: "Print to PDF",
    blocks: "the print dialog",
    remedy: "Open the HTML file directly in a browser to print.",
    probe: ({sandboxAllows}) => sandboxAllows("allow-modals"),
});
