// Canary of Answers (features.py, answers): whether obs-html serve served this page (its URL carries the
// obs-answers parameter over http), so its local server is the sink (answers.js). Elsewhere it stays
// silent: a trusted bundle may register a sink later, and without one the payload is shown as text.
globalThis.obsCapabilities.canary({
    key: "answers", feature: "Answers",
    blocks: "sending answers, so they are shown as text to copy",
    remedy: "Open the URL obs-html serve prints to send answers to the waiting command.",
    probe({view}) {
        const {protocol, search, origin, pathname} = view.location;
        return /^https?:$/.test(protocol) && new URLSearchParams(search).get("obs-answers")
            ? {allowed: true, observation: `served by obs-html serve at ${origin}${pathname}`}
            : {allowed: undefined, observation: "not served by obs-html serve; a registered sink or the text applies"};
    },
});
