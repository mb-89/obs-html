---
obs: {bless: pending}
---
# Which store keeps the deck

Five places could keep the deck.

```pugh
title: Which store keeps the deck
supersededBy: Decision 7, the deck moves to the wiki
criteria:
  - {key: cost, label: Monthly cost of the store, weight: 3, better: higher, kind: judged}
  - {key: reach, label: Reachable from a phone, weight: 2, better: higher, kind: judged}
  - {key: ops, label: Ease of operation, weight: 1, better: higher, kind: judged}
candidates:
  - {key: disk, label: A local disk, what: A folder on the build machine., marks: {cost: 0, reach: 0, ops: 0}}
  - {key: bucket, label: An object bucket, what: A bucket we rent., marks: {cost: -2, reach: 2, ops: 1},
     wins: Reachable anywhere., losses: A bill every month.}
  - {key: repo, label: The repository, what: A branch of the repository., marks: {cost: 0, reach: 1, ops: 1}}
  - {key: wiki, label: A page of the team wiki, what: A page of the wiki., marks: {cost: -1, reach: 1, ops: -1}}
  - {key: mail, label: Mail to the owner, what: The artifact sent by mail., marks: {cost: 0, reach: 2, ops: -2},
     losses: Lost in an inbox.}
datum: {prefer: [disk]}
```
