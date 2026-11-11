// Attach source ZIP to PDF (features.py, the downloads feature's source-archive part): ships only in
// an artifact with an embedded source archive (source_archive.py). Settings' Attach source ZIP to PDF
// reads a PDF the reader saved from this HTML, attaches the archive with the PDF library, through its door (pdf-door.js), as the
// interim adapter does, and saves the result through the file offers (file-offers.js); Download source
// ZIP is artifact.js's.
(() => {
    const archive = document.getElementById("obs-source-archive");
    if (!archive) return;
    const filename = "obs-html-source.zip";
    const status = (message, failed = false) => {
        const target = document.querySelector("[data-export-status]");
        target.textContent = message;
        target.hidden = false;
        if (failed) console.error(message);
    };
    const bytes = () => globalThis.obsPayload ? globalThis.obsPayload.bytes() :
        Uint8Array.from(atob(archive.textContent.trim()), char => char.charCodeAt(0));
    // The PDF library's door (pdf-door.js) attaches the archive.
    const attach = async (source) => globalThis.obsPdf.attach(source, await bytes(), {
        filename, mimeType: "application/zip", description: "The vault's source files"});
    let busy = false;
    const picker = document.createElement("input");
    picker.type = "file";
    picker.accept = ".pdf,application/pdf";
    picker.hidden = true;
    picker.dataset.transientView = "";
    document.body.append(picker);
    document.addEventListener("click", (event) => {
        if (!event.target.closest?.("[data-source-attach]") || busy) return;
        event.preventDefault();
        picker.value = "";
        picker.click();
    });
    picker.addEventListener("change", async () => {
        const file = picker.files[0];
        if (!file || busy) return;
        busy = true;
        try {
            const result = await attach(await file.arrayBuffer());
            const {message} = await globalThis.obsFileOffers.save({
                filename: `${file.name.replace(/\.pdf$/i, "")}-with-source.pdf`,
                data: new Blob([result], {type: "application/pdf"})});
            status(message || "PDF with source ZIP downloaded.");
        } catch (error) {
            status(`Could not attach source ZIP: ${error.message}`, true);
        } finally {
            busy = false;
        }
    });
    globalThis.obsArchive = {attach};
})();
