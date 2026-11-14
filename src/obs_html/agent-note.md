# For agents: reading and driving this page

This page is an obs artifact: one HTML file that shows a document one section (chapter) at a time.
It runs in a browser with scripts; what follows is in the page's `globalThis`.

- Wait until it is ready: `await obsHtmlReady`.
- Sections: `obsArtifact.documentRecords()` lists them, each with its `slug`, `title` and `text`;
  `await obsArtifact.activateChapter(slug)` shows one. The section shown is `[data-active-chapter]`,
  its text `[data-chapter-body]`.
- Filter: `obsFilter.setExpression(expression)` filters the sections as the reader's filter does.
- Without a browser: `obs-html --print-chapter FILE SLUG --chapter-format text` prints a section's text.
