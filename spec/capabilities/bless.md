---
kind: adapter-behavior
capability:
  id: bless
  summary: Let the reader of a chapter that asks for a bless bless, decline, ask or pick another option, and send the verdicts at once.
  authoring: Ask with obs.bless pending in a chapter note (obs input-model, Bless requests); the reader's keys and Send need nothing more.
  dependsOn: ["answers"]
  source: "[[bless#Contract]]"
---

# Bless verdicts

Reader: whoever builds a deck of chapters that ask for a bless, reads the answers it sends, or
changes this feature.

The feature `bless` (`features.py`) ships only in an artifact whose Document has a chapter that
asks for a bless, and so does the answer sink, the feature `answers` ([[capabilities/answers]]).
[[artifact-ui#Bless verdicts]] owns what the reader sees; this note owns what Send hands over.

## Contract

Send hands `obsArtifact.sendAnswers` one payload: obs's answers file, whose fields
`src/obs/answers.schema.json` of the core owns once (obs input-model, Answers). The adapter
writes it and `obs-document --answers` reads it back, so the answered artifact is the record:

```js
{verdicts: [{chapter: "record", version: "<sha256>", verdict: "pick", comment: "B reads better.",
  pick: {figure: "record--figure-1", option: "B"},
  figures: {"record--figure-1": {weights: {places: 1}, marks: {}, rulings: {}, winner: "B"}}}]}
```

- One verdict per asking chapter whose verdict is complete; `version` is the chapter's.
- `figures` holds, by figure anchor, what `obsPugh.readerState()` gives for the chapter's
  decision figures the reader changed: weights, marks, rulings with their tripwires, and the
  winner they give ([[artifact-ui#Decision figures]]).
- `bless.js` keeps which verdicts were sent in browser storage, per chapter and version; the
  feature's canary (`canaries/bless.js`) reports a host that refuses it, where a sent verdict
  shows as unsent after a reload.

[`bless.js`](../../src/obs_html/bless.js) implements the keys and Send,
[`bless_record.py`](../../src/obs_html/bless_record.py) the read-only answer;
`test/test_bless_browser.py` tests them on the example deck of obs's spec.
