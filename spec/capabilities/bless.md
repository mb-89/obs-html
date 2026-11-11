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
  figures: {"record--figure-1": {weights: {places: 1}, marks: {}, rulings: {}, winner: "B"}}},
  {chapter: "swipe", version: "<sha256>", comment: "Only a thought."}]}
```

- One entry per asking chapter whose verdict is complete or that has a comment; `version` is the
  chapter's. A complete verdict carries its comment where there is one, Bless's optional one too;
  a chapter with a comment and no complete verdict sends the comment alone, with no `verdict`
  and no `pick`:
  `{chapter: "swipe", version: "<sha256>", comment: "Only a thought."}`. The comment is sent as
  typed, trimmed at its ends.
- `figures` holds, by figure anchor, what `obsPugh.readerState()` gives for the chapter's
  decision figures the reader changed: weights, marks, rulings with their tripwires, and the
  winner they give ([[artifact-ui#Decision figures]]).
- `bless.js` keeps which verdicts were sent in browser storage, per chapter and version; the
  feature's canary (`canaries/bless.js`) reports a host that refuses it, where a sent verdict
  shows as unsent after a reload.

## Drafts

Decided by the owner, 11 Nov 2026 (work issue `fix/decision-comments-never-lost-20261111`):
what the reader gives a chapter, its verdict, pick and comment, is its draft
([[artifact-ui#Comments that are never lost]]). The draft is reader state: `bless.js` keeps it in
the browser's session storage, under `obs-bless-draft:<deck>:<chapter>` with the chapter's version,
the deck being the Document's title as for the sent verdicts, and restores it on a reload where
the version is the chapter's. It is written on every change and removed once a sink confirms the
send that carried it. obs-html restores every chapter's draft itself, a Bless as every other
verdict: opening the chapters in any order shows each one's verdict, pick and comment, so a host
bundle needs no restore of its own.

- A confirmed send is a `sendAnswers` result from a registered sink or the local server
  ([[capabilities/answers#Contract]]); the text sink and a rejection are not, and the drafts stay.
- The draft never reaches the artifact or the payload beyond its fields above: no storage key,
  no draft version and nothing of another chapter. The artifact's markup carries no typed text.
- A host that refuses session storage keeps the draft for the page's life only; the feature's
  canary reports it as it does a refused local storage.

[`bless.js`](../../src/obs_html/bless.js) implements the keys and Send,
[`bless_record.py`](../../src/obs_html/bless_record.py) the read-only answer;
`test/test_bless_browser.py` tests them on the example deck of obs's spec.
