---
title: Adapter behaviors
---

Every behavior this adapter adds beyond obs's capabilities is one note in `capabilities/`, with
`kind: adapter-behavior` and the frontmatter of obs's capability notes. This register is the
query over those notes.

```base
filters: 'kind == "adapter-behavior"'
properties:
  capability.id: {displayName: ID}
  capability.summary: {displayName: Summary}
  capability.authoring: {displayName: How to author}
views:
  - type: table
    name: Adapter behaviors
    order: [capability.id, capability.summary, capability.authoring]
    sort:
      - {property: capability.id, direction: ASC}
```
