---
summary: obs-html renders an obs Document as one portable, reviewable HTML artifact.
---

# obs-html

Reader: whoever decides what the HTML adapter is for.

`obs-html` creates portable HTML artifacts from Obsidian-compatible Markdown vaults. obs's product
note, part of obs's specification, owns the goals every adapter shares; these goals moved here from
it because they hold for the HTML artifact.

## Goals

- Produce one portable HTML file with generation provenance suitable for local viewing or static
  hosting.
- Keep all artifact data inside that file so it can be sent by email and opened on another
  machine without access to the source vault.
- Network CDN dependencies are allowed; local filesystem dependencies are not.
- Present one chapter at a time with table-of-contents and previous/next navigation.

## Non-goals for the first release

- Synchronizing generated HTML changes back to Markdown.

See [[architecture]], [[cli]], [[configuration]], and [[input-model]].
