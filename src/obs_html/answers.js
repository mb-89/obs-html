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

    // Pure: whether a sink's name is plain text for the reader, 1 to 40 characters with no control
    // character and no space at either end (answers.md, Contract: Name).
    const readerName = name => typeof name === "string" && name.length >= 1 && name.length <= 40 &&
        name.trim() === name && !/[\u0000-\u001f\u007f-\u009f]/.test(name);

    // Pure: the answers entry's first detail where nothing was sent, in the reader's words (answers.md,
    // Contract): where a sink failed, where the answers did not get to, by the sink's name where it gave
    // one and else this page; where sending is not available, the remedy alone, as the title says the rest.
    const unsent = ({failed, name}) => !failed ? "Copy the answers and hand them over." : name
        ? `They did not reach ${name}. Copy the answers and give them to ${name}.`
        : "They could not be sent from this page. Copy the answers and hand them over.";

    const create = ({trusted}) => {
        if (typeof trusted !== "function") throw new TypeError(`Trusted extension ${namespace} needs the trust owner.`);
        if (!trusted()) {
            throw new Error(`Trusted extension ${namespace}: this HTML has no registered trusted runtime bundle; ` +
                "build it with --trusted-runtime-bundle ID=PATH and call the extension from that bundle.");
        }
        return Object.freeze({
            register({id, send, name} = {}) {
                if (typeof id !== "string" || !/^[a-z][a-z0-9-]{0,63}$/.test(id) || typeof send !== "function") {
                    throw new Error(`Trusted extension ${namespace}: register takes {id, send}, id of lowercase ` +
                        "letters, digits and hyphens and send(payload) a function; correct the bundle's call.");
                }
                if (name !== undefined && !readerName(name)) {
                    throw new Error(`Trusted extension ${namespace}: register: name is ${JSON.stringify(name)}, not ` +
                        "plain text of 1 to 40 characters for the reader; give a short name such as \"Claude\", " +
                        "or leave it out, and correct the bundle's call.");
                }
                if (registered) {
                    throw new Error(`Trusted extension ${namespace}: sink ${registered.id} is registered already; ` +
                        "a page has one sink, so register it once.");
                }
                registered = Object.freeze({id, send, ...(name === undefined ? {} : {name})});
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

    // The last sink: the payload as text with a copy key, saying that sending is not available here, or,
    // where a sink failed, that the answers were not sent; the failure's message is the console's.
    const showText = (text, failed = false, name = undefined) => {
        const notices = root.obsNotices;
        notices.post({
            id: "answers", severity: failed ? "error" : "information",
            title: failed ? "Answers were not sent" : "Answers: sending is not available here",
            details: [unsent({failed, name}), ...copyable(text)],
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
    // the local server, else the text. A failing sink writes its message to the console once, shows the
    // payload as text too and rejects with that message.
    const send = async payload => {
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
            throw failure("obsArtifact.sendAnswers", "the payload is not a JSON object", "Pass the answers as one object");
        }
        const text = JSON.stringify(payload, null, 2);
        const address = server();
        if (!registered && !address) return showText(text);
        const name = registered?.name;
        try {
            if (registered) {
                const sink = registered;
                try {
                    const result = await sink.send(structuredClone(payload));
                    return {sink: sink.id, ...(sink.name ? {name: sink.name} : {}), result};
                } catch (error) {
                    throw failure(`registered sink ${sink.id}`, `send failed (${error?.message || error})`,
                        "Fix the trusted bundle's sink, or copy the answers shown");
                }
            }
            return await post(address, text);
        } catch (error) {
            console.warn(error?.message || error);
            showText(text, true, name);
            throw error;
        }
    };

    return Object.freeze({namespace, create, send, server, readerName, unsent});
});
