---
kind: adapter-behavior
capability:
  id: file-offers
  summary: Hand the reader a file from the page, through the host's save path.
  authoring: Nothing to author; a page published as a Claude artifact declares the downloads capability to keep its file offers.
  dependsOn: ["source-archive", "attachments"]
  source: "[[artifact-ui#Dock menu]]"
---

# File offers

Reader: whoever adds or changes a control of obs-html that hands the reader a file, or publishes
an obs-html artifact in Claude's artifact viewer.

A file offer is a control that hands the reader a file. Each one saves through one owner,
`file-offers.js`, the code of the downloads feature (`features.py`, `downloads`), and no control
of its own writes a download link or clicks one.

## The offers

| Offer | Where | File |
| --- | --- | --- |
| Save reviewed HTML | the Comments bar | the reviewed HTML |
| Download changed HTML | the changed-HTML entry of the notice center | the reviewed HTML |
| Download source ZIP | Settings + exports, the cover's source card, a Base icon of action `sourceArchive` | the source ZIP |
| Attach source ZIP to PDF | Settings + exports | a PDF with the source ZIP |
| An attachment | a chapter of the evidence edition (`--embed-attachments`) | the attachment's bytes |
| A staged asset link with a download name | a chapter changed by a trusted action | the asset's bytes |
| A Base icon marked `download` | a Base table's icon column | the file its link names |

Copy comments and Copy answers hand text to the clipboard, and Print to PDF hands the page to the
browser's print dialog; neither is a file offer.

## Save path by host

The page is in Claude's artifact viewer where it has Claude's artifact runtime, `claude.use`.

- **In Claude's artifact viewer**, a file offer saves through the viewer's `downloads`
  capability, `claude.use("downloads")` then `save({filename, data})`. The viewer asks the reader
  to confirm; a refusal shows its reason beside the control. Where the page has no `downloads`
  capability, its file offers are hidden and the downloads warning of the notice center says
  so, with what to declare. A file offer used before the viewer has answered waits for the
  answer.
- **Elsewhere**, in a browser, `obs-html serve` or another host, a file offer is a browser
  download, as it always was, with the downloads canary's help where a host may block it.

## What to declare

A page published as a Claude artifact declares the `downloads` capability to keep its file
offers: `capabilities: {downloads: true}`. Without it the viewer saves no file, so the page hides
its file offers. The viewer saves only the file types it allows; an attachment of another type
says so when used.
