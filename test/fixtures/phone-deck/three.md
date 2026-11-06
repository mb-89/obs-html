---
obs: {bless: pending}
---
# Where the answer is kept

A reader's verdicts must be kept where the decision can be read again later.

```pugh
title: Where the answer is kept
chosen: html
context: a deck read on phones
concern: where a verdict is kept
confirmation: The answers check refuses an artifact without its answers.
criteria:
  - {key: places, label: Places that hold the verdict, weight: 3, better: lower}
  - {key: readable, label: Readable as the decision it answers, weight: 2, better: higher, kind: judged}
  - {key: effort, label: Effort for the reader, weight: 1, better: higher, kind: judged}
candidates:
  - {key: export, label: Comment export, what: A document-level comment in the comment export., values: {places: 2},
     marks: {readable: {mark: 0, because: it is where comments live today}, effort: 0},
     losses: The verdict lives beside the decision.}
  - {key: html, label: Answered artifact, short: Artifact, what: obs-document --answers builds the artifact with the answers in it.,
     values: {places: 1},
     marks: {readable: {mark: 2, because: the verdict sits in the decision it answers}, effort: 1},
     wins: The changed artifact is its own record.}
  - {key: json, label: Answers file alone, what: The answers.json the server writes., values: {places: 1},
     marks: {readable: {mark: -1, because: the file holds no decision}, effort: 1}, losses: Read without the decision it answers.}
datum: {prefer: [export]}
```

## The record

The record of earlier verdicts, which the one-pager no longer carries below it.

### Kept answers

Every answer is kept with the version of the chapter it answers.

## Earlier attempts

A comment export was tried first.
