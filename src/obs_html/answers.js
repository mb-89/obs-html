((root, factory) => {
    const api = factory(root);
    if (typeof module === "object" && module.exports) module.exports = api;
    root.ObsHtmlAnswers = api;
    (root.obsHtmlTrustedExtensions ||= []).push(api);
})(typeof globalThis === "undefined" ? this : globalThis, root => {
    "use strict";

    // The answers feature (features.py, answers): the page hands one answers payload to a sink, and the
    // trusted extension obsHtml.answers lets a trusted runtime bundle register a sink of its own.
    // spec/capabilities/answers.md owns the contract; the local server is obs-html serve (serve.py).
    const namespace = "obsHtml.answers";
    const failure = (sink, message, remedy) => new Error(`${namespace}: ${sink}: ${message}. ${remedy}.`);
    let registered = null;

    // The local server's address, the page's own, where the canary found that obs-html serve served it
    // (canaries/answers.js owns that decision).
    const server = () => {
        const served = root.obsCapabilities?.results.find(item => item.key === "answers")?.allowed;
        const location = root.location;
        return served ? `${location.origin}${location.pathname}${location.search}` : null;
    };

    const create = ({trusted}) => {
        if (typeof trusted !== "function") throw new TypeError(`Trusted extension ${namespace} needs the trust owner.`);
        if (!trusted()) {
            throw new Error(`Trusted extension ${namespace}: this HTML has no registered trusted runtime bundle; ` +
                "build it with --trusted-runtime-bundle ID=PATH and call the extension from that bundle.");
        }
        return Object.freeze({
            register({id, send} = {}) {
                if (typeof id !== "string" || !/^[a-z][a-z0-9-]{0,63}$/.test(id) || typeof send !== "function") {
                    throw new Error(`Trusted extension ${namespace}: register takes {id, send}, id of lowercase ` +
                        "letters, digits and hyphens and send(payload) a function; correct the bundle's call.");
                }
                if (registered) {
                    throw new Error(`Trusted extension ${namespace}: sink ${registered.id} is registered already; ` +
                        "a page has one sink, so register it once.");
                }
                registered = Object.freeze({id, send});
            },
        });
    };

    const copyable = text => {
        const document = root.document;
        const block = document.createElement("pre");
        block.dataset.answersText = "";
        block.textContent = text;
        const copy = document.createElement("button");
        copy.type = "button";
        copy.dataset.answersCopy = "";
        copy.textContent = "Copy answers";
        copy.addEventListener("click", async () => {
            const capabilities = root.obsCapabilities;
            if (capabilities?.limit("clipboard")?.refused) {
                capabilities.note(copy, `Answers were not copied. ${capabilities.explain("clipboard")}`);
                return;
            }
            try {
                await root.navigator.clipboard.writeText(text);
                capabilities?.note(copy, "Answers copied to clipboard.");
            } catch (error) {
                const reason = capabilities?.fail("clipboard", `navigator.clipboard.writeText rejected: ${error?.message || error}`);
                capabilities?.note(copy, `Answers were not copied: ${error?.message || error}${reason ? ` ${reason}` : ""} ` +
                    "Select the text and copy it.");
            }
        });
        return [block, copy];
    };

    // The last sink: the payload as text with a copy key, saying that sending is not available here.
    const showText = (text, error) => {
        const notices = root.obsNotices;
        notices.post({
            id: "answers", severity: error ? "error" : "information",
            title: error ? "Answers were not sent" : "Answers: sending is not available here",
            details: [error ? error.message : "Sending is not available here: this page was not opened through " +
                "obs-html serve and no trusted bundle registered a sink. Copy the answers and hand them over.",
            ...copyable(text)],
        });
        notices.reveal("answers");
        return {sink: "text"};
    };

    const post = async (address, text) => {
        const source = `obs-html serve at ${address.split("?")[0]}`;
        let response;
        try {
            response = await root.fetch(address, {method: "POST", headers: {"Content-Type": "application/json"}, body: text});
        } catch (error) {
            throw failure(source, `the server cannot be reached (${error?.message || error})`,
                "Start obs-html serve on the artifact again and open the URL it prints");
        }
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw failure(source, `refused the answers with HTTP ${response.status}: ${body.error || response.statusText}`,
                "Correct the answers, or open the URL obs-html serve prints");
        }
        return {sink: "server", written: body.written};
    };

    // Hand one answers payload, a JSON object, to the first sink that applies: a registered sink, else
    // the local server, else the text. A failing sink shows the payload as text too and rejects.
    const send = async payload => {
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
            throw failure("obsArtifact.sendAnswers", "the payload is not a JSON object", "Pass the answers as one object");
        }
        const text = JSON.stringify(payload, null, 2);
        const address = server();
        try {
            if (registered) {
                const sink = registered;
                try {
                    return {sink: sink.id, result: await sink.send(structuredClone(payload))};
                } catch (error) {
                    throw failure(`registered sink ${sink.id}`, `send failed (${error?.message || error})`,
                        "Fix the trusted bundle's sink, or copy the answers shown");
                }
            }
            return address ? await post(address, text) : showText(text);
        } catch (error) {
            showText(text, error);
            throw error;
        }
    };

    return Object.freeze({namespace, create, send, server});
});
