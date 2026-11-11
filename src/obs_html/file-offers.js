// File offers (features.py, downloads; spec/capabilities/file-offers.md): the one owner that hands the
// reader a file. Every file offer saves through save(); a link that offers a file (a[download]) is one
// of OFFERS too. In Claude's artifact viewer (claude.use exists) a save goes through the viewer's
// downloads capability; where the page has none, the offers are hidden and the downloads canary's
// warning says what to declare. Elsewhere a save is a browser download, as it always was.
(() => {
    const runtime = typeof globalThis.claude?.use === "function" ? globalThis.claude : null;
    // Every control that offers a file, and the card that holds only one.
    const OFFERS = ["a[download]", "[data-source-download]", 'a[href="obs-source:archive"]', ".source-archive-bar",
        "[data-source-attach]", "[data-artifact-download]", "[data-comment-save]"].join(", ");
    const UNAVAILABLE = new Set(["unavailable", "not_granted", "capability_disabled", "capability_removed"]);
    const REMEDY = "Open the HTML file directly in a browser to download it.";

    // The viewer's downloads namespace, or null where this view has none; asked once.
    const downloads = runtime
        ? Promise.resolve().then(() => runtime.use("downloads")).catch(() => null)
        : Promise.resolve(null);
    const hide = (observation) => {
        if (document.documentElement.dataset.fileOffers === "hidden") return;
        document.documentElement.dataset.fileOffers = "hidden";
        const style = document.createElement("style");
        style.id = "file-offers-hidden";
        style.textContent = `${OFFERS} { display: none !important; }`;
        document.head.append(style);
        globalThis.obsCapabilities?.fail("downloads", observation);
    };
    const ready = runtime ? downloads.then((namespace) => {
        if (!namespace) hide("the Claude app's viewer serves this page no downloads capability");
    }) : Promise.resolve();

    const refusal = (error, filename) => {
        const code = error?.code;
        if (code === "declined") return "The save was declined; nothing was saved.";
        if (code === "rate_limited") return "Another save is waiting for an answer; try again in a moment.";
        if (code === "rejected_extension" || code === "extension_not_enabled") {
            const extension = /\.([^.]+)$/.exec(filename)?.[1] || "this";
            return `The Claude app does not save .${extension} files. ${REMEDY}`;
        }
        if (code === "too_large") return `The file is too large for the Claude app to save. ${REMEDY}`;
        return `The Claude app could not save the file${code ? ` (${code})` : ""}. ${REMEDY}`;
    };

    // Hands the reader one file: {filename, data, type}, data a string, Blob or bytes. Resolves
    // {saved, message}: saved where the host took the file (a browser download is never confirmed),
    // message what to show beside the control, or "" where there is nothing to say.
    const save = async ({filename, data, type = "application/octet-stream"}) => {
        if (!runtime) {
            const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], {type}));
            const link = document.createElement("a");
            link.href = url;
            link.download = filename;
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            return {saved: true, message: globalThis.obsCapabilities?.explain("downloads") || ""};
        }
        const namespace = await downloads;
        await ready;
        if (!namespace) return {saved: false, message: globalThis.obsCapabilities?.explain("downloads") || ""};
        try {
            await namespace.save({filename, data});
            return {saved: true, message: "The Claude app took the file."};
        } catch (error) {
            if (UNAVAILABLE.has(error?.code)) hide(`the Claude app refused the save (${error.code})`);
            return {saved: false, message: refusal(error, filename)};
        }
    };

    // The bytes a file link names: a data: URL decoded, a blob: URL the payload made; no fetch, which
    // the viewer's policy may refuse.
    const linkData = (link) => {
        const href = link.getAttribute("href") || "";
        const inline = /^data:([^;,]*)(;base64)?,(.*)$/s.exec(href);
        if (inline) {
            const text = decodeURIComponent(inline[3]);
            return inline[2] ? Uint8Array.from(atob(text), (char) => char.charCodeAt(0)) : text;
        }
        if (href.startsWith("blob:")) return globalThis.obsPayload?.blobFor?.(href) || null;
        return null;
    };
    const filenameOf = (link) => link.getAttribute("download") ||
        decodeURIComponent((link.getAttribute("href") || "").split(/[?#]/)[0].split("/").pop() || "") || "file";

    // In the viewer a file link would do nothing, so its click saves through save().
    if (runtime) {
        document.addEventListener("click", async (event) => {
            const link = event.target.closest?.("a[download]");
            if (!link || (link.getAttribute("href") || "").startsWith("obs-asset:")) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            const filename = filenameOf(link);
            const data = linkData(link);
            const result = data === null
                ? {message: `The Claude app cannot save this link's file. ${REMEDY}`}
                : await save({filename, data});
            if (result.message && link.isConnected) globalThis.obsCapabilities?.note(link, result.message);
        }, true);
    }

    globalThis.obsFileOffers = Object.freeze({claude: Boolean(runtime), ready, save});
})();
