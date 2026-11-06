---
kind: adapter-behavior
capability:
  id: answers
  summary: Hand a reader's answers from the page to the agent that asked, through a local server or a registered sink.
  authoring: Call obsArtifact.sendAnswers from the page; a trusted runtime bundle registers its own sink through the obsHtml.answers trusted extension.
  dependsOn: ["trusted-actions"]
  source: "[[answers#Contract]]"
---

# Answers

Reader: whoever asks a reader for answers in an obs-html artifact, writes a trusted runtime bundle
that saves them, or changes this extension.

The page hands one answers payload, a JSON object, to one sink with
`obsArtifact.sendAnswers(payload)`. The answers reach the agent that asked, wherever the artifact is
open: locally, `obs-html serve --wait` serves the artifact and exits with the payload
([[cli#Serving answers]]), and a host's own save path plugs in as a registered sink. obs names no
host application.

## Sinks

The first that applies takes the payload:

1. **A registered sink**: one a trusted runtime bundle registered (below). It takes the payload in
   place of the built-in sinks.
2. **The local server**: where `obs-html serve` served the page. The page posts the payload to its
   own URL, and the server writes `answers.json` beside the artifact.
3. **The text**: elsewhere, the notice center shows the payload as text with a Copy answers key,
   saying that sending is not available here.

The feature's canary (`canaries/answers.js`, registered as `answers` in `features.py`) decides
whether the local server is reachable: the URL `obs-html serve` prints carries its `obs-answers`
token over http. Elsewhere the canary stays silent and raises no warning, since a sink may still
be registered and the text always works.

## Contract

```js
const result = await obsArtifact.sendAnswers({verdicts: [{id: "one", verdict: "bless"}]});
// result: {sink: "host-save", result} | {sink: "server", written: "answers.json"} | {sink: "text"}
```

A trusted runtime bundle registers a sink once, after `obsArtifact.registerApplication`:

```js
obsArtifact.trustedExtension("obsHtml.answers").register({
    id: "host-save",                 // lowercase letters, digits and hyphens
    send: async payload => save(payload), // its result is the result's result
});
```

- Trust: the namespace and its trust rule are those of
  [[capabilities/attachment-replacement#Namespace and trust|attachment replacement]]; without a
  registered bundle `trustedExtension("obsHtml.answers")` throws and names
  `--trusted-runtime-bundle` as the remedy.
- One sink per page; a second registration throws, naming the first.
- Errors name where they come from and the remedy: `obsHtml.answers: <sink>: <what failed>.
  <remedy>.`, the sink being `obsArtifact.sendAnswers` for a payload that is no object, the
  server's address, or the registered sink's id. A failing sink also shows the payload as text,
  so no answer is lost, and `sendAnswers` rejects.

[`answers.js`](../../src/obs_html/answers.js) implements the sinks and the extension;
`test/test_answers_browser.py` tests them with `obs-html serve` and a test bundle.
