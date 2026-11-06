# Overview

Reader: whoever changes the HTML adapter or authors a vault for its artifact.

This specification accompanies the HTML adapter, `obs-html`, and the interim adapter
`obs-html-interim` it replaces at the cutover. It covers everything about their output: the
artifact's reader and review interface, its tables, figures, print and PDF, its configuration and
command line, and the options vaults set for it in the `obsHtml` namespace.

The adapter renders a Document of obs, which obs's own specification describes: the
Obsidian-compatible Markdown, the Document, the capabilities, the core's command line and the
adapter contract. That specification is the input contract this one builds on; this one does not
restate it.
