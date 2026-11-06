// Attachment downloads of the evidence edition (features.py, downloads; render.py, _download).
// A blocked download cannot be observed, so where the canary could not decide, the help names the
// remedy; where it decided the host blocks downloads, a click also says why beside the control.
(() => {
    const help = (event) => {
        const control = event.target.closest?.("[data-attachment-download]");
        const hint = control && globalThis.obsCapabilities?.hint("downloads");
        if (hint) control.dataset.hoverHelp = hint;
    };
    // Capture runs before the hover card resolves its trigger, so the help is there when it does.
    document.addEventListener("pointerover", help, true);
    document.addEventListener("focusin", help, true);
    document.addEventListener("click", (event) => {
        const control = event.target.closest?.("[data-attachment-download]");
        const limited = control && globalThis.obsCapabilities?.explain("downloads");
        if (limited) globalThis.obsCapabilities.note(control, limited);
    });
})();
