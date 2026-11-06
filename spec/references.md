---
title: References
---

Every external source is one note with a `url`; the document links that note, and its hover card
holds the external link. This register is the query over those notes.

```base
filters: 'url != null'
properties:
  title: {displayName: Reference}
  description: {displayName: Description}
views:
  - type: table
    name: References
    order: [title, description]
    sort:
      - {property: title, direction: ASC}
```
