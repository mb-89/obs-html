(() => {
    const input = document.querySelector("[data-theme-select]");
    const root = document.documentElement;
    const apply = (value) => {
        input.value = value;
        root.dataset.theme = value;
        globalThis.obsAssets.replace(document.querySelector("[data-theme-icon]"), `theme.${value}`);
    };

    apply(JSON.parse(document.querySelector("[data-artifact-data]").textContent).reading.theme);
    input.addEventListener("change", () => apply(input.value));
    const headingNames = document.querySelector("[data-heading-names-toggle]");
    const applyHeadingNames = (shown) => {
        headingNames.checked = shown;
        root.classList.toggle("heading-names-hidden", !shown);
    };
    applyHeadingNames(true);
    headingNames.addEventListener("change", () => applyHeadingNames(headingNames.checked));
    document.querySelector("[data-pages-toggle]").addEventListener("change", (event) => {
        globalThis.obsPages.setPaged(event.target.checked);
    });
    document.querySelector("[data-export-pdf]").addEventListener("click", async () => {
        const message = document.querySelector("[data-export-status]");
        message.hidden = true;
        try {
            await globalThis.obsPages.exportPDF();
        } catch (error) {
            message.textContent = `PDF export failed: ${error.message}`;
            message.hidden = false;
            console.error(message.textContent);
        }
    });
})();
