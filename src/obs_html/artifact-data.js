(() => {
    const inertType = "application/x-obs-html-script";
    const fail = (error) => {
        const message = document.createElement("p");
        message.id = "artifact-initialization-error";
        message.setAttribute("role", "alert");
        message.textContent = `HTML could not be opened: ${error.message}`;
        document.querySelector("[data-chapter-body]")?.replaceChildren(message);
        if (!message.isConnected || message.closest("[inert]")) document.body.prepend(message);
        document.documentElement.dataset.artifactStatus = "error";
    };
    const streamBytes = async (bytes, Stream) => {
        const source = new ReadableStream({
            start(controller) { controller.enqueue(bytes); controller.close(); },
        });
        return new Uint8Array(await new Response(source.pipeThrough(new Stream("gzip"))).arrayBuffer());
    };
    const escapeJson = (text) => text.replace(/</g, "\\u003c");
    const encode = async (serialized, compression) => {
        if (!["gzip", "none"].includes(compression)) throw new Error(`Saving: compression ${JSON.stringify(compression)} is neither gzip nor none; the HTML's save settings were edited. Rebuild it with obs-html or open the original file.`);
        const text = escapeJson(JSON.stringify(JSON.parse(serialized)));
        if (compression === "none") return {text, type: "application/json"};
        if (typeof CompressionStream === "undefined") throw new Error("Gzip HTML saving is not supported by this browser.");
        const raw = new TextEncoder().encode(text);
        const bytes = await streamBytes(raw, CompressionStream);
        let binary = "";
        for (let offset = 0; offset < bytes.length; offset += 32768) {
            binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
        }
        const encoded = btoa(binary);
        const overhead = "application/octet-stream".length - "application/json".length +
            ' data-encoding="gzip"'.length;
        return encoded.length + overhead < raw.length
            ? {text: encoded, type: "application/octet-stream", encoding: "gzip"}
            : {text, type: "application/json"};
    };
    const writeIsland = async (island, serialized) => {
        const encoded = await encode(serialized, island.dataset.compression || "none");
        island.textContent = encoded.text;
        island.type = encoded.type;
        if (encoded.encoding) island.dataset.encoding = encoded.encoding;
        else delete island.dataset.encoding;
    };
    const restoreScripts = (root) => root.querySelectorAll("script[data-obs-runtime]").forEach((script) => {
        script.type = inertType;
    });
    const work = [];
    let opening = true;
    // Startup work runs in slices: a step yields to the browser only once the slice has
    // run as long as a browser long task (50 ms), and then waits until a frame is painted.
    const sliceMilliseconds = 50;
    let sliceStart = performance.now();
    const paint = () => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))).then(() => {
        sliceStart = performance.now();
    });
    const yieldSlice = async () => {
        if (performance.now() - sliceStart >= sliceMilliseconds) await paint();
    };
    // Each startup step is a User Timing measure named "obs-startup <step>"; profilers and the
    // startup test read them with performance.getEntriesByType("measure").
    const step = async (name, run) => {
        const start = performance.now();
        try {
            return await run();
        } finally {
            performance.measure(`obs-startup ${name}`, {start});
        }
    };
    globalThis.obsStartup = Object.freeze({
        paint,
        yield: yieldSlice,
        defer(label, run) {
            if (opening) work.push({label, run});
            else yieldSlice().then(run).catch(fail);
        },
    });
    const parsed = document.readyState === "loading"
        ? new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve, {once: true}))
        : Promise.resolve();
    const decode = async () => {
        const island = document.querySelector("[data-artifact-data]");
        if (!island) throw new Error("The HTML's embedded data is missing; the file was cut off or edited. Rebuild it with obs-html or open the original file.");
        let text = island.textContent;
        if (island.dataset.encoding === "gzip") {
            if (island.type !== "application/octet-stream") throw new Error("The HTML's embedded data is marked gzip but not stored as binary; the file was edited. Rebuild it with obs-html or open the original file.");
            if (typeof DecompressionStream === "undefined") throw new Error("Gzip HTML opening is not supported by this browser.");
            const binary = atob(text.replace(/\s/g, ""));
            const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
            text = new TextDecoder("utf-8", {fatal: true}).decode(await streamBytes(bytes, DecompressionStream));
        } else if (island.dataset.encoding || island.type !== "application/json") {
            throw new Error("The HTML's embedded data has an encoding this HTML cannot read; the file was edited. Rebuild it with obs-html or open the original file.");
        }
        const data = JSON.parse(text);
        if (!data || typeof data !== "object" || Array.isArray(data) ||
                !Array.isArray(data.notes) || !Array.isArray(data.toc)) {
            throw new Error("The HTML's embedded data has no chapters or contents; the file was cut off or edited. Rebuild it with obs-html or open the original file.");
        }
        island.textContent = escapeJson(text);
        island.type = "application/json";
        delete island.dataset.encoding;
        return data;
    };
    const dataReady = parsed.then(async () => {
        document.documentElement.dataset.artifactStatus = "loading";
        document.querySelector(".app-shell")?.setAttribute("inert", "");
        document.querySelector("[data-menu-button]")?.setAttribute("disabled", "");
        await paint();
        return step("decode artifact data", decode);
    });
    globalThis.obsArtifactTransport = Object.freeze({encode, writeIsland, restoreScripts});
    globalThis.obsHtmlDataReady = dataReady;
    globalThis.obsHtmlReady = dataReady.then(async () => {
        for (const original of document.querySelectorAll(`script[type="${inertType}"]`)) {
            await yieldSlice();
            const start = performance.now();
            const script = document.createElement("script");
            for (const {name, value} of original.attributes) {
                if (name !== "type") script.setAttribute(name, value);
            }
            script.textContent = original.textContent;
            const loaded = script.src ? new Promise((resolve, reject) => {
                script.onload = resolve;
                // Optional network runtimes (CDN Plotly) degrade to their own notices.
                script.onerror = () => script.hasAttribute("data-optional-runtime")
                    ? resolve()
                    : reject(new Error(`Runtime could not be loaded: ${script.id}`));
            }) : null;
            let failure;
            const scriptError = (event) => { failure = event.error || new Error(event.message); };
            globalThis.addEventListener("error", scriptError);
            try {
                original.replaceWith(script);
            } finally {
                globalThis.removeEventListener("error", scriptError);
            }
            if (failure) throw failure;
            if (loaded) await loaded;
            performance.measure(`obs-startup start ${script.id || "script"}`, {start});
        }
        const selected = document.querySelector('meta[name="obs-trusted-runtime"]')?.content || "";
        globalThis.obsArtifact?.validateApplicationRuntime?.(selected);
        document.querySelector(".app-shell")?.removeAttribute("inert");
        document.querySelector("[data-menu-button]")?.removeAttribute("disabled");
        document.dispatchEvent(new CustomEvent("obs-html-interactive"));
        for (const task of work) {
            await yieldSlice();
            await step(task.label, task.run);
        }
        opening = false;
        document.documentElement.dataset.artifactStatus = "ready";
        document.dispatchEvent(new CustomEvent("obs-html-ready"));
    });
    globalThis.obsHtmlReady.catch(fail);
})();
